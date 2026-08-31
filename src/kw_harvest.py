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

BOUNDARY_STOPS lives here (not in kw_vocab.py) specifically to keep
kw_vocab.py free of a sklearn dependency — src/keyword_match.py (Phase 4b,
the classifier) is meant to be pandas/stdlib-only per the topic-redo plan,
and will import kw_vocab.py's tokenizer/canonicalization helpers; it must not
transitively require sklearn just because kw_vocab.py happened to need
ENGLISH_STOP_WORDS for one constant.
"""
from __future__ import annotations

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

from src.kw_vocab import CONTENT_BEARING_RESTORE, KW_TOKEN_PATTERN, canonical_term, is_stopword_only

MIN_DF = 5
MAX_DF = 0.25
SUBSUMPTION_THRESHOLD = 0.8

# Closed-class function words that pollute n-gram boundaries: sklearn glues
# "of"/"in"/"and"/"their"/etc. onto an adjacent content word during n-gram
# assembly (e.g. "data in", "of data", "analysis and", "their work"), none of
# which are in DOMAIN_STOPS (only "the" is) since that list was built for
# LDA/c-TF-IDF label vocabulary, not boundary hygiene. Subtracting
# CONTENT_BEARING_RESTORE fixes a real collision: sklearn's own list includes
# "system", which this project deliberately un-stopped so "systems
# engineering" can survive — using ENGLISH_STOP_WORDS unmodified would have
# silently reintroduced that bug.
BOUNDARY_STOPS = frozenset(ENGLISH_STOP_WORDS) - CONTENT_BEARING_RESTORE

# Measured survivors only (not a guessed list) — standard Latin/scientific
# set phrases that start with a common preposition and would otherwise be
# wrongly dropped by the boundary rule. "et al" deliberately excluded: it
# survives min_df/max_df too, but it's a citation artifact, not a topic
# keyword.
SCIENTIFIC_IDIOM_ALLOWLIST = frozenset({
    "in vivo", "in vitro", "in situ", "in silico", "in utero", "ex vivo",
    "de novo", "a priori", "in real time", "in real-time",
})


def is_boundary_polluted(term: str) -> bool:
    """True if `term`'s leading or trailing token is a closed-class function
    word — a boundary-glued n-gram fragment, not a real multi-word term.
    Single-token terms are never boundary-polluted (that's
    kw_vocab.is_stopword_only's job).

    Also catches a bare "s" token anywhere in the n-gram — measured: always a
    possessive-apostrophe tokenization artifact (KW_TOKEN_PATTERN splits
    "project's" into "project" + "s"), never real content. Checked
    corpus-wide before adding this: 8/8 surviving "* s *" terms in the Plan B
    candidate vocabulary were artifacts ("project s", "nsf s", "child s",
    "project s broader", ...) — zero false positives."""
    if term in SCIENTIFIC_IDIOM_ALLOWLIST:
        return False
    tokens = term.split()
    if "s" in tokens:
        return True
    return len(tokens) > 1 and (tokens[0] in BOUNDARY_STOPS or tokens[-1] in BOUNDARY_STOPS)


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


def drop_boundary_polluted_terms(terms: np.ndarray, X: sparse.csr_matrix):
    """Post-hoc boundary-fragment filter (see is_boundary_polluted). Returns
    (kept_terms, kept_X, dropped_terms). Measured: removes ~66.5% of the raw
    harvested vocabulary at zero coverage cost (same zero-match-doc count
    before and after)."""
    keep_mask = np.array([not is_boundary_polluted(t) for t in terms])
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


def full_harvest(docs: list[str]) -> tuple[np.ndarray, sparse.csr_matrix, dict]:
    """The complete, canonical harvest pipeline — extract, drop stopword-only,
    drop boundary-polluted, dedup — in the one fixed order every caller must
    use. Introduced specifically because this exact 3-4 line chain was
    duplicated identically across 5 files (kw_discover.py, kw_vocab_discover.py,
    kw_term_groups.py, kw_term_cluster.py, kw_stability.py); adding a new
    filtering step (like the boundary filter) meant editing all 5 in lockstep
    or risking term-to-column mismatches between phases. Order matters: the
    boundary filter runs BEFORE dedup, since a subsumption relationship
    computed against soon-to-be-deleted boundary-polluted terms is meaningless.

    Returns (terms, X, dropped) where dropped = {"stopword_only": [...],
    "boundary_polluted": [...], "dedup_log": [...]}.
    """
    vec, X = harvest_vectorizer(docs)
    terms, X, dropped_stop = drop_stopword_only_terms(vec, X)
    terms, X, dropped_boundary = drop_boundary_polluted_terms(terms, X)
    kept_idx, dedup_log = subsume_terms(terms, X)
    terms = terms[kept_idx]
    X = X[:, kept_idx]
    return terms, X, {
        "stopword_only": dropped_stop,
        "boundary_polluted": dropped_boundary,
        "dedup_log": dedup_log,
    }
