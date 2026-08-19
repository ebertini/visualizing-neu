# CLAUDE.md

Guidance for working in this repository. Read this before touching data, notebooks, or the pipeline.

## What this project is

An exploratory **data-visualization project on Northeastern University's faculty funding and grant history** (window ~1995–2026, ~$2.18B in awards). The deliverable is an interactive visualization telling the story of NEU grant funding. Current work is EDA + topic modeling in Jupyter notebooks published to GitHub Pages. A dual-mode **Plotly Dash** dashboard (touchscreen **kiosk** build + responsive public browser build from one codebase) is still a possible final goal, but that direction is under-defined and `docs/WEEKLY_PLAN.md`, which used to describe it, is now deprecated.

**Two parallel visualization tracks publish into `docs/onlineoutput/` — know which is whose before editing either.** `docs/EnricoVis/` (`grant_atlas`, `topic_islands`, `topic_hierarchy`) is a **parallel effort by the PI** — read-only reference / inspiration, not something to casually modify. `docs/TopicVizPrototypes/` (`topic_flow`, `what_we_can_see`) is **the user's own** topic-model visualization work, built to reinforce their own analysis — it reuses EnricoVis's canonical BERTopic output as a read-only upstream input (see `src/build_viz_aggregates.py`) but writes only into its own directory. Both are "best current sense of what the final deliverable could look like" — EnricoVis for the spatial-embedding forms, TopicVizPrototypes for time/coverage forms EnricoVis doesn't cover.

Sanity-check names (known-good faculty for spot-checking joins): **Saiph Savage** (resolves correctly to Khoury College), **Michael Ann DeVito**, **Benjamin Gyori** — the latter two are not matched as a PI on any grant in the current corpus, so PI-keyed joins legitimately come up empty for them (not a bug). ID-reconciliation running example: **Chris Martens** (`faculty_id 2963712`).

## Repository layout

```
DataSet/            Raw .xlsx / .csv inputs (see caveat below — these ARE committed)
src/                ETL pipeline (build_dataset.py) + SPECTER2 embedder
data/processed/     Pipeline output: *.parquet (+ shareable *.csv) — GITIGNORED
notebooks/          Numbered EDA notebooks 01–07, run in order
scripts/            generate_index.py (docs) + underscore-prefixed ad-hoc diagnostics
docs/               Reference docs (*.md), published HTML, EnricoVis/ (PI's parallel work) +
                    TopicVizPrototypes/ (user's own prototypes) + NedaNotebooks/
outputs/            Generated PNG/CSV figures (w4_/w5_/w6_/w7_ prefixes) — GITIGNORED
figures/            Duplicate of some topic figures
```

## Setup & core commands

```bash
pip install -r requirements.txt          # Python 3.11+; CPU-only for everything
python src/build_dataset.py              # ~30s; regenerates ALL data/processed/*.parquet
python src/build_specter2_embeddings.py  # one-shot SPECTER2 cache for notebook 07 (~5–8 min CPU)
jupyter lab notebooks/01_schema_overview.ipynb   # run notebooks 01→07 in order

# TopicVizPrototypes' lighter build path (pandas/pyarrow/openpyxl/rapidfuzz only,
# not the full torch/bertopic stack): requirements-viz.txt + a venv.
# Bare `python3.11 -m venv` FAILS on this machine (uv-managed Python is a
# relocatable build that needs uv's own wiring — see CLAUDE.md history /
# session logs for the exact error). Use uv instead:
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -r requirements-viz.txt
python -m src.refresh_topicviz           # build_viz_data (if stale) + build_viz_aggregates +
                                          # _inline_topicviz_data, in one command (~1s total)
```

Full topic-model refit pipeline (heavy deps, local-only — see `docs/TOPIC_MODEL_REFIT_CHECKLIST.md`
for the complete swap-in contract): `build_dataset.py` → `reconcile_orphans.py` →
`build_specter2_embeddings.py` → `topics_bertopic.py` → `refresh_topicviz.py`.

`build_dataset.py` flags (both optional): `--input-dir DataSet --output-dir data/processed`.

Publishing (GitHub Pages via `.github/workflows/deploy-notebooks.yml`): on push to `main`, notebooks are `nbconvert`ed to HTML into `docs/onlineoutput/`, `scripts/generate_index.py` rebuilds the index there, and `docs/onlineoutput/` (not `docs/` itself) deploys. To do it locally: `python -m nbconvert --to html notebooks/*.ipynb --output-dir=docs/onlineoutput`.

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
4. **Abstract coverage:** only **1,928 of 2,676 grants (72%)** have usable abstract text; only ~37% of the 8,075 abstract rows match a grant_id. The **NIH abstract "cliff"** (near-0% coverage from 2020+) is a **data-collection artifact, not a funding decline** — only NIH RePORTER backfill can fix it. Reassuringly, missing the abstract barely hurts BERTopic assignment confidence: unassigned rate is **28.0%** for grants with an abstract vs **27.6%** for title-only grants — titles carry most of the signal (verified in `docs/TopicVizPrototypes/what_we_can_see.html`).
5. **"Unassigned" (no confident topic) is the single largest topic bucket by dollars** — 808 grants / **$607M / 27.8%** of the corpus (746 HDBSCAN noise + 62 in the flagged topic-11 artifact), bigger than any one of the 8 parent themes. Any topic-based chart must show it, not drop it.
6. Prefer `startdate`/`startdateyear` over `awarddate` (98% null). Use `totaldollars` from `ri_matches`, not the abstract file's unreliable `Dollar Amount`.
7. **External collaborators are invisible.** Every grant record is stamped "Northeastern" regardless of who else worked on it — there's no way to see co-investigators at other institutions, so any collaboration-network analysis from this data is NEU-internal only.

## Notebooks (`notebooks/`, run 01→07 in order)

All share a bootstrap: `warnings.filterwarnings('ignore')`, walk up parents to find `data/processed` as `REPO_ROOT`, load the parquets, `sns.set_theme(style='whitegrid', palette='muted')`. Figures saved `dpi=150, bbox_inches='tight'` to `outputs/` (and topic figures also to `notebooks/figures/`).

| # | Notebook | Covers |
|---|---|---|
| 01 | schema_overview | Load/profile all tables, nulls/schemas, join sanity checks, abstract-coverage diagnostics |
| 02 | funding_landscape | Baseline distributions: grant size (linear+log), duration, per-year, agency, rank/tenure, co-PI rate |
| 03 | funding_over_time | Annual/cumulative funding 2000–2025, rolling avg, college×year heatmap, agency mix, pre/post-COVID |
| 04 | who_gets_funded | Concentration (**Gini ≈ 0.632**, top-10 ≈19.6%), top-25 faculty, top-15 depts, agency×dept, `neu_status` attribution |
| 05 | collaboration_network | Co-PI NetworkX graph, degree/PageRank/betweenness, Louvain communities, cross-college matrix |
| 06 | research_topics | **LDA k=8** over abstracts — now historical/legacy, kept standalone for comparison, no longer feeds nb07 or EnricoVis; coherence + confidence validation; topics × time/college/agency/funding. Writes `outputs/topic_assignments.csv` |
| 07 | topic_deep_dive | **BERTopic (canonical)** — loads `topic_assignments.parquet` (25 topics + "Unassigned" noise cluster) independently of nb06; college profiles, 8-parent-theme hierarchy, SPECTER2-centroid dendrogram, UMAP on canonical SPECTER2 coords. Writes interactive HTML (`docs/07_grant_projection_specter2.html` — deprecated/unpublished, see reference map) |

## Topic modeling — state of play

- **BERTopic is now the canonical topic model** (SPECTER2 → UMAP → HDBSCAN → c-TF-IDF): **25 topics + an explicit "Unassigned" noise cluster**, `min_cluster_size=25` (stable across 3 seeds). Fit via `src/topics_bertopic.py`, output is `data/processed/topic_assignments.parquet`, consumed by nb07 and all three EnricoVis apps (`grant_atlas`, `topic_islands`, `topic_hierarchy`) — plus, one hop further downstream via **`src/build_viz_data.py`** (this repo's own script, not a PI-owned pipeline — it just reuses the PI's fitted model as input), which writes EnricoVis's committed JSON that `src/build_viz_aggregates.py` in turn reads for the user's own `docs/TopicVizPrototypes/` apps. See `docs/TOPIC_WORK_EXECUTION_REPORT.md` for what M1–M4 actually delivered, including the corpus growing 2,676 → 2,741 docs via orphan-abstract reconciliation, and **`docs/TOPIC_MODEL_REFIT_CHECKLIST.md`** for the full re-fit runbook — `topics_bertopic.py` now also persists the 2-D UMAP (`specter2_umap_2d.npy`) and bootstraps a seed `outputs/topic_labels.json` on every run, closing two gaps that previously had no producing script at all.
- **LDA is now historical, not canonical.** `src/topics_lda.py` is kept as a labelled legacy module; nb06 (`research_topics`, LDA k=8) still runs standalone for comparison but no longer feeds nb07 or the EnricoVis apps (previously nb07 consumed nb06's `outputs/topic_assignments.csv`; it now loads the BERTopic parquet independently). BERTopic fixed LDA's cross-vocabulary mis-parenting (e.g. Alshawabkeh Puerto-Rico environmental grants, previously mis-bucketed under Biomedical).
- **Text cleaning is unified** in `src/clean_text.py` (with a regression test suite), shared by both the legacy LDA path and the canonical BERTopic path.
- **LDA label drift is still a live gotcha if you touch nb06:** LDA assigns topic IDs randomly, so hand-curated labels silently break after any corpus/param change. This doesn't apply to the canonical BERTopic path, which uses c-TF-IDF-derived labels from a shared `topic_labels.json`.
- **SPECTER2 / UMAP / HDBSCAN CANNOT run in a sandbox/CI container** (no HuggingFace network access). Always precompute locally and commit the cached artifacts (`specter2_embeddings.npy` + `specter2_ids.txt`); CI and HTML apps consume only committed artifacts/JSON.
- **M5 (per `docs/TOPIC_WORK_FORWARD_PLAN.md`) is not yet started** — NIH RePORTER abstract backfill, LDA-vs-BERTopic agreement crosstab, sub-topic label curation, faculty-embedding UMAP, topic×dollars trends, and a report notebook are all still open.
- **The refit pipeline itself is unverified end-to-end.** `docs/TOPIC_MODEL_REFIT_CHECKLIST.md`'s command sequence and `build_viz_aggregates.py`'s crash-hazard fixes were exercised against the current committed data and a simulated parent-count change, but no real BERTopic refit has been run through it yet — no HuggingFace network access in this working environment.

## Open threads

- **Enrico's (the PI) proposed keyword→classifier topic method — architecture confirmed, mechanisms narrowed but not finalized, not yet acted on in code.** Two conversations (Slack, then in person) confirmed the *shape*: a transparent classifier where topics are defined by human-inspectable keyword lists, and documents are linked to topics through those lists — a candidate alternative/complement to BERTopic. The two originally-open mechanisms have both narrowed: (1) keyword-list extraction/curation resolves to a **manual curation pass on BERTopic's existing 25 topic c-TF-IDF keyword lists** (`docs/EnricoVis/data/topics.json`), not fresh clustering; (2) the topic-to-document link resolves to **an LLM given a grant's text + the curated keyword lists**, not a hand-coded scoring function or a trained classifier. Still unresolved: the curation procedure (who does it, against what accept/reject criteria, whether it restores the domain-stopword-stripped phrases noted in `src/clean_text.py`'s `DOMAIN_STOPS`), LLM choice/prompt design/cost at 2,676-grant scale, single- vs multi-label, whether the LLM can abstain (relevant since Unassigned is currently 808 grants / $607M / 27.8% of the corpus), and which student/prior work Enrico wants looped in (still unnamed). Full record, constraints, and the narrowed question list: `docs/TOPIC_CLASSIFICATION_BRAINSTORM.md`.

## `docs/` reference map

- `data_dictionary.md` — per-column reference for raw files + join keys.
- `data_quality_report.md` — flagged issues (NSF/NIH bias, pre-hire attribution, roster gaps, abstract coverage).
- `ID_RECONCILIATION.md` — authoritative account of the 4-ids-per-person problem and the personid bridge.
- `INSIGHTS.md` — narrative findings across all notebooks (local-only, not published).
- `TOPIC_ANALYSIS_COMPENDIUM.md` — definitive LDA parameters, coverage bias, follow-ups.
- `TOPIC_WORK_FORWARD_PLAN.md` — the BERTopic migration + orphan-reconciliation roadmap (M1–M5).
- `TOPIC_WORK_EXECUTION_REPORT.md` — companion to the forward plan; documents what M1–M4 actually shipped (see "Topic modeling — state of play" above for the current summary). M5 not started.
- `TOPIC_MODEL_REFIT_CHECKLIST.md` — the runbook for redoing the topic model: full command sequence, exactly which artifacts constitute "a new topic model" to swap in, and what still needs a human afterward (parent-theme curation, the manually-synced `PARENT_NAMES`/`PARENT_COLORS` copies, `CAVEATS` prose) vs. what's now automatic (`src/refresh_topicviz.py`).
- `TOPIC_CLASSIFICATION_BRAINSTORM.md` — record of the PI's proposed transparent keyword→classifier topic method (a candidate alternative/complement to BERTopic), now updated past the pre-meeting prep stage: the two mechanisms his Slack reply left open have both narrowed after an in-person follow-up — keyword-list extraction/curation resolves to a manual curation pass on BERTopic's existing 25 topic keyword lists (no fresh clustering), and the topic-to-document link resolves to using an LLM against those curated lists (not a hand-coded scoring function or a trained classifier). Neither is a finished spec yet (LLM choice, prompt design, cost/scale, curation procedure all still open) and none of it is acted on in code — this doc tracks the narrowed remaining questions.
- `EnricoVis/` — **a parallel visualization effort by the PI**, not this user's own work (treat as read-only reference unless told otherwise). 3 self-contained interactive HTML apps (`grant_atlas`, `topic_islands`, `topic_hierarchy`) + their SPECTER2 pipeline; `grants_visualization_work_breakdown.md` is the handoff doc. Published copies live in `onlineoutput/` (below).
- `TopicVizPrototypes/` — **the user's own** topic-model visualization prototypes: `topic_flow.html` (funding over time) and `what_we_can_see.html`, a **tabbed** dashboard — now **three** tabs (down from six panels across four tabs, after direct PI feedback to deprecate the Coverage tab and the "Does it matter? What we can't see" tab and reinvest that space): **"Every grant"**, **"Every PI"** (new), and **"What's missing & where it goes"**. Both unit-visualization grids ("Every grant, arranged" and "Every PI, arranged") are built by one shared engine, `createGrid()` in the app script — a factory instantiated twice (`data: FACETS`/`GRANT_FACET_DEFS` vs. `data: FACETS_PI`/`PI_FACET_DEFS`) rather than duplicated, so every layout/interaction fix applies to both. "Every grant" arranges/splits/sorts/colors by any of 7 facets (agency, year, college, NEU attribution, parent theme, leaf topic, dollar band); "Every PI" does the same over 11 facets (college, department, rank, appointment track, tenure status, hire year, employment status, has-grants, grant-count band, dollars-as-PI, parent theme-as-PI) across **all 2,247 roster faculty**, not just the 570 with a grant in this corpus — "no grants" is a first-class bin, same "nobody's silently dropped" invariant `facets.json` already holds for grants. Dollars/theme on the PI grid are credited **PI-only** (not full- or fractional-credit), per the funding-credit-model caveat. A fixed 4.8px mark size applies to every Rows×Columns arrangement (previously reflowed between five size tiers, which PI feedback flagged as distracting); the controls dock is a floating, default-collapsed overlay, anchored under a `.gridtoolbar` row (not the whole section, as before) so it always opens directly beneath its own dial regardless of title length; clicking a mark or cell selects it via nearest-hit-testing and opens a floating "Selected" card (not a modal — one was built and explicitly rejected earlier), `position:fixed` to the viewport's bottom-right (was absolutely positioned over the chart) with its own close button and Esc-to-dismiss. Both grid headers dropped their "How this is computed" drawer and description line (PI feedback: unnecessary, took up space), and — in a later session — their caveats row too (moved to a new `about.html` page, see below): each header is now just a title and a single "dial" toggle, no caveats row anymore. The dial replaces the shared kit's two-button fold/opener pattern (`shared/enrico.css`'s `.dock`/`.opener`, still used as-is by `topic_flow.html`) with one persistent toggle (`setupDial` in the app script). It was first pinned to the section's true left margin deliberately NOT next to the title text (a follow-up correction at the time) — then reversed again later: dial and title now sit together in a `.gridtoolbar` row (dial closest to the true left margin, title right after), because collapsing the row-label lane to 0px whenever Rows is "— none —" (see below) left the old floating dial covering the chart's own column headers. The color legend moved the same way — out of a floating overlay over the chart's corner into the same toolbar (right side: legend closest to center, its own open/close toggle closest to the true right margin) — defaulting OPEN (unlike the dial) and becoming a floating overlay itself only once its content would actually need a vertical scrollbar (`measureLegendOverlay`, ~56px threshold), so a legend that fits inline never grows the toolbar. The dock's four cards are now ordered Columns → Rows → Color by → Sort bins (was Rows → Columns → Sort → Color), and Rows can be set to "— none —" too (previously only Columns could) — the default arrangement is column-first (Columns = the facet, Rows = none), not row-first. Row/column labels also abbreviate long college names at render time (`COLLEGE_SHORT`), falling back to the full name on hover. "What's missing & where it goes" now covers three grains via a Grants/PIs/Abstract-records switch (each scored against its own population — 2,676 grants, 2,247 roster faculty, 8,075 raw abstract-upload records), a sortable field-by-field table (Known/Missing/%/Recoverable/Where the gap comes from), the by-agency and by-year coverage bar charts salvaged from the deprecated Coverage tab's heatmap, the kept NIH-vs-NSF cliff chart, the mosaic panel's finding as one line, and the unchanged abstract-sourcing funnel; the "What we cannot see" negative-space card deck was dropped (its points now live in `viz_meta.json`'s `caveats[]`, several of which weren't rendered anywhere before). Reads EnricoVis's canonical BERTopic/SPECTER2 output as a read-only upstream input (`docs/EnricoVis/data/{grants_umap,topics}.json`) via `src/build_viz_aggregates.py`, which emits `viz_meta.json`/`topic_time.json`/`coverage.json`/`facets.json`/**`facets_pi.json`** (new, over `data/processed/faculty.parquet` + `faculty_id_lookup.parquet` + `faculty_grants.parquet`)/`missingness.json` (now `{"grains": {"grants":..., "pis":..., "abstract_records":...}}`, each field carrying a `where` string and an optional `recoverable` count)/`funnel.json`; writes only into its own `data/` and `shared/`. A new diagnostic, `scripts/_check_new_abstracts.py`, cross-checks a refreshed abstract export the data team dropped (`DataSet/AcAn Grants 2026-08-13.xlsx`) against the pipeline's current one and writes `data/processed/new_abstract_recovery.parquet` (not adopted into `build_dataset.py` itself — see `docs/data_quality_report.md` §9 and `docs/TOPIC_CLASSIFICATION_BRAINSTORM.md` for why: it would desync the recovered text from the frozen, unrefit BERTopic output — newly-recovered abstracts get no real topic assignment until the model is actually refit, see `docs/TOPIC_MODEL_REFIT_CHECKLIST.md`. `build_viz_aggregates.py`'s `validate()` no longer hard-blocks on a corpus-size change on its own, since a later session softened its literal asserts to informational lines, but that was never the harder half of the problem). `scripts/_inline_topicviz_data.py`'s `TARGETS` maps each JSON to a `const NAME = {};` placeholder in the HTML (now including `FACETS_PI`) — re-run it after any `build_viz_aggregates` run. **House convention: all audience-facing copy (section headers, "How this is computed" drawers) is plain-language only** — no file/column/function names (`.parquet`, `grant_id`, etc.); that detail belongs in this repo's own docs, not the dashboard. **Publishing decided:** the user confirmed all of `TopicVizPrototypes/` should be online, not just `what_we_can_see.html` — both prototype HTML files are wired into `.github/workflows/deploy-notebooks.yml`. A new third page, `about.html`, holds everything the caveats-row removal above took off the two grid pages: the coverage headline, all of `VIZ_META.caveats[]` grouped by severity, and the model's `frozen_inputs` summary — linked from both prototypes' headers and wired into the same deploy step and `_inline_topicviz_data.py` `TARGETS` list as the other two. **Still open, blocked on the PI:** a topic-reliability/manual-inspection panel — he has now replied on the classification method (confirming the *architecture*: a transparent classifier where topics are defined by human-inspectable keyword lists, and documents are linked to topics through those lists) but left the two concrete mechanisms — how the keyword list per topic is extracted/curated, and what function links topics to documents via keywords — explicitly unresolved pending a brainstorming session; he also still wants a student from related prior work looped in first (not yet named). **Next-direction priority (captured, not yet built):** a grant search/lookup box (filter/highlight matching grants live in the grid by title, PI, agency, or abstract text) and a topic-keyword "fingerprint" view (a selected grant's abstract shown against its topic's keyword list, highlighting which terms actually appear — a working prototype of the still-open topic-reliability/manual-inspection panel above) are the two directions to explore next, chosen ahead of the earlier-planned "Round 2" (money-vs-volume slope chart, treemap, agency→theme→college Sankey), which remains further back in the queue and hasn't been picked back up.
- `onlineoutput/` — the actual published site (nbconverted notebooks + EnricoVis apps + TopicVizPrototypes apps + index.html); committed to git despite being CI build output.
- **Deprecated:** `WEEKLY_PLAN.md` (the 13-week plan and Dash kiosk/browser delivery target it described are superseded — see "What this project is" above) and `07_grant_projection_specter2.html` (nb07's interactive BERTopic projection, written to `docs/` root; superseded, not copied into `onlineoutput/` by the deploy workflow).
- **Stale / secondary — do not treat as current:** `SETUP_GUIDE_WEEK3_OLD.md` (old table names/counts), `PUBLISHING.md` (describes an old `docs/index.html` / `--output-dir=docs` setup the workflow no longer uses — actual output goes to `onlineoutput/`), and `NedaNotebooks/` (a parallel EDA track with a different conda env and different numbers — `Capstone_Report_Jun_2 (1).pdf` lives here too, as parallel-work supporting material, not the canonical pipeline's report).

## Conventions & gotchas

- **Never commit notebook outputs.** Use `nbstripout` (in requirements) or "Restart kernel & clear outputs" before `git add`. Notebooks are committed with outputs stripped; the CI executes/renders them.
- **`data/processed/` and `outputs/` are gitignored** (`*.parquet` too), with one targeted exception: `outputs/topic_labels.json` (the curated topic-label/parent-theme map) is un-ignored via `!outputs/topic_labels.json` — note a bare `outputs/` directory-level ignore can't be selectively un-ignored by a file-level negation at all; it had to become `outputs/*` first (git can't re-include a path whose *parent directory* is what's excluded, only a path excluded by a wildcard on its contents). Regenerate everything else with `build_dataset.py`; don't hand-edit parquets.
- **Caveat — raw `DataSet/*.xlsx` ARE committed** despite `DataSet/ReadMe.md` and `WEEKLY_PLAN.md` stating raw data should not be. Treat the committed raw files as sensitive; confirm before adding/removing them.
- `scripts/_*.py` are **ad-hoc diagnostics**, not part of the pipeline — but note `_diagnose_orphans.py` and `_orphan_faculty_overlap.py` still **write CSVs into `data/processed/`**, so they aren't purely read-only. The authoritative `personid_to_faculty` comes from `build_dataset.py`, not the looser CSV of the same name from `_orphan_faculty_overlap.py`. `_check_new_abstracts.py` similarly writes `new_abstract_recovery.parquet` into `data/processed/` — an optional input `build_viz_aggregates.py` degrades honestly without (see `docs/data_quality_report.md` §9).
- Several legacy parquets (`grant_faculty`, `grant_text`, `faculty_id_lookup`) still sit on disk from older pipeline versions; the current canonical tables are the 7 listed above (see the "renamed outputs" note in `src/README.md`).
- Join keys are frequently coerced to `str` before merging — do the same to avoid dtype-mismatch silent empty joins.
- Code-quality tools available: `ruff`, `black`, `nbstripout`.
- `src/build_viz_aggregates.py` had three now-fixed bugs worth not reintroducing: the "Other" agency bucket was labeled using the first point's `agencyLabel` (made it look like all "Other" grants were USDA); `viz_meta.json`/`coverage.json` each had a field named `share` meaning different things (dollar-share vs. count-share) — now `unassigned_share_d` / `unassigned.share_n` respectively; and the `abstract_records` missingness grain briefly had a `has_text` field (known only among the 5,095 unmatched-only orphan records, `na` for matched ones) that read as a smaller, contradicting count of the grants-grain's own `Abstract text` field (1,936 known) despite scoring an entirely different population — removed rather than re-captioned, since the funnel section already tells that narrower story more precisely.
- D3/SVG panels: a fixed-CSS-height container paired with a dynamically-sized `viewBox` silently scales all content down as it grows (e.g. more facet-grid bins than fit on screen). Size the container to content (with a sensible floor), not a fixed `vh`.
- `.rowlabel` is a class name shared across the Every grant/Every PI facet grids' row labels and other charts (coverage-by-agency bars, the NIH-vs-NSF cliff chart) in `what_we_can_see.html` — only the facet grids' own row labels need `pointer-events:auto` (scoped via `#facetlabels .rowlabel`/`#pilabels .rowlabel`), so keep future `.rowlabel` changes scoped by id rather than applied to the bare class.
- **No browser is available in this working environment** for `TopicVizPrototypes` HTML/JS changes (confirmed across multiple sessions). Verification relies on Python-based static checks — bracket/backtick balance, an `HTMLParser` tag-balance check, a `getElementById`/markup-`id` cross-reference — which catch structural breakage but never confirm actual rendering/layout. Treat every such change as needing a real-browser check before publishing, and say so explicitly rather than implying it was visually confirmed.

## Tech stack

Python 3.11+ · pandas / numpy / pyarrow · matplotlib / seaborn / plotly · scikit-learn / gensim / nltk / wordcloud (topic modeling) · networkx / python-louvain (network) · rapidfuzz (fuzzy matching) · umap-learn + `allenai/specter2_base` (embeddings, local-only) · jupyterlab. Target app framework: Plotly Dash + dash-cytoscape.
