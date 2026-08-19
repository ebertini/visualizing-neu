"""
_check_topicviz.py — ad-hoc diagnostic, not part of the build pipeline
except as a read-only verification step (see the underscore-prefix
convention in CLAUDE.md). Unlike some other scripts/_*.py diagnostics, this
one writes nothing anywhere — it only reads and reports.

Replaces scripts/_inline_topicviz_data.py, deleted as part of the switch
from inlining docs/TopicVizPrototypes/data/*.json into the three prototype
HTML files to having each page fetch() it at load from an ES module (see
docs/TOPIC_MODEL_REFIT_CHECKLIST.md). The inliner's `--check` mode answered
"is the duplicated copy stale?" — a question that no longer has meaning
once there is no duplicate. This script checks the inverse invariant that
matters now: does every dataset a page fetches actually exist in data/ and
parse, and does the aggregator (src/build_viz_aggregates.py) emit anything
no page reads?

It also runs a handful of structural checks over the three pages' JS
modules — import resolution, named-export agreement, cycle detection, and
an id cross-reference — that a real browser would surface as a boot-fatal
error but that a text editor or a Python-only environment can't otherwise
see. See the "what this cannot prove" footer this script prints: it is
NOT a substitute for loading the pages in a real browser.

Usage:
    .venv/bin/python scripts/_check_topicviz.py               # everything
    .venv/bin/python scripts/_check_topicviz.py --data-only    # just the
                                                                # dataset
                                                                # reconcile
    .venv/bin/python scripts/_check_topicviz.py --root docs/onlineoutput
                                                                # check a
                                                                # published
                                                                # copy
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO_ROOT / "docs" / "TopicVizPrototypes"

# (html filename, data.js module the page's entry chain fetches from)
PAGES = [
    ("what_we_can_see.html", "what_we_can_see/data.js"),
    ("topic_flow.html", "topic_flow/data.js"),
    ("about.html", "about/data.js"),
]

FOOTER = """\
These are STATIC checks. They prove the files parse, resolve, and reference
ids and datasets that exist. They CANNOT prove:
  - that anything renders at all (no DOM, no layout engine, no d3 execution)
  - that the layout is correct (box model, computed styles, SVG viewBox/
    height interaction)
  - that any interaction works (clicks, hover, hit-testing, dial/legend
    toggles, tab switching, Esc-to-dismiss)
  - that the fetch()/await ordering is right — a render running before its
    data resolves is invisible to every check here
  - that colors, scales, sort orders, or numbers are unchanged from before
A REAL-BROWSER PASS IS REQUIRED BEFORE PUBLISHING:
    python -m http.server 8000 --directory docs/TopicVizPrototypes
then load each page and confirm the Console and Network tab are clean."""


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def ok(msg: str) -> None:
    print(f"  ok    {msg}")


# ---------------------------------------------------------------- dataset reconcile

def _extract_datasets_literal(data_js: Path) -> dict[str, str]:
    """Regex the `export const DATASETS = {...};` object literal out of a
    data.js module — mirrors how the old inliner regexed `const NAME = `
    out of the HTML, keeping the JS the single source of truth."""
    text = data_js.read_text(encoding="utf-8")
    m = re.search(r"export const DATASETS\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        return {}
    pairs = re.findall(r'(\w+)\s*:\s*"([^"]+)"', m.group(1))
    return dict(pairs)


def _extract_aggregator_emits(build_viz_aggregates: Path) -> set[str]:
    """Regex the emit list out of src/build_viz_aggregates.py's main()."""
    text = build_viz_aggregates.read_text(encoding="utf-8")
    m = re.search(r"for name, obj in \[(.*?)\]:", text, re.S)
    if not m:
        return set()
    return set(re.findall(r'\("(\w+)"', m.group(1)))


def check_datasets(root: Path) -> bool:
    print(f"data wiring — {root.relative_to(REPO_ROOT) if root.is_relative_to(REPO_ROOT) else root}")
    all_ok = True
    referenced: set[str] = set()

    for html_name, data_js_rel in PAGES:
        data_js = root / data_js_rel
        if not data_js.exists():
            fail(f"{html_name}: {data_js_rel} not found")
            all_ok = False
            continue
        datasets = _extract_datasets_literal(data_js)
        if not datasets:
            fail(f"{html_name}: no DATASETS literal found in {data_js_rel}")
            all_ok = False
            continue
        for const_name, rel_path in datasets.items():
            referenced.add(Path(rel_path).name)
            fpath = root / rel_path
            if not fpath.exists():
                fail(f"{html_name}: {const_name} -> {rel_path} not found in data/")
                all_ok = False
                continue
            try:
                json.loads(fpath.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                fail(f"{html_name}: {const_name} -> {rel_path} does not parse ({e})")
                all_ok = False
                continue
            size_kb = fpath.stat().st_size / 1024
            ok(f"{html_name:22} {const_name:12} {rel_path:24} {size_kb:>7.0f} KB")

    aggregates_py = REPO_ROOT / "src" / "build_viz_aggregates.py"
    if aggregates_py.exists():
        emitted = {f"{n}.json" for n in _extract_aggregator_emits(aggregates_py)}
        unread = emitted - referenced
        for name in sorted(unread):
            warn(f"src.build_viz_aggregates emits {name} — no page fetches it")
        missing_emit = referenced - emitted
        # facets.json/facets_pi.json/etc. are all in `emitted`; anything
        # referenced but not emitted is a real mismatch (typo, or a rename
        # applied to one side only).
        for name in sorted(missing_emit):
            fail(f"a page fetches {name} — src.build_viz_aggregates.py does not emit it")
            all_ok = False

    print(f"\n{len(referenced)} distinct datasets referenced across {len(PAGES)} pages.")
    return all_ok


# ---------------------------------------------------------------- JS module graph

IMPORT_RE = re.compile(r'import\s*\{([^}]*)\}\s*from\s*["\'](\./[^"\']+)["\']')
# `export const a = 1;` and function/class declarations — single-name forms.
EXPORT_DECL_RE = re.compile(
    r'export\s+(?:function\*?|class|async\s+function)\s+([A-Za-z_$][\w$]*)'
)
# `export const a = 1, b = 2, c = 3;` — one `export const/let/var` statement
# can declare several comma-separated names (see layout.js's MIN_CELL_COLS/
# CELL_PAD/.../LABEL_LANE line); capture the WHOLE statement up to its
# terminating `;` and pull every top-level identifier before an `=` out of it,
# rather than just the first one.
EXPORT_CONST_STMT_RE = re.compile(r'export\s+(?:const|let|var)\s+(.*?);', re.S)
EXPORT_CONST_NAME_RE = re.compile(r'(?:^|,)\s*([A-Za-z_$][\w$]*)\s*=')
EXPORT_BRACE_RE = re.compile(r'export\s*\{([^}]*)\}(?!\s*from)')
# Attribute order isn't required — `<script src="..." type="module">` is
# just as valid HTML as `<script type="module" src="...">`, so matching a
# fixed order would silently stop finding entry points on a harmless
# reordering. Lookaheads assert both attributes are present on the SAME
# tag regardless of order, with `src`'s value as the one capture group.
SCRIPT_MODULE_SRC_RE = re.compile(r'<script(?=[^>]*\btype="module")(?=[^>]*\bsrc="([^"]+)")[^>]*>')
# topic_flow.html and about.html use an INLINE `<script type="module">` (no
# src) — their import line pulls in data.js, but the rest of the page logic
# (the id-touching code) stays inline in the HTML. Capture that text too so
# the id cross-reference actually checks something for those two pages.
SCRIPT_MODULE_INLINE_RE = re.compile(r'<script\s+type="module"(?!\s+src)[^>]*>(.*?)</script>', re.S)
GETID_RE = re.compile(r'getElementById\(["\']([^"\']+)["\']\)')
QUERY_ID_RE = re.compile(r'querySelector(?:All)?\(["\']#([A-Za-z_][\w-]*)["\']')
HTML_ID_RE = re.compile(r'\bid="([^"]+)"')


def _strip_comments(text: str) -> str:
    """Blank out //-line and /*block*/ comments, leaving everything else
    (including string/template contents) at its original position and
    line number — so a commented-out `export const NOISE = ...` can't be
    regex-matched as a real export, and a template literal containing `//`
    or `/*` (none currently do, but don't assume that stays true) is left
    alone. A real tokenizer would be more correct; this lightweight
    string-aware scan is enough to close the specific false-pass this
    script's regexes are exposed to without pulling in a JS parser."""
    out = []
    i, n = 0, len(text)
    in_string: str | None = None  # one of '"', "'", "`", or None
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == in_string:
                in_string = None
            i += 1
            continue
        if c in "\"'`":
            in_string = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _module_exports(path: Path) -> set[str]:
    text = _strip_comments(path.read_text(encoding="utf-8"))
    names = set(EXPORT_DECL_RE.findall(text))
    for stmt in EXPORT_CONST_STMT_RE.findall(text):
        names.update(EXPORT_CONST_NAME_RE.findall(stmt))
    for m in EXPORT_BRACE_RE.finditer(text):
        for part in m.group(1).split(","):
            part = part.strip()
            if not part:
                continue
            names.add(part.split(" as ")[-1].strip())
    return names


def _module_imports(path: Path) -> list[tuple[list[str], Path]]:
    text = _strip_comments(path.read_text(encoding="utf-8"))
    out = []
    for names_str, rel in IMPORT_RE.findall(text):
        names = [n.strip().split(" as ")[-1].strip() for n in names_str.split(",") if n.strip()]
        target = (path.parent / rel).resolve()
        out.append((names, target))
    return out


def check_js_graph(root: Path) -> bool:
    print("\nJS module graph")
    all_ok = True
    node_check_ok = _check_node_available()

    all_modules: set[Path] = set()
    for html_name, data_js_rel in PAGES:
        html_path = root / html_name
        if not html_path.exists():
            fail(f"{html_name}: not found — its JS was not checked at all")
            all_ok = False
            continue
        html_text = html_path.read_text(encoding="utf-8")

        for entry_rel in SCRIPT_MODULE_SRC_RE.findall(html_text):
            entry = (root / entry_rel).resolve()
            all_ok &= _walk_graph(entry, all_modules, node_check_ok)

        # topic_flow.html and about.html keep their page logic INLINE inside
        # `<script type="module">` (no src) and only import data.js
        # externally — walking only external `<script src>` entries (as
        # above) would give those two pages zero JS checking at all. Check
        # the inline body's own syntax and walk whatever it imports.
        for inline_body in SCRIPT_MODULE_INLINE_RE.findall(html_text):
            if node_check_ok:
                proc = subprocess.run(
                    ["node", "--input-type=module", "--check"],
                    input=inline_body, capture_output=True, text=True,
                )
                if proc.returncode != 0:
                    fail(f"{html_name}: inline <script type=\"module\"> syntax error\n{proc.stderr.strip()}")
                    all_ok = False
            for names, rel in IMPORT_RE.findall(_strip_comments(inline_body)):
                target = (html_path.parent / rel).resolve()
                target_names = [n.strip().split(" as ")[-1].strip() for n in names.split(",") if n.strip()]
                if target.exists():
                    target_exports = _module_exports(target)
                    for name in target_names:
                        if name not in target_exports:
                            fail(f"{html_name}: inline module imports `{name}` from {target.name}, which does not export it")
                            all_ok = False
                all_ok &= _walk_graph(target, all_modules, node_check_ok)

    return all_ok


def _check_node_available() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        warn("node not found on PATH — skipping per-file syntax checks (node --input-type=module --check)")
        return False


def _node_syntax_ok(path: Path) -> bool:
    # IMPORTANT: bare `node --check somefile.js` silently exits 0 on invalid
    # ES-module syntax in a plain .js file (confirmed on node v22.14.0 —
    # Node's CJS/ESM syntax detection swallows the error). Reading from
    # stdin with --input-type=module forces the real module parser.
    proc = subprocess.run(
        ["node", "--input-type=module", "--check"],
        input=path.read_text(encoding="utf-8"),
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        fail(f"{path.name}: syntax error\n{proc.stderr.strip()}")
        return False
    return True


def _walk_graph(entry: Path, seen: set[Path], node_check_ok: bool, stack: tuple[Path, ...] = ()) -> bool:
    all_ok = True
    if entry in stack:
        cycle = " -> ".join(p.name for p in stack + (entry,))
        fail(f"import cycle: {cycle}")
        return False
    if entry in seen:
        return True
    seen.add(entry)

    if not entry.exists():
        fail(f"{entry} does not exist (imported but missing)")
        return False

    if node_check_ok and not _node_syntax_ok(entry):
        all_ok = False

    for names, target in _module_imports(entry):
        if target.exists():
            # Always check against the TARGET's own exports. (A previous
            # version of this check also short-circuited on the importer's
            # own export set, which meant an import was silently treated as
            # fine whenever the importer happened to export a same-named
            # symbol of its own — an unrelated coincidence. Always resolve
            # against the target, never the importer.)
            target_exports = _module_exports(target)
            for name in names:
                if name not in target_exports:
                    fail(f"{entry.name} imports `{name}` from {target.name}, which does not export it")
                    all_ok = False
        all_ok &= _walk_graph(target, seen, node_check_ok, stack + (entry,))

    ok(f"{entry.relative_to(entry.parent.parent) if entry.parent.parent.exists() else entry.name}")
    return all_ok


def check_id_crossref(root: Path) -> bool:
    print("\nid cross-reference (per page, over its reachable modules)")
    all_ok = True
    for html_name, _ in PAGES:
        html_path = root / html_name
        if not html_path.exists():
            continue
        html_text = html_path.read_text(encoding="utf-8")
        html_ids = set(HTML_ID_RE.findall(html_text))

        entries = SCRIPT_MODULE_SRC_RE.findall(html_text)
        modules: set[Path] = set()
        for entry_rel in entries:
            _collect_modules((root / entry_rel).resolve(), modules)

        referenced_ids: set[str] = set()
        for mod in modules:
            if not mod.exists():
                continue
            text = mod.read_text(encoding="utf-8")
            referenced_ids |= set(GETID_RE.findall(text))
            referenced_ids |= set(QUERY_ID_RE.findall(text))
        # Inline module script bodies (topic_flow.html, about.html keep their
        # page logic inline, only importing data.js externally) — scan those
        # directly out of the HTML too.
        for inline_body in SCRIPT_MODULE_INLINE_RE.findall(html_text):
            referenced_ids |= set(GETID_RE.findall(inline_body))
            referenced_ids |= set(QUERY_ID_RE.findall(inline_body))

        missing = referenced_ids - html_ids
        for mid in sorted(missing):
            fail(f"{html_name}: id \"{mid}\" is referenced in JS but not present in the markup")
            all_ok = False
        if not missing:
            ok(f"{html_name}: all {len(referenced_ids)} referenced ids exist in the markup")
    return all_ok


def _collect_modules(entry: Path, seen: set[Path]) -> None:
    if entry in seen or not entry.exists():
        seen.add(entry)
        return
    seen.add(entry)
    for _, target in _module_imports(entry):
        _collect_modules(target, seen)


# ---------------------------------------------------------------- HTML sanity

class _BalanceChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"mismatched </{tag}> at line {self.getpos()[0]}")
        elif self.stack:
            self.stack.pop()


def check_html(root: Path) -> bool:
    print("\nHTML structural checks")
    all_ok = True
    for html_name, _ in PAGES:
        html_path = root / html_name
        if not html_path.exists():
            continue
        text = html_path.read_text(encoding="utf-8")
        size_kb = html_path.stat().st_size / 1024

        parser = _BalanceChecker()
        parser.feed(text)
        if parser.errors:
            for e in parser.errors:
                fail(f"{html_name}: {e}")
            all_ok = False
        elif parser.stack:
            fail(f"{html_name}: unclosed tag(s): {parser.stack}")
            all_ok = False
        else:
            ok(f"{html_name}: tags balanced ({size_kb:.0f} KB)")

        # Regression guard: the whole point of the fetch() refactor is that
        # these pages never re-inline a multi-KB data blob. A `const NAME =`
        # for any of the known dataset names is exactly what a reverted or
        # copy-pasted change would look like.
        for bad_const in ("VIZ_META", "COVERAGE", "FACETS", "FACETS_PI", "MISSINGNESS", "FUNNEL", "TOPIC_TIME"):
            if re.search(rf'\bconst\s+{bad_const}\s*=\s*[\[{{]', text):
                fail(f"{html_name}: found an inlined `const {bad_const} = ...` — data should be fetched, not embedded")
                all_ok = False

        if size_kb > 200:
            fail(f"{html_name}: {size_kb:.0f} KB — over the 200 KB ceiling; check for a re-inlined blob")
            all_ok = False

    return all_ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                     help="directory containing the three pages (default: docs/TopicVizPrototypes)")
    ap.add_argument("--data-only", action="store_true",
                     help="run only the dataset reconcile (for use as a build-pipeline step)")
    args = ap.parse_args()

    root = args.root.resolve()
    all_ok = check_datasets(root)

    if not args.data_only:
        all_ok &= check_html(root)
        all_ok &= check_js_graph(root)
        all_ok &= check_id_crossref(root)

    print("\n" + FOOTER)

    if not all_ok:
        raise SystemExit("\nsome checks FAILED — see above")
    print("\nPASS")


if __name__ == "__main__":
    main()
