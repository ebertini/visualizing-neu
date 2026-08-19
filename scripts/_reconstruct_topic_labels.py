"""
_reconstruct_topic_labels.py — one-off recovery of outputs/topic_labels.json.

Context: outputs/topic_labels.json is the hand-curated "single source of
truth" for topic labels + parent-theme grouping (see
docs/TOPIC_WORK_FORWARD_PLAN.md M3), read by src/build_viz_data.py. It is
absent from this machine — outputs/ was, until this pass, fully gitignored
(see .gitignore), so the file was never actually committed despite the plan
saying it should be. The curation work it holds is NOT lost: it survives,
byte-for-byte, inside two already-committed files this repo does publish:

  docs/EnricoVis/data/topics.json        25 topics + noise, each with its
                                          curated label, top-10 c-TF-IDF
                                          terms, and "P0".."P7"/null parent key
  docs/EnricoVis/data/grants_hier.json   the parent GROUP names ("P0" ->
                                          "Life Sciences & Biomedicine", etc.)
                                          that topics.json's bare "P0" keys
                                          don't carry on their own

This script reconstructs outputs/topic_labels.json from those two files —
restoring src/build_viz_data.py (and everything downstream of it) to a
runnable state WITHOUT redoing any curation. It does not touch the topic
model itself and needs no heavy dependencies (stdlib json + pathlib only).

Run once, now, to unblock the pipeline:
    python scripts/_reconstruct_topic_labels.py

Refuses to overwrite an existing outputs/topic_labels.json (same
never-clobber-curation stance as the seed-bootstrap step added to
src/topics_bertopic.py) — delete it first if you deliberately want to
regenerate from the committed EnricoVis JSON instead of whatever's on disk.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENRICOVIS_DATA = REPO_ROOT / "docs" / "EnricoVis" / "data"
OUTPUTS = REPO_ROOT / "outputs"


def reconstruct() -> dict:
    topics = json.loads((ENRICOVIS_DATA / "topics.json").read_text(encoding="utf-8"))
    hier = json.loads((ENRICOVIS_DATA / "grants_hier.json").read_text(encoding="utf-8"))

    topics_out = {
        str(t["id"]): {"label": t["name"], "top_terms": t["terms"], "parent": t["parent"]}
        for t in topics
    }

    # grants_hier.json's "parents" list carries the human-readable group name
    # per integer parent id (0..7, or -1 for "Unassigned") — topics.json only
    # has the bare "P0".."P7" key. Reassemble the {pid: {label, topic_ids}}
    # shape src/build_viz_data.py expects.
    parents_out = {}
    for hp in hier["parents"]:
        if hp["id"] < 0:
            continue  # "Unassigned" isn't a real "Pn" group
        pid = f"P{hp['id']}"
        topic_ids = sorted(t["id"] for t in topics if t["parent"] == pid)
        parents_out[pid] = {"label": hp["name"], "topic_ids": topic_ids}

    n_topics = len([t for t in topics if t["id"] >= 0])
    return {"_meta": {"n_topics": n_topics}, "topics": topics_out, "parents": parents_out}


def main() -> None:
    out_path = OUTPUTS / "topic_labels.json"
    if out_path.exists():
        raise SystemExit(
            f"{out_path} already exists — refusing to overwrite (it may be hand-curated "
            "beyond what's reconstructable from the committed EnricoVis JSON). Delete it "
            "first if you deliberately want to regenerate from docs/EnricoVis/data/."
        )

    labels = reconstruct()
    OUTPUTS.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
    print(f"wrote {out_path}  "
          f"({labels['_meta']['n_topics']} topics, {len(labels['parents'])} parents)")


if __name__ == "__main__":
    main()
