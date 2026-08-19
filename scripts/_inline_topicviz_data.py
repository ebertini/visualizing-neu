"""
_inline_topicviz_data.py — ad-hoc diagnostic/build helper, not part of the
pipeline (see the underscore-prefix convention in CLAUDE.md).

Re-inlines the current docs/TopicVizPrototypes/data/*.json into the three
prototype HTML files (topic_flow.html, what_we_can_see.html, about.html),
which embed their data as `const NAME = <json>;` rather than fetch()-ing it —
CI never publishes source data/ directories, so a fetch() build would 404 on
GitHub Pages (see docs/TOPIC_WORK_EXECUTION_REPORT.md and the topic_flow.html
module comment).

These prototypes are the user's own analysis work (docs/TopicVizPrototypes/),
kept separate from docs/EnricoVis/ (a parallel visualization effort by the
PI) — see src/build_viz_aggregates.py's module docstring for the split.

Run this after any `python -m src.build_viz_aggregates` if you've edited the
HTML template and need to resync the embedded data blocks — or let
src/refresh_topicviz.py call it for you as the last step of a full recompile.

Usage:
    .venv/bin/python scripts/_inline_topicviz_data.py           # rewrite in place
    .venv/bin/python scripts/_inline_topicviz_data.py --check    # verify only, write nothing
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "docs" / "TopicVizPrototypes" / "data"
VIZ_DIR = REPO_ROOT / "docs" / "TopicVizPrototypes"

# (html filename, [(JS const name, json filename), ...])
TARGETS = [
    ("topic_flow.html", [("VIZ_META", "viz_meta.json"), ("TOPIC_TIME", "topic_time.json")]),
    ("what_we_can_see.html", [
        ("VIZ_META", "viz_meta.json"), ("COVERAGE", "coverage.json"),
        ("FACETS", "facets.json"), ("FACETS_PI", "facets_pi.json"),
        ("MISSINGNESS", "missingness.json"), ("FUNNEL", "funnel.json"),
    ]),
    ("about.html", [("VIZ_META", "viz_meta.json"), ("COVERAGE", "coverage.json")]),
]


def _pattern(const_name: str) -> re.Pattern[str]:
    return re.compile(rf"(const {const_name} = ).*?(;\n)", re.S)


def reinline(html_name: str, bindings: list[tuple[str, str]]) -> None:
    path = VIZ_DIR / html_name
    text = path.read_text(encoding="utf-8")
    for const_name, json_name in bindings:
        payload = (DATA_DIR / json_name).read_text(encoding="utf-8")
        text, n = _pattern(const_name).subn(lambda m: m.group(1) + payload + m.group(2), text, count=1)
        if n != 1:
            raise RuntimeError(f"expected exactly one `const {const_name} = ...;` in {html_name}, found {n}")
    path.write_text(text, encoding="utf-8")
    print(f"re-inlined {html_name}  ({path.stat().st_size / 1024:.0f} KB)")


def check(html_name: str, bindings: list[tuple[str, str]]) -> bool:
    """Verify each binding's currently-inlined blob matches data/*.json, without writing.

    Answers "did someone run build_viz_aggregates but forget to re-inline?" —
    a MISMATCH means the HTML is stale relative to data/*.json, not that
    anything is broken outright.
    """
    text = (VIZ_DIR / html_name).read_text(encoding="utf-8")
    all_ok = True
    for const_name, json_name in bindings:
        expected = (DATA_DIR / json_name).read_text(encoding="utf-8")
        m = _pattern(const_name).search(text)
        if m is None:
            print(f"  MISMATCH  {html_name}: const {const_name} = ...; not found")
            all_ok = False
            continue
        actual = m.group(0)[len(m.group(1)):-len(m.group(2))]
        status = "PASS" if actual == expected else "MISMATCH"
        if status == "MISMATCH":
            all_ok = False
        print(f"  {status:8}  {html_name}: {const_name} ({json_name})")
    return all_ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                     help="verify the inlined blobs match data/*.json; write nothing")
    args = ap.parse_args()

    if args.check:
        all_ok = True
        for html_name, bindings in TARGETS:
            all_ok &= check(html_name, bindings)
        if not all_ok:
            raise SystemExit(
                "\nSome inlined data is stale — run "
                "`.venv/bin/python scripts/_inline_topicviz_data.py` (no --check) to fix."
            )
        print("\nall inlined data matches docs/TopicVizPrototypes/data/*.json")
        return

    for html_name, bindings in TARGETS:
        reinline(html_name, bindings)


if __name__ == "__main__":
    main()
