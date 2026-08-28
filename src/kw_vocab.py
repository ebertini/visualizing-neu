"""
kw_vocab.py — shared vocabulary policy for the keyword-mediated topic redesign
(docs/... topic-model-redo plan, Plan A and Plan B discovery-comparison run).

`src/clean_text.DOMAIN_STOPS` was tuned for the opposite objective of a keyword
classifier: it strips broad academic words (science, engineering, data, ...) so
BERTopic's c-TF-IDF labels stay *discriminative between clusters*. For a
keyword-mediated classifier those same words are exactly the ones that make
compound terms like "data science" / "systems engineering" possible, since a
term is dropped only if EVERY token in it is a stopword — restoring the broad
unigrams lets multi-word compounds containing them survive, while IDF
naturally down-weights the bare unigrams (see the topic-redo plan's measured
IDF table: `data science` carries ~4.5x the weight of bare `data`).

This module does not touch `DOMAIN_STOPS` itself — it splits it by explicit
allowlist so a future edit to `DOMAIN_STOPS` fails loudly (via the assert)
rather than silently changing classifier vocabulary.
"""
from __future__ import annotations

import re

try:
    from src.clean_text import DOMAIN_STOPS
except ImportError:  # run from within src/
    from clean_text import DOMAIN_STOPS

# The broad, content-bearing academic words DOMAIN_STOPS strips only because
# they blurred BERTopic's per-cluster labels. Restoring these for the keyword
# extractor is what lets compounds built from them ("data science", "systems
# engineering", "information theory") survive at all.
CONTENT_BEARING_RESTORE = frozenset({
    "science", "engineering", "technology", "design",
    "data", "information", "system", "systems",
    "model", "models", "method", "methods",
    "field", "fields", "understanding", "impact", "students",
})
assert CONTENT_BEARING_RESTORE <= DOMAIN_STOPS, (
    "CONTENT_BEARING_RESTORE must stay a subset of DOMAIN_STOPS — if this "
    "fails, DOMAIN_STOPS changed underneath this module; update the allowlist "
    "deliberately rather than silently drifting."
)

# Everything else in DOMAIN_STOPS: grant-prose filler + markup residue, junk
# for classification just as much as for labelling.
PROSE_STOPS = frozenset(DOMAIN_STOPS - CONTENT_BEARING_RESTORE)
BROAD_DOMAIN_STOPS = CONTENT_BEARING_RESTORE  # named to mirror the plan's split

EXTRA_PROSE_STOPS: frozenset[str] = frozenset()  # none identified yet
CLASSIFIER_STOPS = frozenset(PROSE_STOPS | EXTRA_PROSE_STOPS)

# Keeps intra-token -/./+  so "covid-19", "pm2.5", "sars-cov-2", "cd4+" survive
# tokenization (BERTopic's own `_preprocess_text` regex would destroy these —
# see the plan's fact (b) — but harvesting outside BERTopic sidesteps it).
KW_TOKEN_PATTERN = r"(?u)[A-Za-z0-9]+(?:[-./][A-Za-z0-9]+)*\+*"

_TOKEN_RE = re.compile(KW_TOKEN_PATTERN)


def is_stopword_only(term: str, stopset: frozenset[str] = CLASSIFIER_STOPS) -> bool:
    """True if EVERY token in `term` is a stopword (unigram-level policy) —
    "data" alone is dropped, but "data science" survives because "science"
    survives the check on its own token."""
    tokens = term.split()
    return bool(tokens) and all(t in stopset for t in tokens)


def _fold_plural(word: str) -> str:
    """Crude, conservative singular fold for surface-level term dedup only —
    not a real stemmer, just enough to merge "sensor"/"sensors"."""
    if len(word) <= 4:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ses", "xes", "zes", "shes", "ches")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def canonical_term(term: str) -> str:
    """Surface-normalize a term for dedup: lowercase + per-token plural fold.
    Two terms with the same canonical form are treated as the same candidate
    (e.g. "neural network" / "neural networks")."""
    return " ".join(_fold_plural(w) for w in term.lower().split())


def tokenize(text: str) -> list[str]:
    """Same tokenization the CountVectorizer instances in kw_discover.py /
    kw_vocab_discover.py use, exposed standalone for term-doc-set bookkeeping
    and for src/keyword_match.py (Phase 4b) to stay consistent with it."""
    return _TOKEN_RE.findall(text.lower())
