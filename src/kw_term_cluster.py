"""
kw_term_cluster.py — PLAN B, Phase 3: cluster the pruned candidate terms
(from kw_vocab_discover.py) ONCE, cut the same dendrogram at two heights to
get leaves and parents from the same tree — so a leaf cluster is guaranteed
to be a subset of exactly one parent cluster BY CONSTRUCTION, with no
"parent_matches_leaf_parent" reconciliation needed the way Plan A's two
independent classifiers require.

Term representation: doc-centroid vectors — v_t = mean of SPECTER2 vectors of
docs containing t — computed only over the pruned candidates from Phase 1+2.
**Centered before clustering**: raw doc-centroids were measured to be
anisotropic (every term vector sits in a thin cone around the corpus mean —
mean cosine between a term's raw centroid and the corpus centroid rises from
0.949 at df 5-6 to 0.996 at df 101-700), which made cosine distance dominated
by the shared direction rather than term content — the real cause of an
84.5%-of-terms mega-cluster measured in an earlier run, confirmed by testing
term quality in isolation (a cleaned term set still produced a 91.2% blob
under the RAW representation). Fix: `V = cosine_normalize(raw_centroids -
embeddings.mean(axis=0))` — subtract the CORPUS's mean embedding (not a mean
of already-normalized vectors; SPECTER2 vectors aren't unit-norm, and that
variant was measured to fail, leaving a 90.8% blob) before normalizing.
Silhouette values are NOT comparable before/after centering (it measures
0.354 raw vs 0.180 centered on the same terms, even though cluster quality is
clearly better centered) — only use silhouette to pick k *within* one fixed
representation.

Term ranking within a cluster is by closeness to the cluster's own centroid
(most prototypical first, using the same centered V) rather than re-deriving
a c-TF-IDF score, since BERTopic's ClassTfidfTransformer is never IMPORTED in
Plan B — though src/kw_class_stats.py reimplements its formula (verified
bit-exact) against the canonical partition for both term selection
(kw_vocab_discover.py) and the ARI diagnostic below.

Legacy-topic overlap and the ARI diagnostic both use the ALREADY-COMMITTED
canonical BERTopic assignment (data/processed/topic_assignments.parquet) as
the one document-level partition on disk — Plan B has no document partition
of its own before this step, unlike Plan A's freshly-fit leaves.

Run (numpy/scipy/sklearn only — no torch/BERTopic/HF import; fast, seconds):
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m src.kw_term_cluster

Reads:
    outputs/kw_vocab_candidates.json, data/processed/topic_assignments.parquet
Writes:
    outputs/kw_term_groups_planB.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster
from sklearn.metrics import adjusted_rand_score

from src.kw_class_stats import class_ctfidf, load_canonical_partition
from src.kw_cluster_utils import cosine_normalize, linkage_and_silhouette_sweep
from src.kw_harvest import full_harvest
from src.model_docs import load_docs_and_embeddings

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
OUTPUTS = REPO_ROOT / "outputs"

K_PARENT_SWEEP = range(6, 17)
K_PARENT_PREFERRED_RANGE = (8, 12)
K_LEAF_SWEEP = range(25, 51)
AMBIGUOUS_DISPERSION_PCTILE = 90
AMBIGUOUS_SECOND_TOPIC_SHARE = 0.60


def _pick_k(scores: dict[int, float], preferred: tuple[int, int] | None) -> tuple[int, str | None]:
    if preferred:
        in_range = {k: s for k, s in scores.items() if preferred[0] <= k <= preferred[1]}
        if in_range:
            return max(in_range, key=in_range.get), None
    best_k = max(scores, key=scores.get)
    note = None
    if preferred:
        note = (f"Best unconstrained silhouette (k={best_k}, score={scores[best_k]:.4f}) falls "
                f"OUTSIDE the preferred range {preferred} — flagging loudly rather than clamping.")
        print(f"[Plan B Phase 3] WARNING: {note}")
    return best_k, note


def main() -> None:
    cand = json.loads((OUTPUTS / "kw_vocab_candidates.json").read_text())
    pruned_terms = [t["term"] for t in cand["terms"]]
    print(f"[Plan B Phase 3] {len(pruned_terms)} pruned candidate terms from Phase 1+2")

    docs, ids, embeddings = load_docs_and_embeddings()

    # Recompute the SAME deterministic harvest, to map term strings back onto
    # the corpus term-doc matrix without persisting it to disk.
    terms, X, _dropped = full_harvest(docs)
    term_to_col = {t: j for j, t in enumerate(terms)}
    Xc = X.tocsc()

    missing = [t for t in pruned_terms if t not in term_to_col]
    if missing:
        print(f"WARNING: {len(missing)} pruned terms missing from recomputed vocab — dropping")
        pruned_terms = [t for t in pruned_terms if t not in missing]

    legacy = pd.read_parquet(PROC / "topic_assignments.parquet")
    legacy_by_doc = dict(zip(legacy["doc_id"].astype(str), legacy["topic_id"]))
    legacy_topic_sizes = legacy["topic_id"].value_counts().to_dict()

    corpus_mean = embeddings.mean(axis=0)  # centering vector: corpus-wide, so
    # term coordinates don't shift when PRUNE_TARGET changes upstream.

    rows, raw_centroids = [], []
    for t in pruned_terms:
        j = term_to_col[t]
        doc_idx = Xc.getcol(j).nonzero()[0]
        df_corpus = len(doc_idx)
        vecs = embeddings[doc_idx]
        raw_centroid = vecs.mean(axis=0)
        centroid_unit = cosine_normalize(raw_centroid)
        cos_to_centroid = cosine_normalize(vecs) @ centroid_unit
        dispersion = float(1 - cos_to_centroid.mean()) if df_corpus else 1.0

        topic_counts: dict[int, int] = {}
        for di in doc_idx:
            tid = legacy_by_doc.get(ids[di])
            if tid is not None and tid != -1:
                topic_counts[int(tid)] = topic_counts.get(int(tid), 0) + 1
        top2 = sorted(topic_counts.items(), key=lambda kv: -kv[1])[:2]

        rows.append({
            "term": t, "df_corpus": df_corpus, "dispersion": round(dispersion, 4),
            "top2_legacy_topics": [{"topic_id": k, "n_docs": v} for k, v in top2],
        })
        raw_centroids.append(raw_centroid)

    # Clustering representation: CENTERED by the corpus mean embedding before
    # unit-normalizing (see module docstring — raw doc-centroids are
    # anisotropic and were the real cause of an 84.5% mega-cluster).
    V = cosine_normalize(np.vstack(raw_centroids) - corpus_mean)
    disp_arr = np.array([r["dispersion"] for r in rows])
    disp_pctile = np.percentile(disp_arr, AMBIGUOUS_DISPERSION_PCTILE)
    for r in rows:
        t2 = r["top2_legacy_topics"]
        second_share = (t2[1]["n_docs"] / t2[0]["n_docs"]) if len(t2) == 2 and t2[0]["n_docs"] else 0.0
        r["ambiguous"] = bool(r["dispersion"] >= disp_pctile or second_share > AMBIGUOUS_SECOND_TOPIC_SHARE)

    # ONE clustering pass on the pruned candidates.
    print("[Plan B Phase 3] clustering (average linkage, cosine distance) ...")
    all_k = sorted(set(K_PARENT_SWEEP) | set(K_LEAF_SWEEP))
    scores, Z = linkage_and_silhouette_sweep(V, all_k)

    parent_scores = {k: s for k, s in scores.items() if k in K_PARENT_SWEEP}
    leaf_scores = {k: s for k, s in scores.items() if k in K_LEAF_SWEEP}
    k_parent, parent_note = _pick_k(parent_scores, K_PARENT_PREFERRED_RANGE)
    k_leaf, leaf_note = _pick_k(leaf_scores, None)
    print(f"[Plan B Phase 3] chosen k_parent={k_parent} (silhouette={parent_scores[k_parent]:.4f}), "
          f"k_leaf={k_leaf} (silhouette={leaf_scores[k_leaf]:.4f})")

    parent_labels = fcluster(Z, t=k_parent, criterion="maxclust")
    leaf_labels = fcluster(Z, t=k_leaf, criterion="maxclust")

    # Live check: every leaf cluster must be a subset of exactly one parent
    # cluster, by construction (same dendrogram, two cuts) — verify, don't
    # just assume.
    leaf_to_parents: dict[int, set[int]] = {}
    for lf, pa in zip(leaf_labels, parent_labels):
        leaf_to_parents.setdefault(int(lf), set()).add(int(pa))
    non_nesting = {lf: sorted(ps) for lf, ps in leaf_to_parents.items() if len(ps) > 1}
    if non_nesting:
        print(f"[Plan B Phase 3] UNEXPECTED: {len(non_nesting)} leaf clusters span >1 parent "
              f"cluster — nesting-by-construction claim FAILED for these: {non_nesting}")
    else:
        print(f"[Plan B Phase 3] verified: all {len(leaf_to_parents)} leaf clusters nest inside "
              f"exactly one parent cluster (by construction)")

    def _build_groups(labels: np.ndarray, prefix: str) -> dict[str, dict]:
        groups = {}
        for cid in sorted(set(labels.tolist())):
            member_idx = np.where(labels == cid)[0]
            member_rows = [rows[i] for i in member_idx]
            member_centroid = cosine_normalize(V[member_idx].mean(axis=0))
            proto_order = np.argsort(-(cosine_normalize(V[member_idx]) @ member_centroid))
            top_terms = [member_rows[i]["term"] for i in proto_order[:15]]
            # Raw n_docs vote weight favors whichever legacy topic is simply
            # LARGEST (topic 0, 269 docs) regardless of relevance — measured:
            # it dominated the top-1 contributing slot for nearly every group.
            # Normalize by that topic's own size (a concentration/precision
            # signal, not a popularity one) so a small-but-genuinely-related
            # topic can outrank a big-but-incidental one.
            topic_votes_raw: dict[int, int] = {}
            topic_votes_norm: dict[int, float] = {}
            for r in member_rows:
                for tl in r["top2_legacy_topics"][:1]:
                    tid = tl["topic_id"]
                    topic_votes_raw[tid] = topic_votes_raw.get(tid, 0) + tl["n_docs"]
                    topic_votes_norm[tid] = topic_votes_norm.get(tid, 0.0) + \
                        tl["n_docs"] / legacy_topic_sizes.get(tid, 1)
            contributing = sorted(topic_votes_norm.items(), key=lambda kv: -kv[1])[:10]
            groups[f"{prefix}{cid}"] = {
                "n_terms": len(member_idx),
                "top_terms": top_terms,
                "contributing_legacy_topics": [
                    {"topic_id": t, "concentration_score": round(w, 3), "raw_n_docs": topic_votes_raw[t]}
                    for t, w in contributing
                ],
                "parent_of_group": (int(list(leaf_to_parents.get(cid, {None}))[0])
                                     if prefix == "L" else None),
            }
        return groups

    parent_groups = _build_groups(parent_labels, "P")
    leaf_groups = _build_groups(leaf_labels, "L")

    # ARI diagnostic: cluster the same terms by their FULL c-TF-IDF loading
    # across all 33 canonical classes (via kw_class_stats — the same
    # bit-exact-verified formula used for term selection in
    # kw_vocab_discover.py) and compare to the doc-centroid grouping at
    # k_leaf. An earlier version used only each term's top-2 legacy topics as
    # a lossy loading proxy, which made ARI measure exactly 0.0 (a degenerate
    # comparison, not evidence of independence) — the full 33-dim loading is
    # the real analogue of Plan A's own leaf-precision-loading diagnostic.
    class_index, class_ids = load_canonical_partition(ids)
    CT_full = class_ctfidf(X, class_index, len(class_ids))  # (n_classes, n_full_vocab_terms)
    pruned_cols = np.array([term_to_col[r["term"]] for r in rows])
    loading = CT_full[:, pruned_cols].T  # (n_terms, n_classes)
    scores_load, Z_load = linkage_and_silhouette_sweep(loading, [k_leaf])
    labels_load = fcluster(Z_load, t=k_leaf, criterion="maxclust")
    ari = float(adjusted_rand_score(leaf_labels, labels_load))
    print(f"[Plan B Phase 3] ARI (doc-centroid grouping vs full c-TF-IDF-loading grouping, "
          f"same k={k_leaf}): {ari:.4f}  "
          f"({'grouping adds real information' if ari < 0.5 else 'groupings largely agree'})")

    ambiguous_terms = [r["term"] for r in rows if r["ambiguous"]]

    out = {
        "_meta": {
            "plan": "B",
            "n_candidate_terms": len(rows),
            "k_parent_sweep_range": list(K_PARENT_SWEEP),
            "k_parent_preferred_range": list(K_PARENT_PREFERRED_RANGE),
            "k_leaf_sweep_range": list(K_LEAF_SWEEP),
            "chosen_k_parent": k_parent,
            "chosen_k_parent_silhouette": round(parent_scores[k_parent], 4),
            "chosen_k_leaf": k_leaf,
            "chosen_k_leaf_silhouette": round(leaf_scores[k_leaf], 4),
            "parent_range_clamped_note": parent_note,
            "n_leaf_clusters_spanning_gt1_parent": len(non_nesting),
            "ari_doc_centroid_vs_full_ctfidf_loading": round(ari, 4),
            "term_representation": "centered_doc_centroid",
            "n_ambiguous_terms": len(ambiguous_terms),
        },
        "silhouette_by_k": {str(k): round(v, 4) for k, v in scores.items()},
        "parent_groups": parent_groups,
        "leaf_groups": leaf_groups,
        "ambiguous_terms_sample": ambiguous_terms[:50],
        "terms": rows,
    }
    out_path = OUTPUTS / "kw_term_groups_planB.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"[Plan B Phase 3] wrote {out_path}")


if __name__ == "__main__":
    main()
