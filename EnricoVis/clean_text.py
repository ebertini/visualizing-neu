"""
clean_text.py — boilerplate/mechanism removal for grant titles + abstracts.

Used identically by build_preview.py (offline sklearn preview) and
pipeline.py (real SPECTER2 + UMAP), so the text fed to either projection
is the same. Cleaning is intentionally conservative: it strips funding
*mechanism* noise (program prefixes, NSF review-criteria boilerplate,
leading grant-id/PI stubs) while leaving the scientific content intact.
"""
import re

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
_LEADING_PREFIX = re.compile(rf"^\s*[\[\(]?\s*(?:{_prefix_alt})\s*[\]\)]?\s*[:\-\u2013\u2014]\s*", re.IGNORECASE)

# Leading NSF grant-id + PI stub some abstracts open with, e.g.
# "9501172  Kaeli, David  This research ..."
_LEADING_ID_STUB = re.compile(r"^\s*\d{5,8}\b[\s,]*(?:[A-Z][A-Za-z.\-']+,\s*[A-Z][A-Za-z.\-']+\s+)?")

# NSF review-criteria boilerplate. Removed as phrases/sentences.
_BOILERPLATE_PATTERNS = [
    re.compile(r"This award reflects NSF'?s statutory mission.*?review criteria\.?", re.IGNORECASE | re.DOTALL),
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
_MANGLED_STRAY = re.compile(r"\band(?:lt|gt|amp)\b", re.IGNORECASE)

def _strip_markup(s: str) -> str:
    s = _REAL_ENTITY.sub(" ", s)
    s = _REAL_TAG.sub(" ", s)
    s = _MANGLED_TAG.sub(" ", s)
    s = _MANGLED_STRAY.sub(" ", s)
    return s


def clean_title(title: str) -> str:
    if not title:
        return ""
    t = _strip_markup(title)
    # Peel off potentially stacked program prefixes ("CAREER: Collaborative Research: X")
    prev = None
    while prev != t:
        prev = t
        t = _LEADING_PREFIX.sub("", t)
    return _MULTISPACE.sub(" ", t).strip()


def clean_abstract(abstract: str) -> str:
    if not abstract:
        return ""
    a = _strip_markup(abstract)
    a = _LEADING_ID_STUB.sub("", a)
    for pat in _BOILERPLATE_PATTERNS:
        a = pat.sub(" ", a)
    return _MULTISPACE.sub(" ", a).strip()


def clean_document(title: str, abstract: str) -> str:
    """SPECTER2 expects title and abstract joined by the tokenizer's SEP.
    We join with a plain separator here; pipeline.py passes them so the
    tokenizer inserts the real [SEP]. For the sklearn preview a plain
    ' [SEP] ' token is harmless (dropped by the analyzer)."""
    ct, ca = clean_title(title), clean_abstract(abstract)
    if ca:
        return f"{ct} [SEP] {ca}"
    return ct
