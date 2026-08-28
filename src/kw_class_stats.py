"""
kw_class_stats.py — light-deps (numpy/scipy/pandas only — NO bertopic/umap/
hdbscan/torch) cross-class term discriminativeness, computed against the
ALREADY-COMMITTED canonical BERTopic partition (data/processed/
topic_assignments.parquet).

Built for Plan B (src/kw_vocab_discover.py, src/kw_term_cluster.py) after the
original dispersion+idf ranking was measured to fail: both dispersion and idf
are monotone in document frequency, so a global top-N cut collapsed onto the
min_df floor (all 2,500 kept terms had df in {5,6}) instead of surfacing
genuinely discriminative vocabulary. A proposed `max_topic_precision>=0.15`
filter was ALSO measured to fail as a filter — it passes 98.8% of df=5
boilerplate and deletes 90% of df>=201 science vocabulary, because precision
alone is anti-correlated with df. `max_class_precision` is kept below only as
a reported diagnostic, not a selection mechanism.

The fix that works: score candidates by c-TF-IDF against the canonical
partition, using it purely as a FREE, already-fit document grouping (a
`doc_id -> topic_id` integer column) — no keyword text, no curated labels,
nothing from outputs/topic_labels.json or docs/EnricoVis/ is read anywhere in
this module. `class_ctfidf` is a deliberate reimplementation (not an import)
of bertopic.vectorizers.ClassTfidfTransformer's formula, verified bit-exact
(max abs diff = 0.0) against the installed transformer, so Plan B keeps zero
bertopic/umap/hdbscan/torch imports while matching the canonical model's
scoring semantics.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"


def load_canonical_partition(ids: list[str]) -> tuple[np.ndarray, list[int]]:
    """Map `ids` (in the SPECTER2-cache doc order) to canonical topic_id class
    indices. Returns (class_index, class_ids) where class_index[i] is the
    position of ids[i]'s class within class_ids (which includes -1/noise as
    its own class). Asserts every id resolves — currently 0 unmapped, make
    that a hard guarantee rather than a hope."""
    ta = pd.read_parquet(PROC / "topic_assignments.parquet")
    by_doc = dict(zip(ta["doc_id"].astype(str), ta["topic_id"].astype(int)))
    missing = [i for i in ids if i not in by_doc]
    assert not missing, (
        f"{len(missing)} doc ids have no canonical topic_assignments.parquet "
        f"entry (cache/partition out of sync?): {missing[:10]}"
    )
    class_ids = sorted(set(by_doc.values()))  # includes -1
    class_pos = {c: i for i, c in enumerate(class_ids)}
    class_index = np.array([class_pos[by_doc[i]] for i in ids], dtype=int)
    return class_index, class_ids


def _class_count_matrix(X: sparse.csr_matrix, class_index: np.ndarray, n_classes: int) -> np.ndarray:
    """Sum term counts within each class -> dense (n_classes, n_terms) RAW
    count matrix C, the shared input both class_ctfidf and max_class_precision
    build from."""
    Xc = X.tocsr()
    C = np.zeros((n_classes, X.shape[1]))
    for c in range(n_classes):
        rows = np.where(class_index == c)[0]
        if len(rows):
            C[c] = np.asarray(Xc[rows].sum(axis=0)).ravel()
    return C


def class_ctfidf(X: sparse.csr_matrix, class_index: np.ndarray, n_classes: int) -> np.ndarray:
    """(n_classes, n_terms) c-TF-IDF weight matrix. Bit-exact vs.
    bertopic.vectorizers.ClassTfidfTransformer (_ctfidf.py:70-83, 98-116):
    L1-normalize each class's raw counts, multiply by log(avg_class_size/df + 1).
    """
    C = _class_count_matrix(X, class_index, n_classes)
    f = C.sum(axis=0)                       # per-term total count across classes
    A = int(C.sum(axis=1).mean())           # average class size
    w = np.log(A / np.maximum(f, 1) + 1)
    row_sums = C.sum(axis=1, keepdims=True)
    CT = (C / np.maximum(row_sums, 1)) * w
    return CT


def max_class_precision(X: sparse.csr_matrix, class_index: np.ndarray, n_classes: int) -> np.ndarray:
    """DIAGNOSTIC ONLY — do not use for selection (see class_ctfidf's
    docstring for why). df_class/df_corpus per term, maxed over classes,
    where df_class is the number of DOCS (not raw term occurrences) in that
    class containing the term at least once — the same formula
    src/kw_discover.py's `_leaf_keyword_table` uses for its `precision`
    field, computed here against the canonical partition instead of a
    freshly-fit one. Measured to be anti-correlated with the right answer as
    a selection filter: at a 0.15 floor it passes 98.8% of df=5 boilerplate
    terms and deletes 90% of df>=201 science vocabulary, because precision
    alone falls as df rises regardless of term quality. Kept only for
    reporting."""
    Xb = (X > 0).astype(np.int32).tocsr()
    df_class = np.zeros((n_classes, X.shape[1]))
    for c in range(n_classes):
        rows = np.where(class_index == c)[0]
        if len(rows):
            df_class[c] = np.asarray(Xb[rows].sum(axis=0)).ravel()
    df_corpus = np.asarray(Xb.sum(axis=0)).ravel()
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = np.where(df_corpus > 0, df_class.max(axis=0) / np.maximum(df_corpus, 1), 0.0)
    return precision
