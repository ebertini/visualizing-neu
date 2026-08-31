"""
adjudicate_low_confidence.py — Phase 4c (OPTIONAL, OFF BY DEFAULT) of the
keyword-classifier topic-model redo. See
/Users/uttkarshnarayan/.claude/plans/if-needed-check-the-imperative-mitten.md
§Phase 4c for the full design spec; this is the execution.

The deterministic BM25F scorer (`src/classify_by_keywords.py`) stays
canonical — this does NOT change that, and does NOT revise decision 1 of the
redo plan (an LLM never becomes the primary topic-to-document link, for the
same reasons already established: offline, reproducible, zero marginal cost
per re-run, fully inspectable). This is an optional, occasional, ADDITIVE
layer scoped tightly to the tail the deterministic scorer is genuinely unsure
about — a few hundred docs, never the full ~2,700-doc corpus. This is the
PI's own original mechanism-(b) proposal (see
docs/TOPIC_CLASSIFICATION_BRAINSTORM.md) — an LLM given a grant's text plus
the *curated* keyword lists, deciding or abstaining — finally applicable now
that a curated artifact and a real confidence signal both exist.

Scope, precisely: docs from `data/processed/topic_keyword_assignments.parquet`
with EITHER of two independent triggers, AND `unassigned_reason !=
"no_usable_text"` (a doc with literally no text can't be helped by an LLM
either — same reason `no_usable_text` docs are excluded from
`src.classify_by_keywords`'s own `--tiebreak=embedding` diagnostic):
  1. `conf_tier in {"low", "none"}` (the original design).
  2. A PEDAGOGY_SIGNAL_TERMS phrase match in title+abstract, REGARDLESS of
     conf_tier (widened 2026-08-29) — targets the "deceptive framing" failure
     mode found during manual curation review: a grant whose surface
     vocabulary points to one domain but whose true purpose is TEACHING that
     domain (e.g. an undergraduate materials-science lab course scored
     confidently as materials-science research). Keyword matching can't
     distinguish "grant ABOUT X" from "grant that TEACHES X" — this can
     happen at HIGH confidence, which trigger #1 alone would never catch
     (confirmed: grant 1171382, currently `high` confidence, flagged by #2).
As of 2026-08-29 this is 641 docs (594 via trigger #1, 47 via #2 only) —
still a few hundred docs, not the full ~2,700-doc corpus. Some trigger-#2
hits will be broader-impacts boilerplate on genuine research grants, not
actual teaching grants — an acceptable false-positive rate for a REVIEW
trigger (costs one LLM call that confirms "no change needed") that would be
unacceptable in a curated MATCHING term (would silently mislabel).

Per-doc prompt sends only the DETERMINISTIC SCORER'S OWN top-K=5 candidate
leaves (recomputed here via the same BM25F machinery `classify_by_keywords`
uses — full per-leaf scores aren't in the committed parquet, which only
stores top-2), not the full 31-leaf taxonomy — bounding the candidate set
keeps the prompt small and keeps the LLM's decision grounded in the curated
lists rather than freelancing a topic; this directly implements "documents
are linked to topics through [the keyword] lists," not through the LLM's own
world knowledge.

Same shape as `src.backfill_nih_reporter`/`backfill_nsf_awards`:
network-touching, run occasionally, `--offline`/`--limit` smoke-test flags,
cached raw responses, its own report. UNLIKE those two, raw responses are
cached under `data/llm_adjudication/` but NOT committed by default (see
.gitignore) — LLM output is cheap to regenerate and treating it as frozen
ground truth would work against the reproducibility this whole redesign is
built around; only the derived parquet + a summary are meant to be shared.

**No live API call is made by running this from this environment.** No
`ANTHROPIC_API_KEY` is set here and the sandbox only allowlists `pypi.org` —
per the NIH RePORTER/NSF Award Search precedent already in this repo, the
user runs the live commands themselves via `!`-prefixed shell commands (see
the module-level `main()` docstring below for the exact invocation).

Output: `data/processed/llm_adjudication.parquet`
(`doc_id, llm_leaf_id, llm_parent_id, llm_confidence, llm_abstain,
llm_rationale, llm_terms_considered, llm_model, llm_run_at`) — never merged
into or redefining `topic_keyword_assignments.parquet`'s own EXISTING columns
(the `titleOnly`/`modelTitleOnly` lesson: add a field, don't reinterpret one).

**Merge-back (built 2026-08-30, previously unwritten — see `merge_adjudication()`
below):** `--merge` reads `llm_adjudication.parquet` + `topic_keyword_assignments
.parquet` and adds FOUR NEW columns to the latter (in place, alongside the
existing ones — nothing existing is touched or redefined):
`final_leaf_id` (= `llm_leaf_id` whenever the LLM reviewed the doc and did
NOT abstain, REGARDLESS of `conf_tier` — this also lets a pedagogy-signal
review override a high/medium-confidence keyword match, not just resolve a
low-confidence one; else `kw_leaf_id` if the keyword classifier had any pick
at all, even a low-confidence one; else `-1`), `final_parent_id` (looked up
from `final_leaf_id` via the curated taxonomy), `final_source`
(`"keyword_classifier"` / `"keyword_classifier_low_confidence"` (a real,
softer-fallback design decision, not silently discarded to Unassigned) /
`"llm_adjudication"` / `"unassigned"` — the last only when the keyword
classifier itself never assigned a leaf AND the LLM didn't resolve it
either), and `llm_reviewed` (bool — was this doc even sent to the LLM at
all, so a consumer can tell "the LLM looked and abstained" apart from "the
LLM never saw this doc"). Downstream consumers (`src/build_viz_data.py`)
should prefer `final_leaf_id`/`final_parent_id` over `kw_leaf_id`/`kw_parent_id`
once this
has been run — and should show `final_source` in the grant detail card so an
LLM-assigned label is never silently indistinguishable from a deterministic
keyword match, preserving this whole method's inspectability claim. Wiring
that preference into `build_viz_data.py` itself is a separate, later
integration step, not part of `--merge`.

Run:
    python -m src.adjudicate_low_confidence --dry-run                # build +
                                                                     # print the
                                                                     # first few
                                                                     # prompts,
                                                                     # no network,
                                                                     # no cache
                                                                     # needed —
                                                                     # review
                                                                     # before
                                                                     # spending
    python -m src.adjudicate_low_confidence --limit 10 --offline   # smoke test
                                                                     # (needs a
                                                                     # cache from
                                                                     # a prior
                                                                     # live run)
    export ANTHROPIC_API_KEY=...
    python -m src.adjudicate_low_confidence --limit 10             # smoke test,
                                                                     # live, cheap
    python -m src.adjudicate_low_confidence                        # full run,
                                                                     # via the
                                                                     # Batches API
                                                                     # (see
                                                                     # module
                                                                     # docstring
                                                                     # for the
                                                                     # current
                                                                     # target
                                                                     # doc count
                                                                     # — recomputed
                                                                     # live, not
                                                                     # hardcoded
                                                                     # here)
    python -m src.adjudicate_low_confidence --model claude-sonnet-5  # cheaper
    python -m src.adjudicate_low_confidence --merge                 # after a live
                                                                     # run: add
                                                                     # final_leaf_id
                                                                     # /final_source
                                                                     # to the
                                                                     # assignments
                                                                     # parquet
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from src.classify_by_keywords import (
        W_TITLE,
        _leaf_norm,
        _sat,
        _term_idf_table,
        load_curated_taxonomy,
    )
    from src.keyword_match import match_text
    from src.model_docs import load_doc_fields
    from src.kw_vocab import tokenize
except ImportError:  # run from within src/
    from classify_by_keywords import (  # type: ignore
        W_TITLE,
        _leaf_norm,
        _sat,
        _term_idf_table,
        load_curated_taxonomy,
    )
    from keyword_match import match_text  # type: ignore
    from model_docs import load_doc_fields  # type: ignore
    from kw_vocab import tokenize  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
ASSIGNMENTS_PATH = PROC / "topic_keyword_assignments.parquet"
OUTPUT_PATH = PROC / "llm_adjudication.parquet"
CACHE_DIR = REPO_ROOT / "data" / "llm_adjudication"  # NOT committed — see module docstring

TOP_K = 5
TARGET_CONF_TIERS = {"low", "none"}
EXCLUDED_UNASSIGNED_REASON = "no_usable_text"

# Widened 2026-08-29: a SECOND, independent trigger alongside conf_tier, for
# the "deceptive framing" failure mode found during manual curation review —
# a grant whose surface vocabulary points to one research domain but whose
# true purpose is TEACHING that domain's content (e.g. an undergraduate
# materials-science lab course, scored confidently as materials-science
# RESEARCH because both use the same domain jargon). Keyword matching
# fundamentally can't distinguish "grant ABOUT X" from "grant that TEACHES X"
# — this can happen at HIGH confidence too, which conf_tier-based triggering
# alone would never catch. Each phrase verified against the real corpus
# before inclusion (some hits are broader-impacts boilerplate on genuine
# research grants, not actual teaching grants — an acceptable false-positive
# rate here, unlike in a curated MATCHING term, since a false trigger just
# costs one LLM call that confirms "no change needed," not a wrong label).
PEDAGOGY_SIGNAL_TERMS = [
    "undergraduate course", "curriculum development", "laboratory course",
    "classroom activities", "students will learn", "teaching materials",
    "undergraduate laboratory", "course materials", "hands-on activities",
]

DEFAULT_MODEL = "claude-opus-5"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "leaf_id": {"type": ["integer", "null"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "abstain": {"type": "boolean"},
        "rationale": {"type": "string"},
        "terms_considered": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["leaf_id", "confidence", "abstain", "rationale", "terms_considered"],
}


def _coerce_terms_considered(v) -> list[str]:
    """Normalize `terms_considered` to a real list of strings before it ever
    reaches pandas/pyarrow. The tool definition below does NOT set
    `strict: true` (JSON-schema `type: array` on a tool input is a hint to
    the model, not a server-enforced guarantee without strict mode) — a live
    619-request run (claude-sonnet-5, effort=medium) confirmed 518 of 619
    responses (84%) returned this field as one comma-separated STRING
    instead of a JSON array, which crashed `pd.DataFrame(...).to_parquet(...)`
    with 'cannot mix list and non-list, non-null values' once every doc's row
    was assembled into one column. None -> [] (missing/null); a
    comma-separated string is split back into the individual terms the model
    clearly intended (confirmed real terms, comma+space separated, in every
    sampled case — not an assumption); any other bare scalar -> a
    single-element list; an already-well-formed list passes through
    unchanged."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, str):
        return [t.strip() for t in v.split(",") if t.strip()]
    return [str(v)]


def _pedagogy_signal_doc_ids() -> set[str]:
    """doc_ids whose title+abstract contain >=1 PEDAGOGY_SIGNAL_TERMS phrase —
    computed regardless of conf_tier, so a HIGH-confidence-but-actually-about-
    teaching grant gets flagged too (conf_tier alone would never catch it)."""
    ids, titles, abstracts = load_doc_fields()
    flagged = set()
    for did, title, abstract in zip(ids, titles, abstracts):
        if match_text(title, PEDAGOGY_SIGNAL_TERMS) or match_text(abstract, PEDAGOGY_SIGNAL_TERMS):
            flagged.add(did)
    return flagged


def _target_docs() -> pd.DataFrame:
    if not ASSIGNMENTS_PATH.exists():
        raise FileNotFoundError(
            f"{ASSIGNMENTS_PATH} does not exist — run `python -m src.classify_by_keywords` first."
        )
    df = pd.read_parquet(ASSIGNMENTS_PATH)
    low_conf = (
        df["conf_tier"].isin(TARGET_CONF_TIERS)
        & (df["unassigned_reason"] != EXCLUDED_UNASSIGNED_REASON)
    )
    pedagogy_flagged = df["doc_id"].astype(str).isin(_pedagogy_signal_doc_ids())
    # Same no_usable_text exclusion applies to the pedagogy trigger too — a
    # doc with no text can't be reviewed by an LLM regardless of why it was
    # selected.
    target = df[(low_conf | pedagogy_flagged) & (df["unassigned_reason"] != EXCLUDED_UNASSIGNED_REASON)].copy()
    target["trigger_reason"] = [
        "low_confidence" if lc else "pedagogy_signal"
        for lc in low_conf[target.index]
    ]
    return target


def _top_k_candidates(leaves: dict, target_ids: set[str], k: int = TOP_K) -> dict[str, list[str]]:
    """Recompute full per-leaf BM25F scores for ONLY the target docs (the
    committed parquet stores just top-2) and return doc_id -> the top-k leaf
    ids by score, reusing classify_by_keywords's own scoring primitives so
    this can't silently diverge from what the deterministic scorer itself
    would rank first. Deliberately NOT a call to `classify()` — that returns
    one row per doc with only kw_leaf_id/kw_leaf2_id, not the full ranking."""
    ids, titles, abstracts = load_doc_fields()
    by_id = {did: (t, a) for did, t, a in zip(ids, titles, abstracts) if did in target_ids}

    all_terms = sorted({kw["term"] for leaf in leaves.values()
                         for kw in list(leaf.get("keywords", [])) + list(leaf.get("negative_keywords", []))})
    idf = _term_idf_table(leaves, len(ids))  # N = full corpus, same as classify_by_keywords.classify()
    leaf_norms = {lid: _leaf_norm(leaf, idf) for lid, leaf in leaves.items()}

    # Corpus-wide average length, computed the same way classify() does, so
    # sat() values here are directly comparable to the committed parquet's.
    doc_lens = [W_TITLE * len(tokenize(t)) + len(tokenize(a)) for t, a in zip(titles, abstracts)]
    avg_len = sum(doc_lens) / len(doc_lens) if doc_lens else 0.0

    out: dict[str, list[str]] = {}
    for did, (title, abstract) in by_id.items():
        doc_len = W_TITLE * len(tokenize(title)) + len(tokenize(abstract))
        title_matches = match_text(title, all_terms)
        abstract_matches = match_text(abstract, all_terms)
        tf_t = Counter(m.term for m in title_matches)
        tf_a = Counter(m.term for m in abstract_matches)
        sat_by_term = {}
        for m in title_matches + abstract_matches:
            term = m.term
            if term in sat_by_term:
                continue
            pseudo_tf = W_TITLE * tf_t.get(term, 0) + tf_a.get(term, 0)
            sat_by_term[term] = _sat(pseudo_tf, doc_len, avg_len)

        scores = {}
        for lid, leaf in leaves.items():
            pos = sum(kw.get("weight", 1.0) * idf.get(kw["term"], 0.0) * sat_by_term.get(kw["term"], 0.0)
                      for kw in leaf.get("keywords", []))
            neg = sum(kw.get("weight", 1.0) * idf.get(kw["term"], 0.0) * sat_by_term.get(kw["term"], 0.0)
                      for kw in leaf.get("negative_keywords", []))
            scores[lid] = (pos - neg) / leaf_norms[lid]
        ranked = sorted(leaves.keys(), key=lambda lid: (-scores[lid], int(lid)))
        out[did] = ranked[:k]
    return out


def build_prompt(title: str, abstract: str, candidates: list[dict]) -> str:
    """candidates: [{leaf_id, label, parent_label, keywords: [str, ...]}, ...],
    already bounded to TOP_K by the caller."""
    lines = [
        "You are adjudicating which research topic (if any) a grant belongs to, "
        "using ONLY the candidate topics and their curated keyword lists below — "
        "do not use outside knowledge of the grant or invent a topic not listed.",
        "",
        f"Grant title: {title or '(no title)'}",
        f"Grant abstract: {abstract or '(no abstract available)'}",
        "",
        "Candidate topics (ranked by a deterministic keyword-matching score; "
        "the ranking is a hint, not a constraint — pick whichever fits best, or none):",
    ]
    for c in candidates:
        lines.append(f"- leaf_id {c['leaf_id']} — \"{c['label']}\" (parent: {c['parent_label']}); "
                      f"keywords: {', '.join(c['keywords'][:15])}")
    lines.append("")
    lines.append(
        "Respond with the structured fields only. Set abstain=true and leaf_id=null "
        "if none of the candidates genuinely fit — do not force a choice."
    )
    return "\n".join(lines)


def _cache_path(model: str) -> Path:
    return CACHE_DIR / f"raw_responses_{model}.jsonl"


def _load_cache(model: str) -> dict[str, dict]:
    path = _cache_path(model)
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        out[rec["doc_id"]] = rec
    return out


def _append_cache(model: str, doc_id: str, response: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with _cache_path(model).open("a") as f:
        f.write(json.dumps({"doc_id": doc_id, **response}) + "\n")


def _run_batch_live(prompts: dict[str, str], model: str) -> dict[str, dict]:
    """Submit one Anthropic Batches API job covering every doc_id in `prompts`,
    poll until complete, and return doc_id -> parsed structured response.

    NOT exercised by this session (no ANTHROPIC_API_KEY, sandbox blocks
    non-pypi.org network) — written to be correct against the Messages/
    Batches API shape, but its first real run should be treated as
    unverified until the user runs it themselves.
    """
    try:
        import anthropic
    except ImportError as e:
        raise SystemExit(
            "the `anthropic` package is not installed — `pip install anthropic` "
            "(it's in requirements.txt as of this Phase 4c skeleton, but a plain "
            "requirements-viz.txt .venv won't have it)."
        ) from e

    client = anthropic.Anthropic()
    requests = [
        anthropic.types.message_create_params.MessageCreateParamsNonStreaming(
            custom_id=doc_id,
            params={
                "model": model,
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [{
                    "name": "adjudicate",
                    "description": "Record the topic adjudication decision.",
                    "input_schema": RESPONSE_SCHEMA,
                }],
                "tool_choice": {"type": "tool", "name": "adjudicate"},
                # This is a short classification task, not a hard reasoning
                # problem — the default "high" effort buys little here and
                # (since thinking tokens count against the 512-token cap)
                # risks occasionally spending the whole budget on reasoning
                # before ever emitting the tool call. "medium" is cheaper and
                # leaves more of the 512-token budget for the actual answer.
                "output_config": {"effort": "medium"},
            },
        )
        for doc_id, prompt in prompts.items()
    ]
    batch = client.messages.batches.create(requests=requests)
    print(f"submitted batch {batch.id} ({len(requests)} requests) — polling...")
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        import time
        time.sleep(30)

    results: dict[str, dict] = {}
    for entry in client.messages.batches.results(batch.id):
        doc_id = entry.custom_id
        if entry.result.type != "succeeded":
            results[doc_id] = {"leaf_id": None, "confidence": "low", "abstain": True,
                                "rationale": f"batch entry failed: {entry.result.type}",
                                "terms_considered": []}
            continue
        message = entry.result.message
        tool_use = next((b for b in message.content if b.type == "tool_use"), None)
        parsed = tool_use.input if tool_use else {
            "leaf_id": None, "confidence": "low", "abstain": True,
            "rationale": "no tool_use block in response", "terms_considered": [],
        }
        results[doc_id] = parsed
    return results


def merge_adjudication() -> pd.DataFrame:
    """Merge-back step (previously unwritten — see module docstring). Adds
    `final_leaf_id`/`final_parent_id`/`final_source`/`llm_reviewed` as NEW
    columns onto `topic_keyword_assignments.parquet`, leaving every existing
    column untouched, then writes the result back to the same file.

    Resolution rule (revised — the first version had a real bug, see below):
    1. If the LLM reviewed this doc AND did not abstain, its pick wins,
       REGARDLESS of conf_tier. This is deliberate, not just for the
       low/none-confidence tail: a doc can also reach the LLM via the
       PEDAGOGY_SIGNAL_TERMS trigger while sitting at high/medium conf_tier
       (the whole point of that trigger — catching a confident keyword match
       that's actually wrong because of deceptive framing, e.g. a materials-
       science COURSE scored as materials-science RESEARCH; confirmed real
       case: grant 1171382). The original version of this function checked
       `conf_tier in (high, medium)` FIRST and `continue`d before ever
       looking at the LLM's answer — which silently defeated that trigger
       for every doc it was built to catch, since a pedagogy-flagged
       high-confidence doc could never be overridden no matter what the LLM
       said. Found and fixed in the same session that added the softer
       fallback below, not by design up front.
    2. Otherwise (not reviewed, or the LLM abstained): trust the
       deterministic scorer's own pick if it has one, even at `low`
       confidence — `final_source` distinguishes this
       (`keyword_classifier_low_confidence`) from a genuinely trustworthy
       one (`keyword_classifier`), so a low-confidence guess is visible
       AND labeled as shaky, rather than either silently passed off as
       confident or discarded to Unassigned. This is a real product
       decision, not a default: an earlier version discarded every
       non-LLM-confirmed low-confidence doc to Unassigned outright, which
       is more conservative but inflates the Unassigned bucket far beyond
       what the keyword classifier's own conf_tier already communicates.
    3. Only a doc the deterministic scorer itself never assigned at all
       (`kw_leaf_id == -1` — i.e. `conf_tier == "none"`) and that the LLM
       didn't resolve either ends up `final_source == "unassigned"`.
    """
    if not OUTPUT_PATH.exists():
        raise FileNotFoundError(
            f"{OUTPUT_PATH} does not exist — run a live adjudication pass first "
            "(see this module's Run: examples)."
        )
    if not ASSIGNMENTS_PATH.exists():
        raise FileNotFoundError(f"{ASSIGNMENTS_PATH} does not exist — run `python -m "
                                 "src.classify_by_keywords` first.")

    leaves, _parents = load_curated_taxonomy()
    kw = pd.read_parquet(ASSIGNMENTS_PATH)
    kw["doc_id"] = kw["doc_id"].astype(str)
    llm = pd.read_parquet(OUTPUT_PATH)
    llm["doc_id"] = llm["doc_id"].astype(str)
    llm = llm.set_index("doc_id")

    # Drop any stale final_* / llm_reviewed columns from a prior --merge run
    # before re-adding them, so re-running --merge after a re-adjudication
    # pass doesn't silently duplicate or shadow columns.
    stale = [c for c in ("final_leaf_id", "final_parent_id", "final_source", "llm_reviewed") if c in kw.columns]
    kw = kw.drop(columns=stale)

    final_leaf_ids, final_parent_ids, final_sources, llm_reviewed = [], [], [], []
    for row in kw.itertuples():
        reviewed = row.doc_id in llm.index
        llm_reviewed.append(reviewed)

        if reviewed:
            llm_row = llm.loc[row.doc_id]
            llm_leaf_id = llm_row["llm_leaf_id"]
            if not bool(llm_row["llm_abstain"]) and pd.notna(llm_leaf_id):
                lid = str(int(llm_leaf_id))
                final_leaf_ids.append(int(llm_leaf_id))
                final_parent_ids.append(leaves.get(lid, {}).get("parent"))
                final_sources.append("llm_adjudication")
                continue

        if row.kw_leaf_id != -1:
            final_leaf_ids.append(row.kw_leaf_id)
            final_parent_ids.append(row.kw_parent_id)
            final_sources.append(
                "keyword_classifier" if row.conf_tier in ("high", "medium")
                else "keyword_classifier_low_confidence"
            )
            continue

        final_leaf_ids.append(-1)
        final_parent_ids.append(None)
        final_sources.append("unassigned")

    kw["final_leaf_id"] = final_leaf_ids
    kw["final_parent_id"] = final_parent_ids
    kw["final_source"] = final_sources
    kw["llm_reviewed"] = llm_reviewed

    kw.to_parquet(ASSIGNMENTS_PATH, index=False)
    counts = pd.Series(final_sources).value_counts().to_dict()
    print(f"merged: final_source counts = {counts}, wrote {ASSIGNMENTS_PATH}")
    return kw


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true",
                     help="replay cached responses only — no network call")
    ap.add_argument("--dry-run", action="store_true",
                     help="build and print the target-doc count + first few prompts, "
                          "make NO network call and require NO cache — review the prompt "
                          "before spending anything on a live run")
    ap.add_argument("--merge", action="store_true",
                     help="skip adjudication; merge an existing llm_adjudication.parquet "
                          "into topic_keyword_assignments.parquet as final_leaf_id/"
                          "final_parent_id/final_source/llm_reviewed (new columns only)")
    ap.add_argument("--limit", type=int, default=None, help="adjudicate only the first N target docs")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                     choices=["claude-opus-5", "claude-sonnet-5"])
    args = ap.parse_args()

    if args.merge:
        merge_adjudication()
        return

    leaves, parents = load_curated_taxonomy()
    target = _target_docs()
    if args.limit:
        target = target.head(args.limit)
    target_ids = set(target["doc_id"])
    by_reason = target["trigger_reason"].value_counts().to_dict()
    print(f"{len(target_ids)} target docs (conf_tier in {TARGET_CONF_TIERS} OR pedagogy-signal "
          f"phrase matched, unassigned_reason != '{EXCLUDED_UNASSIGNED_REASON}') — {by_reason}")

    candidates_by_doc = _top_k_candidates(leaves, target_ids)

    ids, titles, abstracts = load_doc_fields()
    text_by_id = {did: (t, a) for did, t, a in zip(ids, titles, abstracts)}

    prompts = {}
    for doc_id in target_ids:
        title, abstract = text_by_id.get(doc_id, ("", ""))
        cand_leaf_ids = candidates_by_doc.get(doc_id, [])
        cands = [
            {"leaf_id": int(lid), "label": leaves[lid]["label"],
             "parent_label": parents.get(leaves[lid].get("parent"), {}).get("label", "?"),
             "keywords": [kw["term"] for kw in leaves[lid].get("keywords", [])]}
            for lid in cand_leaf_ids if lid in leaves
        ]
        prompts[doc_id] = build_prompt(title, abstract, cands)

    if args.dry_run:
        total_chars = sum(len(p) for p in prompts.values())
        print(f"\n--dry-run: {len(prompts)} prompts built, NO network call made, "
              f"total prompt chars: {total_chars:,} (~{total_chars // 4:,} tokens, rough estimate)")
        print("\n--- first 3 prompts (of", len(prompts), ") ---\n")
        for doc_id, prompt in list(prompts.items())[:3]:
            print(f"=== doc_id {doc_id} ===")
            print(prompt)
            print()
        return

    if args.offline:
        responses = _load_cache(args.model)
        missing = target_ids - set(responses)
        if missing:
            raise SystemExit(
                f"--offline requires a cache entry for every target doc — missing "
                f"{len(missing)} (e.g. {sorted(missing)[:5]}). Run a live pass first."
            )
    else:
        responses = _run_batch_live(prompts, args.model)
        for doc_id, resp in responses.items():
            _append_cache(args.model, doc_id, resp)

    run_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for doc_id in target_ids:
        resp = responses.get(doc_id, {"leaf_id": None, "confidence": "low", "abstain": True,
                                       "rationale": "no response", "terms_considered": []})
        leaf_id = resp.get("leaf_id")
        rows.append({
            "doc_id": doc_id,
            "llm_leaf_id": leaf_id,
            "llm_parent_id": leaves[str(leaf_id)].get("parent") if leaf_id is not None and str(leaf_id) in leaves else None,
            "llm_confidence": resp.get("confidence"),
            "llm_abstain": bool(resp.get("abstain", True)),
            "llm_rationale": resp.get("rationale", ""),
            "llm_terms_considered": _coerce_terms_considered(resp.get("terms_considered")),
            "llm_model": args.model,
            "llm_run_at": run_at,
        })
    out = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUTPUT_PATH, index=False)
    n_abstain = int(out["llm_abstain"].sum())
    print(f"wrote {OUTPUT_PATH}  ({len(out)} rows, {n_abstain} abstained "
          f"[{100 * n_abstain / len(out):.1f}%])")


if __name__ == "__main__":
    main()
