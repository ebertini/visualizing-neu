"""Cleaner regression tests (M1 of docs/TOPIC_WORK_FORWARD_PLAN.md).

Five known-bad inputs that used to leak funding-mechanism / markup noise into
the topic model. Each asserts the relevant `src.clean_text` function strips the
junk while keeping the scientific content.

Run:  pytest tests/test_clean_text.py
"""
import pytest

from src.clean_text import (
    clean_abstract,
    clean_document,
    clean_for_lda,
    clean_title,
    passes_length_filter,
)

# (id, raw_title, raw_abstract) — the five historical offenders.
BAD_CASES = [
    (
        "mangled_andlt_andgt",
        "Sensing andlt br/ andgt in networks",
        "We build robots andlt br/ andgt that sense the environment andamp map it "
        "over long horizons using distributed estimation and control techniques.",
    ),
    (
        "nsf_boilerplate",
        "Foundations of adaptive optics",
        "This project develops adaptive optics for large telescopes and novel "
        "wavefront sensors. This award reflects NSF's statutory mission and has "
        "been deemed worthy of support through evaluation using the Foundation's "
        "intellectual merit and broader impacts review criteria.",
    ),
    (
        "leading_id_pi_stub",
        "Computer architecture for data-parallel workloads",
        "9501172  Kaeli, David  This research investigates memory-system design "
        "for throughput-oriented processors and the compiler support required to "
        "exploit them across scientific and machine-learning workloads.",
    ),
    (
        "stacked_program_prefix",
        "CAREER: Collaborative Research: Explorable formal models of privacy policies",
        "The proposal studies formal verification techniques for privacy policy "
        "languages and their application to regulatory compliance across domains.",
    ),
    (
        "html_entities_and_tags",
        "Robots &amp; sensors in the field",
        "<p>Autonomous sensing &amp; actuation <br/> for agricultural robots, with "
        "field trials &amp; long-term autonomy studies over multiple growing "
        "seasons in real deployments.</p>",
    ),
]

IDS = [c[0] for c in BAD_CASES]


@pytest.fixture(params=BAD_CASES, ids=IDS)
def bad_case(request):
    key, title, abstract = request.param
    return {
        "key": key,
        "title": title,
        "abstract": abstract,
        "clean_title": clean_title(title),
        "clean_abstract": clean_abstract(abstract),
        "clean_for_lda": clean_for_lda(abstract),
        "clean_document": clean_document(title, abstract),
    }


def test_no_mangled_markup_survives(bad_case):
    """andlt / andgt / andamp and bare lt/gt/amp residue are gone everywhere."""
    for field in ("clean_title", "clean_abstract", "clean_for_lda", "clean_document"):
        text = bad_case[field].lower()
        for junk in ("andlt", "andgt", "andamp"):
            assert junk not in text, f"{junk!r} leaked into {field} of {bad_case['key']}"
        # bare residue only meaningful as standalone tokens
        assert " lt " not in f" {text} "
        assert " gt " not in f" {text} "
        assert " amp " not in f" {text} "


def test_no_html_entities_or_tags(bad_case):
    for field in ("clean_abstract", "clean_document"):
        text = bad_case[field]
        assert "&amp;" not in text and "&lt;" not in text and "&gt;" not in text
        assert "<br" not in text and "<p>" not in text and "</p>" not in text


def test_nsf_boilerplate_removed():
    cleaned = clean_abstract(BAD_CASES[1][2])
    assert "statutory mission" not in cleaned.lower()
    assert "review criteria" not in cleaned.lower()
    # ...but the science survives
    assert "adaptive optics" in cleaned.lower()
    assert clean_for_lda(BAD_CASES[1][2]).count("nsf") == 0


def test_leading_id_and_pi_stub_removed():
    raw = BAD_CASES[2][2]
    cleaned = clean_abstract(raw)
    assert not cleaned.lstrip().startswith("9501172")
    assert "Kaeli" not in cleaned  # PI stub peeled off
    assert cleaned.lower().startswith("this research investigates")


def test_stacked_program_prefixes_peeled():
    raw_title = BAD_CASES[3][1]
    cleaned = clean_title(raw_title)
    assert not cleaned.upper().startswith("CAREER")
    assert "Collaborative Research" not in cleaned
    assert cleaned.startswith("Explorable formal models")


def test_clean_for_lda_is_letters_only():
    out = clean_for_lda("Grant #1234: CRISPR-based γ-editing, 42% yield (2020)!")
    assert out == out.lower()
    assert all(ch.isalpha() or ch == " " for ch in out)
    assert "1234" not in out and "42" not in out


def test_passes_length_filter_thresholds():
    # Too short (< 200 chars) -> rejected regardless of token count
    assert passes_length_filter("short abstract") is False
    # Long, substantive abstract (>= 200 chars AND >= 40 cleaned tokens) -> accepted
    long_abstract = (
        "This research develops distributed algorithms for multi-robot coordination "
        "in unstructured environments, addressing perception, planning, and control "
        "under communication constraints, with field validation across a range of "
        "agricultural and search-and-rescue scenarios spanning several seasons and sites. "
        "The team studies how heterogeneous teams share belief state, recover from "
        "individual sensor failures, and adapt their formations to changing terrain and "
        "weather while maintaining connectivity and bounded localization error."
    )
    assert len(long_abstract) >= 200
    assert passes_length_filter(long_abstract) is True
