"""
kw_term_groups.py — PLAN A, Phase 3: cluster candidate terms (harvested by
kw_discover.py) into human-reviewable parent groups.

Term representation: doc-centroid — v_t = mean of SPECTER2 vectors of docs
containing t. Same embedding space as everything else in the pipeline.
**Centered before clustering**: raw doc-centroids are anisotropic (every term
vector sits in a thin cone around the corpus mean), which was measured (on
Plan B's analogous representation, then confirmed here too) to be the real
cause of an 83%-of-terms mega-cluster at the originally-chosen k=9 — not a
term-quality problem, since a cleaned term set still produced an even larger
blob under the raw representation. Fix: `V = cosine_normalize(raw_centroids -
embeddings.mean(axis=0))` before clustering. Silhouette values are NOT
comparable before/after centering — only use it to pick k within one fixed
representation. Three guards against this representation's remaining real
failure modes:

  1. min_term_df=8 for clustering VOTES — a term with df<8 still lives in its
     leaf's keyword list, it just doesn't get to define a parent group
     (assigned_by_nearest=True instead).
  2. max_leaf_precision>=0.15 filter — strips the generic blob (a term spread
     thin across many leaves) before clustering, so it can't eat a parent slot.
  3. dispersion + top2_leaves — polysemy is this representation's one real,
     unfixable weakness; flag ambiguous rather than hide it.

Clustering: scipy.cluster.hierarchy.linkage(V, method="average",
metric="cosine"), deterministic, no seed. Sweep k in [6,16], pick the best
cosine silhouette within [8,12] (today's PARENT_COLORS palette headroom); if
the unconstrained best falls outside that range, say so loudly rather than
clamp silently.

Run (HEAVY interpreter for scipy/sklearn; fast, seconds):
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m src.kw_term_groups

Reads:
    outputs/kw_candidates.json, outputs/kw_leaf_assignments_planA.csv
Writes:
    outputs/kw_term_groups_planA.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster
from sklearn.metrics import adjusted_rand_score

from src.kw_cluster_utils import cosine_normalize as _cosine_normalize
from src.kw_cluster_utils import linkage_and_silhouette_sweep as _silhouette_sweep
from src.kw_harvest import full_harvest
from src.model_docs import load_docs_and_embeddings

OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"

MIN_TERM_DF = 8
MAX_LEAF_PRECISION_FLOOR = 0.15
K_SWEEP = range(6, 17)
K_PREFERRED_RANGE = (8, 12)
AMBIGUOUS_DISPERSION_PCTILE = 90
AMBIGUOUS_SECOND_LEAF_SHARE = 0.60


def main() -> None:
    candidates = json.loads((OUTPUTS / "kw_candidates.json").read_text())
    assign = pd.read_csv(OUTPUTS / "kw_leaf_assignments_planA.csv", dtype={"doc_id": str})
    doc_to_leaf = dict(zip(assign["doc_id"], assign["leaf_id"]))

    docs, ids, embeddings = load_docs_and_embeddings()
    doc_pos = {did: i for i, did in enumerate(ids)}

    # Recompute the SAME deterministic harvest kw_discover.py used, so term
    # strings map back onto the same corpus term-doc matrix without needing
    # to persist a 2741x35640 sparse matrix to disk. NOTE: this now includes
    # the boundary-fragment filter (kw_harvest.full_harvest) — if
    # outputs/kw_candidates.json was generated before that filter existed,
    # many of its candidate_terms will show up as "missing from recomputed
    # vocab" below (harmless — they're dropped) rather than crash. Re-run
    # kw_discover.py first if you want a fully consistent Plan A artifact.
    terms, X, _dropped = full_harvest(docs)
    term_to_col = {t: j for j, t in enumerate(terms)}
    Xc = X.tocsc()

    # Candidate set: the union of every leaf's top-N keyword table.
    per_term_leaf_precision: dict[str, dict[str, float]] = {}
    for lid, leaf in candidates["leaves"].items():
        for row in leaf["terms"]:
            per_term_leaf_precision.setdefault(row["term"], {})[lid] = row["precision"]

    candidate_terms = sorted(per_term_leaf_precision.keys())
    missing = [t for t in candidate_terms if t not in term_to_col]
    if missing:
        print(f"WARNING: {len(missing)} candidate terms not found in recomputed vocab "
              f"(harvest nondeterminism?) — dropping them: {missing[:10]}")
        candidate_terms = [t for t in candidate_terms if t not in missing]
    print(f"[Plan A Phase 3] {len(candidate_terms)} unique candidate terms across "
          f"{len(candidates['leaves'])} leaves")

    # Per-term stats: df_corpus, centroid vector, dispersion, top2_leaves.
    rows = []
    raw_centroids = []
    for t in candidate_terms:
        j = term_to_col[t]
        doc_idx = Xc.getcol(j).nonzero()[0]
        df_corpus = len(doc_idx)
        vecs = embeddings[doc_idx]
        raw_centroid = vecs.mean(axis=0)
        centroid_unit = _cosine_normalize(raw_centroid)
        cos_to_centroid = _cosine_normalize(vecs) @ centroid_unit
        dispersion = float(1 - cos_to_centroid.mean()) if df_corpus else 1.0

        leaf_precisions = per_term_leaf_precision[t]
        max_leaf_precision = max(leaf_precisions.values()) if leaf_precisions else 0.0
        leaf_counts: dict[str, int] = {}
        for did in doc_idx:
            lid = doc_to_leaf.get(ids[did])
            if lid is not None and lid != -1:
                leaf_counts[str(lid)] = leaf_counts.get(str(lid), 0) + 1
        top2 = sorted(leaf_counts.items(), key=lambda kv: -kv[1])[:2]

        rows.append({
            "term": t, "df_corpus": df_corpus, "dispersion": round(dispersion, 4),
            "max_leaf_precision": round(max_leaf_precision, 4),
            "top2_leaves": [{"leaf_id": k, "n_docs": v} for k, v in top2],
        })
        raw_centroids.append(raw_centroid)

    # Clustering representation: CENTERED by the corpus mean embedding before
    # unit-normalizing (see module docstring).
    V = _cosine_normalize(np.vstack(raw_centroids) - embeddings.mean(axis=0))
    disp_arr = np.array([r["dispersion"] for r in rows])
    disp_pctile = np.percentile(disp_arr, AMBIGUOUS_DISPERSION_PCTILE)
    for r in rows:
        second_share = (r["top2_leaves"][1]["n_docs"] / r["top2_leaves"][0]["n_docs"]) \
            if len(r["top2_leaves"]) == 2 and r["top2_leaves"][0]["n_docs"] else 0.0
        r["ambiguous"] = bool(r["dispersion"] >= disp_pctile or second_share > AMBIGUOUS_SECOND_LEAF_SHARE)

    # Guards 1+2: voters must clear both the df floor and the generic-blob filter.
    is_voter = np.array([
        r["df_corpus"] >= MIN_TERM_DF and r["max_leaf_precision"] >= MAX_LEAF_PRECISION_FLOOR
        for r in rows
    ])
    n_voters = int(is_voter.sum())
    print(f"[Plan A Phase 3] {n_voters}/{len(rows)} terms qualify as clustering voters "
          f"(df>={MIN_TERM_DF} and max_leaf_precision>={MAX_LEAF_PRECISION_FLOOR})")

    V_voters = V[is_voter]
    scores, Z = _silhouette_sweep(V_voters, K_SWEEP)
    in_range = {k: s for k, s in scores.items() if K_PREFERRED_RANGE[0] <= k <= K_PREFERRED_RANGE[1]}
    if in_range:
        best_k = max(in_range, key=in_range.get)
        clamped_note = None
    else:
        best_k = max(scores, key=scores.get)
        clamped_note = (f"Best unconstrained silhouette (k={best_k}, score={scores[best_k]:.4f}) "
                         f"falls OUTSIDE the palette-headroom-preferred range "
                         f"{K_PREFERRED_RANGE} — flagging loudly rather than clamping silently.")
        print(f"[Plan A Phase 3] WARNING: {clamped_note}")

    labels = fcluster(Z, t=best_k, criterion="maxclust")
    print(f"[Plan A Phase 3] chosen k={best_k}  silhouette={scores[best_k]:.4f}")
    print("[Plan A Phase 3] silhouette by k:", {k: round(v, 4) for k, v in scores.items()})

    # Assign non-voter terms to the nearest resulting cluster centroid.
    cluster_ids = sorted(set(labels.tolist()))
    cluster_centroids = {
        cid: _cosine_normalize(V_voters[labels == cid].mean(axis=0)) for cid in cluster_ids
    }
    cc_matrix = np.vstack([cluster_centroids[c] for c in cluster_ids])

    voter_positions = np.where(is_voter)[0]
    nonvoter_positions = np.where(~is_voter)[0]
    assigned_by_nearest = {}
    if len(nonvoter_positions):
        sims = _cosine_normalize(V[nonvoter_positions]) @ cc_matrix.T
        nearest = sims.argmax(axis=1)
        for pos, ni in zip(nonvoter_positions, nearest):
            assigned_by_nearest[rows[pos]["term"]] = cluster_ids[ni]

    term_to_group: dict[str, int] = {}
    for pos, lab in zip(voter_positions, labels):
        term_to_group[rows[pos]["term"]] = int(lab)
    term_to_group.update(assigned_by_nearest)

    groups: dict[str, dict] = {}
    for cid in cluster_ids:
        member_terms = [t for t, g in term_to_group.items() if g == cid]
        member_rows = [r for r in rows if r["term"] in set(member_terms)]
        # representative terms: highest df_corpus among voters in this group
        voter_members = [r for r in member_rows if r["df_corpus"] >= MIN_TERM_DF
                          and r["max_leaf_precision"] >= MAX_LEAF_PRECISION_FLOOR]
        top_terms = sorted(voter_members, key=lambda r: -r["df_corpus"])[:15]
        leaf_votes: dict[str, int] = {}
        for r in member_rows:
            for tl in r["top2_leaves"][:1]:
                leaf_votes[tl["leaf_id"]] = leaf_votes.get(tl["leaf_id"], 0) + tl["n_docs"]
        contributing_leaves = sorted(leaf_votes.items(), key=lambda kv: -kv[1])[:10]
        groups[f"G{cid}"] = {
            "n_terms": len(member_terms),
            "n_voter_terms": len(voter_members),
            "n_assigned_by_nearest": len(member_terms) - len(voter_members),
            "top_terms": [r["term"] for r in top_terms],
            "contributing_leaves": [{"leaf_id": lid, "vote_weight": w} for lid, w in contributing_leaves],
        }

    ambiguous_terms = [r["term"] for r in rows if r["ambiguous"]]

    # ARI diagnostic: cluster the SAME voter terms by their leaf-precision
    # loading vector (a proxy for "c-TF-IDF column vector" grouping — two
    # terms are "similar" only if they load on the same leaves) and compare
    # to the doc-centroid grouping above. Low ARI = the doc-centroid grouping
    # adds real information beyond leaf-membership, which matters given there
    # is no ground truth anywhere in this project.
    all_leaf_ids = sorted(candidates["leaves"].keys())
    leaf_col = {lid: i for i, lid in enumerate(all_leaf_ids)}
    loading = np.zeros((len(rows), len(all_leaf_ids)))
    for i, t in enumerate(candidate_terms):
        for lid, prec in per_term_leaf_precision[t].items():
            loading[i, leaf_col[lid]] = prec
    loading_voters = loading[is_voter]
    scores_load, Z_load = _silhouette_sweep(loading_voters, [best_k])
    labels_load = fcluster(Z_load, t=best_k, criterion="maxclust")
    ari = float(adjusted_rand_score(labels, labels_load))
    print(f"[Plan A Phase 3] ARI (doc-centroid grouping vs leaf-precision-loading "
          f"grouping, same k={best_k}): {ari:.4f}  "
          f"({'grouping adds real information' if ari < 0.5 else 'groupings largely agree'})")

    out = {
        "_meta": {
            "plan": "A",
            "n_candidate_terms": len(rows),
            "n_voters": n_voters,
            "min_term_df": MIN_TERM_DF,
            "max_leaf_precision_floor": MAX_LEAF_PRECISION_FLOOR,
            "k_sweep_range": list(K_SWEEP),
            "k_preferred_range": list(K_PREFERRED_RANGE),
            "chosen_k": best_k,
            "chosen_k_silhouette": round(scores[best_k], 4),
            "clamped_outside_preferred_range": clamped_note,
            "ari_doc_centroid_vs_leaf_loading": round(ari, 4),
            "term_representation": "centered_doc_centroid",
            "n_ambiguous_terms": len(ambiguous_terms),
        },
        "silhouette_by_k": {str(k): round(v, 4) for k, v in scores.items()},
        "groups": groups,
        "ambiguous_terms_sample": ambiguous_terms[:50],
        "terms": rows,
    }
    out_path = OUTPUTS / "kw_term_groups_planA.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"[Plan A Phase 3] wrote {out_path}")


if __name__ == "__main__":
    main()
