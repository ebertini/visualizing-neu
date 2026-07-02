"""Regenerate docs/index.html with links to every converted notebook.

Scans notebooks/*.ipynb, extracts a title (first H1 in the first markdown cell)
and an optional description (following non-empty line/paragraph), and rewrites
the <ul class="notebook-list"> block in docs/index.html.
"""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = ROOT / "notebooks"
INDEX_PATH = ROOT / "docs" / "index.html"

LIST_BLOCK_RE = re.compile(
    r'(<ul class="notebook-list">)(.*?)(</ul>)',
    re.DOTALL,
)


def prettify(stem: str) -> str:
    # "01_schema_overview" -> "01 · Schema Overview"
    parts = stem.split("_", 1)
    if len(parts) == 2 and parts[0].isdigit():
        num, rest = parts
        return f"{num} · {rest.replace('_', ' ').title()}"
    return stem.replace("_", " ").title()


def extract_meta(nb_path: Path) -> tuple[str, str]:
    try:
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
    except Exception:
        return prettify(nb_path.stem), ""

    title = ""
    description = ""
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        source = cell.get("source", "")
        text = "".join(source) if isinstance(source, list) else source
        lines = [ln.strip() for ln in text.splitlines()]
        for i, ln in enumerate(lines):
            if not title and ln.startswith("# "):
                title = ln.lstrip("# ").strip()
                # Look for the next non-empty, non-heading line as description.
                for follow in lines[i + 1 :]:
                    if follow and not follow.startswith("#"):
                        description = follow
                        break
                break
        if title:
            break

    if not title:
        title = prettify(nb_path.stem)
    return title, description


def build_items() -> str:
    notebooks = sorted(NOTEBOOKS_DIR.glob("*.ipynb"))
    items: list[str] = []
    for nb in notebooks:
        if nb.stem.startswith("."):
            continue
        title, description = extract_meta(nb)
        href = f"{nb.stem}.html"
        desc_html = (
            f'\n                <div class="description">{escape(description)}</div>'
            if description
            else ""
        )
        items.append(
            "            <li>\n"
            f'                <a href="{escape(href)}">{escape(title)}</a>'
            f"{desc_html}\n"
            "            </li>"
        )
    return "\n" + "\n".join(items) + "\n        "


def main() -> None:
    if not INDEX_PATH.exists():
        raise SystemExit(f"index.html not found at {INDEX_PATH}")

    html = INDEX_PATH.read_text(encoding="utf-8")
    new_items = build_items()

    if not LIST_BLOCK_RE.search(html):
        raise SystemExit(
            'Could not find <ul class="notebook-list"> block in index.html'
        )

    new_html = LIST_BLOCK_RE.sub(
        lambda m: f"{m.group(1)}{new_items}{m.group(3)}",
        html,
        count=1,
    )
    INDEX_PATH.write_text(new_html, encoding="utf-8")
    print(f"Updated {INDEX_PATH} with {new_html.count('<li>')} notebook link(s).")


if __name__ == "__main__":
    main()
