"""
kw_vocab_discover.py — PLAN B, Phase 1+2: corpus-wide candidate keyword
extraction, NO document pre-clustering of any kind.

Shares the exact same vocabulary harvest as Plan A's Phase 2
(kw_harvest.full_harvest — same CountVectorizer config, same stopword-only +
boundary-fragment + dedup policy) since the plan document specifies both
plans use "the same vocabulary policy... applied as ONE CountVectorizer over
all 2,741 docs at once" — Plan B just never groups that harvest by a document
partition afterward.

SELECTION (fixed after measurement): candidates are ranked by c-TF-IDF
against the CANONICAL, already-committed BERTopic partition
(data/processed/topic_assignments.parquet — src/kw_class_stats.py), used
purely as a free document GROUPING (integer topic_id per doc), not as a
source of keywords or curated labels — no file under outputs/topic_labels.json
or docs/EnricoVis/ is read anywhere in this module. An earlier version of
this script ranked by dispersion+idf alone; that was measured to fail (both
signals are monotone in document frequency, so a top-2500 cut collapsed onto
the min_df=5 floor — every kept term had df in {5,6}, and the top-ranked
terms were grant-prose boilerplate, not science content). A subsequent
`max_topic_precision>=0.15` filter was ALSO measured to fail — see
kw_class_stats.max_class_precision's docstring. c-TF-IDF is the only
candidate signal with a term-frequency numerator, so it rewards concentration
AND support instead of penalizing support twice.

`dispersion` and `idf` are still computed and reported (used by Phase 3's
`ambiguous` flag and for diagnostic transparency) but no longer drive
selection.

Run (HEAVY interpreter — needs numpy/scipy/pandas only; no torch/BERTopic/HF
import, SPECTER2 embeddings + the canonical partition already on disk):
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m src.kw_vocab_discover

Writes:
    outputs/kw_vocab_candidates.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from src.kw_class_stats import class_ctfidf, load_canonical_partition, max_class_precision
from src.kw_harvest import full_harvest
from src.model_docs import load_docs_and_embeddings

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = REPO_ROOT / "outputs"

PRUNE_TARGET = 2500  # swept 1000-4000 against the c-TF-IDF score: coverage is
# flat past 2500 while curation burden and prose-fragment share keep rising —
# stays within the plan's originally-stated 2,000-3,000 band.


def _cosine_normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n == 0, 1, n)


def main() -> None:
    t0 = time.time()
    docs, ids, embeddings = load_docs_and_embeddings()
    n = len(docs)
    print(f"[Plan B] {n} docs / embeddings {embeddings.shape} (no BERTopic import needed)")

    print("[Plan B] harvesting corpus-level keyword candidates (same policy as Plan A Phase 2) ...")
    terms, X, dropped = full_harvest(docs)
    Xc = X.tocsc()
    df_corpus = np.diff(Xc.indptr)
    print(f"[Plan B] vocabulary: {len(terms)} terms after stopword-only drop "
          f"({len(dropped['stopword_only'])} dropped), boundary-fragment drop "
          f"({len(dropped['boundary_polluted'])} dropped), and dedup "
          f"({len(dropped['dedup_log'])} merged/subsumed)")

    # Coverage BEFORE anything else — the number that says this is on track.
    doc_has_term = np.asarray((X > 0).sum(axis=1)).ravel() > 0
    zero_match_ids = [ids[i] for i in range(n) if not doc_has_term[i]]
    coverage_full = {
        "docs_matching_0_terms": int((~doc_has_term).sum()),
        "n_zero_match_doc_ids": len(zero_match_ids),
    }
    print(f"[Plan B] COVERAGE (full harvested vocab, pre-pruning): "
          f"{coverage_full['docs_matching_0_terms']}/{n} docs match 0 terms")

    # idf + dispersion: still computed, now DIAGNOSTIC ONLY (Phase 3's
    # `ambiguous` flag uses dispersion; both are reported for transparency).
    idf = np.log((1 + n) / (1 + df_corpus)) + 1
    dispersion = np.ones(len(terms))
    for j in range(len(terms)):
        doc_idx = Xc.getcol(j).nonzero()[0]
        if len(doc_idx) == 0:
            continue
        vecs = embeddings[doc_idx]
        centroid = _cosine_normalize(vecs.mean(axis=0))
        cos_to_centroid = _cosine_normalize(vecs) @ centroid
        dispersion[j] = 1 - cos_to_centroid.mean()

    # SELECTION: c-TF-IDF against the canonical partition (includes -1/noise
    # as its own class — measured to contribute zero top-2500 argmaxes since
    # L1-normalizing a 674-doc heterogeneous class dilutes every term in it,
    # itself a finding: the Unassigned bucket has no characteristic
    # vocabulary of its own — but kept so noise-only terms get a nonzero
    # score for the backfill step below).
    class_index, class_ids = load_canonical_partition(ids)
    n_classes = len(class_ids)
    CT = class_ctfidf(X, class_index, n_classes)
    score = CT.max(axis=0)
    top_class_pos = CT.argmax(axis=0)
    top_class = np.array(class_ids)[top_class_pos]
    max_topic_precision = max_class_precision(X, class_index, n_classes)  # diagnostic only

    # kind="stable" is deliberate: the prior dispersion+idf ranking had ~7,479
    # terms exactly tied on idf at df=5, so np.argsort's default quicksort
    # tie-break made ~21% of the old selection an artifact of sort algorithm,
    # not signal. c-TF-IDF ties are far rarer, but staying stable costs
    # nothing and removes the failure mode outright.
    order = np.argsort(-score, kind="stable")
    keep_mask = np.zeros(len(terms), dtype=bool)
    keep_mask[order[:PRUNE_TARGET]] = True

    pruned_doc_has_term = np.asarray((X[:, keep_mask] > 0).sum(axis=1)).ravel() > 0
    n_zero_pre_backfill = int((~pruned_doc_has_term).sum())
    print(f"[Plan B] COVERAGE (pruned to top {PRUNE_TARGET} by c-TF-IDF, pre-backfill): "
          f"{n_zero_pre_backfill}/{n} docs match 0 of the pruned set "
          f"(vs {coverage_full['docs_matching_0_terms']}/{n} on the full harvested vocab)")

    # Coverage backfill: force-include each still-zero-match doc's single
    # best pre-prune term (by the same c-TF-IDF score), so post-prune
    # coverage converges to exactly the full-vocab floor — both plans are
    # bounded by the same kw_harvest.py vocabulary extraction, so parity here
    # is the expected, checkable outcome, not a coincidence.
    backfilled: dict[str, str] = {}
    Xr = X.tocsr()
    zero_idx = np.where(~pruned_doc_has_term)[0]
    for di in zero_idx:
        cols = Xr.getrow(di).nonzero()[1]
        if len(cols) == 0:
            continue  # genuinely zero terms in the full vocab too — the irreducible floor
        best_col = cols[np.argmax(score[cols])]
        keep_mask[best_col] = True
        backfilled[ids[di]] = terms[best_col]
    backfilled_terms = set(backfilled.values())

    pruned_doc_has_term = np.asarray((X[:, keep_mask] > 0).sum(axis=1)).ravel() > 0
    coverage_pruned = {
        "n_docs": n,
        "docs_matching_0_terms": coverage_full["docs_matching_0_terms"],
        "docs_matching_0_of_pruned_set_pre_backfill": n_zero_pre_backfill,
        "docs_matching_0_of_pruned_set": int((~pruned_doc_has_term).sum()),
        "pruned_vocab_size": int(keep_mask.sum()),
        "full_vocab_size": len(terms),
        "n_backfilled": len(backfilled),
        "backfilled": backfilled,
    }
    # Post-backfill this is an exact invariant: every backfilled doc had >=1
    # term in the full vocab by construction, so post-backfill zero-match
    # can only be docs with ZERO terms in the full vocab too.
    assert coverage_pruned["docs_matching_0_of_pruned_set"] == coverage_full["docs_matching_0_terms"], (
        "coverage backfill invariant violated — a doc with a full-vocab term "
        "was not backfilled, or a genuinely zero-vocab doc was miscounted"
    )
    print(f"[Plan B] COVERAGE (post-backfill): {coverage_pruned['docs_matching_0_of_pruned_set']}/{n} "
          f"docs match 0 terms — equals the full-vocab floor ({len(backfilled)} docs backfilled)")

    dropped_by_pruning = [
        {"term": terms[j], "df_corpus": int(df_corpus[j]), "idf": round(float(idf[j]), 3),
         "dispersion": round(float(dispersion[j]), 4), "ctfidf": round(float(score[j]), 5),
         "reason": "pruned_by_rank"}
        for j in order[PRUNE_TARGET:PRUNE_TARGET + 200]  # sample just past the cut
    ]

    kept_terms = [
        {"term": terms[j], "df_corpus": int(df_corpus[j]), "idf": round(float(idf[j]), 3),
         "dispersion": round(float(dispersion[j]), 4), "ctfidf": round(float(score[j]), 5),
         "top_class": int(top_class[j]), "max_topic_precision": round(float(max_topic_precision[j]), 4),
         "backfilled": terms[j] in backfilled_terms, "kept": True}
        for j in np.where(keep_mask)[0]
    ]

    elapsed = time.time() - t0
    out = {
        "_meta": {
            "plan": "B",
            "n_docs": n,
            "prune_target": PRUNE_TARGET,
            "full_vocab_size": len(terms),
            "n_classes": n_classes,
            "selection": "max_class_ctfidf_vs_canonical_partition",
            "selection_history": "dispersion+idf (measured to collapse onto min_df floor) "
                                  "-> max_topic_precision filter (measured anti-correlated with df) "
                                  "-> max class c-TF-IDF vs canonical partition (current)",
            "n_backfilled": len(backfilled),
            "noise_class_argmax_count_full_vocab": int((top_class == -1).sum()),
            "noise_class_argmax_count_kept": int((top_class[keep_mask] == -1).sum()),
            "elapsed_sec": round(elapsed, 1),
            "note": "No BERTopic/UMAP/HDBSCAN import anywhere in this script — "
                    "numpy/scipy/pandas + the already-cached SPECTER2 embeddings + "
                    "the already-committed canonical partition only. class_ctfidf is "
                    "a deliberate reimplementation (not an import) of "
                    "bertopic.vectorizers.ClassTfidfTransformer's formula, verified "
                    "bit-exact (max abs diff 0.0) against the installed transformer.",
        },
        "coverage_full_vocab": coverage_full,
        "coverage_pruned": coverage_pruned,
        "dropped": {
            "stopword_only_n": len(dropped["stopword_only"]),
            "boundary_polluted_n": len(dropped["boundary_polluted"]),
            "boundary_polluted_sample": dropped["boundary_polluted"][:100],
            "dedup_n": len(dropped["dedup_log"]),
            "pruned_by_rank_sample": dropped_by_pruning,
        },
        "terms": kept_terms,
    }
    out_path = OUTPUTS / "kw_vocab_candidates.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"[Plan B] wrote {out_path}  ({elapsed:.1f}s total)")


if __name__ == "__main__":
    main()
