"""
kw_harvest.py — light-deps (numpy/scipy/scikit-learn only — NO bertopic/umap/
hdbscan/torch) corpus-wide keyword-candidate harvesting, shared verbatim by
both discovery plans:
  - src/kw_discover.py        (Plan A Phase 1+2 — groups this harvest by leaf)
  - src/kw_vocab_discover.py  (Plan B Phase 1+2 — uses this harvest directly,
                                no document grouping at all)

Split out specifically so Plan B's discovery script never has to import
bertopic/umap/hdbscan/torch just to get the term-candidate vocabulary — see
the plan's own point that Plan B's "only 'heavy' precondition" is the
already-cached SPECTER2 embeddings, not a fresh BERTopic import.

stop_words=None is deliberate everywhere here: sklearn's stopword removal
fabricates n-grams that occur in zero documents (verified against the
installed sklearn — stop words are removed BEFORE n-gram assembly, so
n-grams glue across the gap). Unigram-only stopword filtering happens
post-hoc instead (kw_vocab.is_stopword_only).
"""
from __future__ import annotations

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer

from src.kw_vocab import KW_TOKEN_PATTERN, canonical_term, is_stopword_only

MIN_DF = 5
MAX_DF = 0.25
SUBSUMPTION_THRESHOLD = 0.8


def harvest_vectorizer(docs: list[str]) -> tuple[CountVectorizer, sparse.csr_matrix]:
    """Corpus-level per-document term counts, harvested OUTSIDE BERTopic."""
    vec = CountVectorizer(
        token_pattern=KW_TOKEN_PATTERN, ngram_range=(1, 3),
        min_df=MIN_DF, max_df=MAX_DF, stop_words=None,
    )
    X = vec.fit_transform(docs)
    return vec, X


def drop_stopword_only_terms(vec: CountVectorizer, X: sparse.csr_matrix):
    """Post-hoc unigram-level stopword filter. Returns (kept_terms, kept_X, dropped_terms)."""
    terms = vec.get_feature_names_out()
    keep_mask = np.array([not is_stopword_only(t) for t in terms])
    dropped = [t for t, k in zip(terms, keep_mask) if not k]
    return terms[keep_mask], X[:, keep_mask], dropped


def subsume_terms(terms: np.ndarray, X: sparse.csr_matrix) -> tuple[list[int], list[dict]]:
    """Two-stage dedup: (1) canonical-surface merge, (2) document-support
    subsumption — drop a shorter term if it occurs almost exclusively inside
    an ADJACENT longer n-gram built from it (df(A∩B)/df(A) > 0.8). Restricted
    to adjacent sub-n-grams (not all token subsets) so this stays O(vocab)
    instead of the O(vocab^2) a full pairwise check would require at this
    vocab size (tens of thousands of terms after min_df/max_df filtering)."""
    Xc = X.tocsc()
    df = np.diff(Xc.indptr)

    canon_groups: dict[str, list[int]] = {}
    for j, t in enumerate(terms):
        canon_groups.setdefault(canonical_term(t), []).append(j)
    survivors = []
    merged_log = []
    for canon, idxs in canon_groups.items():
        if len(idxs) == 1:
            survivors.append(idxs[0])
            continue
        best = max(idxs, key=lambda j: df[j])
        survivors.append(best)
        for j in idxs:
            if j != best:
                merged_log.append({"dropped": terms[j], "merged_into": terms[best], "reason": "surface_merge"})

    term_to_idx = {terms[j]: j for j in survivors}

    dropped_idx: set[int] = set()
    subsumed_log = []
    for j in sorted(survivors, key=lambda j: -len(terms[j].split())):
        if j in dropped_idx:
            continue
        tokens = terms[j].split()
        if len(tokens) < 2:
            continue
        docs_j = set(Xc.getcol(j).nonzero()[0].tolist())
        candidates = {" ".join(tokens[:-1]), " ".join(tokens[1:])}
        for cand in candidates:
            i = term_to_idx.get(cand)
            if i is None or i == j or i in dropped_idx:
                continue
            docs_i = set(Xc.getcol(i).nonzero()[0].tolist())
            df_i = df[i] or 1
            overlap = len(docs_i & docs_j) / df_i
            if overlap > SUBSUMPTION_THRESHOLD:
                dropped_idx.add(i)
                subsumed_log.append({
                    "dropped": terms[i], "subsumed_by": terms[j],
                    "support_overlap": round(float(overlap), 3), "reason": "subsumption",
                })

    kept = [j for j in survivors if j not in dropped_idx]
    return kept, merged_log + subsumed_log
