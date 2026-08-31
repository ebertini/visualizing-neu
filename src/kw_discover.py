"""
kw_discover.py — PLAN A, Phase 1+2: cluster documents (discovery only), then
harvest per-leaf keywords OUTSIDE BERTopic.

This is the discovery-only-comparison scope agreed with the user: a single
primary fit (min_cluster_size=15, seed=42 — finer than the canonical 20, per
outputs/bertopic_sweep.json showing mcs=15 has both lower noise and higher
intra-cluster cosine, so there is no tradeoff to weigh) plus one noise-only
re-fit on the primary fit's HDBSCAN-noise docs, so Plan A gets a fair shot at
covering the same currently-Unassigned region Plan B covers by construction.
The full plan's 6-fit stability grid (mcs x seed, for a per-term stability
score used in human-curation triage) is deliberately SKIPPED here — it adds
6x the heavy-fit cost for a signal that only matters once someone is doing
the real ~60-90 min curation pass, not for an A-vs-B discovery comparison.

Keyword extraction happens outside BERTopic entirely (forced by 3 verified
library facts: BERTopic's own min_df counts topics not documents; MMR/KeyBERT
representations are no-ops on this precomputed-embeddings pipeline; BERTopic's
internal `_preprocess_text` strips hyphens/periods before its vectorizer ever
sees the text). Concretely: our own per-document CountVectorizer (stop_words=
None, so sklearn can't fabricate n-grams across a removed stopword gap) feeds
BERTopic's own `ClassTfidfTransformer` — same scoring semantics as the
canonical model, harvested our own way.

Run (HEAVY, foreground, unsandboxed — see CLAUDE.md):
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m src.kw_discover

Writes:
    outputs/kw_candidates.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from bertopic.vectorizers import ClassTfidfTransformer
from scipy import sparse

from src.kw_harvest import full_harvest
from src.topics_bertopic import OUTPUTS, PROC, _load_docs_aligned_to_cache, fit

PRIMARY_MCS = 15
PRIMARY_SEED = 42
NOISE_REFIT_MCS = 7  # swept on the actual 656-doc noise subset (this file's
# git history / session log has the sweep): 5-8 give healthy multi-cluster
# structure (24-39 topics, ~21-23% residual noise); >=10 collapses to a single
# 616-doc mega-cluster, the same degenerate failure mode the canonical fit's
# own min_cluster_size=25 sweep hit — re-sweep this if the primary fit's
# params or the corpus ever change, don't assume 7 stays right.
NOISE_ID_OFFSET = 1000
TOP_N_PER_LEAF = 40
MIN_DF = 5
MAX_DF = 0.25

# Harvest/dedup/boundary-filter logic lives in src/kw_harvest.py (numpy/scipy/
# sklearn only — no bertopic/umap/hdbscan) so Plan B's kw_vocab_discover.py
# can reuse the identical vocabulary policy without importing the heavy stack
# this module needs for its own document-clustering half.


def _leaf_keyword_table(leaf_docs_idx: list[int], terms: np.ndarray, X: sparse.csr_matrix,
                         all_topics: np.ndarray, this_leaf_col_in_ctfidf: int,
                         ctfidf_row: np.ndarray, df_corpus: np.ndarray, n_corpus: int) -> list[dict]:
    """Rank this leaf's terms by c-TF-IDF weight, attach precision/recall."""
    n_leaf = len(leaf_docs_idx)
    leaf_X = X[leaf_docs_idx]
    df_leaf = np.asarray((leaf_X > 0).sum(axis=0)).ravel()
    order = np.argsort(-ctfidf_row)
    rows = []
    for j in order:
        if df_leaf[j] == 0:
            continue
        rows.append({
            "term": terms[j],
            "ctfidf": round(float(ctfidf_row[j]), 5),
            "df_corpus": int(df_corpus[j]),
            "df_leaf": int(df_leaf[j]),
            "precision": round(float(df_leaf[j] / df_corpus[j]), 4) if df_corpus[j] else 0.0,
            "recall": round(float(df_leaf[j] / n_leaf), 4) if n_leaf else 0.0,
        })
        if len(rows) >= TOP_N_PER_LEAF:
            break
    return rows


def main() -> None:
    t0 = time.time()
    docs, ids, embeddings = _load_docs_aligned_to_cache()
    n = len(docs)
    print(f"[Plan A] {n} docs / embeddings {embeddings.shape}")

    print(f"[Plan A] primary fit: mcs={PRIMARY_MCS} seed={PRIMARY_SEED} ...")
    model, diag = fit(docs, embeddings, seed=PRIMARY_SEED, min_cluster_size=PRIMARY_MCS)
    topics = np.asarray(model.topics_)
    print(f"[Plan A] primary: n_topics={diag['n_topics']} noise={diag['pct_noise']}% "
          f"intra={diag['mean_intra_cluster_cosine']}")

    noise_mask = topics == -1
    n_noise = int(noise_mask.sum())
    print(f"[Plan A] noise-only re-fit on {n_noise} docs, mcs={NOISE_REFIT_MCS} ...")
    noise_docs = [d for d, m in zip(docs, noise_mask) if m]
    noise_emb = embeddings[noise_mask]
    noise_model, noise_diag = fit(noise_docs, noise_emb, seed=PRIMARY_SEED, min_cluster_size=NOISE_REFIT_MCS)
    noise_topics_local = np.asarray(noise_model.topics_)
    print(f"[Plan A] noise re-fit: n_topics={noise_diag['n_topics']} "
          f"still-noise={noise_diag['pct_noise']}%")

    # Merge primary + noise-refit leaf assignment into one array (offset noise
    # leaf ids by NOISE_ID_OFFSET so they don't collide with primary leaf ids;
    # -1 stays noise-of-noise, i.e. genuinely unclusterable even within the
    # noise subset).
    combined_leaf = topics.copy()
    noise_positions = np.where(noise_mask)[0]
    for local_i, global_i in enumerate(noise_positions):
        t = noise_topics_local[local_i]
        combined_leaf[global_i] = (t + NOISE_ID_OFFSET) if t != -1 else -1

    leaf_ids = sorted(set(combined_leaf.tolist()) - {-1})
    print(f"[Plan A] combined leaves: {len(leaf_ids)} "
          f"({diag['n_topics']} primary + {len(leaf_ids) - diag['n_topics']} from noise re-fit)")

    # Harvest keyword candidates OUTSIDE BERTopic.
    print("[Plan A] harvesting corpus-level keyword candidates ...")
    terms, X, dropped = full_harvest(docs)
    df_corpus = np.asarray((X > 0).sum(axis=0)).ravel()
    print(f"[Plan A] vocabulary: {len(terms)} terms after stopword-only drop "
          f"({len(dropped['stopword_only'])} dropped), boundary-fragment drop "
          f"({len(dropped['boundary_polluted'])} dropped), and dedup "
          f"({len(dropped['dedup_log'])} merged/subsumed)")

    # Coverage block FIRST — the number that says whether this is on track.
    doc_has_term = np.asarray((X > 0).sum(axis=1)).ravel() > 0
    zero_match_ids = [ids[i] for i in range(n) if not doc_has_term[i]]
    noise_doc_positions = np.where(noise_mask)[0]
    noise_matching = int(doc_has_term[noise_doc_positions].sum())
    coverage = {
        "n_docs": n,
        "docs_matching_0_terms": int((~doc_has_term).sum()),
        "noise_docs_total": n_noise,
        "noise_docs_matching_ge1_term": noise_matching,
        "noise_docs_matching_pct": round(100 * noise_matching / max(n_noise, 1), 1),
        "zero_match_doc_ids_sample": zero_match_ids[:30],
        "n_zero_match_doc_ids": len(zero_match_ids),
    }
    print(f"[Plan A] COVERAGE: {coverage['noise_docs_matching_ge1_term']}/{coverage['noise_docs_total']} "
          f"({coverage['noise_docs_matching_pct']}%) noise docs match >=1 candidate term; "
          f"{coverage['docs_matching_0_terms']} of {n} docs total match 0 terms")

    # Per-leaf c-TF-IDF via BERTopic's own transformer (reuse, not reimplement).
    print("[Plan A] scoring leaves with BERTopic's ClassTfidfTransformer ...")
    leaf_row_sums = []
    leaf_doc_idx_by_leaf = {}
    for lid in leaf_ids:
        idx = np.where(combined_leaf == lid)[0].tolist()
        leaf_doc_idx_by_leaf[lid] = idx
        leaf_row_sums.append(np.asarray(X[idx].sum(axis=0)).ravel())
    leaf_matrix = sparse.csr_matrix(np.vstack(leaf_row_sums))
    ctfidf_model = ClassTfidfTransformer()
    ctfidf_model = ctfidf_model.fit(leaf_matrix)
    ctfidf = ctfidf_model.transform(leaf_matrix).toarray()

    # Legacy-topic overlap (best doc-overlap Jaccard vs the canonical mcs=20 fit).
    legacy = pd.read_parquet(PROC / "topic_assignments.parquet")
    legacy_by_doc = dict(zip(legacy["doc_id"].astype(str), legacy["topic_id"]))
    id_to_pos = {did: i for i, did in enumerate(ids)}

    leaves_out = {}
    total_leaf_docs = 0
    for row_i, lid in enumerate(leaf_ids):
        idx = leaf_doc_idx_by_leaf[lid]
        total_leaf_docs += len(idx)
        leaf_ctfidf_row = ctfidf[row_i]
        term_table = _leaf_keyword_table(idx, terms, X, combined_leaf, row_i, leaf_ctfidf_row, df_corpus, n)

        legacy_topics_here = [legacy_by_doc.get(ids[i]) for i in idx if ids[i] in legacy_by_doc]
        legacy_topics_here = [t for t in legacy_topics_here if t is not None]
        best_legacy, best_jaccard = None, 0.0
        if legacy_topics_here:
            vals, counts = np.unique(legacy_topics_here, return_counts=True)
            for v, c in zip(vals, counts):
                legacy_doc_ids = set(legacy.loc[legacy["topic_id"] == v, "doc_id"].astype(str))
                this_doc_ids = {ids[i] for i in idx}
                jac = len(legacy_doc_ids & this_doc_ids) / max(len(legacy_doc_ids | this_doc_ids), 1)
                if jac > best_jaccard:
                    best_legacy, best_jaccard = int(v), jac

        dollars = None
        leaves_out[str(lid)] = {
            "source": "noise_refit" if lid >= NOISE_ID_OFFSET else "primary",
            "n_docs": len(idx),
            "legacy_topic_id": best_legacy,
            "legacy_jaccard": round(best_jaccard, 3),
            "representative_doc_ids": [ids[i] for i in idx[:5]],
            "terms": term_table,
        }

    elapsed = time.time() - t0
    out = {
        "_meta": {
            "plan": "A",
            "source_fit": {
                "primary": {"min_cluster_size": PRIMARY_MCS, "seed": PRIMARY_SEED, "n_topics": diag["n_topics"]},
                "noise_refit": {"min_cluster_size": NOISE_REFIT_MCS, "n_topics": noise_diag["n_topics"],
                                 "input_docs": n_noise},
            },
            "n_leaves": len(leaf_ids),
            "n_docs_total": n,
            "n_docs_in_leaves": total_leaf_docs,
            "vocab_size": len(terms),
            "top_n_per_leaf": TOP_N_PER_LEAF,
            "elapsed_sec": round(elapsed, 1),
            "note": "Discovery-only comparison run: skips the full plan's 6-fit "
                    "stability grid (term-stability scoring is a human-curation "
                    "triage aid, not needed to compare A vs B raw discovery quality).",
        },
        "coverage": coverage,
        "dropped": {
            "stopword_only": dropped["stopword_only"][:200],
            "n_stopword_only_dropped": len(dropped["stopword_only"]),
            "boundary_polluted_sample": dropped["boundary_polluted"][:200],
            "n_boundary_polluted_dropped": len(dropped["boundary_polluted"]),
            "dedup_log_sample": dropped["dedup_log"][:200],
            "n_dedup_dropped": len(dropped["dedup_log"]),
        },
        "leaves": leaves_out,
    }
    # Persist doc->leaf assignment so Phase 3 (kw_term_groups.py) can build
    # term doc-centroids and top2_leaves without re-running the two heavy fits.
    assign_df = pd.DataFrame({"doc_id": ids, "leaf_id": combined_leaf.tolist()})
    assign_path = OUTPUTS / "kw_leaf_assignments_planA.csv"
    assign_df.to_csv(assign_path, index=False)
    print(f"[Plan A] wrote {assign_path}")

    OUTPUTS.mkdir(exist_ok=True)
    out_path = OUTPUTS / "kw_candidates.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"[Plan A] wrote {out_path}  ({elapsed:.1f}s total)")


if __name__ == "__main__":
    main()
