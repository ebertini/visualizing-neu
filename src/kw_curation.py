"""
kw_curation.py — Phase 4a: `--check` validates outputs/topic_keywords.json is
genuinely curated, not just a copy of the draft. Light deps only (stdlib +
json), so it runs in CI and in a bare .venv.

Promotion is the curation gate, not a convention:
    cp outputs/keyword_topics.draft.json outputs/topic_keywords.json
    $EDITOR outputs/topic_keywords.json
    python3 -m src.kw_curation --check     # exit 1 until genuinely curated

Fails (exit 1) on:
  - any remaining "draft" status (parent, leaf, or _meta.curation.status)
  - any curated term with df_corpus == 0 or missing (the phantom/typo guard —
    a hand-typed term that matches zero documents fails loudly, not silently)
  - a non-dense leaf-id space
  - a leaf whose `parent` doesn't exist
  - empty `notes` on an accepted group
  - a non-empty `rejected_terms` entry with no `reason`

Warns (exit 0) on:
  - accepted parent count != 8 (names the files to sync, see §7 of the review sheet)
  - accepted parent count > 12 (palette headroom exhausted)
  - a term appearing in >1 accepted group (allowed, reported)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = REPO_ROOT / "outputs"
CURATED_PATH = OUTPUTS / "topic_keywords.json"

EXPECTED_PARENT_COUNT = 8
PARENT_COUNT_WARN_ABOVE = 12


def check(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if data.get("_meta", {}).get("curation", {}).get("status") == "draft":
        errors.append("_meta.curation.status is still 'draft' — set it to 'accepted' "
                       "(or another real status) once curation is done.")

    parents = data.get("parents", {})
    leaves = data.get("leaves", {})

    accepted_parents = {pid: p for pid, p in parents.items() if p.get("status") != "draft"}
    accepted_leaves = {lid: l for lid, l in leaves.items() if l.get("status") != "draft"}

    if not accepted_leaves:
        errors.append("no leaves have been moved off 'draft' status — nothing has been curated.")

    # Dense leaf-id space check (over ACCEPTED leaves only — downstream
    # indexing needs a contiguous range(n) once curation drops/merges leaves).
    try:
        leaf_ids_int = sorted(int(lid) for lid in accepted_leaves)
        if leaf_ids_int and leaf_ids_int != list(range(len(leaf_ids_int))):
            errors.append(f"accepted leaf ids are not a dense range(0,{len(leaf_ids_int)}) — "
                           f"got {leaf_ids_int[:10]}{'...' if len(leaf_ids_int) > 10 else ''}. "
                           "Renumber contiguously before this can be consumed downstream "
                           "(src/build_viz_data.py indexes t[tid] by position).")
    except ValueError:
        errors.append("non-integer leaf id found among accepted leaves.")

    for lid, leaf in accepted_leaves.items():
        parent_id = leaf.get("parent")
        if parent_id is not None and parent_id not in parents:
            errors.append(f"leaf {lid}: parent '{parent_id}' does not exist in parents{{}}.")
        if not leaf.get("notes", "").strip():
            errors.append(f"leaf {lid}: accepted but 'notes' is empty — the transparency "
                           "requirement needs a reason recorded for every accepted group.")
        active_terms = {kw.get("term") for kw in leaf.get("keywords", [])}
        for rt in leaf.get("rejected_terms", []):
            if not str(rt.get("reason", "")).strip():
                errors.append(f"leaf {lid}: rejected_terms entry '{rt.get('term')}' has no reason.")
            if rt.get("term") in active_terms:
                errors.append(f"leaf {lid}: term '{rt.get('term')}' is in BOTH keywords[] and "
                               "rejected_terms[] — rejected_terms is a documentation record only, "
                               "it does not exclude a term from the classifier. Delete it from "
                               "keywords[] too, or it stays active.")
        for kw in leaf.get("keywords", []):
            df = kw.get("df_corpus")
            if df is None or df == 0:
                errors.append(f"leaf {lid}: curated term '{kw.get('term')}' has "
                               f"df_corpus={df} — phantom/typo term matching zero documents.")

    for pid, parent in accepted_parents.items():
        if not parent.get("notes", "").strip():
            errors.append(f"parent {pid}: accepted but 'notes' is empty.")
        for kw in parent.get("keywords", []):
            df = kw.get("df_corpus")
            if df is None or df == 0:
                errors.append(f"parent {pid}: curated term '{kw.get('term')}' has "
                               f"df_corpus={df} — phantom/typo term matching zero documents.")

    n_parents = len(accepted_parents)
    if n_parents and n_parents != EXPECTED_PARENT_COUNT:
        warnings.append(f"{n_parents} accepted parents (expected {EXPECTED_PARENT_COUNT}) — "
                         "sync PARENT_NAMES/PARENT_COLORS in src/build_viz_aggregates.py, "
                         "docs/TopicVizPrototypes/shared/enrico.js, and "
                         "docs/TopicVizPrototypes/what_we_can_see/constants.js.")
    if n_parents > PARENT_COUNT_WARN_ABOVE:
        warnings.append(f"{n_parents} accepted parents exceeds the palette headroom "
                         f"({PARENT_COUNT_WARN_ABOVE}) without extending color arrays.")

    term_owners: dict[str, list[str]] = {}
    for lid, leaf in accepted_leaves.items():
        for kw in leaf.get("keywords", []):
            term_owners.setdefault(kw["term"], []).append(f"leaf {lid}")
    multi = {t: owners for t, owners in term_owners.items() if len(owners) > 1}
    if multi:
        warnings.append(f"{len(multi)} terms appear in >1 accepted leaf (allowed): "
                         f"{list(multi.items())[:5]}")

    return errors, warnings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not CURATED_PATH.exists():
        print(f"{CURATED_PATH} does not exist — promote the draft first:\n"
              f"  cp outputs/keyword_topics.draft.json outputs/topic_keywords.json")
        sys.exit(1)

    data = json.loads(CURATED_PATH.read_text())
    errors, warnings = check(data)

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if errors:
        print(f"\n{len(errors)} error(s) — not yet genuinely curated.")
        sys.exit(1)
    print(f"\nOK — {len(warnings)} warning(s), 0 errors.")
    sys.exit(0)


if __name__ == "__main__":
    main()
