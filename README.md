# Northeastern Faculty Funding & Grant Visualization

An exploratory data-visualization project on Northeastern University's faculty funding and
grant history (~1995–2026, ~$2.18B in awards across ~2,676 grants and ~2,247 faculty). This
README is a human-facing tour of what's here and how it fits together. If you're going to work
in the code itself, also read **`CLAUDE.md`** at the repo root — it covers the data pipeline's
internals, identifier gotchas, and a checklist of what's genuinely left unfinished.

## What's in this repo, at a glance

1. **A data pipeline** (`src/`) that cleans and joins six raw Northeastern data exports into a
   handful of tidy tables (`data/processed/*.parquet`).
2. **Nine Jupyter notebooks** (`notebooks/01`–`09`) that explore that data — funding trends,
   who gets funded, collaboration networks, and topic modeling of grant abstracts.
3. **A topic model** of what NEU's grants are actually *about*, built from grant titles and
   abstracts, culminating in a curated keyword classifier (see "How grants are topic-modeled"
   below).
4. **A final interactive dashboard** (`docs/TopicVizPrototypes/`) that turns all of the above
   into something you can explore in a browser, published to GitHub Pages.

Everything under `docs/` is published as a static site — see "Publishing" below.

## Quickstart: what actually needs to run

**Just want to view the finished dashboard? Nothing does.** The dashboard's own data
(`docs/TopicVizPrototypes/data/*.json`) is committed to this repo — it's a built artifact, not
raw data, but it's tracked deliberately so the deliverable works straight out of a fresh clone:

```bash
git clone <this repo>
python -m http.server 8000 --directory docs/TopicVizPrototypes
# open http://localhost:8000/what_we_can_see.html
```

**To regenerate that data** (after a raw-data update, or to work with the underlying tables in
the notebooks), the raw inputs are committed (`DataSet/*.xlsx`) but the derived tables are not
(`data/processed/` is gitignored — see "Should we commit `data/processed/`?" below for why).
Two fast, free, fully deterministic steps rebuild everything the dashboard needs:

```bash
pip install -r requirements.txt      # or requirements-viz.txt for a lighter, dashboard-only set
python src/build_dataset.py          # raw DataSet/*.xlsx -> data/processed/*.parquet (~30s)
python -m src.refresh_topicviz       # data/processed/ + the committed topic-model output ->
                                      # docs/TopicVizPrototypes/data/*.json (~1s)
python -m http.server 8000 --directory docs/TopicVizPrototypes
```

`refresh_topicviz` does **not** need the heavy BERTopic/SPECTER2/embedding pipeline (that's a
separate, rarely-needed step covered in "How grants are topic-modeled" below) — the topic model
itself is already frozen and committed (`docs/EnricoVis/data/*.json`, `outputs/topic_keywords.json`),
and `refresh_topicviz` reads that rather than re-fitting anything.

## 1. The data pipeline

`src/build_dataset.py` reads raw `.xlsx`/`.csv` files from `DataSet/` (HR roster, grant
records, co-PI records, abstract records, federal-award cross-reference data) and writes seven
clean, joined tables to `data/processed/` — one row per faculty member, one row per grant, one
row per (faculty, grant) link, and so on. Run it with:

```bash
pip install -r requirements.txt
python src/build_dataset.py
```

This takes about 30 seconds and needs to be re-run any time the raw data changes; everything
downstream (notebooks, topic model, dashboard) reads from its output, never from the raw files
directly. See `src/README.md` for the full column-by-column reference, and `CLAUDE.md`'s
"Identifiers" section before joining anything by hand — there are a few identifier traps
(mismatched ID spaces, a reserved sentinel value) that are easy to get wrong on a first pass.

## 2. The notebooks (`notebooks/01`–`09`)

Run in order — later notebooks depend on Parquet files produced by earlier steps (or by
`build_dataset.py` directly). Open with `jupyter lab notebooks/01_schema_overview.ipynb`, or
see `notebooks/README.md` for the full list and running order.

| # | What it's for |
|---|---|
| 01 | Sanity-checks the data — schemas, nulls, join integrity. Start here if something looks wrong upstream. |
| 02 | Baseline funding patterns: grant sizes, durations, agencies, faculty rank/tenure. |
| 03 | Funding over time: annual and cumulative totals, trends by college and agency, pre/post-COVID. |
| 04 | Who gets funded: concentration (a small number of faculty hold a large share of dollars), top departments, attribution to NEU vs. prior institutions. |
| 05 | Collaboration: a co-PI network graph, influential collaborators, cross-college collaboration patterns. |
| 06 | An early topic model (LDA) over grant abstracts — kept for historical comparison, not the model the dashboard uses. |
| 07 | A more advanced topic model (BERTopic, using AI-generated document embeddings) — also comparison-only now, not canonical. |
| 08 | How the project recovered a lot of missing grant-abstract text from NIH/NSF's own public databases, and what that did for topic-model quality. |
| 09 | Validates the topic model the dashboard actually uses (see below) against a hand-labeled set of grants. |

Notebooks 06–09 tell the story of how this project arrived at its final topic-modeling
approach: an early, weaker model (06), a stronger one (07), a data-recovery effort that made
both better (08), and finally validation of the approach that replaced them both (09).

## 3. How grants are topic-modeled (the short version)

Early in the project, grants were assigned a "topic" (e.g. "Biomedical Sciences," "Wireless
Communications") using machine-learning clustering methods (LDA, then BERTopic) that group
grants by the similarity of their text. These worked reasonably well but had a real weakness:
nobody could easily see *why* a grant landed in a given topic, and a meaningful chunk of grants
were left "Unassigned."

The final approach — the one the dashboard displays — is a **curated keyword classifier**: a
human-reviewed list of keywords for each of 31 specific topics (grouped into 8 broader parent
categories), and a transparent scoring function that matches each grant's title/abstract against
those keyword lists. This is slower to build (someone has to curate the keyword lists) but far
more inspectable — anyone can see exactly which words caused a grant to be classified the way it
was — and validated meaningfully better against a hand-labeled test set than the earlier
clustering methods. A small number of genuinely hard-to-classify grants get a second look from
an AI model as a final tiebreaker. See `CLAUDE.md`'s "Topic modeling — state of play" for the
full technical account, including known limitations.

## 4. The final dashboard (`docs/TopicVizPrototypes/`)

Two browser pages, built from plain HTML/CSS/JavaScript (no build step, no framework):

- **`what_we_can_see.html`** — the main dashboard, with three tabs:
  - **Every grant** — all 2,676 grants as an arrangeable grid, splittable/sortable/colorable by
    agency, year, college, funding attribution, topic, dollar amount, and more.
  - **Every PI** — all 2,247 roster faculty (not just the ones with a grant in this dataset) as
    a parallel grid, so "no grants" is visible as its own honest category rather than silently
    dropped.
  - **About this data & what's missing** — the dashboard's own honesty layer: what the headline
    numbers mean, every important caveat about the data (in one place, ranked by severity), and
    a field-by-field account of what's known vs. missing and why.
- **`topic_flow.html`** — funding over time, broken down by topic.

Selecting any grant or PI opens a detail card with the full story for that record — funding
amount, collaborators, topic classification (and *why*, via the matched keywords), and abstract
text where available.

### Running it locally

The committed `docs/TopicVizPrototypes/data/*.json` already reflects the current state of
everything below, so this is only needed to *regenerate* that data (see "Quickstart" above for
just viewing it as-is):

```bash
# One-time setup — a lighter dependency set than the full pipeline (no torch/bertopic/umap)
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements-viz.txt

# Rebuild data/processed/ from raw data (needed once, or whenever raw data changes —
# refresh_topicviz below reads from here and will fail without it on a fresh clone)
.venv/bin/python src/build_dataset.py

# Build/refresh the JSON the dashboard reads
.venv/bin/python -m src.refresh_topicviz

# Serve it — the pages fetch() their data as JSON, so this must be over HTTP, not a file:// URL
python -m http.server 8000 --directory docs/TopicVizPrototypes
```

Then open `http://localhost:8000/what_we_can_see.html` or `http://localhost:8000/topic_flow.html`.
See `docs/TopicVizPrototypes/README.md` for the full setup/refresh/verify workflow.

### Should we commit `data/processed/`?

Worth naming explicitly since it's easy to assume otherwise: `data/processed/` (the pipeline's
output) is gitignored, not committed — only the *raw* inputs (`DataSet/*.xlsx`) and the
dashboard's *final* built JSON (`docs/TopicVizPrototypes/data/*.json`) are. In practice this
costs little, because regenerating it is two fast (~30s total), free, fully deterministic
commands (above) from files already in the repo — there's no rate-limited API, paid step, or
manual judgment call involved, unlike (for example) the NIH/NSF backfill data in
`data/nih_nsf_backfill/`, which genuinely *is* committed specifically because re-fetching it
would take a long, rate-limited round trip. The directory also holds some large, non-essential-
for-the-dashboard artifacts (a ~13 MB cached BERTopic model, ~8 MB SPECTER2 embeddings, and a
CSV *and* Parquet copy of every table) that would meaningfully bloat the git history if
committed wholesale. If a future need arises for zero-command reproducibility of just the seven
canonical tables specifically (no CSVs, no model/embedding caches), that's a much smaller,
targeted ask — flag it rather than committing the whole directory.

## Publishing

Everything in `docs/` is published to GitHub Pages via `.github/workflows/deploy-notebooks.yml`,
which runs on every push to `main`: notebooks are converted to HTML, the dashboard's data/module
directories are copied alongside its pages, and an index page is regenerated — all into
`docs/onlineoutput/`, which is what actually deploys.

**If this project ever moves to a different GitHub repo** (ownership transfer, a fork, or
hosting it under someone else's account), the workflow needs no code changes — it's verified
repo-agnostic. The one required step is enabling Pages in the new repo's own Settings → Pages
(source: "GitHub Actions"), since that setting doesn't carry over automatically. See
`CLAUDE.md`'s "Setup & core commands" section for the full walkthrough.

## A note on scope

You'll also find `docs/EnricoVis/` in this repo — a separate, parallel set of visualizations
built independently by the project's faculty advisor, exploring some of the same data from a
spatial-embedding angle. It's included as read-only reference / inspiration, not part of this
project's own deliverable, and shouldn't be edited as part of this codebase's own work.

## Where to go next

- **Working on the code?** Read `CLAUDE.md` — pipeline internals, identifier gotchas, hard-won
  lessons, and an ordered list of what's genuinely left unfinished on this project.
- **Want the full history of decisions and why they were made?** `.claude/sessions/*.md` has a
  running log of past work sessions; `docs/*.md` (see `CLAUDE.md`'s reference map) has deeper
  write-ups of specific efforts like the topic-model redo and the abstract-recovery backfill.
- **Just want to explore the data?** Start with `notebooks/01_schema_overview.ipynb`, or go
  straight to the live dashboard if a published version is already up.
