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
with `conf_tier in {"low", "none"}` AND `unassigned_reason != "no_usable_text"`
(a doc with literally no text can't be helped by an LLM either — same reason
`no_usable_text` docs are excluded from `src.classify_by_keywords`'s own
`--tiebreak=embedding` diagnostic). As of 2026-08-29 this is 836 docs (736
`low` + 100 `none`, of which 28 are `placeholder_title_only` ONR "Grant"
records — included per the letter of the scope rule above, but expected to
mostly `abstain`, since there is no real content for an LLM to adjudicate
either; this is a feature of the honest abstain design, not a bug in the
scoping).

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
into or redefining `topic_keyword_assignments.parquet`'s own columns (the
`titleOnly`/`modelTitleOnly` lesson: add a field, don't reinterpret one). A
separate, explicit resolution step (not built here — future work, see the
plan) would add `final_leaf_id`/`final_source` columns:
`final_leaf_id = leaf_id` when `conf_tier` is `high`/`medium`, else
`llm_leaf_id` when present and not abstained, else `-1`.

Run:
    python -m src.adjudicate_low_confidence --limit 10 --offline   # smoke test
                                                                     # (needs a
                                                                     # cache from
                                                                     # a prior
                                                                     # live run)
    export ANTHROPIC_API_KEY=...
    python -m src.adjudicate_low_confidence --limit 10             # smoke test,
                                                                     # live, cheap
    python -m src.adjudicate_low_confidence                        # full run,
                                                                     # ~836 docs,
                                                                     # via the
                                                                     # Batches API
    python -m src.adjudicate_low_confidence --model claude-sonnet-5  # cheaper
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


def _target_docs() -> pd.DataFrame:
    if not ASSIGNMENTS_PATH.exists():
        raise FileNotFoundError(
            f"{ASSIGNMENTS_PATH} does not exist — run `python -m src.classify_by_keywords` first."
        )
    df = pd.read_parquet(ASSIGNMENTS_PATH)
    return df[
        df["conf_tier"].isin(TARGET_CONF_TIERS)
        & (df["unassigned_reason"] != EXCLUDED_UNASSIGNED_REASON)
    ].copy()


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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true",
                     help="replay cached responses only — no network call")
    ap.add_argument("--limit", type=int, default=None, help="adjudicate only the first N target docs")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                     choices=["claude-opus-5", "claude-sonnet-5"])
    args = ap.parse_args()

    leaves, parents = load_curated_taxonomy()
    target = _target_docs()
    if args.limit:
        target = target.head(args.limit)
    target_ids = set(target["doc_id"])
    print(f"{len(target_ids)} target docs (conf_tier in {TARGET_CONF_TIERS}, "
          f"unassigned_reason != '{EXCLUDED_UNASSIGNED_REASON}')")

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
            "llm_terms_considered": resp.get("terms_considered", []),
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
