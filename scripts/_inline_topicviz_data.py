"""
_inline_topicviz_data.py — ad-hoc diagnostic/build helper, not part of the
pipeline (see the underscore-prefix convention in CLAUDE.md).

Re-inlines the current docs/TopicVizPrototypes/data/*.json into the Round-1
prototype HTML files (topic_flow.html, what_we_can_see.html), which embed
their data as `const NAME = <json>;` rather than fetch()-ing it — CI never
publishes source data/ directories, so a fetch() build would 404 on GitHub
Pages (see docs/TOPIC_WORK_EXECUTION_REPORT.md and the topic_flow.html
module comment).

These prototypes are the user's own analysis work (docs/TopicVizPrototypes/),
kept separate from docs/EnricoVis/ (a parallel visualization effort by the
PI) — see src/build_viz_aggregates.py's module docstring for the split.

Run this after any `python -m src.build_viz_aggregates` if you've edited the
HTML template and need to resync the embedded data blocks.

Usage:
    .venv/bin/python scripts/_inline_topicviz_data.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "docs" / "TopicVizPrototypes" / "data"
VIZ_DIR = REPO_ROOT / "docs" / "TopicVizPrototypes"

# (html filename, [(JS const name, json filename), ...])
TARGETS = [
    ("topic_flow.html", [("VIZ_META", "viz_meta.json"), ("TOPIC_TIME", "topic_time.json")]),
    ("what_we_can_see.html", [("VIZ_META", "viz_meta.json"), ("COVERAGE", "coverage.json")]),
]


def reinline(html_name: str, bindings: list[tuple[str, str]]) -> None:
    path = VIZ_DIR / html_name
    text = path.read_text(encoding="utf-8")
    for const_name, json_name in bindings:
        payload = (DATA_DIR / json_name).read_text(encoding="utf-8")
        pattern = re.compile(rf"(const {const_name} = ).*?(;\n)", re.S)
        text, n = pattern.subn(lambda m: m.group(1) + payload + m.group(2), text, count=1)
        if n != 1:
            raise RuntimeError(f"expected exactly one `const {const_name} = ...;` in {html_name}, found {n}")
    path.write_text(text, encoding="utf-8")
    print(f"re-inlined {html_name}  ({path.stat().st_size / 1024:.0f} KB)")


def main() -> None:
    for html_name, bindings in TARGETS:
        reinline(html_name, bindings)


if __name__ == "__main__":
    main()
