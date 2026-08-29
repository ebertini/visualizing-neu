"""Regression tests for src/classify_by_keywords.py (Phase 4b BM25F scorer).

Uses tiny synthetic taxonomies + a monkeypatched corpus so these run in
milliseconds and don't depend on the real curated taxonomy or corpus being
present. Corpora are padded with realistic-length filler docs so N (corpus
size) stays sane relative to the df_corpus values used — a term's df_corpus
can never exceed the corpus size it was measured over, and an unrealistic
N/df ratio floors idf to 0 (see test_classify_by_keywords's floor logic),
which would make these tests assert on a degenerate case instead of the
real one.

Run:  pytest tests/test_classify_by_keywords.py
"""
import pytest

import src.classify_by_keywords as cbk

N_FILLER = 500
FILLER_ABSTRACT = " ".join(["filler"] * 50)  # a "typical" 50-token doc


def _kw(term, df_corpus, weight=1.0):
    return {"term": term, "weight": weight, "df_corpus": df_corpus}


def _leaf(label, parent, keywords, negative=None):
    return {"label": label, "parent": parent, "keywords": keywords,
            "negative_keywords": negative or []}


def _padded_corpus(real_ids, real_titles, real_abstracts):
    """Prepend N_FILLER realistic-length, non-matching filler docs so the
    corpus size (N) and average length (L_avg) are realistic, then the real
    docs under test."""
    filler_ids = [f"filler{i}" for i in range(N_FILLER)]
    filler_titles = [""] * N_FILLER
    filler_abstracts = [FILLER_ABSTRACT] * N_FILLER
    return (filler_ids + real_ids, filler_titles + real_titles, filler_abstracts + real_abstracts)


@pytest.fixture(autouse=True)
def _no_bertopic_join(monkeypatch):
    # Real topic_assignments.parquet (if present locally) would join on doc_id
    # and find nothing for these synthetic ids anyway, but skip it explicitly
    # so these tests don't depend on local pipeline state at all.
    monkeypatch.setattr(cbk, "PROC", cbk.PROC.parent / "__no_such_dir__")


def test_length_normalization_title_beats_longer_abstract(monkeypatch):
    """The plan's own named regression case: a short title containing one
    high-idf (rare) curated term must outrank a long abstract containing one
    low-idf (common) term — the direct proof the BM25F length term is doing
    its job, not just present in the formula."""
    leaves = {
        "0": _leaf("Rare-term leaf", "P0", [_kw("gravitino", df_corpus=5)]),
        "1": _leaf("Common-term leaf", "P0", [_kw("system", df_corpus=200)]),
    }
    parents = {"P0": {"label": "Physics", "leaf_ids": ["0", "1"]}}

    long_abstract = " ".join(["system"] + ["filler"] * 248)  # ~250 tokens, 1 hit
    ids, titles, abstracts = _padded_corpus(
        ["A", "B"],
        ["Gravitino production", ""],  # A: ~2-token title, 1 rare-term hit
        ["", long_abstract],           # B: ~250-token abstract, 1 common-term hit
    )

    monkeypatch.setattr(cbk, "load_doc_fields", lambda: (ids, titles, abstracts))
    df = cbk.classify(leaves, parents)

    doc_a = df[df["doc_id"] == "A"].iloc[0]
    doc_b = df[df["doc_id"] == "B"].iloc[0]
    assert doc_a["kw_leaf_id"] == 0
    assert doc_b["kw_leaf_id"] == 1
    assert doc_a["score1"] > 0 and doc_b["score1"] > 0
    assert doc_a["score1"] > doc_b["score1"], (
        "a 2-token title hit on a rare (high-idf) term should outscore a "
        "250-token abstract hit on a common (low-idf) term once the title "
        "weight and length normalization are both applied correctly"
    )


def test_unassigned_reasons(monkeypatch):
    leaves = {"0": _leaf("Only leaf", "P0", [_kw("neurons", df_corpus=50)])}
    parents = {"P0": {"label": "Bio", "leaf_ids": ["0"]}}

    ids, titles, abstracts = _padded_corpus(
        ["empty", "placeholder", "no_evidence", "matched"],
        ["", "Grant", "Something else entirely", "Neurons study"],
        ["", "", "totally unrelated boilerplate text", ""],
    )

    monkeypatch.setattr(cbk, "load_doc_fields", lambda: (ids, titles, abstracts))
    df = cbk.classify(leaves, parents).set_index("doc_id")

    assert df.loc["empty", "unassigned_reason"] == "no_usable_text"
    assert df.loc["placeholder", "unassigned_reason"] == "placeholder_title_only"
    assert df.loc["no_evidence", "unassigned_reason"] == "no_keyword_evidence"
    assert df.loc["matched", "unassigned_reason"] is None
    assert df.loc["matched", "kw_leaf_id"] == 0
    assert df.loc["matched", "conf_tier"] != "none"
    for doc_id in ["empty", "placeholder", "no_evidence"]:
        assert df.loc[doc_id, "kw_leaf_id"] == -1
        assert df.loc[doc_id, "conf_tier"] == "none"


def test_ultra_common_term_floors_to_no_keyword_evidence(monkeypatch):
    """A term whose df_corpus is so high its BM25 idf floors to 0 carries no
    real evidence — a doc matching only that term must be treated the same
    as no match at all (unassigned), not spuriously handed a leaf label."""
    leaves = {"0": _leaf("Leaf", "P0", [_kw("common", df_corpus=N_FILLER + 10)])}
    parents = {"P0": {"label": "P", "leaf_ids": ["0"]}}
    ids, titles, abstracts = _padded_corpus(["x"], ["Common study"], [""])

    monkeypatch.setattr(cbk, "load_doc_fields", lambda: (ids, titles, abstracts))
    df = cbk.classify(leaves, parents).set_index("doc_id")
    assert df.loc["x", "unassigned_reason"] == "no_keyword_evidence"
    assert df.loc["x", "kw_leaf_id"] == -1


def test_limit_does_not_change_idf_or_length_normalization(monkeypatch):
    """Regression for a real bug: --limit must only reduce which docs get
    SCORED, never shrink N (the BM25 idf formula's corpus size) or L_avg —
    both must stay computed over the full doc set, since df_corpus is a
    fixed stat from the full corpus regardless of how many docs this run
    actually scores."""
    leaves = {"0": _leaf("Leaf", "P0", [_kw("neurons", df_corpus=50)])}
    parents = {"P0": {"label": "Bio", "leaf_ids": ["0"]}}

    ids, titles, abstracts = _padded_corpus(
        ["doc0"], ["Neurons study"], [""],
    )

    monkeypatch.setattr(cbk, "load_doc_fields", lambda: (ids, titles, abstracts))
    full = cbk.classify(leaves, parents)
    # doc0 is the last doc (index N_FILLER); limit exactly at it so it's
    # still scored, but under a truncated apparent doc count.
    limited = cbk.classify(leaves, parents, limit=N_FILLER + 1)

    score_full = full[full["doc_id"] == "doc0"].iloc[0]["score1"]
    score_limited = limited[limited["doc_id"] == "doc0"].iloc[0]["score1"]
    assert score_full > 0
    assert score_full == pytest.approx(score_limited), (
        "scoring the same doc with a truncating --limit vs. no limit must "
        "give an identical score — N and L_avg must not depend on how many "
        "docs this run happens to score"
    )


def test_matched_terms_scoped_to_winning_leaf_only(monkeypatch):
    leaves = {
        "0": _leaf("Leaf A", "P0", [_kw("alpha", df_corpus=50)]),
        "1": _leaf("Leaf B", "P0", [_kw("beta", df_corpus=50)]),
    }
    parents = {"P0": {"label": "P", "leaf_ids": ["0", "1"]}}
    ids, titles, abstracts = _padded_corpus(["x"], ["alpha alpha alpha beta"], [""])

    monkeypatch.setattr(cbk, "load_doc_fields", lambda: (ids, titles, abstracts))
    df = cbk.classify(leaves, parents).set_index("doc_id")
    row = df.loc["x"]
    assert row["kw_leaf_id"] == 0
    assert row["matched_terms"] == ["alpha"]
    assert "beta" not in row["matched_terms"]


def test_curated_to_topic_labels_schema():
    leaves = {
        "0": {"label": "Leaf Zero", "parent": "P0",
              "keywords": [_kw("alpha", 10), _kw("beta", 20)]},
        "1": {"label": "Leaf One", "parent": "P0", "keywords": [_kw("gamma", 5)]},
    }
    parents = {"P0": {"label": "Parent Zero", "leaf_ids": ["0", "1"]}}
    out = cbk.curated_to_topic_labels(leaves, parents)

    assert out["_meta"]["n_topics"] == 2
    assert "-1" in out["topics"]
    assert out["topics"]["0"]["top_terms"] == ["alpha", "beta"]
    assert out["parents"]["P0"]["topic_ids"] == [0, 1]
