"""
classify_by_keywords.py — Phase 4b: the BM25F keyword classifier. Light deps
only (pandas/numpy/stdlib — no torch/bertopic/umap/hdbscan/sklearn), so this
finally runs fully offline and reproducibly, unlike BERTopic.

Naming discipline: every id from the keyword taxonomy is prefixed `kw_`
(`kw_leaf_id`, `kw_parent_id`, `kw_leaf2_id`, `kw_centroid_leaf_id`) — NEVER
bare `topic_id`, since a joined DataFrame also carries BERTopic's own
`topic_id` (a different id space) as `bertopic_topic_id`.

Scoring — BM25F, per docs/... topic-model-redo plan (Phase 4b spec):

    sat(k,d)   = pseudo_tf(k,d)*(k1+1) / (pseudo_tf(k,d) + k1*(1-b+b*L(d)/L_avg))
    idf(k)     = ln(1 + (N - df_k + 0.5)/(df_k + 0.5))
    score(d,leaf) = [sum(w_k*idf(k)*sat(k,d) for k in leaf.keywords)
                     - sum(w_k*idf(k)*sat(k,d) for k in leaf.negative_keywords)]
                    / (sum(w_k*idf(k) for k in leaf.keywords)) ** alpha

`pseudo_tf(k,d) = W_TITLE*tf_title(k,d) + tf_abstract(k,d)` and
`L(d) = W_TITLE*len_title_tokens(d) + len_abstract_tokens(d)` — title tokens
are weighted BEFORE both saturation and length, so W_TITLE can't silently
re-break the length normalization it's meant to help (a title-only doc's
pseudo_tf/L(d) ratio is unaffected by W_TITLE, since it cancels out).

K1/B/ALPHA/W_TITLE below are literature-standard Okapi BM25 defaults, NOT
calibrated against this corpus — the plan is explicit that calibration
against a gold set is Step 3's job, not guessed here. Likewise the conf_tier
thresholds are a provisional placeholder pending that calibration.

`df_corpus` per curated term is read from the already-curated
`outputs/topic_keywords.json` (itself populated from
`outputs/kw_vocab_candidates.json` at curation time) rather than recomputed
by rescanning the corpus — cheaper, and ties every run to the same discovery
numbers that informed which terms got curated in the first place. `idf` is
NOT reused from that same candidates file: its stored `idf` field is a
different, explicitly-diagnostic-only sklearn-style smoothed IDF
(`kw_vocab_discover.py`'s own comment), not this module's Okapi-style
formula — reusing it under the wrong assumed meaning would repeat the
`titleOnly`/`modelTitleOnly` mistake (CLAUDE.md: "redefining an existing
field's meaning is riskier than it looks"). idf is recomputed here, from the
reused df_corpus, via the formula above.

Run:
    python3 -m src.classify_by_keywords                    # the real curated taxonomy
    python3 -m src.classify_by_keywords --from-topic-labels # bootstrap from the 32-topic
                                                             # BERTopic labels (decouples
                                                             # testing from curation)
    python3 -m src.classify_by_keywords --emit-topic-labels # schema-convert the CURATED
                                                             # file to topic_labels.json's
                                                             # shape and print it (does not
                                                             # touch the real, live
                                                             # outputs/topic_labels.json —
                                                             # that swap is a deliberate,
                                                             # separate downstream-
                                                             # integration step)
    python3 -m src.classify_by_keywords --limit 50          # smoke test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.clean_text import clean_title
    from src.keyword_match import match_text, segment_sentences  # noqa: F401 (re-exported for tests)
    from src.kw_curation import check as kw_curation_check
    from src.kw_vocab import tokenize
    from src.model_docs import load_doc_fields
    from src.topic_keywords import CURATED_PATH
except ImportError:  # run from within src/
    from clean_text import clean_title
    from keyword_match import match_text, segment_sentences  # noqa: F401
    from kw_curation import check as kw_curation_check
    from kw_vocab import tokenize
    from model_docs import load_doc_fields
    from topic_keywords import CURATED_PATH

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = REPO_ROOT / "outputs"
PROC = REPO_ROOT / "data" / "processed"
TOPIC_LABELS_PATH = OUTPUTS / "topic_labels.json"
CANDIDATES_PATH = OUTPUTS / "kw_vocab_candidates.json"
OUTPUT_PATH = PROC / "topic_keyword_assignments.parquet"

# BM25F constants — literature-standard Okapi defaults, provisional pending
# Step 3 gold-set calibration (see module docstring).
K1 = 1.5
B = 0.75
ALPHA = 0.5  # pivoted list-length normalization exponent
W_TITLE = 2.0

# A BERTopic-legacy concept (the ONR placeholder-title artifact cluster,
# formerly topic 11, now 14) — kept None-safe here the same way
# kw_review_sheet.py is, since Step 4 of the redo plan retires it elsewhere.
ARTIFACT_TOPIC_ID = 14

# Cleaned titles that carry literally no information (the 28 ONR "Grant"
# records this redesign explicitly can't do better on than BERTopic did) —
# matched case-insensitively after clean_title() + trailing-punctuation strip.
PLACEHOLDER_TITLES = frozenset({"grant", "research", "project", "award"})

# Provisional conf_tier thresholds — pending Step 3 gold-set calibration
# (the plan is explicit these should come from where accuracy flattens
# against margin_rel, not be guessed; these are a placeholder so the pipeline
# is runnable end-to-end before that calibration exists).
HIGH_MARGIN_REL = 0.5
HIGH_MIN_TERMS = 3
MEDIUM_MARGIN_REL = 0.2
MEDIUM_MIN_TERMS = 1


# ──────────────────────────────────────────────────────────────────────────
# Taxonomy loading
# ──────────────────────────────────────────────────────────────────────────

def _check_candidates_fingerprint(curated: dict) -> None:
    fp = curated.get("_meta", {}).get("candidates_fingerprint")
    if not fp or not CANDIDATES_PATH.exists():
        return
    actual = hashlib.sha256(CANDIDATES_PATH.read_bytes()).hexdigest()
    if actual != fp.get("hash"):
        print(f"WARNING: {CANDIDATES_PATH.name} has changed since the curated "
              f"taxonomy's df_corpus/idf values were populated from it "
              f"(_meta.candidates_fingerprint mismatch) — df_corpus for curated "
              f"terms may be stale relative to the current candidates file.")


def load_curated_taxonomy(path: Path = CURATED_PATH) -> tuple[dict, dict]:
    """Load + validate outputs/topic_keywords.json via the SAME gate
    `kw_curation.py --check` uses (reused, not re-derived, so this can never
    silently accept a taxonomy the curation gate itself would reject)."""
    data = json.loads(path.read_text())
    errors, warnings = kw_curation_check(data)
    if errors:
        raise ValueError(
            f"{path} fails kw_curation.check() with {len(errors)} error(s) — "
            "not a genuinely curated taxonomy:\n" + "\n".join(errors)
        )
    for w in warnings:
        print(f"WARN (from kw_curation.check): {w}")
    _check_candidates_fingerprint(data)

    leaves = {lid: leaf for lid, leaf in data["leaves"].items() if leaf.get("status") != "draft"}
    parents = {pid: p for pid, p in data["parents"].items() if p.get("status") != "draft"}
    return leaves, parents


def load_bootstrap_taxonomy(path: Path = TOPIC_LABELS_PATH) -> tuple[dict, dict]:
    """`--from-topic-labels`: synthesize a keyword-taxonomy-shaped structure
    from the EXISTING BERTopic `outputs/topic_labels.json` (32 topics' own
    c-TF-IDF top_terms, weight=1.0), so this classifier's scoring path,
    output schema, and tests can all be built/run without waiting on a
    finished curation pass. `df_corpus` is unknown for these terms (this
    file never recorded it) — computed here by a one-time corpus scan
    instead of trusting a curated value that doesn't exist yet."""
    labels = json.loads(path.read_text())
    ids, titles, abstracts = load_doc_fields()
    all_terms = sorted({t for topic in labels["topics"].values() for t in topic.get("top_terms", [])})
    df_counts = Counter()
    for title, abstract in zip(titles, abstracts):
        matched_here = {m.term for m in match_text(title, all_terms)} | \
                       {m.term for m in match_text(abstract, all_terms)}
        df_counts.update(matched_here)

    leaves = {}
    for tid, topic in labels["topics"].items():
        if tid == "-1":
            continue
        leaves[tid] = {
            "label": topic["label"],
            "status": "bootstrap",
            "parent": topic.get("parent"),
            "notes": "bootstrap from outputs/topic_labels.json — not curated",
            "keywords": [
                {"term": t, "weight": 1.0, "df_corpus": max(df_counts.get(t, 0), 1)}
                for t in topic.get("top_terms", [])
            ],
            "negative_keywords": [],
        }
    parents = {}
    for pid, p in labels.get("parents", {}).items():
        parents[pid] = {
            "label": p["label"],
            "status": "bootstrap",
            "notes": "bootstrap from outputs/topic_labels.json — not curated",
            "leaf_ids": [str(t) for t in p.get("topic_ids", [])],
        }
    return leaves, parents


# ──────────────────────────────────────────────────────────────────────────
# topic_keywords.json <-> topic_labels.json schema converter (Step 2e)
# ──────────────────────────────────────────────────────────────────────────

def curated_to_topic_labels(leaves: dict, parents: dict) -> dict:
    """The `--emit-topic-labels` conversion: curated taxonomy -> the shape
    `outputs/topic_labels.json` needs (src/build_viz_data.py's only consumer
    of that file). NOT applied to the live file by this script — see the
    module docstring; wiring it in is a deliberate, separate downstream-
    integration step once Step 3 validation has run."""
    topics = {}
    for lid, leaf in leaves.items():
        top_terms = [kw["term"] for kw in leaf.get("keywords", [])][:10]
        topics[lid] = {"label": leaf["label"], "top_terms": top_terms, "parent": leaf.get("parent")}
    topics["-1"] = {"label": "Unassigned", "top_terms": [], "parent": None}

    out_parents = {}
    for pid, p in parents.items():
        out_parents[pid] = {
            "label": p["label"],
            "topic_ids": sorted(int(lid) for lid in p.get("leaf_ids", [])),
        }
    return {"_meta": {"n_topics": len(leaves)}, "topics": topics, "parents": out_parents}


# ──────────────────────────────────────────────────────────────────────────
# BM25F scoring
# ──────────────────────────────────────────────────────────────────────────

def _clean_placeholder_title(title: str) -> str:
    return clean_title(title).strip().rstrip(".!").strip().lower()


def _bm25_idf(df: int, n_docs: int) -> float:
    # Floored at 0: classic Okapi BM25 idf goes negative for a term appearing
    # in more than ~half the corpus, which would otherwise make matching an
    # ultra-common word SUBTRACT from a leaf's score — an unintended side
    # effect of the formula, not the deliberate exclusion negative_keywords
    # exists for. Also guards the math-domain error if df_corpus (computed
    # once at discovery time over the full corpus) is ever paired with a
    # smaller n_docs than it was computed against (corpus drift).
    x = 1 + (n_docs - df + 0.5) / (df + 0.5)
    return max(math.log(x), 0.0) if x > 0 else 0.0


def _sat(pseudo_tf: float, doc_len: float, avg_len: float) -> float:
    if pseudo_tf <= 0:
        return 0.0
    denom = pseudo_tf + K1 * (1 - B + B * (doc_len / avg_len if avg_len else 0.0))
    return pseudo_tf * (K1 + 1) / denom if denom else 0.0


def _term_idf_table(leaves: dict, n_docs: int) -> dict[str, float]:
    """term -> idf, deduped across leaves (df_corpus is a corpus-wide stat so
    two leaves sharing a term should agree; the first value seen wins, with a
    loud warning if they disagree)."""
    df_by_term: dict[str, int] = {}
    for leaf in leaves.values():
        for kw in list(leaf.get("keywords", [])) + list(leaf.get("negative_keywords", [])):
            term, df = kw["term"], kw.get("df_corpus")
            if df is None:
                continue
            if term in df_by_term and df_by_term[term] != df:
                print(f"WARNING: term '{term}' has conflicting df_corpus across leaves "
                      f"({df_by_term[term]} vs {df}) — keeping the first seen.")
                continue
            df_by_term[term] = df
    return {term: _bm25_idf(df, n_docs) for term, df in df_by_term.items()}


def _leaf_norm(leaf: dict, idf: dict[str, float]) -> float:
    total = sum(kw.get("weight", 1.0) * idf.get(kw["term"], 0.0) for kw in leaf.get("keywords", []))
    return total ** ALPHA if total > 0 else 1.0


def match_corpus(leaves: dict, ids: list[str], titles: list[str], abstracts: list[str]) -> list[dict]:
    """The expensive, CONSTANT-INVARIANT half of `classify()`: run `match_text`
    for every doc against every curated term once. Nothing here depends on
    K1/B/ALPHA/W_TITLE or the conf_tier thresholds — only on the taxonomy's
    term list and the corpus text — so a sweep over those constants (see
    `src/tune_bm25f.py`) should call this ONCE and reuse the result, rather
    than re-running match_text (the ~30s-per-run cost) per grid point.

    Returns one dict per doc, in `ids` order: `{doc_id, title, abstract,
    tf_title, tf_abstract, how_seen, tok_title_len, tok_abstract_len,
    has_text}` — everything `score_corpus` below needs, and nothing more.
    """
    all_terms = sorted({kw["term"] for leaf in leaves.values()
                         for kw in list(leaf.get("keywords", [])) + list(leaf.get("negative_keywords", []))})
    out = []
    for did, title, abstract in zip(ids, titles, abstracts):
        tok_title = tokenize(title)
        tok_abstract = tokenize(abstract)
        matches_title = match_text(title, all_terms) if all_terms and title else []
        matches_abstract = match_text(abstract, all_terms) if all_terms and abstract else []
        tf_title = Counter(m.term for m in matches_title)
        tf_abstract = Counter(m.term for m in matches_abstract)
        how_seen: dict[str, set[str]] = {}
        for m in matches_title + matches_abstract:
            how_seen.setdefault(m.term, set()).add(m.how)
        out.append({
            "doc_id": did, "title": title, "abstract": abstract,
            "tf_title": tf_title, "tf_abstract": tf_abstract, "how_seen": how_seen,
            "tok_title_len": len(tok_title), "tok_abstract_len": len(tok_abstract),
            "has_text": bool(tok_title) or bool(tok_abstract),
        })
    return out


def score_corpus(match_results: list[dict], leaves: dict, parents: dict,
                  n_docs_full: int, match_results_full: list[dict] | None = None) -> pd.DataFrame:
    """The cheap, CONSTANT-DEPENDENT half of `classify()`: given `match_corpus`'s
    cached per-doc matches, compute doc lengths/idf/leaf scores/conf_tier
    using the CURRENT values of the module-level K1/B/ALPHA/W_TITLE and
    HIGH_MARGIN_REL/HIGH_MIN_TERMS/MEDIUM_MARGIN_REL/MEDIUM_MIN_TERMS — so a
    sweep can vary those (module globals, same pattern the test suite already
    uses via monkeypatch) and re-call this function cheaply, without
    re-matching. `classify()` itself is unchanged behaviorally; it now just
    calls `match_corpus` then this.

    `match_results_full` (defaulting to `match_results` itself) is the FULL,
    unlimited corpus's match results, used ONLY to compute L_avg — mirrors
    `classify()`'s original contract that a `--limit` smoke-test subset must
    not change the corpus-wide average length (or N) the curated terms' fixed
    df_corpus values were computed against; see
    test_limit_does_not_change_idf_or_length_normalization.
    """
    full = match_results_full if match_results_full is not None else match_results
    doc_lens_full = [W_TITLE * m["tok_title_len"] + m["tok_abstract_len"] for m in full]
    avg_len = (sum(doc_lens_full) / n_docs_full) if n_docs_full else 0.0

    idf = _term_idf_table(leaves, n_docs_full)
    leaf_norms = {lid: _leaf_norm(leaf, idf) for lid, leaf in leaves.items()}
    leaf_ids_sorted = sorted(leaves.keys(), key=int)

    rows = []
    for m in match_results:
        doc_len = W_TITLE * m["tok_title_len"] + m["tok_abstract_len"]
        did, title = m["doc_id"], m["title"]
        tf_title, tf_abstract, how_seen = m["tf_title"], m["tf_abstract"], m["how_seen"]

        # no_usable_text is the only reason decided up front — everything
        # else (placeholder_title_only, no_keyword_evidence) is decided
        # AFTER scoring, from score1 itself, not from whether a term merely
        # matched literally: a matched term whose idf floors to 0 (an
        # ultra-common word) carries zero real evidence, and should be
        # treated the same as no match at all, not spuriously hand a doc to
        # whichever leaf happens to own that now-worthless term.
        unassigned_reason = "no_usable_text" if not m["has_text"] else None

        total_matched_terms = set(tf_title) | set(tf_abstract)

        sat_by_term = {}
        for term in total_matched_terms:
            pseudo_tf = W_TITLE * tf_title.get(term, 0) + tf_abstract.get(term, 0)
            sat_by_term[term] = _sat(pseudo_tf, doc_len, avg_len)

        scores = {}
        for lid, leaf in leaves.items():
            pos = sum(kw.get("weight", 1.0) * idf.get(kw["term"], 0.0) * sat_by_term.get(kw["term"], 0.0)
                      for kw in leaf.get("keywords", []))
            neg = sum(kw.get("weight", 1.0) * idf.get(kw["term"], 0.0) * sat_by_term.get(kw["term"], 0.0)
                      for kw in leaf.get("negative_keywords", []))
            scores[lid] = (pos - neg) / leaf_norms[lid]

        ranked = sorted(leaf_ids_sorted, key=lambda lid: (-scores[lid], int(lid)))
        lid1, lid2 = ranked[0], ranked[1] if len(ranked) > 1 else ranked[0]
        score1, score2 = scores[lid1], scores[lid2]

        if unassigned_reason is None:
            if not m["tok_abstract_len"] and _clean_placeholder_title(title) in PLACEHOLDER_TITLES:
                unassigned_reason = "placeholder_title_only"
            elif score1 <= 0:
                unassigned_reason = "no_keyword_evidence"

        if unassigned_reason is not None:
            kw_leaf_id, kw_leaf_label, kw_parent_id, kw_parent_label = -1, "Unassigned", None, None
            score1 = score2 = 0.0
            margin_abs = margin_rel = 0.0
            n_terms_matched, coverage = 0, 0.0
            matched_terms, matched_detail = [], []
            conf_tier = "none"
        else:
            leaf1 = leaves[lid1]
            kw_leaf_id, kw_leaf_label = int(lid1), leaf1["label"]
            kw_parent_id = leaf1.get("parent")
            kw_parent_label = parents.get(kw_parent_id, {}).get("label") if kw_parent_id else None
            margin_abs = score1 - score2
            margin_rel = (margin_abs / score1) if score1 else 0.0

            leaf1_terms = {kw["term"] for kw in leaf1.get("keywords", [])}
            matched_terms = sorted(leaf1_terms & total_matched_terms)
            n_terms_matched = len(matched_terms)
            coverage = n_terms_matched / len(leaf1_terms) if leaf1_terms else 0.0
            matched_detail = [
                {
                    "term": term,
                    "tf_title": tf_title.get(term, 0),
                    "tf_abstract": tf_abstract.get(term, 0),
                    "how": sorted(how_seen.get(term, set()), key=lambda h: {"exact": 0, "collapsed": 1, "stem": 2}[h])[0],
                    "idf": round(idf.get(term, 0.0), 4),
                    "contrib": round(next(kw["weight"] for kw in leaf1["keywords"] if kw["term"] == term)
                                      * idf.get(term, 0.0) * sat_by_term.get(term, 0.0), 4),
                }
                for term in matched_terms
            ]

            # score1 > 0 is guaranteed here — score1 <= 0 was already routed
            # to unassigned_reason="no_keyword_evidence" above.
            if margin_rel >= HIGH_MARGIN_REL and n_terms_matched >= HIGH_MIN_TERMS:
                conf_tier = "high"
            elif margin_rel >= MEDIUM_MARGIN_REL and n_terms_matched >= MEDIUM_MIN_TERMS:
                conf_tier = "medium"
            else:
                conf_tier = "low"

        rows.append({
            "doc_id": did,
            "is_extra": did.startswith("orphan-"),
            "kw_leaf_id": kw_leaf_id,
            "kw_leaf_label": kw_leaf_label,
            "kw_parent_id": kw_parent_id,
            "kw_parent_label": kw_parent_label,
            "score1": score1,
            "score2": score2,
            "kw_leaf2_id": int(lid2) if unassigned_reason is None else None,
            "margin_abs": margin_abs,
            "margin_rel": margin_rel,
            "coverage": coverage,
            "n_terms_matched": n_terms_matched,
            "conf_tier": conf_tier,
            "matched_terms": matched_terms,
            "matched_detail_json": json.dumps(matched_detail),
            "unassigned_reason": unassigned_reason,
            "tie_broken_by": None,
        })

    return pd.DataFrame(rows)


def classify(leaves: dict, parents: dict, limit: int | None = None,
             tiebreak: str = "none") -> pd.DataFrame:
    ids, titles, abstracts = load_doc_fields()
    n_docs_full = len(ids)  # the BM25 N — MUST be the corpus df_corpus was
    # computed against, never shrunk by --limit (a smoke-test convenience for
    # which docs get SCORED, not a redefinition of the corpus those fixed
    # per-term document-frequency stats describe).

    # match_corpus tokenizes + matches over the FULL doc set before any
    # --limit slicing, so a smoke-test subset can't silently change L_avg (or
    # N above) out from under the curated terms' fixed df_corpus values.
    match_results_full = match_corpus(leaves, ids, titles, abstracts)
    match_results = match_results_full[:limit] if limit else match_results_full

    df = score_corpus(match_results, leaves, parents, n_docs_full, match_results_full=match_results_full)
    ids = df["doc_id"].tolist()
    _attach_bertopic_columns(df)
    if tiebreak == "embedding":
        _attach_embedding_tiebreak(df, ids)
    else:
        df["kw_centroid_leaf_id"] = None
        df["centroid_cos1"] = np.nan
        df["centroid_margin"] = np.nan
    return df


def _attach_bertopic_columns(df: pd.DataFrame) -> None:
    """`bertopic_topic_id` (a straight join) + `agrees_with_bertopic`
    (nullable — never False when either side has no label). Agreement is
    computed via a majority-vote crosswalk: for each old BERTopic topic id,
    the most common `kw_leaf_id` among docs BERTopic put in that topic. This
    is a coarse, single-run diagnostic, not the calibrated agreement
    analysis Step 3's validation notebook owns — that step should treat this
    column as a starting point, not a final answer."""
    ta_path = PROC / "topic_assignments.parquet"
    if not ta_path.exists():
        df["bertopic_topic_id"] = None
        df["agrees_with_bertopic"] = None
        return
    ta = pd.read_parquet(ta_path)[["doc_id", "topic_id"]].copy()
    ta["doc_id"] = ta["doc_id"].astype(str)
    df["doc_id"] = df["doc_id"].astype(str)
    merged = df.merge(ta, on="doc_id", how="left")
    df["bertopic_topic_id"] = merged["topic_id"]

    noise_like = {-1, ARTIFACT_TOPIC_ID}
    votable = merged[~merged["topic_id"].isin(noise_like) & merged["topic_id"].notna()
                      & (merged["kw_leaf_id"] != -1)]
    crosswalk = (votable.groupby("topic_id")["kw_leaf_id"]
                 .agg(lambda s: s.value_counts().idxmax()).to_dict())

    def _agrees(row):
        bt = row["topic_id"]
        if pd.isna(bt) or bt in noise_like or row["kw_leaf_id"] == -1:
            return None
        expected = crosswalk.get(bt)
        return None if expected is None else bool(expected == row["kw_leaf_id"])

    df["agrees_with_bertopic"] = merged.apply(_agrees, axis=1)


def _attach_embedding_tiebreak(df: pd.DataFrame, ids: list[str]) -> None:
    """`--tiebreak=embedding`: a DIAGNOSTIC, never used to change `kw_leaf_id`.
    Leaf centroids are the mean SPECTER2 embedding of that leaf's own
    high/medium-confidence docs from THIS run's keyword scores; every doc is
    then compared, by cosine, only against its own BM25F top-2 leaves'
    centroids — the plan's own noise-population margin measurement (0.008
    vs. 0.025) is exactly why this never drives the primary label."""
    from src.model_docs import load_docs_and_embeddings
    _, cache_ids, embeddings = load_docs_and_embeddings()
    emb_by_id = {i: e for i, e in zip(cache_ids, embeddings)}

    confident = df[df["conf_tier"].isin(["high", "medium"])]
    centroids: dict[int, np.ndarray] = {}
    for lid, sub in confident.groupby("kw_leaf_id"):
        vecs = [emb_by_id[d] for d in sub["doc_id"] if d in emb_by_id]
        if vecs:
            centroids[int(lid)] = np.mean(vecs, axis=0)

    def _cos(a, b):
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        return float(np.dot(a, b) / (na * nb)) if na and nb else 0.0

    kw_centroid_leaf_id, cos1_col, margin_col, tie_col = [], [], [], []
    for _, row in df.iterrows():
        emb = emb_by_id.get(row["doc_id"])
        lid1, lid2 = row["kw_leaf_id"], row["kw_leaf2_id"]
        if emb is None or lid1 not in centroids or lid2 not in centroids or lid1 == -1:
            kw_centroid_leaf_id.append(None)
            cos1_col.append(np.nan)
            margin_col.append(np.nan)
            tie_col.append(None)
            continue
        c1, c2 = _cos(emb, centroids[lid1]), _cos(emb, centroids[lid2])
        kw_centroid_leaf_id.append(lid1 if c1 >= c2 else lid2)
        cos1_col.append(c1)
        margin_col.append(c1 - c2)
        tie_col.append("embedding")
    df["kw_centroid_leaf_id"] = kw_centroid_leaf_id
    df["centroid_cos1"] = cos1_col
    df["centroid_margin"] = margin_col
    df["tie_broken_by"] = tie_col


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-topic-labels", action="store_true",
                     help="bootstrap the taxonomy from outputs/topic_labels.json "
                          "instead of the curated outputs/topic_keywords.json")
    ap.add_argument("--emit-topic-labels", action="store_true",
                     help="convert the curated taxonomy to topic_labels.json's "
                          "schema and print it (does NOT write the live file)")
    ap.add_argument("--write-topic-labels", action="store_true",
                     help="like --emit-topic-labels, but WRITES the conversion to "
                          "the live outputs/topic_labels.json — the deliberate "
                          "downstream-integration swap (Step 4), not something "
                          "to run casually or automatically on every refit")
    ap.add_argument("--tiebreak", choices=["none", "embedding"], default="none")
    ap.add_argument("--limit", type=int, default=None, help="classify only the first N docs")
    ap.add_argument("--check-only", action="store_true", help="run but do not write the parquet")
    args = ap.parse_args()

    leaves, parents = (load_bootstrap_taxonomy() if args.from_topic_labels
                        else load_curated_taxonomy())
    print(f"loaded taxonomy: {len(leaves)} leaves / {len(parents)} parents "
          f"({'bootstrap' if args.from_topic_labels else 'curated'})")

    if args.emit_topic_labels or args.write_topic_labels:
        converted = curated_to_topic_labels(leaves, parents)
        if args.write_topic_labels:
            TOPIC_LABELS_PATH.write_text(json.dumps(converted, indent=2))
            print(f"wrote {TOPIC_LABELS_PATH}  ({len(leaves)} leaves / {len(parents)} parents)")
        else:
            print(json.dumps(converted, indent=2))
            print(f"\n(printed only — {TOPIC_LABELS_PATH} was NOT written; pass "
                  "--write-topic-labels to actually perform the swap)")
        return

    df = classify(leaves, parents, limit=args.limit, tiebreak=args.tiebreak)

    n = len(df)
    unassigned = df[df["kw_leaf_id"] == -1]
    print(f"classified {n} docs")
    print(f"  unassigned: {len(unassigned)} ({100*len(unassigned)/n:.1f}%)")
    print("  by_reason:", unassigned["unassigned_reason"].value_counts().to_dict())
    print("  conf_tier:", df["conf_tier"].value_counts().to_dict())
    if "agrees_with_bertopic" in df:
        agree = df["agrees_with_bertopic"].dropna()
        if len(agree):
            print(f"  agrees_with_bertopic (of {len(agree)} comparable docs): "
                  f"{100*agree.mean():.1f}%")

    if not args.check_only:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(OUTPUT_PATH, index=False)
        print(f"wrote {OUTPUT_PATH}  ({len(df)} rows)")


if __name__ == "__main__":
    main()
