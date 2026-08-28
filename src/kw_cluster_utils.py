"""
kw_cluster_utils.py — tiny shared numpy/scipy helpers for term-vector
clustering, used identically by both discovery plans' Phase 3:
  - src/kw_term_groups.py   (Plan A — one cut, parents only)
  - src/kw_term_cluster.py  (Plan B — one dendrogram, two cuts)
"""
from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.metrics import silhouette_score


def cosine_normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n == 0, 1, n)


def linkage_and_silhouette_sweep(V: np.ndarray, ks) -> tuple[dict[int, float], np.ndarray]:
    """Average-linkage, cosine-distance hierarchical clustering + a silhouette
    sweep over `ks`. Deterministic, no seed — not Ward (undefined for
    non-Euclidean metrics), not KMeans (this project was already burned once
    by seed sensitivity in the mcs=25 BERTopic sweep)."""
    dist = 1 - cosine_normalize(V) @ cosine_normalize(V).T
    dist = np.clip(dist, 0, 2)
    np.fill_diagonal(dist, 0)
    condensed = squareform(dist, checks=False)
    Z = linkage(condensed, method="average")
    scores = {}
    for k in ks:
        labels = fcluster(Z, t=k, criterion="maxclust")
        if len(set(labels)) < 2:
            continue
        scores[k] = float(silhouette_score(dist, labels, metric="precomputed"))
    return scores, Z
