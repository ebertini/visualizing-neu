"""
clean_text.py — the single source of truth for grant title/abstract cleaning.

Two consumers, two cleaning depths (M1 of docs/TOPIC_WORK_FORWARD_PLAN.md):

1. **SPECTER2 embedding** (src/build_specter2_embeddings.py) and the EnricoVis
   preview use `clean_title` / `clean_abstract` / `clean_document`. These are
   *conservative*: they strip funding-mechanism noise (program prefixes, NSF
   review-criteria boilerplate, leading grant-id/PI stubs, mangled markup) but
   keep real sentences, casing, and punctuation, because SPECTER2 is a
   sentence-transformer trained on published-paper prose.

2. **LDA / bag-of-words** (src/topics_lda.py) uses `clean_for_lda`, which is
   *aggressive*: after the same markup/boilerplate stripping it reduces text to
   lowercase letters-only tokens. `DOMAIN_STOPS` and the length thresholds used
   to select model-worthy abstracts also live here so both tracks agree.

Originally two copies existed (docs/EnricoVis/clean_text.py + inline rules in
notebooks/06_research_topics.ipynb); this module merges them.
"""
from __future__ import annotations

import html
import re

# ──────────────────────────────────────────────────────────────────────────────
# Shared patterns (used by both the conservative and the aggressive cleaners)
# ──────────────────────────────────────────────────────────────────────────────

# Program-name prefixes NSF/agencies stamp onto titles. These describe the
# funding vehicle, not the science, so they add noise to the embedding.
PROGRAM_PREFIXES = [
    "CAREER", "Collaborative Research", "Collaborative Proposal",
    "RAPID", "EAGER", "CRII", "RUI", "REU Site", "REU",
    "SBIR Phase I", "SBIR Phase II", "SBIR", "STTR",
    "Doctoral Dissertation Research", "DDRIG",
    "Conference", "Workshop", "Symposium", "Travel", "Student Travel",
    "I-Corps", "NRI", "BRIGE", "GOALI", "US Ignite", "PFI", "PFI:AIR",
    "MRI", "FRG", "AF", "SaTC", "CDS&E", "CIF", "NeTS", "CSR", "SHF",
    "Cyber-Physical Systems", "CPS", "Secure and Trustworthy Cyberspace",
]

# Compiled once: matches one-or-more leading "PREFIX:" tokens (case-insensitive),
# optionally wrapped in brackets, e.g. "CAREER: Collaborative Research: ..."
_prefix_alt = "|".join(re.escape(p) for p in sorted(PROGRAM_PREFIXES, key=len, reverse=True))
_LEADING_PREFIX = re.compile(rf"^\s*[\[\(]?\s*(?:{_prefix_alt})\s*[\]\)]?\s*[:\-–—]\s*", re.IGNORECASE)

# Leading NSF grant-id + PI stub some abstracts open with, e.g.
# "9501172  Kaeli, David  This research ..."
_LEADING_ID_STUB = re.compile(r"^\s*\d{5,8}\b[\s,]*(?:[A-Z][A-Za-z.\-']+,\s*[A-Z][A-Za-z.\-']+\s+)?")

# NSF review-criteria boilerplate. `_NSF_MISSION` is the broad form used by the
# nb06 cleaner (ends at "...criteria"); the extra scaffolding phrases below are
# the finer EnricoVis set. All are removed as phrases/sentences.
_NSF_MISSION = re.compile(
    r"this award reflects nsf'?s statutory mission.*?criteria\.?",
    re.IGNORECASE | re.DOTALL,
)
_BOILERPLATE_PATTERNS = [
    _NSF_MISSION,
    re.compile(r"\bIntellectual[ _]Merit\b\s*[:\.\-]?", re.IGNORECASE),
    re.compile(r"\bBroader[ _]Impacts?\b\s*[:\.\-]?", re.IGNORECASE),
    re.compile(r"\bBroader[ _]Impact\b\s*[:\.\-]?", re.IGNORECASE),
    # Generic proposal scaffolding phrases that recur across many abstracts
    re.compile(r"\bThe (?:intellectual merit|broader impacts?) of (?:this|the) (?:project|proposal|award|research)\b", re.IGNORECASE),
]

_MULTISPACE = re.compile(r"\s+")

# Markup noise: some abstracts carry HTML where <, >, & were mangled into the
# literal tokens "andlt", "andgt", "andamp" (e.g. "andlt.br/andgt"), plus a few
# real <br/> / </p> tags and &…; entities. All of it is junk for modeling.
_REAL_ENTITY = re.compile(r"&[a-zA-Z#0-9]+;")
_REAL_TAG = re.compile(r"<[^>]{0,40}>")
_MANGLED_TAG = re.compile(r"andlt\b.{0,14}?andgt\b", re.IGNORECASE)
# Stray mangled/entity residue left after tag removal: andlt/andgt/andamp and the
# bare lt/gt/amp tokens HTML unescaping can leave behind.
_MANGLED_STRAY = re.compile(r"\b(?:andlt|andgt|andamp|lt|gt|amp)\b", re.IGNORECASE)


def _strip_markup(s: str) -> str:
    """Unescape HTML entities, then remove real tags, mangled and*-tags, and
    any stray lt/gt/amp residue. Shared by every cleaner in this module."""
    s = html.unescape(s)          # &amp; -> &, &lt; -> <, ... (nb06 behaviour)
    s = _MANGLED_TAG.sub(" ", s)  # "andlt br/ andgt" -> " " (before entity/tag pass)
    s = _REAL_ENTITY.sub(" ", s)
    s = _REAL_TAG.sub(" ", s)
    s = _MANGLED_STRAY.sub(" ", s)
    return s


# ──────────────────────────────────────────────────────────────────────────────
# Conservative cleaners — feed SPECTER2 (keep sentences, case, punctuation)
# ──────────────────────────────────────────────────────────────────────────────

def clean_title(title: str) -> str:
    if not title:
        return ""
    t = _strip_markup(str(title))
    # Peel off potentially stacked program prefixes ("CAREER: Collaborative Research: X")
    prev = None
    while prev != t:
        prev = t
        t = _LEADING_PREFIX.sub("", t)
    return _MULTISPACE.sub(" ", t).strip()


def clean_abstract(abstract: str) -> str:
    if not abstract:
        return ""
    a = _strip_markup(str(abstract))
    a = _LEADING_ID_STUB.sub("", a)
    for pat in _BOILERPLATE_PATTERNS:
        a = pat.sub(" ", a)
    return _MULTISPACE.sub(" ", a).strip()


def clean_document(title: str, abstract: str) -> str:
    """Join a cleaned title + abstract for SPECTER2.

    SPECTER2 expects title and abstract joined by the tokenizer's [SEP].
    build_specter2_embeddings.py cleans the two halves and lets the tokenizer
    insert the real [SEP]; this helper is for the sklearn preview / any caller
    that needs a single string (a literal ' [SEP] ' token is harmless — the
    analyzer drops it)."""
    ct, ca = clean_title(title), clean_abstract(abstract)
    if ca:
        return f"{ct} [SEP] {ca}"
    return ct


# Abstract sources whose text is real enough to store/display, but NOT
# trustworthy enough to feed the topic model — currently just the NIH
# RePORTER parent-center fallback (a subaward grant whose specific subproject
# has no abstract of its own borrows its parent center's text instead; see
# src/backfill_nih_reporter.py). grants.parquet keeps the real text either
# way (CSV export, a future detail view); only the MODELING path excludes it.
LOW_TRUST_ABSTRACT_SOURCES = frozenset({"nih_reporter_parent"})


def _safe_str(value) -> str:
    """"" for None or float NaN, else str(value). `str(value or "")` looks
    equivalent but isn't: `bool(float("nan"))` is True, so a NaN would
    survive as the literal string "nan" rather than becoming "" — this
    checks for NaN directly (a NaN is the only float that's != itself)
    rather than relying on truthiness.
    """
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return str(value)


def usable_abstract(abstract: str, abstract_source: str = "") -> str:
    """Abstract text as the topic model may see it: "" when `abstract_source`
    is low-trust, even though the real text is stored elsewhere for display.
    """
    if _safe_str(abstract_source).strip() in LOW_TRUST_ABSTRACT_SOURCES:
        return ""
    return _safe_str(abstract)


def model_doc_halves(title: str, abstract: str, abstract_source: str = "") -> tuple[str, str]:
    """The (cleaned title, cleaned modeling-abstract) pair every fit-time
    consumer (build_specter2_embeddings.py, topics_bertopic.py) should build
    its doc text from, so they can't drift apart on how they treat
    LOW_TRUST_ABSTRACT_SOURCES OR on NaN-handling for the title half (found
    while auditing this: one caller had its own `.fillna("")` for the title,
    the other didn't — `_safe_str` here means neither needs to anymore)."""
    return clean_title(_safe_str(title)), clean_abstract(usable_abstract(abstract, abstract_source))


# ──────────────────────────────────────────────────────────────────────────────
# Aggressive cleaner + vocabulary controls — feed LDA / bag-of-words
# ──────────────────────────────────────────────────────────────────────────────

def clean_for_lda(text: str) -> str:
    """Reduce an abstract to lowercase letters-only tokens for CountVectorizer.

    This is the nb06 `clean_abstract` rule, kept faithful: HTML unescape ->
    strip NSF mission boilerplate -> strip tags/entities -> letters + whitespace
    only -> collapse whitespace -> lowercase. Punctuation, digits, and casing are
    intentionally discarded (bag-of-words does not use them)."""
    t = html.unescape(str(text))
    t = _NSF_MISSION.sub(" ", t)
    t = _REAL_TAG.sub(" ", t)
    t = _REAL_ENTITY.sub(" ", t)
    t = re.sub(r"[^a-zA-Z\s]", " ", t)      # letters + whitespace only
    t = _MANGLED_STRAY.sub(" ", t)          # drop andgt/andlt/lt/gt/amp residue
    return _MULTISPACE.sub(" ", t).strip().lower()


# Length thresholds used to decide which abstracts are model-worthy. nb06 filters
# on the RAW abstract character count first, then on the cleaned token count.
MIN_ABSTRACT_CHARS = 200
MIN_ABSTRACT_TOKENS = 40


def passes_length_filter(
    raw_abstract: str,
    min_chars: int = MIN_ABSTRACT_CHARS,
    min_tokens: int = MIN_ABSTRACT_TOKENS,
) -> bool:
    """True if `raw_abstract` is long enough to feed the topic model.

    Mirrors nb06: raw length >= 200 chars AND >= 40 tokens after `clean_for_lda`.
    """
    raw = str(raw_abstract).strip()
    if len(raw) < min_chars:
        return False
    return len(clean_for_lda(raw).split()) >= min_tokens


# Domain-specific stopwords: high-frequency grant-prose words that merge
# otherwise-distinct topics. Applied as a post-vectorizer vocabulary filter in
# topics_lda.build_dtm (a token is dropped if every part of it is in this set).
DOMAIN_STOPS = frozenset({
    'research', 'project', 'study', 'studies', 'proposal', 'proposed', 'abstract',
    'investigator', 'pi', 'principal', 'university', 'northeastern', 'professor', 'dr',
    'grant', 'award', 'program', 'support', 'use', 'using', 'used', 'also', 'will', 'new',
    'based', 'provide', 'provides', 'provided', 'include', 'including', 'result', 'results',
    'approach', 'methods', 'method', 'work', 'data', 'system', 'systems', 'model', 'models',
    'effect', 'effects', 'high', 'low', 'level', 'levels', 'group', 'field', 'fields', 'case',
    'cases', 'well', 'one', 'two', 'three', 'many', 'may', 'can', 'however', 'thus', 'across',
    'among', 'within', 'without', 'via', 'per', 'set', 'term', 'terms', 'part', 'parts', 'way',
    'ways', 'due', 'current', 'developed', 'develop', 'developing', 'development', 'goal',
    'goals', 'objective', 'objectives', 'aim', 'aims', 'specific', 'general', 'particular',
    'important', 'significant', 'significantly', 'improve', 'improved', 'improvement',
    'need', 'needed', 'uses', 'application', 'applications', 'area', 'areas', 'summary',
    'background', 'introduction', 'overview', 'description', 'the',
    'andgt', 'andlt', 'andamp', 'lt', 'gt', 'amp',
    # broad academic words that were merging otherwise-distinct topics
    'students', 'understanding', 'large', 'real', 'impact', 'information',
    'science', 'engineering', 'technology', 'design',
})
