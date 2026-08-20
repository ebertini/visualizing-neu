"""Award-number normalizer + matching regression tests for
src/backfill_nsf_awards.py. Covers the leading-zero loss and null-id gaps
found while sizing the NSF Award Search backfill (companion to
src/backfill_nih_reporter.py, M5a of docs/TOPIC_WORK_FORWARD_PLAN.md).

Run:  pytest tests/test_backfill_nsf_awards.py
"""
import pandas as pd
import pytest

from src.backfill_nsf_awards import (
    _co_pdpi_to_first_last,
    extract_investigators,
    fetch_by_org_year,
    match_by_fuzzy_title,
    match_by_id,
    normalize_nsf_award_num,
)

# (raw agencygrantid, expected padded id, expected confidence) — real samples
# from data/processed/grants.parquet's NSF agencygrantid column.
REAL_SAMPLES = [
    ("2212537", "2212537", "exact"),
    ("853685", "0853685", "padded_high"),
    ("227577", "0227577", "padded_high"),
    ("532387", "0532387", "padded_high"),
    ("93752", "0093752", "padded_low"),
    ("96543", "0096543", "padded_low"),
]


@pytest.mark.parametrize("raw,padded,confidence", REAL_SAMPLES)
def test_normalize_real_samples(raw, padded, confidence):
    assert normalize_nsf_award_num(raw) == (padded, confidence)


def test_normalize_handles_float_coercion_artifact():
    # pandas reads a numeric-looking Excel column as float64; str(853685.0)
    # == "853685.0" -- the ".0" must be stripped before padding.
    assert normalize_nsf_award_num(853685.0) == ("0853685", "padded_high")
    assert normalize_nsf_award_num("853685.0") == ("0853685", "padded_high")


@pytest.mark.parametrize("raw", [None, float("nan"), "", "not-a-number", "12345678", "1234"])
def test_normalize_rejects_invalid(raw):
    assert normalize_nsf_award_num(raw) == (None, "invalid")


# Real coPDPI strings, sampled from a live api.nsf.gov response: always
# "First [Middle] Last[, Suffix] email@domain", never "Last, First" (that
# shape was a pre-live-verification guess and never actually occurs).
@pytest.mark.parametrize("raw,expected", [
    ("Mario Sznaier msznaier@coe.neu.edu", "Mario Sznaier"),
    ("J Timothy T Sage jtsage@neu.edu", "J Timothy T Sage"),
    ("Tomasz R Taylor (Former) taylor@neu.edu", "Tomasz R Taylor"),
    ("Albert Sacco, Jr. asacco@coe.neu.edu", "Albert Sacco"),
    ("Charles A DiMarzio dimarzio@ece.neu.edu", "Charles A DiMarzio"),
])
def test_co_pdpi_real_live_samples(raw, expected):
    assert _co_pdpi_to_first_last(raw) == expected


def test_co_pdpi_handles_empty():
    assert _co_pdpi_to_first_last("") == ""
    assert _co_pdpi_to_first_last(None) == ""


def test_extract_investigators_pi_and_copdpi():
    rec = {"piFirstName": "Jane", "piLastName": "Doe",
           "coPDPI": ["John Smith jsmith@example.edu", "Amy Lee alee@example.edu"]}
    rows = extract_investigators(rec)
    assert rows[0] == {"full_name": "Jane Doe", "is_contact_pi": True, "rank_order": 0}
    assert rows[1] == {"full_name": "John Smith", "is_contact_pi": False, "rank_order": 1}
    assert rows[2] == {"full_name": "Amy Lee", "is_contact_pi": False, "rank_order": 2}


def test_extract_investigators_handles_missing_pi_name():
    assert extract_investigators({"coPDPI": ["John Smith jsmith@example.edu"]}) == [
        {"full_name": "John Smith", "is_contact_pi": False, "rank_order": 1},
    ]


def test_extract_investigators_strips_suffix_before_surname_extraction():
    """The bug this guards against: taking the final whitespace token as the
    surname (as propose_faculty_matches does) would pick 'Jr.' as the
    surname unless the ', Jr.' suffix is stripped first.
    """
    rows = extract_investigators({"coPDPI": ["Albert Sacco, Jr. asacco@coe.neu.edu"]})
    assert rows[0]["full_name"].split()[-1] == "Sacco"


def _grant(grant_id, agencygrantid):
    return {"grant_id": grant_id, "agencygrantid": agencygrantid}


def test_match_by_id_pads_before_matching():
    grants = pd.DataFrame([_grant("g1", "853685")])
    records = [{"id": "0853685", "title": "Soil remediation", "abstractText": "some text",
                "awardeeName": "Northeastern University"}]
    result = match_by_id(grants, records)
    assert len(result["abstracts"]) == 1
    assert result["abstracts"][0]["award_num"] == "0853685"
    assert result["abstracts"][0]["match_score"] == 100


def test_match_by_id_flags_low_confidence_five_digit_padding():
    grants = pd.DataFrame([_grant("g1", "93752")])
    records = [{"id": "0093752", "title": "x", "abstractText": "text", "awardeeName": "NEU"}]
    result = match_by_id(grants, records)
    assert result["low_confidence"] == ["g1"]


def test_match_by_id_reports_unmatched_when_no_abstract():
    grants = pd.DataFrame([_grant("g1", "2212537")])
    records = [{"id": "2212537", "title": "x", "abstractText": "", "awardeeName": "NEU"}]
    result = match_by_id(grants, records)
    assert result["abstracts"] == []
    assert result["unmatched"] == ["2212537"]


def test_match_by_fuzzy_title_accepts_strong_match_only():
    grants = pd.DataFrame([{
        "grant_id": "g1",
        "grantname": "CAREER: An information-theoretic approach to network coding",
        "startdateyear": 2004,
    }])
    strong = {"id": "1234567",
              "title": "CAREER: An information theoretic approach to network coding",
              "abstractText": "abstract text", "awardeeName": "NEU", "startDate": "01/01/2004"}
    weak = {"id": "7654321", "title": "Totally unrelated study of soil chemistry",
            "abstractText": "other text", "awardeeName": "NEU", "startDate": "01/01/2004"}
    result = match_by_fuzzy_title(grants, [weak, strong])
    assert len(result["abstracts"]) == 1
    assert result["abstracts"][0]["award_num"] == "1234567"
    assert result["near_misses"] == []


def test_match_by_fuzzy_title_reports_near_miss_without_adopting():
    grants = pd.DataFrame([{
        "grant_id": "g1", "grantname": "Studies of quantum chaos", "startdateyear": 2003,
    }])
    near = {"id": "1111111", "title": "Studies of quantum systems", "abstractText": "text",
            "awardeeName": "NEU", "startDate": "01/01/2003"}
    result = match_by_fuzzy_title(grants, [near])
    assert result["abstracts"] == []
    assert len(result["near_misses"]) == 1
    assert result["near_misses"][0][0] == "g1"


class _FakeResponse:
    def __init__(self, awards):
        self._awards = awards

    def raise_for_status(self):
        pass

    def json(self):
        return {"response": {"award": self._awards}}


class _FakeSession:
    """Records every `.get` call's params instead of hitting the network."""
    def __init__(self, pages: list[list[dict]]):
        self._pages = pages
        self.calls: list[dict] = []

    def get(self, url, params, timeout):
        self.calls.append(params)
        page = self._pages[len(self.calls) - 1] if len(self.calls) <= len(self._pages) else []
        return _FakeResponse(page)


def test_fetch_by_org_year_wraps_awardee_name_in_literal_quotes():
    """Live-verified against api.nsf.gov: an UNQUOTED multi-word awardeeName
    is silently ignored (returns unfiltered nationwide results, no error) --
    caught by inspecting a --limit smoke-test cache before the first full
    run, where "bulk" records came back from UMass/Northwestern/etc, not
    NEU. The value MUST be wrapped in literal double quotes.
    """
    session = _FakeSession(pages=[[]])
    fetch_by_org_year(session, "Northeastern University", 2010, sleep=0)
    assert session.calls[0]["awardeeName"] == '"Northeastern University"'


def test_fetch_by_org_year_stops_on_identical_consecutive_pages():
    """Defends against a differently-misnamed parameter that makes every
    'page' echo the same full-size page regardless of offset -- must bail
    on the second, repeated page rather than looping up to MAX_BULK_PAGES
    times. A short page would already break the loop on its own (the normal
    end-of-results case), so this uses a FULL page (BULK_PAGE_SIZE items) to
    isolate the identical-page detection specifically.
    """
    full_page = [{"id": "1234567", "title": "x"}] * 25
    session = _FakeSession(pages=[full_page, full_page, full_page])
    out = fetch_by_org_year(session, "Northeastern University", 2010, sleep=0)
    assert len(session.calls) == 2  # first page accepted, second (repeat) triggers the bail-out
    assert out == full_page
