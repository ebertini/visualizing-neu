"""
_kw_term_df.py — ad-hoc diagnostic (not part of the pipeline): computes a real
`df_corpus` for one or more CANDIDATE keyword terms, for use when manually
curating a new term into `outputs/topic_keywords.json` (`src/kw_curation.py
--check` requires a non-zero `df_corpus` on every curated term, and refusing
to guess this number is the whole point of the check).

Ties df_corpus to the SAME matching semantics `classify_by_keywords.py` uses
at scoring time (`src.keyword_match.match_text`'s exact/collapsed/stem
tiers) — deliberately not `kw_vocab_discover.py`'s sklearn-vectorizer count,
which uses different tokenization and would silently disagree with what a
curated term will actually match once curated.

Run:
    python3 scripts/_kw_term_df.py "term one" "term two" ...
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.keyword_match import match_text  # noqa: E402
from src.model_docs import load_doc_fields  # noqa: E402


def main() -> None:
    terms = sys.argv[1:]
    if not terms:
        raise SystemExit("usage: python3 scripts/_kw_term_df.py <term> [<term> ...]")

    ids, titles, abstracts = load_doc_fields()
    n = len(ids)
    print(f"corpus size N={n}\n")

    for term in terms:
        df = 0
        for title, abstract in zip(titles, abstracts):
            matches = match_text(f"{title}. {abstract}", [term])
            if matches:
                df += 1
        print(f"{term!r}: df_corpus={df}")


if __name__ == "__main__":
    main()
