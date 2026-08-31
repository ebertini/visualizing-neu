"""Award-number normalizer + response-parsing regression tests for
src/backfill_nih_reporter.py. Covers every raw `agencygrantid` shape sampled
from data/processed/grants.parquet while scoping the NIH RePORTER backfill
(M5a of docs/TOPIC_WORK_FORWARD_PLAN.md).

Run:  pytest tests/test_backfill_nih_reporter.py
"""
import pandas as pd
import pytest

from src.backfill_nih_reporter import (
    _granularity_rank,
    core_key,
    extract_investigators,
    match_grants,
    parse_award_num,
    parse_record,
)

# (raw agencygrantid, expected core, expected suffix, expected suffix_kind)
REAL_SAMPLES = [
    ("R01DK035090", "R01DK035090", None, None),
    ("P30CA118100-4", "P30CA118100", "4", "support_year"),
    ("P41RR000862-6313", "P41RR000862", "6313", "subproject"),
    ("P01HL081427-9001", "P01HL081427", "9001", "subproject"),
    ("M01RR000054-706", "M01RR000054", "706", "support_year"),
    ("R01 HS13591", "R01HS13591", None, None),          # AHRQ, 5-digit serial, space-separated
    ("U54CA113007-1", "U54CA113007", "1", "support_year"),
    ("P20RR016480-5568", "P20RR016480", "5568", "subproject"),
    ("P20RR016480-8", "P20RR016480", "8", "support_year"),
    ("P41RR008630-8866", "P41RR008630", "8866", "subproject"),
    ("R21CA246150", "R21CA246150", None, None),
    ("T32GM007057", "T32GM007057", None, None),
    # letter-second activity codes (NIH Director's / exploratory / VA
    # mechanisms), all confirmed present on 2016+ grants in this corpus --
    # exactly the abstract-cliff cohort this backfill exists to fix.
    ("DP2CA174495", "DP2CA174495", None, None),
    ("UH3AA026214", "UH3AA026214", None, None),
    ("RF1AG072607", "RF1AG072607", None, None),
    ("UF1NS107694", "UF1NS107694", None, None),
    ("UG3OD023251", "UG3OD023251", None, None),
    ("IK2CX001984", "IK2CX001984", None, None),
]


@pytest.mark.parametrize("raw,core,suffix,kind", REAL_SAMPLES)
def test_parse_award_num_real_samples(raw, core, suffix, kind):
    parsed = parse_award_num(raw)
    assert parsed.valid is True
    assert parsed.core == core
    assert parsed.suffix == suffix
    assert parsed.suffix_kind == kind


@pytest.mark.parametrize("raw", [None, "", "   ", float("nan"), "not-an-award", "12345"])
def test_parse_award_num_rejects_junk(raw):
    parsed = parse_award_num(raw)
    assert parsed.valid is False
    assert parsed.core is None


def test_parse_award_num_is_case_and_whitespace_insensitive():
    a = parse_award_num("r01dk035090")
    b = parse_award_num("  R01   DK035090  ")
    assert a.valid and b.valid
    assert a.core == b.core == "R01DK035090"


def test_core_key_numeric_tolerant_across_padding():
    # RePORTER's own core_project_num may zero-pad the serial differently
    # than our locally-parsed core -- the key must still agree numerically.
    assert core_key("R01DK035090") == core_key("R01DK35090")
    assert core_key("R01DK035090") != core_key("R01DK035091")
    assert core_key("not-a-core") is None


def test_parse_record_flattens_reporter_schema():
    rec = {
        "project_num": "5R01DK035090-24",
        "core_project_num": "R01DK035090",
        "subproject_id": None,
        "fiscal_year": 2022,
        "abstract_text": "  Studies of diabetic nephropathy.  ",
        "project_title": "Diabetic kidney disease",
        "organization": {"org_name": "Northeastern University"},
    }
    parsed = parse_record(rec)
    assert parsed["core_project_num"] == "R01DK035090"
    assert parsed["abstract"] == "Studies of diabetic nephropathy."
    assert parsed["is_neu_org"] is True


def test_parse_record_flags_non_neu_org():
    rec = {"core_project_num": "R01DK035090", "organization": {"org_name": "Boston University"}}
    assert parse_record(rec)["is_neu_org"] is False


def test_extract_investigators_preserves_contact_pi_and_order():
    rec = {
        "core_project_num": "R01DK035090",
        "project_num": "5R01DK035090-24",
        "principal_investigators": [
            {"profile_id": 111, "full_name": "Jane Smith", "is_contact_pi": True},
            {"profile_id": 222, "full_name": "John Doe", "is_contact_pi": False},
        ],
    }
    rows = extract_investigators(rec)
    assert [r["full_name"] for r in rows] == ["Jane Smith", "John Doe"]
    assert rows[0]["is_contact_pi"] is True
    assert rows[1]["is_contact_pi"] is False
    assert [r["rank_order"] for r in rows] == [0, 1]


def test_extract_investigators_flags_non_neu_organization():
    """The sub-award slice's PIs are dominated by the PRIME institution, not
    NEU -- reviewers need a column to filter those out before adopting any
    proposed faculty link.
    """
    rec = {
        "core_project_num": "P41RR000862", "project_num": "P41RR000862",
        "organization": {"org_name": "Boston University"},
        "principal_investigators": [{"full_name": "Jane Smith", "is_contact_pi": True}],
    }
    row = extract_investigators(rec)[0]
    assert row["org_name"] == "Boston University"
    assert row["is_neu_org"] is False


def _grant(grant_id, agencygrantid, startdateyear):
    return {"grant_id": grant_id, "agencygrantid": agencygrantid, "startdateyear": startdateyear}


def test_match_grants_prefers_closest_fiscal_year():
    grants = pd.DataFrame([_grant("g1", "R01DK035090", 2010)])
    records = [
        {"core_project_num": "R01DK035090", "project_num": "5R01DK035090-05",
         "fiscal_year": 2005, "abstract_text": "far year text",
         "organization": {"org_name": "Northeastern University"}},
        {"core_project_num": "R01DK035090", "project_num": "5R01DK035090-10",
         "fiscal_year": 2010, "abstract_text": "close year text",
         "organization": {"org_name": "Northeastern University"}},
    ]
    result = match_grants(grants, records)
    row = result["abstracts"].iloc[0]
    assert row["abstract"] == "close year text"
    assert row["abstract_source"] == "nih_reporter"


def test_match_grants_subproject_uses_parent_fallback_when_untagged():
    """A subaward grant (suffix_kind == 'subproject') whose specific
    subproject record has no abstract of its own falls back to the parent
    center's text -- but is tagged nih_reporter_parent so it can be excluded
    from the topic-model fit (the risk this whole subaward slice carries).
    """
    grants = pd.DataFrame([_grant("g_sub", "P41RR000862-6313", 2008)])
    records = [
        # the subproject itself: no abstract text
        {"core_project_num": "P41RR000862", "project_num": "P41RR000862-6313",
         "subproject_id": "6313", "fiscal_year": 2008, "abstract_text": "",
         "organization": {"org_name": "Some Other University"}},
        # the parent center record: has text
        {"core_project_num": "P41RR000862", "project_num": "P41RR000862",
         "subproject_id": None, "fiscal_year": 2008,
         "abstract_text": "parent center description",
         "organization": {"org_name": "Some Other University"}},
    ]
    result = match_grants(grants, records)
    row = result["abstracts"].iloc[0]
    assert row["abstract"] == "parent center description"
    assert row["abstract_source"] == "nih_reporter_parent"
    assert result["parent_fallback_n"] == 1


def test_match_grants_subproject_prefers_its_own_abstract_when_present():
    grants = pd.DataFrame([_grant("g_sub", "P41RR000862-6313", 2008)])
    records = [
        {"core_project_num": "P41RR000862", "project_num": "P41RR000862-6313",
         "subproject_id": "6313", "fiscal_year": 2008,
         "abstract_text": "this subproject's own text",
         "organization": {"org_name": "Some Other University"}},
        {"core_project_num": "P41RR000862", "project_num": "P41RR000862",
         "subproject_id": None, "fiscal_year": 2008,
         "abstract_text": "parent center description",
         "organization": {"org_name": "Some Other University"}},
    ]
    result = match_grants(grants, records)
    row = result["abstracts"].iloc[0]
    assert row["abstract"] == "this subproject's own text"
    assert row["abstract_source"] == "nih_reporter"
    assert result["parent_fallback_n"] == 0


def test_match_grants_reports_unmatched_and_unparsed():
    grants = pd.DataFrame([
        _grant("g_bad", "not-an-award-number", 2010),
        _grant("g_none", "R01ZZ099999", 2010),
    ])
    result = match_grants(grants, [])
    assert result["unparsed"] == ["not-an-award-number"]
    assert result["unmatched_cores"] == ["R01ZZ099999"]
    assert result["abstracts"].empty


def test_match_grants_center_grant_prefers_core_text_over_closer_subproject():
    """A center-level grant (support_year suffix, e.g. P30CA118100-4) must
    NOT be handed a narrow subproject's abstract just because that
    subproject's fiscal year happens to line up better than the actual
    center record's -- granularity fit outranks fiscal-year closeness.
    """
    grants = pd.DataFrame([_grant("g_center", "P30CA118100-4", 2007)])
    records = [
        {"core_project_num": "P30CA118100", "project_num": "P30CA118100",
         "subproject_id": None, "fiscal_year": 2009,
         "abstract_text": "the real center abstract",
         "organization": {"org_name": "Northeastern University"}},
        {"core_project_num": "P30CA118100", "project_num": "P30CA118100-9001",
         "subproject_id": "9001", "fiscal_year": 2007,
         "abstract_text": "a narrow subproject about an unrelated topic",
         "organization": {"org_name": "Northeastern University"}},
    ]
    result = match_grants(grants, records)
    row = result["abstracts"].iloc[0]
    assert row["abstract"] == "the real center abstract"
    assert row["abstract_source"] == "nih_reporter"
    assert result["parent_fallback_n"] == 0


def test_match_grants_center_grant_falls_back_to_subproject_text_when_no_core_text():
    """If NO core-level record has text, a center-level grant may still fall
    back to a subproject's text as a last resort -- but must be tagged
    nih_reporter_parent, the same risk category as the reverse direction.
    """
    grants = pd.DataFrame([_grant("g_center", "P30CA118100-4", 2007)])
    records = [
        {"core_project_num": "P30CA118100", "project_num": "P30CA118100",
         "subproject_id": None, "fiscal_year": 2007, "abstract_text": "",
         "organization": {"org_name": "Northeastern University"}},
        {"core_project_num": "P30CA118100", "project_num": "P30CA118100-9001",
         "subproject_id": "9001", "fiscal_year": 2007,
         "abstract_text": "only the subproject has text",
         "organization": {"org_name": "Northeastern University"}},
    ]
    result = match_grants(grants, records)
    row = result["abstracts"].iloc[0]
    assert row["abstract"] == "only the subproject has text"
    assert row["abstract_source"] == "nih_reporter_parent"
    assert result["parent_fallback_n"] == 1


def test_match_grants_subproject_pi_wins_even_when_abstract_borrowed_from_parent():
    """The subproject's own PI list must be used even when its abstract had
    to fall back to the parent center's text (a subproject can lack an
    abstract but still have its own listed PI).
    """
    grants = pd.DataFrame([_grant("g_sub", "P41RR000862-6313", 2008)])
    records = [
        {"core_project_num": "P41RR000862", "project_num": "P41RR000862-6313",
         "subproject_id": "6313", "fiscal_year": 2008, "abstract_text": "",
         "organization": {"org_name": "Some Other University"},
         "principal_investigators": [{"full_name": "Real Subproject PI", "is_contact_pi": True}]},
        {"core_project_num": "P41RR000862", "project_num": "P41RR000862",
         "subproject_id": None, "fiscal_year": 2008,
         "abstract_text": "parent center description",
         "organization": {"org_name": "Some Other University"},
         "principal_investigators": [{"full_name": "Center Director", "is_contact_pi": True}]},
    ]
    result = match_grants(grants, records)
    assert result["abstracts"].iloc[0]["abstract_source"] == "nih_reporter_parent"
    inv = result["investigators"]
    assert list(inv["full_name"]) == ["Real Subproject PI"]


@pytest.mark.parametrize("p_sub,sub_id,want_sub,expected_rank", [
    ("6313", "6313", True, 0),   # exact subproject match
    (None, "6313", True, 1),     # core-level fallback
    ("9999", "6313", True, 2),   # a different, unrelated subproject
    (None, None, False, 0),      # core-level, correctly requested
    ("9001", None, False, 1),    # subproject used for a whole-center grant
])
def test_granularity_rank_orders_as_documented(p_sub, sub_id, want_sub, expected_rank):
    assert _granularity_rank(p_sub, sub_id, want_sub) == expected_rank
