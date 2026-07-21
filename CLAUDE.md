# CLAUDE.md

Guidance for working in this repository. Read this before touching data, notebooks, or the pipeline.

## What this project is

An exploratory **data-visualization project on Northeastern University's faculty funding and grant history** (window ~1995–2026, ~$2.18B in awards). The deliverable is an interactive visualization telling the story of NEU grant funding. Current work is EDA + topic modeling in Jupyter notebooks published to GitHub Pages; the eventual target (see `docs/WEEKLY_PLAN.md`) is a dual-mode **Plotly Dash** dashboard — a touchscreen **kiosk** build plus a responsive public browser build from one codebase.

Sanity-check names (known-good faculty for spot-checking joins): **Saiph Savage, Michael Ann DeVito, Benjamin Gyori**. ID-reconciliation running example: **Chris Martens** (`faculty_id 2963712`).

## Repository layout

```
DataSet/            Raw .xlsx / .csv inputs (see caveat below — these ARE committed)
src/                ETL pipeline (build_dataset.py) + SPECTER2 embedder
data/processed/     Pipeline output: *.parquet (+ shareable *.csv) — GITIGNORED
notebooks/          Numbered EDA notebooks 01–07, run in order
scripts/            generate_index.py (docs) + underscore-prefixed ad-hoc diagnostics
docs/               Reference docs (*.md), published HTML, EnricoVis/ + NedaNotebooks/
outputs/            Generated PNG/CSV figures (w4_/w5_/w6_/w7_ prefixes) — GITIGNORED
figures/            Duplicate of some topic figures
```

## Setup & core commands

```bash
pip install -r requirements.txt          # Python 3.11+; CPU-only for everything
python src/build_dataset.py              # ~30s; regenerates ALL data/processed/*.parquet
python src/build_specter2_embeddings.py  # one-shot SPECTER2 cache for notebook 07 (~5–8 min CPU)
jupyter lab notebooks/01_schema_overview.ipynb   # run notebooks 01→07 in order
```

`build_dataset.py` flags (both optional): `--input-dir DataSet --output-dir data/processed`.

Publishing (GitHub Pages via `.github/workflows/deploy-notebooks.yml`): on push to `main`, notebooks are `nbconvert`ed to HTML into `docs/`, `scripts/generate_index.py` rebuilds the index, and the `docs/` folder deploys. To do it locally: `python -m nbconvert --to html notebooks/*.ipynb --output-dir=docs`.

## The data pipeline (`src/build_dataset.py`)

Reads 6 raw files from `DataSet/`, cleans/joins, and writes 7 tables to `data/processed/` (each as `.parquet` snappy **and** `.csv` utf-8-sig for Excel), plus `PIPELINE_VALIDATION.txt` (authoritative row counts + coverage). Run it whenever raw data or logic changes; notebooks auto-pick up the new parquets.

**Canonical output tables** (see `src/README.md` for full column dictionary):
| Table | Rows | Grain |
|---|---|---|
| `faculty.parquet` | 2,247 | one per faculty (2,232 HR roster + 15 `UnmatchedFaculty.csv` supplement) |
| `grants.parquet` | 2,676 | one per `grant_id`; abstract text merged in |
| `faculty_grants.parquet` | 3,144 | one per (faculty, grant) link; the join table |
| `grant_orphaned_abstracts.parquet` | 5,095 | abstracts not matched to any NEU grant |
| `faculty_missing_metadata.parquet` | 13 | grant-active faculty absent from HR (backfill worklist) |
| `faculty_id_lookup.parquet` | 2,247 | faculty_id → college/dept/AAUID |
| `personid_to_faculty.parquet` | 1,042 | the ID bridge (see below) |

**Key logic:**
- Column headers normalized via `_lower_cols`; academic ranks collapsed to ~8 buckets via `_normalize_rank`.
- Faculty **names come from grant tables** (mode/most-common `personname` per id), **not** from HR.
- AAD federal-coverage merged onto grants by **fuzzy agency-name match** (`rapidfuzz token_set_ratio`, **threshold 85**).
- Abstracts matched to grants on `sourceactivityid == grant_id`, keeping the **most-recently-updated** record per grant; non-matches become orphans.
- `personid_to_faculty` uses a **strict 100% co-occurrence majority vote** (a personid resolves only if exactly one faculty shares 100% of its grants); ties/zero → unresolved.

## Identifiers — read this, it's the #1 source of bugs

- **Canonical keys: `faculty_id` and `grant_id`.**
  - `faculty_id` = HR `Employee ID` = `ClientFacultyId` in grant tables.
  - `grant_id` = `grantid` in grant tables = `sourceactivityid` in the abstract table.
- **`"00000"`** is the reserved sentinel for grant rows whose `ClientFacultyId` was missing (currently resolves to 0 rows after cleaning, but the code path exists).
- **The `PersonId` trap:** two raw files have a `PersonId` column that are *different ID spaces with zero overlap* — `grants-with-coPI.PersonId` is the **AAUID** (Academic Analytics vendor id), `grants-with-abstract.PersonId` is an **internal upload-system id**. Neither joins directly to `faculty_id`. To go from an abstract `personid` to a faculty, use `personid_to_faculty.parquet` only.
- **AAUID** is preserved on `faculty_id_lookup` for future enrichment but is **never a join key**.

## Analytical caveats — must be disclosed in any deliverable

1. **`$2.18B headline ≠ money NEU raised.** Grants get attributed to a faculty member even if the award predates their NEU hire (source marks everyone "Northeastern"). Use **`faculty_grants.neu_status == 'earned_at_neu'`** for external/NEU-work reporting:
   - `earned_at_neu` (start ≥ hire): 2,098 rows / ~$1,408M
   - `prior_institution` (start < hire): 866 rows / ~$685M — does NOT count as NEU work
   - `unknown` (missing dates): 180 rows / ~$153M
2. **Funding-credit model matters.** PI-only vs full-credit vs fractional split materially reorder faculty leaderboards — always state which model a chart uses. (`src/README.md` has the three canonical snippets.)
3. **Data is NSF/NIH-skewed** (~88% of dollars). Internal/foundation/industry funding is largely invisible.
4. **Abstract coverage:** only **1,928 of 2,676 grants (72%)** have usable abstract text; only ~37% of the 8,075 abstract rows match a grant_id. The **NIH abstract "cliff"** (near-0% coverage from 2020+) is a **data-collection artifact, not a funding decline** — only NIH RePORTER backfill can fix it.
5. Prefer `startdate`/`startdateyear` over `awarddate` (98% null). Use `totaldollars` from `ri_matches`, not the abstract file's unreliable `Dollar Amount`.

## Notebooks (`notebooks/`, run 01→07 in order)

All share a bootstrap: `warnings.filterwarnings('ignore')`, walk up parents to find `data/processed` as `REPO_ROOT`, load the parquets, `sns.set_theme(style='whitegrid', palette='muted')`. Figures saved `dpi=150, bbox_inches='tight'` to `outputs/` (and topic figures also to `notebooks/figures/`).

| # | Notebook | Covers |
|---|---|---|
| 01 | schema_overview | Load/profile all tables, nulls/schemas, join sanity checks, abstract-coverage diagnostics |
| 02 | funding_landscape | Baseline distributions: grant size (linear+log), duration, per-year, agency, rank/tenure, co-PI rate |
| 03 | funding_over_time | Annual/cumulative funding 2000–2025, rolling avg, college×year heatmap, agency mix, pre/post-COVID |
| 04 | who_gets_funded | Concentration (**Gini ≈ 0.632**, top-10 ≈19.6%), top-25 faculty, top-15 depts, agency×dept, `neu_status` attribution |
| 05 | collaboration_network | Co-PI NetworkX graph, degree/PageRank/betweenness, Louvain communities, cross-college matrix |
| 06 | research_topics | **LDA k=8** over abstracts; coherence + confidence validation; topics × time/college/agency/funding. Writes `outputs/topic_assignments.csv` |
| 07 | topic_deep_dive | College profiles, 32 sub-topics (LDA k=4/parent), JS-distance dendrogram, UMAP (TF-IDF + SPECTER2). Consumes nb06's CSV; writes interactive HTML to `docs/` |

## Topic modeling — state of play

- **Two LDA regimes currently coexist:** analytical notebooks use **LDA k=8**; the EnricoVis HTML apps use **LDA k=12** with an 8→25 hierarchy.
- **The forward plan (`docs/TOPIC_WORK_FORWARD_PLAN.md`) retires both LDA regimes for BERTopic** (SPECTER2 → UMAP → HDBSCAN → c-TF-IDF). Check that doc before extending topic work.
- **LDA label drift is the biggest gotcha:** LDA assigns topic IDs randomly, so the hand-curated `TOPIC_LABELS` silently break after any corpus/param change. Re-inspect top terms and rewrite labels after every rerun. (nb07 auto-realigns via crosstab argmax.)
- **SPECTER2 / UMAP / HDBSCAN CANNOT run in a sandbox/CI container** (no HuggingFace network access). Always precompute locally and commit the cached artifacts (`specter2_embeddings.npy` + `specter2_ids.txt`); CI and HTML apps consume only committed artifacts/JSON.

## `docs/` reference map

- `data_dictionary.md` — per-column reference for raw files + join keys.
- `data_quality_report.md` — flagged issues (NSF/NIH bias, pre-hire attribution, roster gaps, abstract coverage).
- `ID_RECONCILIATION.md` — authoritative account of the 4-ids-per-person problem and the personid bridge.
- `INSIGHTS.md` — narrative findings across all notebooks (local-only, not published).
- `TOPIC_ANALYSIS_COMPENDIUM.md` — definitive LDA parameters, coverage bias, follow-ups.
- `TOPIC_WORK_FORWARD_PLAN.md` — the BERTopic migration + orphan-reconciliation roadmap (M1–M5).
- `WEEKLY_PLAN.md` — 13-week plan; the Dash kiosk/browser delivery target and design rules (≥56px tap targets, colorblind-safe, WCAG AA).
- `EnricoVis/` — 3 self-contained interactive HTML apps (`grant_atlas`, `topic_islands`, `topic_hierarchy`) + their SPECTER2 pipeline; `grants_visualization_work_breakdown.md` is the handoff doc.
- **Stale / secondary — do not treat as current schema:** `SETUP_GUIDE_WEEK3_OLD.md` (old table names/counts) and `NedaNotebooks/` (a parallel EDA track with a different conda env and different numbers).

## Conventions & gotchas

- **Never commit notebook outputs.** Use `nbstripout` (in requirements) or "Restart kernel & clear outputs" before `git add`. Notebooks are committed with outputs stripped; the CI executes/renders them.
- **`data/processed/` and `outputs/` are gitignored** (`*.parquet` too). Regenerate with `build_dataset.py`; don't hand-edit parquets.
- **Caveat — raw `DataSet/*.xlsx` ARE committed** despite `DataSet/ReadMe.md` and `WEEKLY_PLAN.md` stating raw data should not be. Treat the committed raw files as sensitive; confirm before adding/removing them.
- `scripts/_*.py` are **ad-hoc diagnostics**, not part of the pipeline — but note `_diagnose_orphans.py` and `_orphan_faculty_overlap.py` still **write CSVs into `data/processed/`**, so they aren't purely read-only. The authoritative `personid_to_faculty` comes from `build_dataset.py`, not the looser CSV of the same name from `_orphan_faculty_overlap.py`.
- Several legacy parquets (`grant_faculty`, `grant_text`, `faculty_id_lookup`) still sit on disk from older pipeline versions; the current canonical tables are the 7 listed above (see the "renamed outputs" note in `src/README.md`).
- Join keys are frequently coerced to `str` before merging — do the same to avoid dtype-mismatch silent empty joins.
- Code-quality tools available: `ruff`, `black`, `nbstripout`.

## Tech stack

Python 3.11+ · pandas / numpy / pyarrow · matplotlib / seaborn / plotly · scikit-learn / gensim / nltk / wordcloud (topic modeling) · networkx / python-louvain (network) · rapidfuzz (fuzzy matching) · umap-learn + `allenai/specter2_base` (embeddings, local-only) · jupyterlab. Target app framework: Plotly Dash + dash-cytoscape.
