"""
model_docs.py — light-deps (pandas/numpy/pyarrow only, NO bertopic/umap/hdbscan/
torch) loader for "cleaned doc text aligned to the cached SPECTER2 embeddings."

Extracted from topics_bertopic._load_docs_aligned_to_cache, which now
delegates here, so the two paths can't drift on cleaning/masking. Needed
because several consumers want the aligned (docs, ids, embeddings) triple
without paying for a BERTopic/UMAP/HDBSCAN import:
  - src/kw_vocab_discover.py (Plan B Phase 1+2 — no document clustering at all)
  - src/classify_by_keywords.py (Phase 4b — doesn't even need the .npy, just
    the cleaned text, but importing this module must not drag in torch either)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.clean_text import model_doc_halves
except ImportError:  # run from within src/
    from clean_text import model_doc_halves

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"


def _raw_text_lookup() -> dict[str, tuple[str, str, str]]:
    """grant_id / 'orphan-<id>' -> (raw title, raw abstract, abstract_source),
    UNcleaned — shared by every doc-text consumer below so they can't drift on
    which raw columns/fallbacks feed the cleaner."""
    gr = pd.read_parquet(PROC / "grants.parquet")
    gr["grant_id"] = gr["grant_id"].astype(str)
    title_col = "title_from_abstract" if "title_from_abstract" in gr.columns else "grantname"
    gr["_title"] = gr[title_col].where(gr[title_col].astype(str).str.len() > 0, gr["grantname"])
    # A null title_from_abstract passes the .where() condition above (NaN's
    # str() is "nan", which has length 3), so it needs its own fillna rather
    # than relying on the .where() alone.
    gr["_title"] = gr["_title"].fillna("").astype(str)
    gr["abstract"] = gr["abstract"].fillna("").astype(str)
    # Mask LOW_TRUST_ABSTRACT_SOURCES text so the doc text seen here matches
    # what build_specter2_embeddings.py already embedded — a grant tagged
    # low-trust reads as title-only in both places, not just one.
    src = gr["abstract_source"].fillna("").astype(str) if "abstract_source" in gr.columns \
        else pd.Series([""] * len(gr), index=gr.index)
    by_id = {gid: (t, a, s) for gid, t, a, s in zip(gr["grant_id"], gr["_title"], gr["abstract"], src)}

    # M2 orphan pseudo-docs ('orphan-<id>') live in extra_neu_abstracts, not grants.
    extra_path = PROC / "extra_neu_abstracts.parquet"
    if extra_path.exists():
        ex = pd.read_parquet(extra_path)
        ex_src = ex["abstract_source"].fillna("").astype(str) if "abstract_source" in ex.columns \
            else pd.Series([""] * len(ex), index=ex.index)
        for did, t, a, s in zip(ex["doc_id"], ex["title"], ex["abstract"], ex_src):
            by_id[str(did)] = (t, a, s)
    return by_id


def _doc_id_order() -> list[str]:
    """The doc-id order every doc-aligned artifact (SPECTER2 cache,
    topic_assignments.parquet) shares — read from the plain-text id list, NOT
    the .npy, so a caller that only needs ids/text never pays for loading
    embeddings."""
    ids_path = PROC / "specter2_ids.txt"
    if not ids_path.exists():
        raise FileNotFoundError(
            f"Missing {ids_path.name}. Run `python -m src.build_specter2_embeddings` "
            "locally first (this file is a cheap byproduct of that run, even for a "
            "caller that never touches the embeddings themselves)."
        )
    return ids_path.read_text().splitlines()


def load_docs_and_embeddings() -> tuple[list[str], list[str], np.ndarray]:
    """Load cached SPECTER2 embeddings + build cleaned docs in the SAME order
    as the cache. Returns (docs, ids, embeddings)."""
    vec_path = PROC / "specter2_embeddings.npy"
    if not vec_path.exists():
        raise FileNotFoundError(
            f"Missing {vec_path.name}. Run `python -m src.build_specter2_embeddings` "
            "locally first."
        )
    embeddings = np.load(vec_path)
    ids = _doc_id_order()
    by_id = _raw_text_lookup()

    docs, missing = [], 0
    for did in ids:
        if did in by_id:
            t, a, s = by_id[did]
            title, abstract = model_doc_halves(t, a, s)
            docs.append(f"{title}. {abstract}".strip())
        else:
            docs.append("")  # keep alignment; should not happen if cache is fresh
            missing += 1
    if missing:
        print(f"WARNING: {missing} cache ids not found in grants/extras (cache stale?)")
    if len(docs) != len(embeddings):
        raise ValueError(f"docs ({len(docs)}) and embeddings ({len(embeddings)}) misaligned")
    return docs, ids, embeddings


def load_doc_fields() -> tuple[list[str], list[str], list[str]]:
    """Cleaned (title, abstract) kept as SEPARATE fields, aligned to the same
    doc-id order as load_docs_and_embeddings() — for BM25F-style consumers
    (src/classify_by_keywords.py) that need title/abstract scored separately
    and must NOT pull in the SPECTER2 .npy (a heavy, torch-regenerable
    artifact) just to get doc text. Returns (ids, titles, abstracts)."""
    ids = _doc_id_order()
    by_id = _raw_text_lookup()

    titles, abstracts, missing = [], [], 0
    for did in ids:
        if did in by_id:
            t, a, s = by_id[did]
            title, abstract = model_doc_halves(t, a, s)
        else:
            title, abstract = "", ""  # keep alignment; should not happen if cache is fresh
            missing += 1
        titles.append(title)
        abstracts.append(abstract)
    if missing:
        print(f"WARNING: {missing} ids not found in grants/extras (cache stale?)")
    return ids, titles, abstracts
