"""Regression tests for the docs/TopicVizPrototypes/data/*.json contract —
the frontend JS modules dereference these key paths directly with no runtime
schema check of their own, so a silent shape change here is a page-breaking
change nothing else catches until a real browser load (see CLAUDE.md: no
browser is available in this working environment).

Also covers the src/build_viz_aggregates.py <-> shared/enrico.js hand-synced
copies (PARENT_NAMES/PARENT_COLORS) and the caveat-id whitelist <-> CAVEATS
contract — the same invariants scripts/_check_topicviz.py's
`check_parent_taxonomy()` enforces at build time, re-asserted here as a
regular pytest so `pytest -q` alone catches a regression without a separate
script invocation.

Reads the ALREADY-COMMITTED docs/TopicVizPrototypes/data/*.json — does not
regenerate them (that's `python -m src.build_viz_aggregates`'s job). Skipped
gracefully if that data hasn't been built locally yet.

Run:  pytest tests/test_viz_schema.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "docs" / "TopicVizPrototypes" / "data"
ENRICO_JS = REPO_ROOT / "docs" / "TopicVizPrototypes" / "shared" / "enrico.js"
TOPIC_FLOW_HTML = REPO_ROOT / "docs" / "TopicVizPrototypes" / "topic_flow.html"
MISSING_JS = REPO_ROOT / "docs" / "TopicVizPrototypes" / "what_we_can_see" / "missing.js"
BUILD_VIZ_AGGREGATES = REPO_ROOT / "src" / "build_viz_aggregates.py"

VIZ_META = DATA_DIR / "viz_meta.json"
COVERAGE = DATA_DIR / "coverage.json"
FACETS = DATA_DIR / "facets.json"
FACETS_PI = DATA_DIR / "facets_pi.json"

pytestmark = pytest.mark.skipif(
    not VIZ_META.exists() or not COVERAGE.exists(),
    reason="docs/TopicVizPrototypes/data/*.json not built locally yet "
           "(run python -m src.build_viz_aggregates)",
)


@pytest.fixture(scope="module")
def viz_meta() -> dict:
    return json.loads(VIZ_META.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def coverage() -> dict:
    return json.loads(COVERAGE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def facets() -> dict:
    return json.loads(FACETS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def facets_pi() -> dict:
    return json.loads(FACETS_PI.read_text(encoding="utf-8"))


# ── viz_meta.json key paths the JS modules dereference directly ────────────

def test_viz_meta_frozen_inputs_n_topics(viz_meta):
    assert isinstance(viz_meta["frozen_inputs"]["n_topics"], int)
    assert viz_meta["frozen_inputs"]["n_topics"] > 0


def test_viz_meta_caveats_have_ids(viz_meta):
    ids = [c["id"] for c in viz_meta["caveats"]]
    assert ids, "VIZ_META.caveats is empty"
    assert len(ids) == len(set(ids)), "duplicate caveat id"


def test_viz_meta_parents_and_topics_counts(viz_meta):
    # 8 real parents (P3 split into a redefined P3 + new P7 on 2026-08-29,
    # same day as promotion) + the synthetic id=-1 "Unassigned" entry = 9.
    assert len(viz_meta["parents"]) == 9
    real_parent_ids = {p["id"] for p in viz_meta["parents"] if p["id"] >= 0}
    assert real_parent_ids == set(range(8))

    # 31 real leaf topics + the id=-1 noise entry = 32.
    real_topics = [t for t in viz_meta["topics"] if t["id"] >= 0]
    assert len(real_topics) == 31
    assert {t["id"] for t in real_topics} == set(range(31))
    for t in real_topics:
        assert t["artifact"] is False, f"topic {t['id']} unexpectedly flagged artifact"
        assert "conf_mean" in t


def test_viz_meta_college_collab_shape(viz_meta):
    # The inter-college PI/co-PI collaboration story rendered on the About
    # section — a real cross-check on load_colleges_per_grant()'s college
    # normalization (a wrong-but-plausible unnormalized count silently
    # inflated this by 22% before it was fixed, see CLAUDE.md).
    cc = viz_meta["college_collab"]
    assert isinstance(cc["n_cross_college"], int)
    assert cc["n_cross_college"] > 0
    assert isinstance(cc["dollars"], (int, float))
    assert cc["dollars"] > 0

    pairs = cc["pairs"]
    assert pairs, "college_collab.pairs is empty"
    for p in pairs:
        assert p["a"] != p["b"], f"self-pair not filtered out: {p}"
        assert p["n"] > 0
        assert p["dollars"] >= 0
    # sorted descending by grant count, as the frontend bar list assumes
    assert [p["n"] for p in pairs] == sorted((p["n"] for p in pairs), reverse=True)
    # a 3-college grant contributes to 3 pairs, so the pair-count sum is a
    # lower bound on the cross-college grant total, never smaller than it
    assert sum(p["n"] for p in pairs) >= cc["n_cross_college"]

    # The About section's collaboration matrix orders its rows/columns by
    # by_college participation descending (server-sorted, not re-sorted
    # client-side) so the densest corner lands top-left — if this ever came
    # back unsorted or missing a field the matrix would silently mis-order
    # or throw on the frontend.
    by_college = cc["by_college"]
    assert len(by_college) >= 2, "need at least 2 colleges for any pair to exist"
    for c in by_college:
        assert isinstance(c["college"], str) and c["college"]
        assert isinstance(c["n"], int) and c["n"] > 0
    assert [c["n"] for c in by_college] == sorted((c["n"] for c in by_college), reverse=True)
    # every pair's colleges must be names that actually appear in by_college
    # (the matrix looks each one up via COLLEGE_SHORT keyed on this exact
    # string) — a name mismatch here would render a pair the matrix can
    # never place in its own row/column order.
    college_names = {c["college"] for c in by_college}
    for p in cc["pairs"]:
        assert p["a"] in college_names, f"pair college not in by_college: {p['a']}"
        assert p["b"] in college_names, f"pair college not in by_college: {p['b']}"

    # by_year feeds the client-computed "cross-college grants have grown"
    # sentence (about.js's collabGrowthPhrase) — must be real year/count
    # pairs, not just present.
    by_year = cc["by_year"]
    assert by_year, "college_collab.by_year is empty"
    for y in by_year:
        assert isinstance(y["year"], int)
        assert isinstance(y["n"], int) and y["n"] >= 0


# ── coverage.json key paths ─────────────────────────────────────────────────

def test_coverage_unassigned_by_reason_sums_to_n(coverage):
    unassigned = coverage["unassigned"]
    assert sum(unassigned["by_reason"].values()) == unassigned["n"]
    assert unassigned["artifact_n"] == 0
    assert "t11_n" not in unassigned, "old t11_n fossil should have been dropped, not just zeroed"
    assert "noise_n" not in unassigned, "old noise_n fossil should have been dropped, not just zeroed"


def test_coverage_confidence_by_text_shape(coverage):
    cb = coverage["confidence_by_text"]
    for key in ("abs", "title"):
        block = cb[key]
        for field in ("n", "high", "medium", "low", "none", "mean_margin"):
            assert field in block, f"confidence_by_text.{key} missing '{field}'"
        assert block["high"] + block["medium"] + block["low"] + block["none"] == block["n"]


# ── PARENT_NAMES/PARENT_COLORS hand-synced-copy consistency ────────────────

def _extract_string_list(text: str, marker: str) -> list[str]:
    i = text.find(marker)
    if i == -1:
        return []
    start = text.index("[", i)
    end = text.index("]", start)
    return re.findall(r'"([^"]*)"', text[start:end])


@pytest.mark.skipif(not ENRICO_JS.exists() or not BUILD_VIZ_AGGREGATES.exists(),
                     reason="shared/enrico.js or src/build_viz_aggregates.py not found")
def test_parent_names_value_identical_between_python_and_js():
    py_text = BUILD_VIZ_AGGREGATES.read_text(encoding="utf-8")
    js_text = ENRICO_JS.read_text(encoding="utf-8")
    py_names = _extract_string_list(py_text, "PARENT_NAMES = [")
    js_names = _extract_string_list(js_text, "const PARENT_NAMES = [")
    assert py_names, "could not parse PARENT_NAMES out of build_viz_aggregates.py"
    assert py_names == js_names


@pytest.mark.skipif(not ENRICO_JS.exists() or not BUILD_VIZ_AGGREGATES.exists(),
                     reason="shared/enrico.js or src/build_viz_aggregates.py not found")
def test_parent_colors_value_identical_between_python_and_js():
    py_text = BUILD_VIZ_AGGREGATES.read_text(encoding="utf-8")
    js_text = ENRICO_JS.read_text(encoding="utf-8")
    py_colors = _extract_string_list(py_text, "PARENT_COLORS = [")
    js_colors = _extract_string_list(js_text, "const PARENT_COLORS = [")
    assert py_colors, "could not parse PARENT_COLORS out of build_viz_aggregates.py"
    assert py_colors == js_colors


@pytest.mark.skipif(not ENRICO_JS.exists(), reason="shared/enrico.js not found")
def test_topic_colors_capacity_covers_leaf_count(viz_meta):
    js_text = ENRICO_JS.read_text(encoding="utf-8")
    topic_colors = _extract_string_list(js_text, "const TOPIC_COLORS = [")
    n_topics = viz_meta["frozen_inputs"]["n_topics"]
    assert len(topic_colors) >= n_topics, (
        f"TOPIC_COLORS has {len(topic_colors)} entries, fewer than the "
        f"{n_topics} curated leaf topics — colors will start silently repeating"
    )


# ── caveat-id whitelist <-> CAVEATS cross-reference ─────────────────────────

def _extract_caveat_whitelist(text: str) -> list[str]:
    m = re.search(r"renderCaveats\([^,]+,\s*VIZ_META\.caveats\s*,\s*\[([^\]]*)\]\s*\)", text)
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


@pytest.mark.parametrize("label,path", [
    ("topic_flow.html", TOPIC_FLOW_HTML),
    ("what_we_can_see/missing.js", MISSING_JS),
])
def test_caveat_whitelist_ids_exist_in_viz_meta(viz_meta, label, path):
    if not path.exists():
        pytest.skip(f"{label} not found")
    whitelist = _extract_caveat_whitelist(path.read_text(encoding="utf-8"))
    if not whitelist:
        pytest.skip(f"{label}: no renderCaveats(...) whitelist call found")
    caveat_ids = {c["id"] for c in viz_meta["caveats"]}
    unknown = [cid for cid in whitelist if cid not in caveat_ids]
    assert not unknown, f"{label} whitelists unknown caveat id(s): {unknown}"


# ── facets.json / facets_pi.json new-field contract (2026-08-30 additions) ──
# Locks in the fields added for the PI-feedback items (grant search box,
# topic-keyword fingerprint view, colleges-per-grant, PI dollars earned at
# NEU) so a future refactor can't silently drop them without a test noticing
# — the frontend dereferences these directly with no runtime schema check.

@pytest.mark.skipif(not FACETS.exists(), reason="facets.json not built locally yet")
def test_facets_matched_terms_and_pi_names_shape(facets):
    n = facets["n"]
    assert len(facets["matchedTerms"]) == n
    assert all(isinstance(mt, list) for mt in facets["matchedTerms"])
    assert len(facets["piNames"]) == n
    assert len(facets["nColleges"]) == n
    assert all(isinstance(nc, int) for nc in facets["nColleges"])


@pytest.mark.skipif(not FACETS.exists(), reason="facets.json not built locally yet")
def test_facets_ncol_column_and_levels(facets):
    n = facets["n"]
    assert "ncol" in facets["cols"], "ncol column (colleges-involved facet) missing from facets.json"
    assert len(facets["cols"]["ncol"]) == n
    assert "ncol" in facets["levels"]
    n_levels = len(facets["levels"]["ncol"])
    assert all(0 <= v < n_levels for v in facets["cols"]["ncol"])


@pytest.mark.skipif(not FACETS.exists(), reason="facets.json not built locally yet")
def test_facets_team_size_shape_and_floor(facets):
    """Team size (nTeam/cols.team) must be computed from distinct people
    linked to a grant, NOT a count of is_copi-flagged rows — verified against
    the real corpus that is_copi is a role label, not a team-size signal (see
    load_team_size_per_grant's docstring). Every grant has >=1 linked person,
    so nTeam must never be 0 and the "team" facet needs no miss bin."""
    n = facets["n"]
    assert "nTeam" in facets, "nTeam (raw team-size count) missing from facets.json"
    assert len(facets["nTeam"]) == n
    assert all(v >= 1 for v in facets["nTeam"]), "every grant must have >=1 linked person"
    assert "team" in facets["cols"]
    assert len(facets["cols"]["team"]) == n
    assert "team" in facets["levels"]
    n_levels = len(facets["levels"]["team"])
    assert all(0 <= v < n_levels for v in facets["cols"]["team"])


@pytest.mark.skipif(not FACETS_PI.exists(), reason="facets_pi.json not built locally yet")
def test_facets_pi_amt_neu_shape(facets_pi):
    n = facets_pi["n"]
    assert "amt_neu" in facets_pi["cols"], "amt_neu column (PI dollars earned at NEU) missing"
    assert len(facets_pi["cols"]["amt_neu"]) == n
    assert "amt_neu_raw" in facets_pi["cols"]
    assert len(facets_pi["cols"]["amt_neu_raw"]) == n
    assert "amt_neu" in facets_pi["levels"]
    n_levels = len(facets_pi["levels"]["amt_neu"])
    assert all(0 <= v < n_levels for v in facets_pi["cols"]["amt_neu"])
    # amt_neu should never exceed amt (earned_at_neu is a strict subset of
    # all PI-credited dollars) for any PI with grants.
    for raw_neu, raw_all in zip(facets_pi["cols"]["amt_neu_raw"], facets_pi["cols"]["amt_raw"]):
        assert raw_neu <= raw_all + 1e-6
