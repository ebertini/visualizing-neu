"""
topic_keywords.py — Phase 4a: the curated keyword-topic artifact.

Builds `outputs/keyword_topics.draft.json` from Plan B's discovery output
(`outputs/kw_term_groups_planB.json` + `outputs/kw_vocab_candidates.json`) in
the schema a human curator edits into `outputs/topic_keywords.json` (promoted
via `cp` + hand edits, validated by `src/kw_curation.py --check`). Every
group/leaf starts `status: "draft"` — nothing here is a finished topic
definition, it's a pre-filled editing surface.

Light deps only (stdlib + json) so it runs in CI / .venv, same class of
script as src/kw_curation.py.

Run:
    python3 -m src.topic_keywords          # writes outputs/keyword_topics.draft.json
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = REPO_ROOT / "outputs"

DRAFT_PATH = OUTPUTS / "keyword_topics.draft.json"
CURATED_PATH = OUTPUTS / "topic_keywords.json"

SMALL_LEAF_FLOOR = 5  # leaves below this are flagged (not auto-dropped) as
# likely PI-idiolect noise rather than a real theme — a human call, not ours.


def _label_from_terms(top_terms: list[str], n: int = 3) -> str:
    return ", ".join(top_terms[:n]) if top_terms else "(unlabeled)"


def build_draft(term_groups_path: Path = OUTPUTS / "kw_term_groups_planB.json",
                 vocab_candidates_path: Path = OUTPUTS / "kw_vocab_candidates.json") -> dict:
    tg = json.loads(term_groups_path.read_text())
    vc = json.loads(vocab_candidates_path.read_text())
    term_stats = {t["term"]: t for t in vc["terms"]}

    def _keywords_for(top_terms: list[str]) -> list[dict]:
        out = []
        for t in top_terms:
            stats = term_stats.get(t, {})
            out.append({
                "term": t, "weight": 1.0,
                "df_corpus": stats.get("df_corpus"),
                "source": "draft",
            })
        return out

    parents = {}
    for gid, g in tg["parent_groups"].items():
        pid = f"P{gid[1:]}"
        contributing = g.get("contributing_legacy_topics", [])
        parents[pid] = {
            "label": _label_from_terms(g["top_terms"]),
            "status": "draft",
            "notes": "",
            "leaf_ids": [],  # filled below from leaf_groups' parent_of_group
            "keywords": _keywords_for(g["top_terms"]),
            "provenance": {
                "group_id": gid,
                "n_terms": g["n_terms"],
                "contributing_legacy_topics": contributing,
            },
        }

    leaves = {}
    dropped_leaves = []
    for gid, g in tg["leaf_groups"].items():
        lid = gid[1:]  # "L4" -> "4"
        parent_cid = g.get("parent_of_group")
        parent_id = f"P{parent_cid}" if parent_cid is not None else None
        if parent_id and parent_id in parents:
            parents[parent_id]["leaf_ids"].append(lid)

        contributing = g.get("contributing_legacy_topics", [])
        best_legacy = contributing[0]["topic_id"] if contributing else None

        entry = {
            "label": _label_from_terms(g["top_terms"]),
            "status": "draft",
            "parent": parent_id,
            "notes": "",
            "keywords": _keywords_for(g["top_terms"]),
            "negative_keywords": [],
            "rejected_terms": [],
            "provenance": {
                "source_leaf_id": lid,
                "legacy_topic_id": best_legacy,
                "contributing_legacy_topics": contributing,
                "n_terms": g["n_terms"],
            },
        }
        if g["n_terms"] < SMALL_LEAF_FLOOR:
            entry["notes"] = (
                f"AUTO-FLAG: only {g['n_terms']} term(s) in this cluster — likely "
                "PI-idiolect noise rather than a real theme. Verify before accepting; "
                "consider moving to dropped_leaves instead."
            )
            dropped_leaves.append({
                "id": lid, "reason": "candidate for drop: cluster below "
                f"{SMALL_LEAF_FLOOR}-term floor, not yet reviewed", "n_terms": g["n_terms"],
                "top_terms": g["top_terms"],
            })
        leaves[lid] = entry

    out = {
        "_meta": {
            "schema_version": 1,
            "provenance": "draft",
            "curation": {"status": "draft", "curated_by": "", "curated_at": ""},
            "source_fit": {
                "method": "keyword_clustering",
                "k_parent": tg["_meta"]["chosen_k_parent"],
                "k_leaf": tg["_meta"]["chosen_k_leaf"],
                "candidate_vocab_size": vc["_meta"]["full_vocab_size"],
                "prune_target": vc["_meta"]["prune_target"],
            },
            "vocab_policy_version": 1,
        },
        "parents": parents,
        "leaves": leaves,
        "dropped_leaves": dropped_leaves,
    }
    return out


def main() -> None:
    if CURATED_PATH.exists():
        print(f"{CURATED_PATH} already exists — leaving it alone (may be hand-curated). "
              "Delete it first if you want to regenerate a fresh draft over it (the draft "
              "file itself is always safe to regenerate).")
    draft = build_draft()
    DRAFT_PATH.write_text(json.dumps(draft, indent=2))
    n_small = len(draft["dropped_leaves"])
    print(f"wrote {DRAFT_PATH}  ({len(draft['parents'])} parents, {len(draft['leaves'])} leaves, "
          f"{n_small} leaves auto-flagged as small-cluster drop candidates)")


if __name__ == "__main__":
    main()
