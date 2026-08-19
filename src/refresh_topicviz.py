"""
refresh_topicviz.py — one command to recompile docs/TopicVizPrototypes/ from
whatever topic-model output is currently on disk.

This is the "visualization compile step," not the analysis itself — it does
NO embedding, UMAP, or HDBSCAN work of its own. Everything it runs is already
fast (src/build_viz_aggregates.py is ~1s) and needs only the light
dependencies (requirements-viz.txt: pandas/pyarrow/rapidfuzz), never torch/
bertopic/umap-learn. Run this after dropping in a new topic-model fit (see
docs/TOPIC_MODEL_REFIT_CHECKLIST.md for the full pipeline, including the
heavy steps that come before this one):

    python -m src.refresh_topicviz

Runs, in order:
  1. python -m src.build_viz_data           — ONLY if data/processed/topic_
                                               assignments.parquet is newer
                                               than docs/EnricoVis/data/
                                               topics.json (see _needs_rebuild
                                               below); skipped otherwise, since
                                               its own inputs (the SPECTER2/
                                               BERTopic artifacts) usually
                                               aren't even present locally.
  2. python -m src.build_viz_aggregates     — always (cheap, and its OTHER
                                               inputs — data/processed/
                                               faculty*.parquet etc. — can
                                               change independent of the
                                               topic model).
  3. scripts/_check_topicviz.py --data-only — always; verifies every dataset
                                               the three prototype pages
                                               fetch() at runtime exists in
                                               data/ and parses, and that the
                                               aggregator has no output no
                                               page reads. Nothing is
                                               rewritten — data/*.json IS what
                                               the pages load; there is no
                                               second copy to keep in sync
                                               (that used to be
                                               scripts/_inline_topicviz_data.py's
                                               job — retired along with the
                                               inlining it existed to redo).

The three prototype pages fetch() their JSON from ./data/ as ES modules, so
they need an HTTP origin — they will NOT work opened directly as a file
(module loading and fetch() are both blocked by file:// CORS rules). Serve
the directory locally to actually look at them:
    python -m http.server 8000 --directory docs/TopicVizPrototypes
GitHub Pages works because .github/workflows/deploy-notebooks.yml copies
data/, shared/, and each page's own module directory alongside the HTML
into docs/onlineoutput/ at the same relative paths.

Each step is invoked as `python -m src.<module>` (a real subprocess, using
the SAME interpreter this script is run with) rather than imported and
called in-process, so this stays a thin, transparent wrapper around exactly
the commands documented in the refit checklist — nothing it does is hidden
from someone reading the printed output.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
ENRICOVIS_DATA = REPO_ROOT / "docs" / "EnricoVis" / "data"


def _run(args: list[str]) -> None:
    print(f"$ {' '.join(args)}")
    subprocess.run(args, check=True)


def _needs_rebuild() -> bool:
    """Is data/processed/topic_assignments.parquet newer than the EnricoVis
    JSON it feeds? Compares mtimes, not content — cheap and sufficient here
    since both sides are always written in one shot by their own script.
    """
    assignments = PROC / "topic_assignments.parquet"
    topics_json = ENRICOVIS_DATA / "topics.json"
    if not assignments.exists():
        return False  # nothing to rebuild from — build_viz_data would just fail loudly
    if not topics_json.exists():
        return True  # EnricoVis JSON missing entirely — needs a first build
    return assignments.stat().st_mtime > topics_json.stat().st_mtime


def main() -> None:
    python = sys.executable

    if _needs_rebuild():
        print("data/processed/topic_assignments.parquet is newer than "
              "docs/EnricoVis/data/topics.json — rebuilding it first.")
        _run([python, "-m", "src.build_viz_data"])
    else:
        print("docs/EnricoVis/data/*.json is up to date with "
              "topic_assignments.parquet — skipping src.build_viz_data.")

    _run([python, "-m", "src.build_viz_aggregates"])
    _run([python, str(REPO_ROOT / "scripts" / "_check_topicviz.py"), "--data-only"])

    print("\ndone — data/*.json is the single source of truth; the pages fetch() it "
          "at load. Verify with:\n"
          f"  {python} -m http.server 8000 --directory docs/TopicVizPrototypes\n"
          "  then open http://localhost:8000/{what_we_can_see,topic_flow,about}.html\n"
          "Full structural check set (syntax/import-graph/id cross-reference, needs node):\n"
          f"  {python} scripts/_check_topicviz.py")


if __name__ == "__main__":
    main()
