"""
build_viz_aggregates.py — Round 1 of the topic-model visualization prototypes
(see docs/TopicVizPrototypes/`topic_flow.html` and `what_we_can_see.html`).

These prototypes are the user's own analysis work, kept separate from
docs/EnricoVis/ (a parallel visualization effort by the PI). They DO read
EnricoVis's canonical BERTopic/SPECTER2 output as an upstream input — that
model is the PI's, reused here rather than re-fit — but every derived file
this script writes goes to docs/TopicVizPrototypes/, never into EnricoVis/.

Unlike src/build_viz_data.py, this script does NOT need specter2_umap_2d.npy /
topic_assignments.parquet / outputs/topic_labels.json — those inputs are
absent locally and not regenerable without a HuggingFace SPECTER2 download.
Topic assignments and UMAP coords are effectively frozen; the real BERTopic
output already lives in the two committed files this script reads FROM:

Reads (frozen, read-only, owned by docs/EnricoVis/ — never write here):
  docs/EnricoVis/data/grants_umap.json   2,676 grant points: id/agency/amount/
                                          year/titleOnly/modelTitleOnly/
                                          dom(topic)/isNoise. titleOnly = data
                                          availability; modelTitleOnly = did
                                          the fit see text (differs only for
                                          LOW_TRUST_ABSTRACT_SOURCES grants —
                                          absent entirely on an older,
                                          pre-backfill grants_umap.json).
  docs/EnricoVis/data/topics.json        26 entries: 25 topics + noise, each
                                          with a "parent" ("P0".."P7" or null)

Reads (locally built, optional — enriches provenance if present):
  data/processed/grants.parquet          grant_id -> abstract_source
                                          ("internal"/"orphan_recovered"/"")
  data/processed/faculty_grants.parquet  grant_id -> PI's faculty_id + neu_status
  data/processed/faculty_id_lookup.parquet  faculty_id -> college/academic_unit
  data/processed/faculty.parquet         faculty_id -> hire_date (known/unknown);
                                          also the full HR roster (2,247 rows)
                                          used directly for the PI-grain
                                          missingness fields and facets_pi.json
  data/processed/grant_orphan_recovery.parquet  full M2 audit (403 usable
                                          orphans -> update/extra/duplicate/
                                          unattributed), see src/reconcile_orphans.py
  data/processed/grant_orphaned_abstracts.parquet  the raw 5,095-row orphan pool
  data/processed/extra_neu_abstracts.parquet  the 65 'extra' pseudo-docs
  data/processed/faculty_missing_metadata.parquet  the 13 grant-active
                                          faculty absent from the HR roster —
                                          included in facets_pi.json as their
                                          own bin, never dropped
  data/processed/personid_to_faculty.parquet  the abstract-upload personid ->
                                          faculty_id bridge, used only for the
                                          abstract_records missingness grain
  data/processed/new_abstract_recovery.parquet  grant_ids the newer AcAn
                                          Grants export can supply abstract
                                          text for (see scripts/_check_new_abstracts.py) —
                                          surfaced as a "recoverable" segment
                                          on the grants-grain abstract field,
                                          not adopted into the pipeline itself

Writes (docs/TopicVizPrototypes/data/, committed — the three prototype
pages fetch() these at load from an ES module; there is no inlined second
copy. CI publishes this directory alongside the HTML, see
.github/workflows/deploy-notebooks.yml and docs/TOPIC_WORK_EXECUTION_REPORT.md):
  viz_meta.json     shared dimensions (agencies, parents, topics, year axis,
                     totals) + the single canonical caveats[] array
  topic_time.json   topic & parent share/dollars per year, dense 2005-2025
                     + a pre-2005 "prelude" summary (too sparse to stack)
  coverage.json     abstract coverage by agency x year, the NIH cliff, and
                     the Unassigned/artifact breakdown
  facets.json       per-grant facet table (columnar/dictionary-encoded) for
                     the "every grant, arranged" unit visualization, plus
                     parallel "titles"/"abstracts" arrays (full text, shown
                     for whichever grant is currently selected)
  facets_pi.json    per-PI facet table (same columnar shape as facets.json)
                     for the "every PI" unit visualization, over all 2,247
                     roster faculty (not just the 570 with grants)
  missingness.json  per-field known/missing/not-applicable counts, split
                     into three grains — grants (2,676), PIs (2,247), and
                     raw abstract-upload records (8,075) — for the
                     "What's missing" panel
  funnel.json       the abstract-sourcing pipeline (raw records -> matched
                     rows -> unique grants -> grants with text) plus the M2
                     orphan-recovery branch (update/extra/duplicate/unattributed)

Run:
    .venv/bin/python -m src.build_viz_aggregates [--check-only]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from src.clean_text import LOW_TRUST_ABSTRACT_SOURCES
except ImportError:  # run from within src/
    from clean_text import LOW_TRUST_ABSTRACT_SOURCES

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
ENRICOVIS_DATA = REPO_ROOT / "docs" / "EnricoVis" / "data"     # read-only upstream (PI's work)
OUT_DIR = REPO_ROOT / "docs" / "TopicVizPrototypes" / "data"   # writable (this script's own output)

# Guard against ever writing into the PI's frozen EnricoVis output — this
# script's OUT_DIR is a different directory already, but keep the stem
# check too as a belt-and-suspenders safety net.
FROZEN_STEMS = {"grants_umap", "topics", "grants_hier"}

# 7-parent-theme names/colors — the curated keyword-classifier taxonomy
# (outputs/topic_keywords.json, promoted 2026-08-29; see
# docs/TOPIC_MODEL_REFIT_CHECKLIST.md's re-curate track). Names/order copied
# verbatim from that file's parents{} (P0..P6, dense zero-based) and must stay
# byte-identical to docs/TopicVizPrototypes/shared/enrico.js's own PARENT_NAMES
# copy. Do not hand-edit one without the other. This REPLACES the prior
# 8-parent BERTopic-era taxonomy ("Life Sciences & Biomedicine", "Physical
# Sciences & Engineering", ... "Education & Learning") — those names never
# matched the curated keyword lists (see the redo plan) and are retired, not
# kept as unused history.
PARENT_NAMES = [
    "Biomedical Sciences", "Public & Behavioral Health", "Environmental Science & Ecology",
    "Social Science, Public Policy & Workforce Development",
    "Materials Science & Structural/Civil Engineering", "Mathematics & Fundamental Physics",
    "Computing, Networking & Robotic Systems",
]
# 7 real names above + 5 SPARE colors below (indices 7-11) — pre-allocated
# headroom so a re-curation that adds an 8th+ parent theme (always a human
# curation step — the classifier's own discovery fit never produces parent
# groups directly, see docs/TOPIC_MODEL_REFIT_CHECKLIST.md) gets a real,
# distinct color the moment it's named in PARENT_NAMES, instead of silently
# reusing color 0 (`i % len(PARENT_COLORS)` wraps once `i` reaches 7). Kept at
# 12 total entries (one more spare than before, since the real count dropped
# 8->7) rather than shrinking the array — every color-consuming line below
# already keys off len(PARENT_COLORS)/len(PARENT_NAMES), not a literal count,
# so extra headroom changes nothing about today's 7-parent rendering.
PARENT_COLORS = [
    "#4E79A7", "#F28E2B", "#59A14F", "#B07AA1", "#76B7B2", "#EDC948", "#9C755F", "#D37295",
    "#6B4C9A", "#1B9E77", "#B6992D", "#7570B3",
]

# The BERTopic-era artifact-topic concept is RETIRED — the curated keyword
# taxonomy has no single "flagged low-coherence cluster" the way HDBSCAN's
# topic 14 was; every leaf here is a deliberate human curation decision. The
# 28 ONR placeholder-title "Grant" records that used to define topic 14 are
# now individually tagged `unassignedReason == "placeholder_title_only"` on
# each point (see src.classify_by_keywords) rather than living in one
# hardcoded topic id. Kept as a named sentinel (rather than deleted) so every
# use site below stays visibly None-safe instead of silently vanishing —
# `== ARTIFACT_TOPIC_ID` / `in (-1, ARTIFACT_TOPIC_ID)` comparisons against
# `None` are safe by construction (a point's `dom`/`bertopicDom` is always an
# int or None, never equal to the sentinel None via `==`).
ARTIFACT_TOPIC_ID = None

# Must match len(TOPIC_COLORS) in docs/TopicVizPrototypes/shared/enrico.js —
# only used for validate()'s palette-headroom warning below, never to index
# anything here.
TOPIC_COLOR_CAPACITY = 32

DENSE_FROM, DENSE_TO = 2005, 2025

CAVEATS = [
    {
        "id": "neu_status",
        "severity": "high",
        "text": (
            "The $2.18B headline is not money Northeastern raised — grants are "
            "attributed to a faculty member even if the award predates their NEU hire."
        ),
    },
    {
        "id": "nih_cliff",
        "severity": "low",
        "text": (
            "UPDATE (2026-08-20): this used to read 'NIH abstract coverage collapses "
            "from 64% (2019) to 0% from 2021 onward' — a data-collection artifact, not "
            "a funding decline. A live NIH RePORTER backfill (src/backfill_nih_reporter.py) "
            "has since closed it: 2020-2025 NIH/NIH-SubAward coverage now runs 94-100%. "
            "Kept here, downgraded, as a record that this was a real prior limitation."
        ),
    },
    {
        "id": "unassigned",
        "severity": "low",
        "text": (
            "UPDATE (2026-08-29): 66 grants (2.5% of grants, 1.9% of dollars) carry no "
            "confident topic under the curated keyword classifier — down from 697 grants "
            "/ 26.7% of dollars under the prior BERTopic/HDBSCAN fit. 38 have real text "
            "but zero curated-keyword evidence (a real curation-coverage gap, worth a "
            "future curation pass, not a modeling failure); 28 are the ONR placeholder-"
            "title records described in 'placeholder_titles' below. Shown as a grey "
            "'Unassigned' band, never dropped."
        ),
    },
    {
        "id": "placeholder_titles",
        "severity": "low",
        "text": (
            "28 grants carry the placeholder title “Grant” (all Office of Naval "
            "Research — ONR has no public abstract API, so no backfill could ever "
            "recover real text for them). Unclassifiable by any text-based method, "
            "keyword or embedding; they have no parent theme. Formerly BERTopic's "
            "flagged 'topic 14' artifact bucket — now tracked per-grant "
            "(unassignedReason == 'placeholder_title_only') rather than as one hardcoded "
            "topic id."
        ),
    },
    {
        "id": "keyword_classifier",
        "severity": "low",
        "text": (
            "As of 2026-08-29, topic labels come from a deterministic, human-curated "
            "keyword classifier (BM25F scoring over 31 leaves / 7 parent themes), not "
            "the prior BERTopic/HDBSCAN fit — chosen for inspectability (every "
            "assignment records which curated terms actually fired) and full offline "
            "reproducibility. BERTopic's own assignment is kept as a comparison field "
            "(bertopicDom/bertopicNoise), not deleted. See "
            "docs/TOPIC_MODEL_REFIT_CHECKLIST.md."
        ),
    },
    {
        "id": "low_confidence",
        "severity": "low",
        "text": (
            "501 grants (18.7%) land in the classifier's 'low' confidence tier — a "
            "curated term matched, but weakly (a thin margin over the runner-up topic, "
            "or few matched terms). The confidence thresholds themselves are a "
            "provisional placeholder pending calibration against a human-labeled gold "
            "set (not yet collected) — treat 'low' as 'worth a second look', not as "
            "a precise probability."
        ),
    },
    {
        "id": "sparse_prelude",
        "severity": "low",
        "text": (
            "1995–2004 (118 grants total) is too sparse to stack reliably and is "
            "shown separately from the 2005–2025 series."
        ),
    },
    {
        "id": "partial_recent",
        "severity": "low",
        "text": "2025 is a partial year; 2026 has essentially no data yet.",
    },
    {
        "id": "agency_skew",
        "severity": "low",
        "text": "~88% of dollars are NSF/NIH. Internal, foundation, and industry funding are largely invisible.",
    },
    {
        "id": "roster_snapshot",
        "severity": "high",
        "text": (
            "The faculty roster is a 2025 snapshot. Departed, retired, or renamed "
            "faculty have no college — their grants are shown honestly as "
            "'PI not on 2025 roster', not silently dropped."
        ),
    },
    {
        "id": "college_unmapped",
        "severity": "low",
        "text": (
            "A handful of raw college strings (e.g. 'Math?', 'Network science "
            "institute') don't match a known college and are shown as their own bin "
            "rather than guessed at."
        ),
    },
    {
        "id": "external_collaborators",
        "severity": "high",
        "text": (
            "Every record is stamped 'Northeastern' regardless of who else worked on "
            "it — external co-investigators at other institutions are invisible here. "
            "The collaboration network this data can support is NEU-internal only."
        ),
    },
]

# Two per-grant "we can't attribute this" bins, used across facets.json and
# missingness.json — distinct from each other on purpose:
#   NO_PI_LABEL         — the grant has no PI row in faculty_grants at all
#   PI_OFF_ROSTER_LABEL — a PI row exists, but that faculty_id has no college
#                          in faculty_id_lookup (roster snapshot gap)
NO_PI_LABEL = "No PI matched"
PI_OFF_ROSTER_LABEL = "PI not on 2025 roster"
# Third "gap" label, distinct from the two above — used on the PI-grain
# side (facets_pi.json / missingness_pis) for a roster field that's simply
# blank on this person's HR record, which is a different fact from "this
# grant has no PI" or "this PI is off the roster".
PI_NOT_RECORDED = "Not recorded"

# Known duplicate/typo college strings observed in faculty_id_lookup.college.
# Everything NOT in this map passes through unchanged — including genuine
# oddities ("Math?", "Network science institute", "Northeastern University")
# which surface as their own honest bin rather than being guessed into one
# of the real colleges.
COLLEGE_NORMALIZE = {
    "Engineering": "College of Engineering",
    "College of science": "College of Science",
    "Khoury": "Khoury College of Computer Sciences",
}

DOLLAR_BANDS = [
    (0, 100_000, "< $100K"),
    (100_000, 500_000, "$100K–$500K"),
    (500_000, 1_000_000, "$500K–$1M"),
    (1_000_000, 5_000_000, "$1M–$5M"),
    (5_000_000, float("inf"), "≥ $5M"),
]

# Ordinal, low-to-high — the classifier's own conf_tier vocabulary
# (src.classify_by_keywords), a facet the old BERTopic one-hot assignment
# couldn't support at all (it had no per-grant confidence signal).
CONF_LEVELS = ["none", "low", "medium", "high"]

# The one cliff this round documents — verified: NIH+NIH-SUB coverage falls
# from 64% (2019) to 3% (2020) to 0% (2021-2025). A module-level constant
# (not inline in build_coverage) so both viz_meta.json AND coverage.json can
# carry it — topic_flow.html only loads VIZ_META, what_we_can_see.html loads
# both, and previously both HTML files hardcoded the 2019.5 marker position
# themselves instead of reading it from here.
CLIFFS = [{
    "agency": "NIH",
    "last_good_year": 2019,
    "first_zero_year": 2021,
    "text": (
        "NIH abstract coverage falls from 64% (2019) to 3% (2020) to 0% "
        "(2021-2025). Data-collection artifact; only NIH RePORTER backfill "
        "can repair it."
    ),
}]


def _dollar_band(amount: float) -> int:
    for i, (lo, hi, _label) in enumerate(DOLLAR_BANDS):
        if lo <= amount < hi:
            return i
    return len(DOLLAR_BANDS) - 1


def _guard_output_path(path: Path) -> None:
    if path.stem in FROZEN_STEMS:
        raise RuntimeError(
            f"refusing to write {path} — {path.stem} is a frozen input "
            "(the real BERTopic/SPECTER2 output); see module docstring."
        )


def _parent_index(parent_key: str | None) -> int:
    """'P0'..'P7' -> 0..7; None (incl. the artifact topic) -> -1 (Unassigned)."""
    if parent_key is None:
        return -1
    m = re.match(r"P(\d+)$", parent_key)
    return int(m.group(1)) if m else -1


def load_frozen() -> tuple[list[dict], list[dict]]:
    grants_umap = json.loads((ENRICOVIS_DATA / "grants_umap.json").read_text(encoding="utf-8"))
    topics = json.loads((ENRICOVIS_DATA / "topics.json").read_text(encoding="utf-8"))
    return grants_umap["points"], topics


def load_abstract_source(points: list[dict]) -> tuple[dict[str, str], str]:
    """Best-effort grant_id -> abstract_source ('internal'/'nih_reporter'/
    'nih_reporter_parent'/'nsf_api'/'orphan_recovered'/'none'). Falls back to
    deriving a two-value approximation from `titleOnly` (data availability —
    exactly correct for the has-text/no-text question) if grants.parquet
    hasn't been built locally: 'none' or a generic 'internal' — the fallback
    can tell IF a grant has text but not WHICH of the newer sources provided
    it, since `titleOnly` alone doesn't carry that distinction.
    """
    parquet_path = PROC / "grants.parquet"
    if parquet_path.exists():
        import pandas as pd  # local import: keep this script runnable with json alone

        g = pd.read_parquet(parquet_path, columns=["grant_id", "abstract_source"])
        g["grant_id"] = g["grant_id"].astype(str).str.strip()
        src = dict(zip(g["grant_id"], g["abstract_source"]))
        by_id = {}
        for p in points:
            v = src.get(str(p["id"]).strip(), "")
            by_id[p["id"]] = v if v else "none"
        return by_id, "parquet"
    # Degraded fallback — never silently fabricate provenance detail we don't have.
    return {p["id"]: ("none" if p["titleOnly"] else "internal") for p in points}, "derived"


def load_abstract_text(points: list[dict]) -> tuple[dict[str, str], str]:
    """Best-effort grant_id -> full abstract text, for the facet grid's
    "read the abstract for the selected grant" feature. A separate loader
    rather than folded into load_abstract_source above — that function has
    two other call sites (build_coverage, missingness) that only need the
    abstract_source column, not the (much larger) text itself.

    Degrades to an empty dict (not a fabricated summary) if grants.parquet
    hasn't been built locally — the caller then shows "no abstract on
    record" for every grant, which is honest (if more pessimistic than
    reality) rather than silently wrong.
    """
    parquet_path = PROC / "grants.parquet"
    if not parquet_path.exists():
        return {}, "derived"
    import pandas as pd  # local import: keep this script runnable with json alone

    g = pd.read_parquet(parquet_path, columns=["grant_id", "abstract"])
    g["grant_id"] = g["grant_id"].astype(str).str.strip()
    text = dict(zip(g["grant_id"], g["abstract"].fillna("")))
    return {p["id"]: (text.get(str(p["id"]).strip(), "") or "").strip() for p in points}, "parquet"


def load_pi_attrs(points: list[dict]) -> tuple[dict[str, dict], str]:
    """grant_id -> {college, academic_unit, hire_date_known, neu_status, on_roster}
    for the grant's PI row (is_pi==True) in faculty_grants.parquet, joined to
    faculty_id_lookup.parquet (college/academic_unit) and faculty.parquet
    (hire_date). A grant absent from this dict has NO PI row at all — the
    caller is responsible for mapping that to NO_PI_LABEL, not this function
    (it only reports what it found).

    Degrades honestly to an empty dict + "derived" if the parquets aren't
    built locally — every grant then reads as NO_PI_LABEL downstream, same
    spirit as load_abstract_source's fallback.
    """
    fg_path = PROC / "faculty_grants.parquet"
    fl_path = PROC / "faculty_id_lookup.parquet"
    fac_path = PROC / "faculty.parquet"
    if not (fg_path.exists() and fl_path.exists() and fac_path.exists()):
        return {}, "derived"

    import pandas as pd  # local import: keep this script runnable with json alone

    fg = pd.read_parquet(fg_path, columns=["faculty_id", "grant_id", "is_pi", "neu_status"])
    fl = pd.read_parquet(fl_path, columns=["faculty_id", "college", "academic_unit"])
    fac = pd.read_parquet(fac_path, columns=["faculty_id", "hire_date"])

    college_by_faculty = dict(zip(fl["faculty_id"], fl["college"]))
    unit_by_faculty = dict(zip(fl["faculty_id"], fl["academic_unit"]))
    hire_known_by_faculty = dict(zip(fac["faculty_id"], fac["hire_date"].notna()))

    pi_rows = fg[fg["is_pi"]].drop_duplicates(subset="grant_id", keep="first")

    out: dict[str, dict] = {}
    for row in pi_rows.itertuples(index=False):
        gid = str(row.grant_id).strip()
        raw_college = college_by_faculty.get(row.faculty_id)
        on_roster = raw_college is not None and str(raw_college).strip() != ""
        raw_unit = unit_by_faculty.get(row.faculty_id)
        college = (
            COLLEGE_NORMALIZE.get(str(raw_college).strip(), str(raw_college).strip())
            if on_roster else PI_OFF_ROSTER_LABEL
        )
        academic_unit = str(raw_unit).strip() if raw_unit is not None and str(raw_unit).strip() else PI_OFF_ROSTER_LABEL
        out[gid] = {
            "college": college,
            "academic_unit": academic_unit,
            "hire_date_known": bool(hire_known_by_faculty.get(row.faculty_id, False)),
            "neu_status": row.neu_status or "unknown",
            "on_roster": on_roster,
        }
    return out, "parquet"


def build_facets(points: list[dict], topics: list[dict]) -> dict:
    """Per-grant facet table for the "every grant, arranged" unit visualization.
    Columnar/dictionary-encoded rather than an array of 2,676 objects — keeps
    the fetched JSON payload small and every column trivial to bin in d3.
    Every categorical column has a bin for missing values; no grant is ever
    dropped from a facet, by construction (see the invariant tests in
    validate()).
    """
    from src.viz_constants import ORDER

    abs_src, abs_source = load_abstract_source(points)
    abs_text, abs_text_source = load_abstract_text(points)
    pi_attrs, pi_source = load_pi_attrs(points)
    parent_of_topic = {t["id"]: _parent_index(t.get("parent")) for t in topics}

    ag_levels = list(ORDER)
    ag_index = {k: i for i, k in enumerate(ag_levels)}
    st_levels = ["earned_at_neu", "prior_institution", "unknown", NO_PI_LABEL]
    st_index = {k: i for i, k in enumerate(st_levels)}
    # Every real src.build_dataset.py abstract_source value, so a backfilled
    # grant (nih_reporter/nsf_api/nih_reporter_parent) doesn't collapse into
    # "none" (the opposite of the truth — it has real, sourced text). Not
    # currently rendered by any facet UI (see what_we_can_see/facets.js:70-72)
    # but emitted in the data, so this enum should still be complete.
    asrc_levels = ["internal", "nih_reporter", "nih_reporter_parent", "nsf_api",
                   "orphan_recovered", "none"]
    asrc_index = {k: i for i, k in enumerate(asrc_levels)}
    amt_levels = [label for (_lo, _hi, label) in DOLLAR_BANDS]

    # College levels are collected dynamically (the roster isn't a fixed enum),
    # but the two miss bins always come first so they read as a deliberate
    # "gap" column rather than being buried among real colleges.
    col_levels: list[str] = [NO_PI_LABEL, PI_OFF_ROSTER_LABEL]
    col_index: dict[str, int] = {NO_PI_LABEL: 0, PI_OFF_ROSTER_LABEL: 1}

    def college_idx(label: str) -> int:
        if label not in col_index:
            col_index[label] = len(col_levels)
            col_levels.append(label)
        return col_index[label]

    ids: list[str] = []
    titles: list[str] = []
    abstracts: list[str] = []
    # "amt" is the 5-level band index used for arranging/splitting (a small,
    # legible enum); "amt_raw" is the actual dollar float, added so the facet
    # grid can offer a real "sort by size ($)" — bands alone can't distinguish
    # a $102K grant from a $480K one within "$100K-$500K". Kept as a separate
    # column rather than replacing "amt" so existing band-based arrangements
    # are untouched.
    cols: dict[str, list[float]] = {k: [] for k in
                                     ("ag", "yr", "col", "st", "ab", "asrc", "tp", "tid", "pi", "amt", "amt_raw", "conf")}
    conf_index = {name: i for i, name in enumerate(CONF_LEVELS)}

    for p in points:
        gid = str(p["id"]).strip()
        ids.append(gid)
        titles.append(p["title"] or "")
        abstracts.append(abs_text.get(gid, ""))
        # .get(..., "Other") rather than a bare [] — every point SHOULD already
        # carry one of the 9 ORDER buckets (build_viz_data.py's agency_bucket()
        # already defaults to "Other"), but a defensive fallback here means an
        # agency string outside that set bins as "Other" instead of crashing
        # the whole build, matching how every other unknown value in this file
        # gets an explicit bin rather than raising.
        cols["ag"].append(ag_index.get(p["agency"], ag_index["Other"]))
        cols["yr"].append(p["year"] if p["year"] is not None else -1)
        cols["tp"].append(parent_of_topic.get(p["dom"], -1))
        cols["tid"].append(p["dom"])
        cols["ab"].append(0 if p["titleOnly"] else 1)
        cols["asrc"].append(asrc_index.get(abs_src.get(gid, "none"), asrc_index["none"]))
        cols["amt"].append(_dollar_band(p["amount"]))
        cols["amt_raw"].append(p["amount"])
        cols["conf"].append(conf_index.get(p.get("confTier", "none"), 0))

        attrs = pi_attrs.get(gid)
        if attrs is None:
            cols["col"].append(college_idx(NO_PI_LABEL))
            cols["st"].append(st_index[NO_PI_LABEL])
            cols["pi"].append(0)
        else:
            cols["col"].append(college_idx(attrs["college"]))
            cols["st"].append(st_index.get(attrs["neu_status"], st_index["unknown"]))
            cols["pi"].append(1 if attrs["on_roster"] else 0)

    return {
        "n": len(points),
        "ids": ids,
        "titles": titles,
        "abstracts": abstracts,
        "levels": {"ag": ag_levels, "col": col_levels, "st": st_levels, "asrc": asrc_levels,
                   "amt": amt_levels, "conf": CONF_LEVELS},
        "cols": cols,
        "provenance": {"abstract_source": abs_source, "pi_attrs": pi_source, "abstract_text": abs_text_source},
    }


NGRANTS_BANDS = [(0, 1, "0"), (1, 2, "1"), (2, 5, "2–4"), (5, 10, "5–9"), (10, float("inf"), "10+")]


def _ngrants_band(n: int) -> int:
    for i, (lo, hi, _label) in enumerate(NGRANTS_BANDS):
        if lo <= n < hi:
            return i
    return len(NGRANTS_BANDS) - 1


def build_facets_pi(fac, points: list[dict], topics: list[dict]) -> dict:
    """Per-PI facet table (same columnar shape as build_facets above) for the
    "every PI" unit visualization — over all 2,247 roster faculty, not just
    the 570 who appear on a grant. That's the deliberate point: most of the
    faculty body has no grant in this corpus at all, and "no grants" is a
    first-class bin on every facet here rather than those rows being dropped.

    Degrades to an empty table (n=0) if faculty.parquet isn't built locally
    — mirrors the same honest-degrade pattern as build_facets/load_pi_attrs.

    Funding is credited PI-only (dollars from grants where is_pi is True),
    per CLAUDE.md's funding-credit-model caveat — the "amt"/"amt_raw" facets
    here are explicitly "dollars as PI", not full- or fractional-credit.
    """
    if fac is None:
        return {"n": 0, "ids": [], "names": [], "levels": {}, "cols": {}, "grant_titles": [], "provenance": "derived"}

    import pandas as pd

    fg_path = PROC / "faculty_grants.parquet"
    if not fg_path.exists():
        return {"n": 0, "ids": [], "names": [], "levels": {}, "cols": {}, "grant_titles": [], "provenance": "derived"}
    fg = pd.read_parquet(fg_path, columns=["faculty_id", "grant_id", "is_pi"])
    fg["faculty_id"] = fg["faculty_id"].astype(str)
    fg["grant_id"] = fg["grant_id"].astype(str).str.strip()

    parent_of_topic = {t["id"]: _parent_index(t.get("parent")) for t in topics}
    point_by_id = {str(p["id"]).strip(): p for p in points}

    ids: list[str] = []
    names: list[str] = []
    cols: dict[str, list] = {k: [] for k in
                              ("col", "dept", "rank", "track", "tenure", "hire_yr",
                               "status", "hasgrants", "ngrants", "amt", "amt_raw", "tp")}
    grant_titles: list[list[str]] = []

    col_levels: list[str] = []
    col_index: dict[str, int] = {}

    def college_idx(raw: str) -> int:
        label = COLLEGE_NORMALIZE.get(raw, raw) if raw else PI_NOT_RECORDED
        if label not in col_index:
            col_index[label] = len(col_levels)
            col_levels.append(label)
        return col_index[label]

    dept_levels: list[str] = [PI_NOT_RECORDED]
    dept_index: dict[str, int] = {PI_NOT_RECORDED: 0}

    def dept_idx(raw: str) -> int:
        label = raw if raw else PI_NOT_RECORDED
        if label not in dept_index:
            dept_index[label] = len(dept_levels)
            dept_levels.append(label)
        return dept_index[label]

    rank_levels: list[str] = [PI_NOT_RECORDED]
    rank_index: dict[str, int] = {PI_NOT_RECORDED: 0}

    def rank_idx(raw: str) -> int:
        label = raw if raw else PI_NOT_RECORDED
        if label not in rank_index:
            rank_index[label] = len(rank_levels)
            rank_levels.append(label)
        return rank_index[label]

    track_levels: list[str] = [PI_NOT_RECORDED]
    track_index: dict[str, int] = {PI_NOT_RECORDED: 0}

    def track_idx(raw: str) -> int:
        label = raw if raw else PI_NOT_RECORDED
        if label not in track_index:
            track_index[label] = len(track_levels)
            track_levels.append(label)
        return track_index[label]

    tenure_levels = ["Tenured", "Tenure Track", "Tenure On Entry", PI_NOT_RECORDED]
    tenure_index = {k: i for i, k in enumerate(tenure_levels)}
    status_levels = ["Active", "Departed"]
    hasgrants_levels = ["No grants in this corpus", "Has grants"]
    amt_levels = ["No grants as PI"] + [label for (_lo, _hi, label) in DOLLAR_BANDS]
    ngrants_levels = [label for (_lo, _hi, label) in NGRANTS_BANDS]  # index-parallel to _ngrants_band's return
    # Index 0 is the "no PI grants" bin (covers both "no grants at all" and
    # "grants but never as PI" — both mean zero PI-credited dollars/theme);
    # then -1 (Unassigned) followed by the 8 named parents, matching
    # build_viz_meta's `parents` order. A sentinel distinct from any real
    # parent index (-1..7) is used while building cols["tp"] below and
    # remapped to 0 afterward — parent index 0 is a real value ("Life
    # Sciences & Biomedicine") and must not collide with the "no PI grants"
    # bin the way a literal 0 sentinel would.
    tp_levels = ["No grants as PI", "Unassigned"] + PARENT_NAMES
    NO_PI_GRANTS_TP = -99
    # range(len(PARENT_NAMES)), not a bare range(8): a refit with a different
    # parent-theme count must not KeyError here — see validate()'s parent-count
    # drift check, which is what actually tells you PARENT_NAMES itself needs
    # updating for a new count.
    tp_index_map = {-1: 1, **{i: 2 + i for i in range(len(PARENT_NAMES))}}

    # Group faculty_grants by faculty_id once, up front, rather than
    # filtering the whole table per roster row (2,247 rows x 3,144-row scan).
    by_faculty: dict[str, "pd.DataFrame"] = {fid: g for fid, g in fg.groupby("faculty_id")}

    for row in fac.itertuples(index=False):
        fid = str(row.faculty_id)
        ids.append(fid)
        names.append(str(row.faculty_name).strip() if pd.notna(row.faculty_name) else "")

        raw_college = str(row.superior_academic_unit) if pd.notna(row.superior_academic_unit) else ""
        cols["col"].append(college_idx(raw_college))
        raw_dept = str(row.academic_unit) if pd.notna(row.academic_unit) else ""
        cols["dept"].append(dept_idx(raw_dept))
        raw_rank = str(row.academic_rank) if pd.notna(row.academic_rank) else ""
        cols["rank"].append(rank_idx(raw_rank))
        raw_track = str(row.academic_track_type) if pd.notna(row.academic_track_type) else ""
        cols["track"].append(track_idx(raw_track))
        raw_tenure = str(row.tenure_status) if pd.notna(row.tenure_status) else ""
        cols["tenure"].append(tenure_index.get(raw_tenure, tenure_index[PI_NOT_RECORDED]))
        cols["hire_yr"].append(int(row.hire_date.year) if pd.notna(row.hire_date) else -1)
        cols["status"].append(0 if pd.isna(row.termination_date) else 1)

        their_grants = by_faculty.get(fid)
        if their_grants is None or their_grants.empty:
            cols["hasgrants"].append(0)
            cols["ngrants"].append(_ngrants_band(0))
            cols["amt"].append(0)
            cols["amt_raw"].append(0.0)
            cols["tp"].append(NO_PI_GRANTS_TP)
            grant_titles.append([])
            continue

        n_grants = their_grants["grant_id"].nunique()
        pi_grant_ids = their_grants.loc[their_grants["is_pi"], "grant_id"].tolist()
        pi_points = [point_by_id[g] for g in pi_grant_ids if g in point_by_id]
        pi_dollars = sum(p["amount"] for p in pi_points)

        cols["hasgrants"].append(1)
        cols["ngrants"].append(_ngrants_band(n_grants))
        cols["amt_raw"].append(pi_dollars)
        if not pi_points:
            cols["amt"].append(0)
            cols["tp"].append(NO_PI_GRANTS_TP)
        else:
            cols["amt"].append(1 + _dollar_band(pi_dollars))
            parent_counts: dict[int, int] = {}
            for p in pi_points:
                pid = parent_of_topic.get(p["dom"], -1)
                parent_counts[pid] = parent_counts.get(pid, 0) + 1
            dominant = max(parent_counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]
            cols["tp"].append(dominant)
        grant_titles.append([p["title"] or "" for p in pi_points][:8])

    # .get(v, 1) rather than [v]: falls back to the "Unassigned" bin (index 1)
    # for a parent id PARENT_NAMES doesn't have a name for yet — e.g. right
    # after a refit adds a 9th parent theme but before a human has updated
    # PARENT_NAMES/PARENT_COLORS (validate()'s parent-count drift check is
    # what actually flags that gap; this is just the "don't crash in the
    # meantime" half of the fix).
    cols["tp"] = [0 if v == NO_PI_GRANTS_TP else tp_index_map.get(v, 1) for v in cols["tp"]]

    return {
        "n": len(ids),
        "ids": ids,
        "names": names,
        "levels": {
            "col": col_levels, "dept": dept_levels, "rank": rank_levels, "track": track_levels,
            "tenure": tenure_levels, "status": status_levels, "hasgrants": hasgrants_levels,
            "ngrants": ngrants_levels, "amt": amt_levels, "tp": tp_levels,
        },
        "cols": cols,
        "grant_titles": grant_titles,
        "provenance": "parquet",
    }


def load_recoverable() -> set[str]:
    """grant_ids the newer AcAn Grants export can supply abstract text for
    (see scripts/_check_new_abstracts.py) — a diagnostic, not a pipeline
    input, so this degrades to an empty set (no "recoverable" segment shown)
    rather than erroring if that script hasn't been run locally."""
    path = PROC / "new_abstract_recovery.parquet"
    if not path.exists():
        return set()
    import pandas as pd

    df = pd.read_parquet(path, columns=["grant_id"])
    return set(df["grant_id"].astype(str).str.strip())


def load_faculty_roster() -> tuple["pd.DataFrame | None", "pd.DataFrame | None", str]:
    """The full 2,247-row HR roster (faculty.parquet) plus aauid coverage
    (faculty_id_lookup.parquet), for the PI-grain missingness fields and
    facets_pi.json. Degrades to (None, None, "derived") if not built locally
    — the caller then omits the PI grain / PI facet grid entirely rather than
    fabricating roster data.
    """
    fac_path = PROC / "faculty.parquet"
    lookup_path = PROC / "faculty_id_lookup.parquet"
    if not fac_path.exists():
        return None, None, "derived"
    import pandas as pd

    fac = pd.read_parquet(fac_path)
    lookup = pd.read_parquet(lookup_path) if lookup_path.exists() else None
    return fac, lookup, "parquet"


def build_missingness_grants(points: list[dict], pi_attrs: dict[str, dict], recoverable: set[str]) -> dict:
    """Per-field known/missing/(recoverable) counts across all 2,676 grants."""
    n = len(points)
    fields = []

    def row(field_id: str, label: str, known: int, where: str, extra: dict | None = None) -> None:
        f = {"id": field_id, "label": label, "known": known, "missing": n - known, "na": 0, "where": where}
        if extra:
            f.update(extra)
        fields.append(f)

    row("agency", "Agency", sum(1 for _ in points), "Always recorded in this corpus.")
    row("dollars", "Dollar amount", sum(1 for p in points if p["amount"] is not None),
        "Always recorded in this corpus.")
    row("dates", "Start year", sum(1 for p in points if p["year"] is not None),
        "Always recorded in this corpus.")

    abs_known = sum(1 for p in points if not p["titleOnly"])
    abs_recoverable = sum(
        1 for p in points if p["titleOnly"] and str(p["id"]).strip() in recoverable
    )
    row("abstract", "Abstract text", abs_known,
        "No abstract record matched this grant in the upload system.",
        extra={"recoverable": abs_recoverable} if recoverable else None)

    row("topic", "Topic label", sum(1 for p in points if p["dom"] not in (-1, ARTIFACT_TOPIC_ID)),
        "No curated keyword term matched this grant's text (or it has no usable text at all).")

    def has(gid: str, pred) -> bool:
        attrs = pi_attrs.get(gid)
        return attrs is not None and pred(attrs)

    row("pi_link", "PI matched to a grant record",
        sum(1 for p in points if pi_attrs.get(str(p["id"]).strip()) is not None),
        "No principal investigator record links to this grant at all.")
    row("college", "PI's college",
        sum(1 for p in points if has(str(p["id"]).strip(), lambda a: a["on_roster"])),
        "The PI isn't on the current faculty roster snapshot (often: departed or renamed).")
    # Real, independent check — NOT the same predicate as "college" above.
    # academic_unit is its own column (PI_OFF_ROSTER_LABEL when blank), so a
    # PI can be on-roster with a known college but a blank department, or
    # vice versa; the two used to share one predicate here, which silently
    # made this row a duplicate of "college" above.
    row("department", "PI's academic unit",
        sum(1 for p in points if has(str(p["id"]).strip(), lambda a: a["academic_unit"] != PI_OFF_ROSTER_LABEL)),
        "The PI's department wasn't recorded on the roster snapshot, even where their college was.")
    row("hire_date", "PI's hire date",
        sum(1 for p in points if has(str(p["id"]).strip(), lambda a: a["hire_date_known"])),
        "The PI's hire date is missing from the roster (mostly the small manually-added supplement).")
    row("neu_status", "Pre-hire vs. at-NEU attribution",
        sum(1 for p in points
            if has(str(p["id"]).strip(), lambda a: a["neu_status"] in ("earned_at_neu", "prior_institution"))),
        "Depends on knowing both the grant's start date and the PI's hire date.")

    fields.sort(key=lambda f: f["missing"], reverse=True)
    return {"n": n, "fields": fields, "provenance": "parquet" if pi_attrs else "derived"}


def build_missingness_pis(fac, lookup) -> dict:
    """Per-field known/missing/not-applicable counts across all 2,247 roster
    faculty (fac = faculty.parquet, lookup = faculty_id_lookup.parquet, both
    already-loaded DataFrames). Distinct denominator from the grants grain —
    most of the roster (1,690 of 2,247) never appears on a grant at all, and
    that's exactly the gap this grain is for.
    """
    if fac is None:
        return {"n": 0, "fields": [], "provenance": "derived"}
    n = len(fac)

    def col_known(series) -> int:
        return int((series.astype(str).str.strip() != "").sum())

    fields = []

    def row(field_id: str, label: str, known: int, na: int, where: str) -> None:
        fields.append({
            "id": field_id, "label": label, "known": known,
            "missing": n - known - na, "na": na, "where": where,
        })

    row("name", "Name on record", col_known(fac["faculty_name"].fillna("")), 0,
        "Only populated for faculty who appear on at least one grant — the roster export itself doesn't carry names.")
    row("college", "College", col_known(fac["superior_academic_unit"].astype("string").fillna("")), 0,
        "Missing from the roster export for this person.")
    row("department", "Department", col_known(fac["academic_unit"].astype("string").fillna("")), 0,
        "Missing from the roster export for this person.")
    row("rank", "Academic rank", col_known(fac["academic_rank"].astype("string").fillna("")), 0,
        "Missing from the roster export for this person.")
    row("track", "Appointment track", col_known(fac["academic_track_type"].astype("string").fillna("")), 0,
        "Missing from the roster export for this person.")
    row("tenure", "Tenure status", col_known(fac["tenure_status"].astype("string").fillna("")), 0,
        "The single largest gap on the roster — tenure status isn't recorded for most non-tenure-track titles.")
    row("terminal_degree", "Terminal degree", col_known(fac["terminal_degrees"].astype("string").fillna("")), 0,
        "Missing from the roster export for this person.")
    row("hire_date", "Hire date", int(fac["hire_date"].notna().sum()), 0,
        "Missing only for the small hand-added supplement of faculty absent from the HR export.")

    if lookup is not None:
        aauid_known = col_known(lookup.set_index("faculty_id").reindex(fac["faculty_id"])["aauid"].fillna(""))
    else:
        aauid_known = 0
    row("aauid", "Analytics vendor ID", aauid_known, 0,
        "Only populated for faculty who appear on at least one grant — it's sourced from the grant tables, not the roster.")

    active = fac["termination_date"].isna()
    row("employment_status", "Departure status", int((~active).sum()), int(active.sum()),
        "Not applicable — this person is still active, so there's nothing to record.")

    fields.sort(key=lambda f: f["missing"], reverse=True)
    return {"n": n, "fields": fields, "provenance": "parquet"}


def build_missingness_abstract_records() -> dict:
    """Per-field known/missing/not-applicable counts across the 8,075 raw
    abstract-upload records (grants-with-abstract.xlsx), restricted to what's
    derivable from committed parquets — RAW_ABSTRACT_RECORDS is the one
    number this script trusts without a raw-file read (see the comment on
    it below); everything else here comes from grant_orphaned_abstracts.parquet
    (the 5,095-row orphan pool) and personid_to_faculty.parquet (the ID
    bridge). Degrades to an empty grain if either is missing locally.
    """
    orphaned_path = PROC / "grant_orphaned_abstracts.parquet"
    bridge_path = PROC / "personid_to_faculty.parquet"
    if not orphaned_path.exists():
        return {"n": 0, "fields": [], "provenance": "derived"}

    import pandas as pd

    orph = pd.read_parquet(orphaned_path, columns=["id", "personid"])
    orphaned_n = len(orph)
    n = RAW_ABSTRACT_RECORDS
    matched_n = n - orphaned_n

    fields = [{
        "id": "matched_grant", "label": "Matches a Northeastern grant",
        "known": matched_n, "missing": orphaned_n, "na": 0,
        "where": "No Northeastern grant shares this record's source ID — it's likely a collaborator's or non-NU award.",
    }]

    # A "has abstract text" field lived here once — dropped as confusing,
    # not just mislabeled: scored only among the 5,095 unmatched records
    # (matched ones are already counted in the grants-grain "Abstract text"
    # field), it read as a smaller, contradicting count of the SAME fact
    # the grants grain reports, when it was actually answering a much
    # narrower question. The funnel section already tells this exact story
    # more precisely, as "usable" text (grant_orphan_recovery.parquet's own
    # threshold, not just non-empty) — no need to duplicate it here.

    if bridge_path.exists():
        bridge = pd.read_parquet(bridge_path, columns=["personid", "faculty_id"])
        resolved_ids = set(bridge.loc[bridge["faculty_id"].astype(str).str.strip() != "", "personid"])
        pi_resolved = int(orph["personid"].astype(str).isin(resolved_ids).sum())
        fields.append({
            "id": "pi_resolved", "label": "Writer matched to a faculty member",
            "known": pi_resolved, "missing": orphaned_n - pi_resolved, "na": matched_n,
            "where": "Scored only among unmatched records — this record's writer ID doesn't map to anyone on the faculty roster via the ID bridge.",
        })
    else:
        # Can't score this without the bridge — the whole grain is "not
        # applicable" rather than a fabricated 0-known claim.
        fields.append({
            "id": "pi_resolved", "label": "Writer matched to a faculty member",
            "known": 0, "missing": 0, "na": n,
            "where": "Scored only among unmatched records — this record's writer ID doesn't map to anyone on the faculty roster via the ID bridge.",
        })

    fields.sort(key=lambda f: f["missing"], reverse=True)
    return {"n": n, "fields": fields, "provenance": "parquet"}


def build_missingness(points: list[dict], pi_attrs: dict[str, dict], recoverable: set[str],
                       fac, lookup) -> dict:
    """Per-field known/missing/not-applicable counts, split by grain — grants,
    PIs, and raw abstract-upload records — for the "What's missing" panel.
    Each grain has its own natural denominator; scoring PI-level gaps against
    2,676 grants (or vice versa) would misrepresent what's actually missing
    and from what population.
    """
    return {
        "grains": {
            "grants": build_missingness_grants(points, pi_attrs, recoverable),
            "pis": build_missingness_pis(fac, lookup),
            "abstract_records": build_missingness_abstract_records(),
        },
    }


# Two facts verified directly against the raw grants-with-abstract.xlsx via
# src/build_dataset.py's own logged run (data/processed/PIPELINE_VALIDATION.txt)
# and NOT recomputable from any committed parquet alone — build_dataset.py's
# matched/orphaned split happens on the raw upload-system rows before either
# is persisted in full, so only the two output sizes below (and their
# difference) survive to disk. Update these two numbers if build_dataset.py
# is ever rerun against a materially different raw abstract export.
RAW_ABSTRACT_RECORDS = 8075
RAW_MATCHED_UNIQUE_GRANTS = 2410  # rows whose sourceactivityid hit an NEU grant_id, deduped to one-per-grant


def build_funnel() -> dict:
    """The abstract-sourcing pipeline (raw upload records -> rows that match
    an NEU grant_id -> deduped unique grants -> grants that end up with real
    text) plus the M2 orphan-recovery branch (src/reconcile_orphans.py) off
    the "didn't match" step. Deliberately does NOT continue the trunk on to
    "grants with a confident topic" — that's a different, independent
    attribute (title-only grants get topics too; see the mosaic panel above)
    and chaining it here would wrongly imply topic assignment requires text.

    Degrades honestly (branch omitted, not zeroed) if the M2 outputs aren't
    built locally.
    """
    orphaned_path = PROC / "grant_orphaned_abstracts.parquet"
    recovery_path = PROC / "grant_orphan_recovery.parquet"
    extra_path = PROC / "extra_neu_abstracts.parquet"
    grants_path = PROC / "grants.parquet"

    if not (orphaned_path.exists() and grants_path.exists()):
        return {"trunk": [], "branch": None, "totals": {}, "provenance": "derived"}

    import pandas as pd

    orphaned_n = len(pd.read_parquet(orphaned_path, columns=["id"]))
    g = pd.read_parquet(grants_path, columns=["abstract_source"])
    # Deliberate choice: this trunk step narrates ONE specific pipeline (the
    # internal upload system's own raw records -> matched rows -> matched
    # grants), so "has_text" here means "the internal match succeeded" —
    # NOT the corpus-wide has-text count (that's has_text_final below,
    # which the M2 branch and the external NIH/NSF backfill both feed).
    # Do not extend this to nih_reporter/nsf_api — they come from an
    # entirely different upload, outside what this trunk is describing.
    has_text_n = int((g["abstract_source"] == "internal").sum())

    # Labels here are the ones rendered directly in the funnel chart, so they're
    # written for the dashboard's stakeholder audience — no column/file names
    # (grant_id, .parquet, etc.); that provenance detail belongs in the code
    # comments and docs, not in audience-facing chart text.
    trunk = [
        {"id": "raw_records", "label": "Raw abstract records uploaded", "n": RAW_ABSTRACT_RECORDS},
        {"id": "matched_rows", "label": "Rows matching an NEU grant", "n": RAW_ABSTRACT_RECORDS - orphaned_n},
        {"id": "matched_grants", "label": "Unique NEU grants matched (most recent record kept)", "n": RAW_MATCHED_UNIQUE_GRANTS},
        {"id": "has_text", "label": "Grants that end up with usable text", "n": has_text_n},
    ]

    if not (recovery_path.exists() and extra_path.exists()):
        return {"trunk": trunk, "branch": None, "totals": {"grants_total": len(g)}, "provenance": "partial"}

    rec = pd.read_parquet(recovery_path, columns=["bucket"])
    bucket_n = rec["bucket"].value_counts().to_dict()
    extra_n = len(pd.read_parquet(extra_path, columns=["doc_id"]))

    branch = {
        "from": "raw_records",
        "n": orphaned_n,
        "label": "Records with no matching NEU grant (“orphans”)",
        "steps": [
            {"id": "usable", "label": "Substantial enough text to attempt a match", "n": sum(bucket_n.values())},
            {"id": "update", "label": "Backfilled onto an existing abstract-less grant", "n": bucket_n.get("update", 0)},
            {"id": "extra", "label": "Added as a new record for the topic model", "n": bucket_n.get("extra", extra_n)},
            {"id": "duplicate", "label": "Re-upload of an already-abstracted grant (dropped, not double-counted)", "n": bucket_n.get("duplicate", 0)},
            {"id": "unattributed", "label": "No faculty resolved (dropped)", "n": bucket_n.get("unattributed", 0)},
        ],
    }

    # Corpus-wide "ends up carrying [MODELING-usable] text" — the "Net
    # effect" sentence rendered in what_we_can_see/missing.js ties this
    # number directly to "the topic model's corpus", so it must match what
    # the model actually sees: every non-empty abstract_source EXCEPT the
    # low-trust ones (nih_reporter_parent has real text, but is excluded
    # from the fit — see src.clean_text.LOW_TRUST_ABSTRACT_SOURCES).
    has_text_final = int(
        ((g["abstract_source"] != "") & (~g["abstract_source"].isin(LOW_TRUST_ABSTRACT_SOURCES))).sum()
    )
    totals = {
        "grants_total": len(g),
        "has_text_final": has_text_final,
        "corpus_for_bertopic": len(g) + extra_n,
    }
    return {"trunk": trunk, "branch": branch, "totals": totals, "provenance": "parquet"}


def build_viz_meta(points: list[dict], topics: list[dict]) -> dict:
    from src.viz_constants import COLORS, ORDER  # reuse verbatim, palettes can't drift

    agencies = []
    for key in ORDER:
        if key == "Other":
            # "Other" is a bucket of several agencies (HHS, NEH, NOAA, USDA, ...)
            # below the naming threshold — taking any single point's agencyLabel
            # here previously mislabeled the whole bucket as one of them.
            label = "Other (HHS, NEH, NOAA, USDA, and other small agencies)"
        else:
            label = next((p["agencyLabel"] for p in points if p["agency"] == key), key)
        agencies.append({"key": key, "label": label, "color": COLORS[key]})

    # PARENT_COLORS[i % len(PARENT_COLORS)], not PARENT_COLORS[i]: matches the
    # modulo pattern the frontend already uses for this same 8-color palette
    # (e.g. shared/enrico.js's parentColor()) — a 9th PARENT_NAMES entry
    # reuses a color instead of raising IndexError if PARENT_COLORS wasn't
    # (yet) extended to match.
    parents = [
        {"id": i, "name": name, "color": PARENT_COLORS[i % len(PARENT_COLORS)]}
        for i, name in enumerate(PARENT_NAMES)
    ] + [{"id": -1, "name": "Unassigned", "color": "#c7ccd3"}]

    topics_out = []
    for t in topics:
        tid = t["id"]
        topics_out.append({
            "id": tid,
            "name": t["name"],
            "parent": _parent_index(t.get("parent")),
            "terms": t.get("terms", []),
            "share": t.get("share", 0.0),
            # Always False now that ARTIFACT_TOPIC_ID is retired (None) — no
            # leaf in the curated taxonomy is a definitional artifact the way
            # BERTopic's topic 14 was; kept as a field (not dropped) so
            # existing frontend code that branches on `t.artifact` (e.g.
            # topic_flow.html's dashed-border small-multiple) degrades to
            # "never dashed" instead of needing its own edit.
            "artifact": tid == ARTIFACT_TOPIC_ID,
            "noise": tid == -1,
            "conf_mean": t.get("conf_mean", 0.0),
        })

    years_present = sorted({p["year"] for p in points if p["year"] is not None})
    prelude_years = [y for y in years_present if y < DENSE_FROM]
    prelude_n = sum(1 for p in points if p["year"] is not None and p["year"] < DENSE_FROM)

    total_dollars = sum(p["amount"] for p in points)
    unassigned_n = sum(1 for p in points if p["dom"] == -1 or p["dom"] == ARTIFACT_TOPIC_ID)
    unassigned_dollars = sum(
        p["amount"] for p in points if p["dom"] == -1 or p["dom"] == ARTIFACT_TOPIC_ID
    )

    return {
        "frozen_inputs": {
            # Coordinates are still SPECTER2 + UMAP; the LABELS are now the
            # curated keyword classifier (BM25F), not HDBSCAN — stating only
            # one half would misrepresent the method (see
            # docs/TOPIC_MODEL_REFIT_CHECKLIST.md's re-curate track).
            "projection": "Curated keyword scoring (BM25F) · layout: SPECTER2 + UMAP",
            "n_points": len(points),
            # len(...), not a literal 25 — about.html renders this verbatim
            # ("N topics + an explicit Unassigned noise cluster"); a hardcoded
            # count would silently disagree with the actual topic model after
            # a refit. Excludes the id=-1 noise entry, same convention as
            # everywhere else in this file that counts "real" topics.
            "n_topics": len([t for t in topics if t["id"] >= 0]),
        },
        "agencies": agencies,
        "parents": parents,
        "topics": topics_out,
        "years": {
            "min": years_present[0],
            "max": years_present[-1],
            "dense_from": DENSE_FROM,
            "dense_to": DENSE_TO,
            "prelude_years": prelude_years,
            "prelude_n": prelude_n,
            "complete_through": 2024,
        },
        "totals": {
            "n_grants": len(points),
            "dollars": total_dollars,
            "unassigned_n": unassigned_n,
            "unassigned_dollars": unassigned_dollars,
            # dollar share, NOT count share — see coverage.json's unassigned.share_n
            # for the count-share sibling. The two were both called "share" before
            # and were easy to mix up across the two files.
            "unassigned_share_d": round(unassigned_dollars / total_dollars, 4),
        },
        "caveats": CAVEATS,
        "cliffs": CLIFFS,
    }


def build_topic_time(points: list[dict], topics: list[dict]) -> dict:
    parent_of_topic = {t["id"]: _parent_index(t.get("parent")) for t in topics}
    years = list(range(DENSE_FROM, DENSE_TO + 1))
    y_index = {y: i for i, y in enumerate(years)}

    def blank():
        return {"n": [0] * len(years), "d": [0.0] * len(years)}

    topic_series = {str(t["id"]): blank() for t in topics}          # "-1".."24"
    # range(-1, len(PARENT_NAMES)), not a bare range(-1, 8): every parent
    # index a point can carry (via _parent_index) must have a bucket here, or
    # the lookups below KeyError. A refit that changes the parent count
    # doesn't need this file re-edited past updating PARENT_NAMES itself.
    parent_series = {str(i): blank() for i in range(-1, len(PARENT_NAMES))}
    topic_title_only = {str(t["id"]): [0] * len(years) for t in topics}
    parent_title_only = {str(i): [0] * len(years) for i in range(-1, len(PARENT_NAMES))}
    totals = blank()

    prelude_n, prelude_d = 0, 0.0
    prelude_by_parent = {str(i): 0 for i in range(-1, len(PARENT_NAMES))}

    for p in points:
        yr = p["year"]
        tid = p["dom"]
        pid = parent_of_topic.get(tid, -1)
        # Clamp to Unassigned (-1) if pid names a parent beyond what
        # PARENT_NAMES currently has a bucket for (parent_series/
        # prelude_by_parent/etc. above are only sized to range(-1,
        # len(PARENT_NAMES))) — same "don't crash, fall back to Unassigned"
        # stance as build_facets_pi's tp_index_map.get(v, 1).
        if pid >= len(PARENT_NAMES):
            pid = -1
        amt = p["amount"]
        if yr is None or yr < DENSE_FROM or yr > DENSE_TO:
            if yr is not None and yr < DENSE_FROM:
                prelude_n += 1
                prelude_d += amt
                prelude_by_parent[str(pid)] += 1
            continue
        i = y_index[yr]
        topic_series[str(tid)]["n"][i] += 1
        topic_series[str(tid)]["d"][i] += amt
        parent_series[str(pid)]["n"][i] += 1
        parent_series[str(pid)]["d"][i] += amt
        totals["n"][i] += 1
        totals["d"][i] += amt
        if p["titleOnly"]:
            topic_title_only[str(tid)][i] += 1
            parent_title_only[str(pid)][i] += 1

    return {
        "years": years,
        "prelude": {"n": prelude_n, "d": prelude_d, "by_parent": prelude_by_parent},
        "series": {"topic": topic_series, "parent": parent_series},
        "title_only": {"topic": topic_title_only, "parent": parent_title_only},
        "totals_by_year": totals,
    }


def build_coverage(points: list[dict]) -> dict:
    from src.viz_constants import COLORS, ORDER

    abs_src, src_path = load_abstract_source(points)

    years = list(range(min(p["year"] for p in points if p["year"]), max(p["year"] for p in points if p["year"]) + 1))
    cells = []
    by_year_n: dict[int, int] = {y: 0 for y in years}
    by_year_abs: dict[int, int] = {y: 0 for y in years}
    by_agency: dict[str, list[int]] = {a: [0, 0] for a in ORDER}

    per_cell: dict[tuple[str, int], list[int]] = {}
    for p in points:
        yr = p["year"]
        if yr is None:
            continue
        has_abs = not p["titleOnly"]
        by_year_n[yr] += 1
        by_year_abs[yr] += 1 if has_abs else 0
        by_agency[p["agency"]][0] += 1
        by_agency[p["agency"]][1] += 1 if has_abs else 0
        key = (p["agency"], yr)
        cell = per_cell.setdefault(key, [0, 0, 0, 0])  # n, abs, noise, title_only
        cell[0] += 1
        cell[1] += 1 if has_abs else 0
        cell[2] += 1 if p["dom"] == -1 else 0
        cell[3] += 1 if p["titleOnly"] else 0

    for (agency, yr), (n, a, noise, title_only) in sorted(per_cell.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        cells.append({
            "agency": agency, "year": yr, "n": n, "abs": a,
            "noise": noise, "title_only": title_only, "cov": round(a / n, 4) if n else None,
        })

    provenance = {"internal": 0, "orphan_recovered": 0, "none": 0}
    for v in abs_src.values():
        provenance[v] = provenance.get(v, 0) + 1
    provenance["source"] = src_path

    unassigned_n = sum(1 for p in points if p["dom"] == -1)

    # by_reason: the classifier's own honest breakdown of WHY a point is
    # Unassigned (src.classify_by_keywords), replacing the old noise_n/t11_n
    # split (which was HDBSCAN-noise-vs-one-hardcoded-artifact-topic — a
    # distinction that no longer exists under the keyword classifier).
    # unassignedReason is only set on points the classifier itself marked
    # dom==-1, so this always partitions unassigned_n exactly (asserted in
    # validate() below, not just assumed here).
    by_reason: dict[str, int] = {}
    for p in points:
        if p["dom"] == -1:
            reason = p.get("unassignedReason") or "no_usable_text"
            by_reason[reason] = by_reason.get(reason, 0) + 1

    # abstract-presence x assignment crosstab — is losing the abstract still
    # a barely-moves-the-needle effect under the keyword classifier the way
    # titles-carry-most-of-the-signal was for BERTopic's HDBSCAN step? This is
    # a MODELING question (did the fit actually see abstract text), so it
    # must use modelTitleOnly, not titleOnly (data availability) — they
    # differ for grants tagged with a LOW_TRUST_ABSTRACT_SOURCES value.
    # .get() fallback: a frozen grants_umap.json from before this field
    # existed has no modelTitleOnly key at all, so fall back to titleOnly
    # (the only information available at that point, and correct for every
    # point anyway before any low-trust backfill existed).
    def _model_title_only(p: dict) -> bool:
        return p.get("modelTitleOnly", p["titleOnly"])

    crosstab = {
        "abs_assigned": sum(1 for p in points if not _model_title_only(p) and p["dom"] != -1),
        "abs_unassigned": sum(1 for p in points if not _model_title_only(p) and p["dom"] == -1),
        "title_assigned": sum(1 for p in points if _model_title_only(p) and p["dom"] != -1),
        "title_unassigned": sum(1 for p in points if _model_title_only(p) and p["dom"] == -1),
    }

    # confidence_by_text: the title-only-normalization check the redo plan
    # calls its single most important automatic test, made into a real,
    # checkable number instead of an assertion — split classifier confidence
    # by whether the model actually saw abstract text (modelTitleOnly, NOT
    # titleOnly — see the crosstab comment above for why). If title-only
    # docs' none/low rate is much worse than abstract-bearing docs', or their
    # mean_margin is HIGHER (the title weight over-boosting), that's a real
    # calibration problem, not a rendering detail.
    def _confidence_block(subset: list[dict]) -> dict:
        n = len(subset)
        tiers = {"high": 0, "medium": 0, "low": 0, "none": 0}
        for p in subset:
            tiers[p.get("confTier", "none")] = tiers.get(p.get("confTier", "none"), 0) + 1
        mean_margin = round(sum(p.get("conf", 0.0) for p in subset) / n, 4) if n else 0.0
        return {"n": n, **tiers, "mean_margin": mean_margin}

    confidence_by_text = {
        "abs": _confidence_block([p for p in points if not _model_title_only(p)]),
        "title": _confidence_block([p for p in points if _model_title_only(p)]),
    }

    return {
        "years": years,
        "agencies": ORDER,
        "colors": COLORS,
        "cells": cells,
        "by_year": {
            "n": [by_year_n[y] for y in years],
            "abs": [by_year_abs[y] for y in years],
            "cov": [round(by_year_abs[y] / by_year_n[y], 4) if by_year_n[y] else None for y in years],
        },
        "by_agency": {
            a: {"n": n, "abs": ab, "cov": round(ab / n, 4) if n else 0.0}
            for a, (n, ab) in by_agency.items()
        },
        "provenance": provenance,
        "unassigned": {
            "n": unassigned_n,
            "by_reason": by_reason,
            "artifact_n": 0,  # ARTIFACT_TOPIC_ID is retired — see its own comment above
            # count share, NOT dollar share — see viz_meta.json's totals.unassigned_share_d
            # for the dollar-share sibling.
            "share_n": round(unassigned_n / len(points), 4),
        },
        "confidence_by_text": confidence_by_text,
        "crosstab": crosstab,
        "cliffs": CLIFFS,
    }


def validate(points: list[dict], topics: list[dict], viz_meta: dict, topic_time: dict,
             coverage: dict, facets: dict, facets_pi: dict, missingness: dict,
             funnel: dict) -> list[str]:
    lines = []
    n = len(points)
    total_dollars = sum(p["amount"] for p in points)
    # Informational, not asserted: these two are the first numbers a topic-
    # model refit or a new grants export legitimately changes. See the
    # internal-reconciliation asserts below (which stay hard) for the checks
    # that actually catch a broken build regardless of corpus size.
    lines.append(f"n_points = {n}")
    lines.append(f"total dollars = {total_dollars:,.0f}")

    # Informational: surface every abstract_source value in play, so a new or
    # renamed tag (e.g. from a future backfill) shows up here instead of
    # silently landing in an unlabeled bucket somewhere downstream. Reuses
    # coverage["provenance"] (build_coverage() already computes this exact,
    # value-agnostic histogram) rather than a second load_abstract_source()
    # call + a third grants.parquet read.
    src_counts = {k: v for k, v in coverage.get("provenance", {}).items() if k != "source"}
    src_method = coverage.get("provenance", {}).get("source", "unknown")
    if src_counts:
        lines.append(
            f"abstract_source counts ({src_method}): "
            + ", ".join(f"{k}={v}" for k, v in sorted(src_counts.items(), key=lambda kv: -kv[1]))
        )

    # Parent-theme shape drift — PARENT_NAMES/PARENT_COLORS (this file) and
    # their manually-synced copies in shared/enrico.js (and, for visual
    # consistency with the PI's read-only EnricoVis apps, topic_hierarchy.html)
    # don't auto-update from the topic model. Nothing crashes on a mismatch
    # (see the modulo/`.get()` fallbacks added where PARENT_NAMES/PARENT_COLORS
    # are consumed) but a silently-wrong parent count is easy to miss without
    # this being loud about it.
    seen_parents = {t.get("parent") for t in topics if t.get("parent")}
    if len(seen_parents) != len(PARENT_NAMES):
        lines.append(
            f"⚠ parent count drifted: topics.json has {len(seen_parents)} parent groups, "
            f"PARENT_NAMES/PARENT_COLORS here have {len(PARENT_NAMES)}. Update both "
            f"(and their manually-synced copies in docs/TopicVizPrototypes/shared/enrico.js "
            f"and, if desired, docs/EnricoVis/topic_hierarchy.html — see the module docstring)."
        )
    else:
        lines.append(f"parent count = {len(seen_parents)} (matches PARENT_NAMES/PARENT_COLORS) ✓")

    # Leaf-topic palette headroom — shared/enrico.js's TOPIC_COLORS has 32
    # entries (verified by counting there); a curated leaf count past that
    # would silently start reusing colors (topicColor() wraps via modulo,
    # never crashes) rather than erroring. Informational, not asserted — a
    # re-curation genuinely can grow past 32, and the fix is extending that
    # array, not failing the build.
    n_leaves_here = len([t for t in topics if t["id"] >= 0])
    if n_leaves_here > TOPIC_COLOR_CAPACITY:
        lines.append(
            f"⚠ {n_leaves_here} curated leaves exceeds shared/enrico.js's TOPIC_COLORS "
            f"capacity ({TOPIC_COLOR_CAPACITY}) — extend that array or leaf colors will "
            "start silently repeating."
        )
    else:
        lines.append(f"leaf count = {n_leaves_here} (within TOPIC_COLORS capacity "
                      f"of {TOPIC_COLOR_CAPACITY}) ✓")

    # ARTIFACT_TOPIC_ID is deliberately retired (None) under the curated
    # keyword taxonomy — every leaf is a human curation decision, not an
    # HDBSCAN byproduct, so there's no single "flagged artifact bucket" to
    # re-derive after a re-curation the way there was after a BERTopic refit.
    # Only warn if it's ever set back to a real id AND that id doesn't
    # actually name an unparented topic (the old staleness check, now scoped
    # to only fire when the concept is back in use at all).
    if ARTIFACT_TOPIC_ID is None:
        lines.append("ARTIFACT_TOPIC_ID retired (None) — curated keyword taxonomy has no "
                      "single artifact bucket; placeholder-title grants are tracked "
                      "per-point via unassignedReason instead ✓")
    else:
        artifact_topic = next((t for t in topics if t["id"] == ARTIFACT_TOPIC_ID), None)
        if artifact_topic is None or artifact_topic.get("parent") is not None:
            lines.append(
                f"⚠ ARTIFACT_TOPIC_ID={ARTIFACT_TOPIC_ID} no longer names a real, unparented topic — "
                f"re-check which topic (if any) is this refit's artifact bucket and update the "
                f"constant (or set it back to None if there isn't one this time)."
            )
        else:
            lines.append(f"ARTIFACT_TOPIC_ID={ARTIFACT_TOPIC_ID} still names "
                          f"'{artifact_topic['name']}', unparented ✓")

    # topic_time reconciliation: dense-window totals + prelude must equal the corpus.
    dense_n = sum(topic_time["totals_by_year"]["n"])
    dense_d = sum(topic_time["totals_by_year"]["d"])
    prelude_n = topic_time["prelude"]["n"]
    prelude_d = topic_time["prelude"]["d"]
    post_2025_n = sum(1 for p in points if p["year"] is not None and p["year"] > DENSE_TO)
    post_2025_d = sum(p["amount"] for p in points if p["year"] is not None and p["year"] > DENSE_TO)
    reconciled_n = dense_n + prelude_n + post_2025_n
    reconciled_d = dense_d + prelude_d + post_2025_d
    lines.append(f"topic_time reconciled n = {reconciled_n} (expect {n})")
    assert reconciled_n == n, "topic_time year buckets don't cover every point"
    assert abs(reconciled_d - total_dollars) < 1.0, "topic_time dollar buckets don't reconcile"

    prelude_by_parent_sum = sum(topic_time["prelude"]["by_parent"].values())
    assert prelude_by_parent_sum == prelude_n, "prelude by_parent doesn't sum to prelude n"

    # per-year parent series must sum to totals_by_year at every index.
    for i in range(len(topic_time["years"])):
        s = sum(topic_time["series"]["parent"][str(k)]["n"][i] for k in range(-1, len(PARENT_NAMES)))
        assert s == topic_time["totals_by_year"]["n"][i], f"parent series don't sum to totals at year index {i}"
    lines.append("parent series sum to totals_by_year at every year ✓")

    # Zero-coverage agencies — a verified fact of the CURRENT corpus, not a
    # structural invariant (a new abstract export, e.g., could genuinely move
    # NIH-SUB off 0.0 — see docs/data_quality_report.md §9). Informational.
    for a in ("NIH-SUB", "Navy", "AFRO"):
        cov = coverage["by_agency"][a]["cov"]
        lines.append(f"{a} coverage = {cov}")

    # Unassigned block — the cross-check between viz_meta and coverage stays
    # hard (they're computed two different ways and must agree regardless of
    # corpus); the literal 808 doesn't (that's the whole point of a refit).
    assert viz_meta["totals"]["unassigned_n"] == coverage["unassigned"]["n"], \
        "Unassigned count disagrees between viz_meta and coverage"
    lines.append(f"Unassigned = {coverage['unassigned']['n']} grants, "
                 f"${viz_meta['totals']['unassigned_dollars']:,.0f} "
                 f"({viz_meta['totals']['unassigned_share_d']:.1%})")

    # by_reason must exactly partition unassigned.n — each Unassigned point
    # contributes to exactly one reason bucket (see build_coverage()).
    by_reason_sum = sum(coverage["unassigned"]["by_reason"].values())
    assert by_reason_sum == coverage["unassigned"]["n"], \
        f"unassigned.by_reason sums to {by_reason_sum}, expected {coverage['unassigned']['n']}"
    lines.append(f"unassigned.by_reason = {coverage['unassigned']['by_reason']} "
                 f"(sums to {by_reason_sum}) ✓")

    # parent_id == parent_of(leaf_id) for every leaf — holds BY CONSTRUCTION
    # under the curated keyword taxonomy (kw_curation.py's own gate already
    # enforces bidirectional leaf<->parent consistency before promotion), so
    # this should never actually fire; kept as a cheap regression net against
    # the topic_keywords.json -> topic_labels.json schema conversion
    # (src.classify_by_keywords.curated_to_topic_labels) silently dropping or
    # scrambling a parent link. Skipped gracefully if the curated source file
    # isn't present or its leaf ids don't match this build's topics (e.g. a
    # bootstrap taxonomy) rather than crashing on an unrelated mismatch.
    curated_path = REPO_ROOT / "outputs" / "topic_keywords.json"
    if curated_path.exists():
        curated = json.loads(curated_path.read_text())
        curated_leaves = curated.get("leaves", {})
        topic_ids_here = {t["id"] for t in topics if t["id"] >= 0}
        if {int(lid) for lid in curated_leaves} == topic_ids_here:
            mismatches = [
                t["id"] for t in topics if t["id"] >= 0
                and t.get("parent") != curated_leaves[str(t["id"])].get("parent")
            ]
            assert not mismatches, (
                f"leaf(s) {mismatches} disagree between topics.json's parent field and "
                "outputs/topic_keywords.json's own leaf->parent mapping — the schema "
                "conversion (curated_to_topic_labels) has drifted from its source."
            )
            lines.append(f"parent_id == parent_of(leaf_id) for all {len(topic_ids_here)} "
                          "leaves (topics.json vs. outputs/topic_keywords.json) ✓")
        else:
            lines.append("skipped parent_id == parent_of(leaf_id) cross-check — "
                          "topics.json's leaf ids don't match outputs/topic_keywords.json "
                          "(bootstrap taxonomy in use?)")

    lines.append(f"abstract_source provenance path = {coverage['provenance']['source']}")

    ct = coverage["crosstab"]
    assert sum(ct.values()) == n, "crosstab doesn't cover every point"
    abs_rate = ct["abs_unassigned"] / (ct["abs_assigned"] + ct["abs_unassigned"])
    title_rate = ct["title_unassigned"] / (ct["title_assigned"] + ct["title_unassigned"])
    lines.append(f"unassigned rate: has-abstract {abs_rate:.1%}, title-only {title_rate:.1%} (should be close)")

    # facets.json — the "no grant ever dropped by a facet change" invariant.
    for col_name, values in facets["cols"].items():
        assert len(values) == n, f"facets column '{col_name}' length != {n}"
    assert len(facets["titles"]) == n, f"facets titles length != {n}"
    assert len(facets["abstracts"]) == n, f"facets abstracts length != {n}"
    lines.append(f"facets: {len(facets['cols'])} columns, all length {n} ✓ (+ titles, abstracts)")
    lines.append(f"facets: pi_attrs provenance path = {facets['provenance']['pi_attrs']}")

    # Abstract text — when grants.parquet was available (provenance ==
    # "parquet"), the count of non-empty facets["abstracts"] entries should
    # match facets["cols"]["ab"]'s has-abstract flag exactly (independently
    # sourced: one from the live grants.parquet text, the other from the
    # frozen corpus's titleOnly flag) — a mismatch means that join has
    # drifted apart. This is a genuine cross-check, not a corpus-size literal,
    # so it stays a hard assert; the count itself is informational.
    n_with_abstract = sum(1 for a in facets["abstracts"] if a)
    lines.append(f"facets: abstract text present for {n_with_abstract}/{n} grants "
                 f"(provenance={facets['provenance']['abstract_text']})")
    if facets["provenance"]["abstract_text"] == "parquet":
        n_flagged_has_abstract = sum(facets["cols"]["ab"])
        assert n_with_abstract == n_flagged_has_abstract, (
            f"abstract text present ({n_with_abstract}) disagrees with the has-abstract "
            f"flag ({n_flagged_has_abstract}) — the two are independently sourced and should agree"
        )

    # amt_raw must reconcile to the same total dollars as everything else —
    # a cheap way to catch a mis-keyed or truncated per-unit dollar column.
    amt_raw_total = sum(facets["cols"]["amt_raw"])
    assert abs(amt_raw_total - total_dollars) < 1.0, "facets.amt_raw doesn't reconcile to total dollars"
    lines.append(f"facets: amt_raw reconciles to total dollars (${amt_raw_total:,.0f}) ✓")

    no_pi_idx = facets["levels"]["col"].index(NO_PI_LABEL)
    off_roster_idx = facets["levels"]["col"].index(PI_OFF_ROSTER_LABEL)
    no_pi_n = sum(1 for v in facets["cols"]["col"] if v == no_pi_idx)
    off_roster_n = sum(1 for v in facets["cols"]["col"] if v == off_roster_idx)
    lines.append(f"facets: {no_pi_n} grants with '{NO_PI_LABEL}', {off_roster_n} with '{PI_OFF_ROSTER_LABEL}'")
    # Informational only below — these counts are a fact of the current
    # grant/roster data (data/processed/*.parquet), not the topic model, but
    # still legitimately change on any rebuild of that data (a new grants
    # export, an HR roster refresh), so they're not asserted against a literal.

    # missingness.json — each grain's fields must sum to that grain's own n,
    # not the grant count (n above) — grains have different denominators.
    for grain_id, grain in missingness["grains"].items():
        for f in grain["fields"]:
            assert f["known"] + f["missing"] + f["na"] == grain["n"], \
                f"missingness grain '{grain_id}' field '{f['id']}' doesn't sum to {grain['n']}"
        lines.append(f"missingness[{grain_id}]: n={grain['n']}, {len(grain['fields'])} fields, "
                      f"all reconcile ✓ (provenance={grain['provenance']})")

    grants_grain = missingness["grains"]["grants"]
    assert grants_grain["n"] == n, "grants-grain missingness n doesn't match the corpus"
    pis_grain = missingness["grains"]["pis"]
    if pis_grain["provenance"] == "parquet":
        lines.append(f"missingness[pis]: n={pis_grain['n']}")  # roster size — informational

    # facets_pi.json — same "nobody ever dropped" invariant as facets.json
    # above, scored against the PI-grain's own n (roster faculty count, not
    # the grant count).
    if facets_pi["provenance"] == "parquet":
        n_pi = facets_pi["n"]
        # Cross-check against missingness's independently-built PI grain
        # (different function, same underlying roster) rather than a
        # literal — a genuine invariant that survives a roster refresh.
        if pis_grain["provenance"] == "parquet":
            assert n_pi == pis_grain["n"], (
                f"facets_pi n ({n_pi}) disagrees with missingness[pis] n ({pis_grain['n']}) — "
                "both should be the same roster faculty count"
            )
        for col_name, values in facets_pi["cols"].items():
            assert len(values) == n_pi, f"facets_pi column '{col_name}' length != {n_pi}"
        assert len(facets_pi["names"]) == n_pi and len(facets_pi["grant_titles"]) == n_pi
        n_has_grants = sum(facets_pi["cols"]["hasgrants"])
        n_as_pi = sum(1 for v in facets_pi["cols"]["tp"] if v != 0)
        lines.append(f"facets_pi: {n_pi} faculty, {n_has_grants} with grants, "
                      f"{n_as_pi} ever a PI in this corpus")
        # Both counts below are informational, not asserted against a
        # literal — they're facts of the current grant/roster data (a new
        # grants export or HR roster refresh legitimately changes them), not
        # of the topic model. n_as_pi in particular only credits a PI grant
        # if it also resolves in the frozen grants_umap corpus, while
        # faculty_grants itself can span a slightly larger grant_id set — a
        # PI whose only credited grant(s) fall outside that set undercounts
        # here by construction, not by a real data drift.

    # funnel.json — the trunk must be monotonically non-increasing, and the
    # raw/matched/orphaned split must reconcile.
    if funnel["provenance"] != "derived":
        trunk_ns = [s["n"] for s in funnel["trunk"]]
        assert trunk_ns == sorted(trunk_ns, reverse=True), "funnel trunk is not monotonically non-increasing"
        # RAW_ABSTRACT_RECORDS (8075, see its own comment) has no source in
        # any committed parquet — it was verified once by hand against a
        # PIPELINE_VALIDATION.txt from a past build_dataset.py run. Report it
        # as a hint rather than assert against it; after a real raw-data
        # rebuild, re-derive the expectation from the FRESH
        # data/processed/PIPELINE_VALIDATION.txt instead of trusting this
        # stale constant.
        lines.append(f"funnel trunk starts at {trunk_ns[0]} raw records "
                      f"(RAW_ABSTRACT_RECORDS constant = {RAW_ABSTRACT_RECORDS})")
        lines.append(f"funnel trunk: {' -> '.join(str(x) for x in trunk_ns)}")
        if funnel["branch"] is not None:
            # trunk_ns[0], not RAW_ABSTRACT_RECORDS: this reconciles the
            # funnel against ITS OWN reported raw count, which is refit-proof
            # (the constant above is not).
            matched_rows_n = trunk_ns[1]
            assert matched_rows_n + funnel["branch"]["n"] == trunk_ns[0], \
                "matched rows + orphaned rows don't sum to the funnel's own raw record count"
            bucket_sum = sum(s["n"] for s in funnel["branch"]["steps"][1:])  # update+extra+duplicate+unattributed
            assert bucket_sum == funnel["branch"]["steps"][0]["n"], \
                "orphan recovery buckets don't sum to the 'usable' step"
            lines.append(f"funnel branch: {funnel['branch']['n']} orphans, "
                         f"{funnel['branch']['steps'][0]['n']} usable, buckets sum to usable ✓")

    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="run validation, print it, write nothing")
    args = ap.parse_args()

    points, topics = load_frozen()
    viz_meta = build_viz_meta(points, topics)
    topic_time = build_topic_time(points, topics)
    coverage = build_coverage(points)
    facets = build_facets(points, topics)
    pi_attrs, _ = load_pi_attrs(points)
    recoverable = load_recoverable()
    fac, lookup, _ = load_faculty_roster()
    facets_pi = build_facets_pi(fac, points, topics)
    missingness = build_missingness(points, pi_attrs, recoverable, fac, lookup)
    funnel = build_funnel()

    report = validate(points, topics, viz_meta, topic_time, coverage, facets, facets_pi, missingness, funnel)
    viz_meta["validation"] = report
    print("\n".join(report))

    if args.check_only:
        print("\n--check-only: nothing written.")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, obj in [
        ("viz_meta", viz_meta), ("topic_time", topic_time), ("coverage", coverage),
        ("facets", facets), ("facets_pi", facets_pi), ("missingness", missingness), ("funnel", funnel),
    ]:
        p = OUT_DIR / f"{name}.json"
        _guard_output_path(p)
        p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {p.relative_to(REPO_ROOT)}  ({p.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
