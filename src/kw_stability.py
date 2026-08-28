"""
kw_stability.py — PLAN A, Phase 1+2 completion: the 6-fit stability grid that
`src/kw_discover.py` explicitly skipped in the discovery-only comparison run
(mcs ∈ {15,20} x seed ∈ {42,7,123} — same loop shape as src/tune_bertopic.py,
~6x the cost of one fit). Produces a per-term STABILITY score (fraction of
the 6 fits in which a term appears in some cluster's top-N list) for every
term already harvested for the primary (mcs=15, seed=42) fit's 43 leaves.

The mcs=15/seed=42 primary fit alone defines leaf identity (unambiguous ids,
already fixed in outputs/kw_candidates.json); the other 5 fits only
contribute stability counts, mapped onto primary leaves by max doc-overlap
Jaccard — exactly as the original topic-redo plan specifies. This grid is
NOT applied to kw_discover.py's own noise-only re-fit (that re-fit is this
session's own addition beyond the original plan's spec, added specifically
so Plan A could compete with Plan B's by-construction coverage of the
Unassigned region — the plan's stability-grid design predates it and only
ever covered the primary corpus fit).

Run (HEAVY, foreground, unsandboxed — 6 BERTopic fits, ~2 min):
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m src.kw_stability

Reads:
    outputs/kw_candidates.json (for the primary fit's leaf/term tables)
Writes:
    outputs/kw_stability_planA.json
"""
from __future__ import annotations

import json

import numpy as np
from bertopic.vectorizers import ClassTfidfTransformer
from scipy import sparse

from src.kw_harvest import drop_stopword_only_terms, harvest_vectorizer, subsume_terms
from src.topics_bertopic import OUTPUTS, _load_docs_aligned_to_cache, fit

SIZES = [15, 20]
SEEDS = [42, 7, 123]
PRIMARY = (15, 42)
TOP_N_PER_LEAF = 40


def _cluster_top_n(topics: np.ndarray, terms: np.ndarray, X: sparse.csr_matrix, top_n: int) -> dict[int, set[str]]:
    """For one fit's topic assignment, return {cluster_id: set(top-N terms)}
    via the same ClassTfidfTransformer scoring kw_discover.py uses."""
    cluster_ids = sorted(set(topics.tolist()) - {-1})
    row_sums = []
    for cid in cluster_ids:
        idx = np.where(topics == cid)[0]
        row_sums.append(np.asarray(X[idx].sum(axis=0)).ravel())
    if not row_sums:
        return {}
    M = sparse.csr_matrix(np.vstack(row_sums))
    ct = ClassTfidfTransformer().fit(M).transform(M).toarray()
    out = {}
    for i, cid in enumerate(cluster_ids):
        order = np.argsort(-ct[i])[:top_n]
        out[cid] = set(terms[order].tolist())
    return out


def _best_jaccard_map(topics_aux: np.ndarray, topics_primary: np.ndarray) -> dict[int, int]:
    """For each auxiliary-fit cluster, find the primary-fit leaf with the
    highest doc-overlap Jaccard."""
    aux_ids = sorted(set(topics_aux.tolist()) - {-1})
    primary_ids = sorted(set(topics_primary.tolist()) - {-1})
    primary_docsets = {p: set(np.where(topics_primary == p)[0].tolist()) for p in primary_ids}
    mapping = {}
    for a in aux_ids:
        aux_docs = set(np.where(topics_aux == a)[0].tolist())
        best_p, best_j = None, 0.0
        for p, pdocs in primary_docsets.items():
            j = len(aux_docs & pdocs) / max(len(aux_docs | pdocs), 1)
            if j > best_j:
                best_p, best_j = p, j
        if best_p is not None:
            mapping[a] = best_p
    return mapping


def main() -> None:
    candidates = json.loads((OUTPUTS / "kw_candidates.json").read_text())
    primary_leaves = {
        int(lid): {row["term"] for row in leaf["terms"]}
        for lid, leaf in candidates["leaves"].items()
        if leaf["source"] == "primary"
    }
    print(f"[Plan A stability] {len(primary_leaves)} primary leaves, "
          f"{sum(len(v) for v in primary_leaves.values())} term-slots to score")

    docs, ids, embeddings = _load_docs_aligned_to_cache()
    vec, X = harvest_vectorizer(docs)
    terms, X, _dropped = drop_stopword_only_terms(vec, X)
    kept_idx, _log = subsume_terms(terms, X)
    terms = terms[kept_idx]
    X = X[:, kept_idx]

    # present[leaf_id][term] = number of fits (out of 6) where `term` appears
    # in the top-N list of whichever cluster maps onto that primary leaf.
    present: dict[int, dict[str, int]] = {lid: {t: 0 for t in ts} for lid, ts in primary_leaves.items()}
    n_fits_run = 0

    topics_primary = None
    for mcs in SIZES:
        for seed in SEEDS:
            print(f"[Plan A stability] fitting mcs={mcs} seed={seed} ...")
            model, diag = fit(docs, embeddings, seed=seed, min_cluster_size=mcs)
            topics = np.asarray(model.topics_)
            n_fits_run += 1
            if (mcs, seed) == PRIMARY:
                topics_primary = topics
                cluster_top_n = _cluster_top_n(topics, terms, X, TOP_N_PER_LEAF)
                for lid in present:
                    for t in cluster_top_n.get(lid, set()):
                        if t in present[lid]:
                            present[lid][t] += 1
                continue
            # Auxiliary fit: map its clusters onto primary leaves, then check
            # term presence in each mapped cluster's own top-N list.
            if topics_primary is None:
                raise RuntimeError("PRIMARY must be fit first — check SIZES/SEEDS ordering")
            cluster_top_n = _cluster_top_n(topics, terms, X, TOP_N_PER_LEAF)
            aux_to_primary = _best_jaccard_map(topics, topics_primary)
            # Invert: for each primary leaf, union of aux clusters mapping to it.
            primary_to_aux: dict[int, list[int]] = {}
            for a, p in aux_to_primary.items():
                primary_to_aux.setdefault(p, []).append(a)
            for lid in present:
                mapped_terms: set[str] = set()
                for a in primary_to_aux.get(lid, []):
                    mapped_terms |= cluster_top_n.get(a, set())
                for t in mapped_terms:
                    if t in present[lid]:
                        present[lid][t] += 1

    assert n_fits_run == len(SIZES) * len(SEEDS) == 6

    stability_out = {}
    all_stability_values = []
    for lid, term_counts in present.items():
        stability_out[str(lid)] = {
            t: {"n_fits_present": c, "stability": round(c / 6, 3)}
            for t, c in term_counts.items()
        }
        all_stability_values.extend(c / 6 for c in term_counts.values())

    arr = np.array(all_stability_values)
    summary = {
        "n_fits": 6,
        "sizes": SIZES, "seeds": SEEDS, "primary": list(PRIMARY),
        "n_terms_scored": len(arr),
        "pct_stable_6_of_6": round(100 * float((arr == 1.0).mean()), 1),
        "pct_stable_ge_4_of_6": round(100 * float((arr >= 4 / 6).mean()), 1),
        "pct_single_fit_only": round(100 * float((arr <= 1 / 6).mean()), 1),
        "mean_stability": round(float(arr.mean()), 3),
    }
    print(f"[Plan A stability] {summary['pct_stable_6_of_6']}% of primary-leaf top-40 terms "
          f"are stable across all 6 fits; {summary['pct_single_fit_only']}% appear in only 1 of 6 "
          f"(seed/mcs-idiosyncratic — candidates for de-prioritizing in curation)")

    out = {"_meta": summary, "by_leaf": stability_out}
    out_path = OUTPUTS / "kw_stability_planA.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"[Plan A stability] wrote {out_path}")


if __name__ == "__main__":
    main()
