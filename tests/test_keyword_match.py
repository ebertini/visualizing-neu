"""Regression tests for src/keyword_match.py (Phase 4b matching layer).

Run:  pytest tests/test_keyword_match.py
"""
from src.keyword_match import find_matches, match_text, segment_sentences


def _hows(matches):
    return sorted((m.term, m.how) for m in matches)


def test_no_substring_match_inside_a_longer_word():
    # "ion" must not match inside "ionosphere"; "cell" must not match inside
    # "excellent" or "cellular" — the whole point of tokenizing before
    # matching rather than doing a naive substring search.
    text = "We study the ionosphere. Cellular biology is excellent."
    ms = match_text(text, ["ion", "cell"])
    assert ms == []


def test_phrase_word_order_and_contiguity_required():
    text = "This grant funds neural network research."
    assert match_text(text, ["neural network"])
    assert match_text(text, ["network neural"]) == []  # order matters
    assert match_text(text, ["neural research"]) == []  # not contiguous


def test_no_match_across_a_sentence_boundary():
    text = "We study neural circuits. Network science is also relevant."
    # "neural" ends sentence 1, "network" starts sentence 2 — a phrase
    # spanning them must not match even though the words are adjacent in
    # the raw character stream.
    assert match_text(text, ["circuits network"]) == []


def test_collapsed_tier_matches_hyphen_variants_both_ways():
    text_hyphen = "We study COVID-19 outcomes."
    text_plain = "We study covid19 outcomes."
    m1 = match_text(text_hyphen, ["covid19"])
    m2 = match_text(text_plain, ["covid-19"])
    assert len(m1) == 1 and m1[0].how == "collapsed"
    assert len(m2) == 1 and m2[0].how == "collapsed"


def test_collapse_does_not_degenerate_trailing_symbol_to_a_common_word():
    # Regression for a real bug found reviewing curated output: the LIGO-era
    # program name "a+" collapsed to bare "a" (stripping a TRAILING '+' with
    # nothing to bridge on the other side), which then matched the article
    # "a" throughout an unrelated antimicrobial-chemistry grant abstract at
    # "medium" confidence. A trailing/leading symbol must never collapse —
    # only punctuation with alphanumeric content on BOTH sides (like the '-'
    # in "covid-19") is a real bridge.
    text = "We propose a new therapeutic approach to bacterial resistance."
    assert match_text(text, ["a+"]) == []


def test_exact_tier_preferred_over_collapsed_when_both_would_match():
    # The literal written form should match at the "exact" tier, not fall
    # through to a weaker tier just because one exists.
    text = "We study covid19 outcomes."
    ms = match_text(text, ["covid19"])
    assert len(ms) == 1 and ms[0].how == "exact"


def test_stem_tier_folds_plurals():
    text = "This grant supports several neural networks broadly."
    ms = match_text(text, ["neural network"])
    assert len(ms) == 1 and ms[0].how == "stem"


def test_exact_and_stem_occurrences_both_counted_independently():
    text = "This grant funds neural network research and neural networks broadly."
    ms = match_text(text, ["neural network"])
    assert _hows(ms) == [("neural network", "exact"), ("neural network", "stem")]


def test_segment_sentences_handles_empty_and_whitespace():
    assert segment_sentences("") == []
    assert segment_sentences("   ") == []
    assert len(segment_sentences("One. Two. Three.")) == 3


def test_find_matches_terms_of_different_lengths_are_independent():
    sentences = segment_sentences("A wireless sensor network for wireless communication.")
    ms = find_matches(sentences, ["wireless", "wireless sensor network"])
    terms_found = {m.term for m in ms}
    assert "wireless" in terms_found
    assert "wireless sensor network" in terms_found
