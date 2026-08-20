"""Regression tests for the LOW_TRUST_ABSTRACT_SOURCES exclusion (Phase 2 of
the NIH RePORTER / NSF Award Search backfill adoption). A grant tagged
`nih_reporter_parent` (a subaward whose specific subproject had no abstract
of its own, so it borrowed its parent center's text) must be embedded and
clustered exactly as if it were still title-only, even though grants.parquet
stores the real borrowed text for display. See src/clean_text.py's
`usable_abstract`/`model_doc_halves` and the callers in
src/build_specter2_embeddings.py and src/topics_bertopic.py.

The manifest/cache checks below need a real (heavy, local-only) SPECTER2 run
to exist — skipped gracefully otherwise, not counted as a failure. The pure
`usable_abstract`/`model_doc_halves` tests always run (light deps only).

Run:  pytest tests/test_low_trust_exclusion.py
"""
from pathlib import Path

import pandas as pd
import pytest

from src.clean_text import LOW_TRUST_ABSTRACT_SOURCES, model_doc_halves, usable_abstract

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
MANIFEST = PROC / "specter2_doc_manifest.parquet"
GRANTS = PROC / "grants.parquet"


# ── Pure contract tests (always run) ────────────────────────────────────────

def test_usable_abstract_masks_low_trust_sources():
    assert usable_abstract("real text here", "nih_reporter_parent") == ""


@pytest.mark.parametrize("source", ["nih_reporter", "nsf_api", "internal",
                                     "orphan_recovered", "orphan_extra", ""])
def test_usable_abstract_passes_through_trusted_sources(source):
    assert usable_abstract("real text here", source) == "real text here"


def test_usable_abstract_handles_missing_values():
    assert usable_abstract(None, "nih_reporter_parent") == ""
    assert usable_abstract(None, "nih_reporter") == ""
    assert usable_abstract("text", None) == "text"


def test_model_doc_halves_masks_abstract_but_keeps_title():
    title, abstract = model_doc_halves("Some Grant Title", "borrowed parent text",
                                        "nih_reporter_parent")
    assert abstract == ""
    assert "Some Grant Title" in title


def test_low_trust_set_is_not_accidentally_empty():
    """Non-vacuity guard: if this set is ever emptied by a careless edit, every
    test above would still pass while testing nothing — the exact
    PI_FACET_DEFS.tp failure mode CLAUDE.md warns about.
    """
    assert len(LOW_TRUST_ABSTRACT_SOURCES) >= 1
    assert "nih_reporter_parent" in LOW_TRUST_ABSTRACT_SOURCES


# ── Integration checks against real artifacts (skipped if absent) ──────────

pytestmark_manifest = pytest.mark.skipif(
    not MANIFEST.exists(), reason="specter2_doc_manifest.parquet not built locally yet "
                                    "(run python -m src.build_specter2_embeddings)"
)


@pytestmark_manifest
def test_manifest_shows_low_trust_grants_embedded_title_only():
    manifest = pd.read_parquet(MANIFEST)
    low_trust = manifest[manifest["abstract_source"].isin(LOW_TRUST_ABSTRACT_SOURCES)]
    assert len(low_trust) >= 1, "non-vacuity: expected >=1 low-trust grant in the manifest"
    assert (low_trust["abstract_chars"] == 0).all(), \
        "a low-trust grant's abstract reached the tokenizer — exclusion isn't working"
    assert (low_trust["title_chars"] > 0).all(), \
        "a low-trust grant has no title either — it would be dropped from the corpus entirely"


@pytestmark_manifest
def test_manifest_row_aligned_with_specter2_ids():
    ids = (PROC / "specter2_ids.txt").read_text().splitlines()
    manifest = pd.read_parquet(MANIFEST)
    assert len(manifest) == len(ids)
    assert manifest["doc_id"].astype(str).tolist() == ids


@pytest.mark.skipif(not GRANTS.exists(), reason="grants.parquet not built locally yet "
                                                  "(run python -m src.build_dataset)")
def test_grants_parquet_still_stores_real_text_for_low_trust_grants():
    """The exclusion is MODELING-only — grants.parquet itself must still
    carry the real borrowed text for human-facing display (CSV export, a
    future detail view)."""
    g = pd.read_parquet(GRANTS)
    low_trust = g[g["abstract_source"].isin(LOW_TRUST_ABSTRACT_SOURCES)]
    if low_trust.empty:
        pytest.skip("no low-trust grants in the current grants.parquet")
    assert (low_trust["abstract"].astype(str).str.len() > 0).all(), \
        "grants.parquet lost the real text for a low-trust-tagged grant — display would break"
