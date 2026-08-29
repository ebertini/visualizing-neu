"""
keyword_match.py — Phase 4b matching layer (stdlib only, no sklearn/nltk):
finds curated keyword-list terms in a document's text as PHRASES over a
token stream, scoped to one sentence at a time.

Never a substring match ("ion" does not match inside "ionosphere", "cell"
does not match inside "excellent") and never across a sentence boundary —
both guarded by construction: matching happens over `tokenize()`'s token
list, and separately per sentence.

Three match tiers, always tried in this priority order per occurrence, so a
stronger tier can never be shadowed by counting the same occurrence again at
a weaker one:
  1. exact     — token-for-token as written
  2. collapsed — intra-token -./+ stripped on both sides, so a keyword
                 written "covid-19" also matches a document token "covid19"
  3. stem      — a small conservative plural fold (kw_vocab.canonical_term),
                 the last-resort tier. No `nltk`: its WordNet lemmatizer
                 needs a network download, which would break the offline
                 requirement this classifier is built around.

Reuses `src.kw_vocab.tokenize()` — its own docstring already declares this
exact contract — so harvesting (kw_vocab_discover.py) and matching (this
module) can never silently diverge on what counts as a token.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

try:
    from src.kw_vocab import canonical_term, tokenize
except ImportError:  # run from within src/
    from kw_vocab import canonical_term, tokenize

# Rough sentence boundary: sentence-ending punctuation followed by whitespace
# and a capital letter or digit. Deliberately conservative — a missed split
# (e.g. "Dr. Smith") just means a real phrase might fail to match across a
# false non-split, a false negative, never a false positive that reaches
# across an actual sentence boundary.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

# Only a BRIDGING separator (alphanumeric on both sides, like the '-' in
# 'covid-19' or the '.' in 'pm2.5') is collapsed. A leading/trailing symbol
# (e.g. 'a+', the Advanced-LIGO-era program name) has no real second half to
# bridge — collapsing it degenerates to a short, extremely common substring
# ('a+' -> 'a', matching the article "a" in any English prose). Found as a
# real bug, not a hypothetical one: a curated LIGO term 'a+' was matching
# antimicrobial-chemistry grant abstracts via this exact degenerate collapse.
_COLLAPSE_RE = re.compile(r"(?<=[A-Za-z0-9])[-./+](?=[A-Za-z0-9])")


def segment_sentences(text: str) -> list[str]:
    """Split `text` into sentence-scoped segments. Empty/whitespace-only
    input returns []."""
    text = (text or "").strip()
    if not text:
        return []
    return [s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _collapse(token: str) -> str:
    """Strip BRIDGING intra-token -./+ so 'covid-19' and 'covid19' are the
    same surface at the collapsed tier (kw_vocab.tokenize() keeps -./+
    intra-token at the exact tier; this tier undoes that only where the
    punctuation actually bridges two alphanumeric halves — see
    _COLLAPSE_RE's docstring for why a trailing/leading symbol must NOT be
    collapsed)."""
    return _COLLAPSE_RE.sub("", token)


def _stem(token: str) -> str:
    """The stem tier's fold — reuses kw_vocab.canonical_term (already applies
    kw_vocab's plural fold), called on one already-lowercased token at a time
    so a multi-word term's words are folded independently before phrase
    matching, not folded as a joined string."""
    return canonical_term(token)


@dataclass(frozen=True)
class TermSurfaces:
    term: str
    exact: tuple[str, ...]
    collapsed: tuple[str, ...]
    stemmed: tuple[str, ...]


def term_surfaces(term: str) -> TermSurfaces:
    words = tokenize(term)
    return TermSurfaces(
        term=term,
        exact=tuple(words),
        collapsed=tuple(_collapse(w) for w in words),
        stemmed=tuple(_stem(w) for w in words),
    )


@dataclass(frozen=True)
class Match:
    term: str
    how: str  # "exact" | "collapsed" | "stem"
    sentence_index: int
    start: int  # token index within the sentence (post-tokenize())


def find_matches(sentences: list[str], terms: list[str]) -> list[Match]:
    """Every occurrence of every `terms` phrase across `sentences`, matched
    as a contiguous token-window within one sentence, tried exact before
    collapsed before stem per occurrence. Terms are deduplicated internally
    by `term_surfaces()`, but callers should not pass the same literal term
    string twice (it would double-count).

    Indexed by window-tuple -> [start positions] per sentence/length/tier so
    this stays a dict-lookup per term rather than a term x window nested
    loop — with ~800+ curated terms x ~2,700 docs, the naive nested loop is
    the difference between seconds and minutes.
    """
    surfaces = [term_surfaces(t) for t in terms]
    lengths_needed = {len(s.exact) for s in surfaces if s.exact}
    if not lengths_needed:
        return []

    matches: list[Match] = []
    for si, sent in enumerate(sentences):
        raw_tokens = tokenize(sent)
        collapsed_tokens = [_collapse(t) for t in raw_tokens]
        stem_tokens = [_stem(t) for t in raw_tokens]
        n = len(raw_tokens)

        windows: dict[int, dict[str, dict[tuple, list[int]]]] = {}
        for length in lengths_needed:
            if length > n:
                continue
            exact_w: dict[tuple, list[int]] = {}
            collapsed_w: dict[tuple, list[int]] = {}
            stem_w: dict[tuple, list[int]] = {}
            for i in range(n - length + 1):
                exact_w.setdefault(tuple(raw_tokens[i:i + length]), []).append(i)
                collapsed_w.setdefault(tuple(collapsed_tokens[i:i + length]), []).append(i)
                stem_w.setdefault(tuple(stem_tokens[i:i + length]), []).append(i)
            windows[length] = {"exact": exact_w, "collapsed": collapsed_w, "stem": stem_w}

        for ts in surfaces:
            length = len(ts.exact)
            if length == 0 or length not in windows:
                continue
            w = windows[length]
            used_positions: set[int] = set()
            for tier, key in (("exact", ts.exact), ("collapsed", ts.collapsed), ("stem", ts.stemmed)):
                for pos in w[tier].get(key, []):
                    if pos in used_positions:
                        continue
                    used_positions.add(pos)
                    matches.append(Match(ts.term, tier, si, pos))
    return matches


def match_text(text: str, terms: list[str]) -> list[Match]:
    """Convenience wrapper: segment `text` into sentences, then find_matches."""
    return find_matches(segment_sentences(text), terms)
