# TopicVizPrototypes

Three self-contained prototype pages for exploring Northeastern's grant/topic
data: **`what_we_can_see.html`** (Every grant / Every PI / What's missing &
where it goes), **`topic_flow.html`** (funding over time by topic), and
**`about.html`** (coverage headline + caveats + frozen-inputs summary).

They fetch their data as JSON from `data/` at load time via ES modules, so
**they must be served over HTTP** — opening them directly as a `file://` URL
will not work (both `fetch()` and ES module loading are blocked by
`file://` CORS rules).

## 1. Set up the light-deps venv (one-time)

These pages only need the ETL/aggregation stack (`pandas`/`pyarrow`/
`openpyxl`/`rapidfuzz`), not the full `torch`/`bertopic`/`umap-learn` stack
used for the topic-model refit itself.

Bare `python3.11 -m venv` fails on this machine (uv-managed Python needs
uv's own wiring), so use `uv` instead, from the repo root:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements-viz.txt
```

## 2. Build/refresh the data the pages read

From the repo root, with the venv's interpreter:

```bash
.venv/bin/python -m src.refresh_topicviz
```

This runs, in order: `src.build_viz_data` (only if
`data/processed/topic_assignments.parquet` is newer than the EnricoVis JSON
it feeds — usually a no-op unless you've just re-fit the topic model),
`src.build_viz_aggregates` (always — writes `docs/TopicVizPrototypes/data/*.json`),
and `scripts/_check_topicviz.py --data-only` (verifies every dataset the
pages fetch() actually exists and parses). Takes about a second.

## 3. Serve the directory and open the pages

```bash
python -m http.server 8000 --directory docs/TopicVizPrototypes
```

Then open in a browser:

- http://localhost:8000/what_we_can_see.html
- http://localhost:8000/topic_flow.html
- http://localhost:8000/about.html

## Notes

- `data/` is the single source of truth for both pages — there's no
  duplicated copy of the datasets inlined in the HTML.
- `docs/EnricoVis/data/{grants_umap,topics}.json` are read as a read-only
  upstream input (the PI's canonical BERTopic/SPECTER2 output); this
  directory writes only into its own `data/` and `shared/`.
- After any structural JS/HTML edit, also run the fuller structural check
  (needs `node`):
  ```bash
  .venv/bin/python scripts/_check_topicviz.py
  ```
  It checks tag balance, the ES-module import graph (syntax, named exports,
  cycles), and an id cross-reference — but it cannot confirm actual
  rendering/layout/interaction in a browser, so treat any visual change as
  needing a real-browser check before publishing.
- On GitHub Pages, `.github/workflows/deploy-notebooks.yml` copies `data/`,
  `shared/`, and each page's own module directory into `docs/onlineoutput/`
  at the same relative paths — no manual step needed there.
