# CLAUDE.md

Guidance for working in this repository. Read this before touching data, notebooks, or the pipeline.

## Handoff status (2026-08-31)

**This project is feature-complete and paused, not actively being iterated.** The prior
owner's active work (topic-model redo, dashboard build-out, PI backfill merge) is done and
verified. If you're new to this repo:

1. Read **`README.md`** (repo root) first — a plain-language tour of the notebooks and the
   final visualization for a human reader, not tuned for an AI coding assistant.
2. Come back to this file for pipeline internals, identifier gotchas, and hard-won lessons
   before you change any code.
3. See **"Open threads"** below for what's genuinely unfinished and worth picking up first.
4. **The dashboard itself needs no setup to view** — its final built JSON is committed, so a
   fresh clone works immediately (see "Setup & core commands" below). Only *regenerating* that
   data, or working with the pipeline/notebooks directly, needs the dependency chain
   (`build_dataset.py` → `refresh_topicviz.py`, both fast and free).

Detailed session-by-session history (what was tried, what broke, why a decision was made)
lives in `.claude/sessions/*.md` and the docs listed under "`docs/` reference map" — this
file states current state, not the story of how it got there.

## What this project is

An exploratory **data-visualization project on Northeastern University's faculty funding and
grant history** (window ~1995–2026, ~$2.18B in awards). The deliverable is an interactive
visualization telling the story of NEU grant funding, published to GitHub Pages. A dual-mode
**Plotly Dash** dashboard (touchscreen kiosk + responsive public browser build) was an earlier
possible direction; it's superseded by the static dashboard below and `docs/WEEKLY_PLAN.md`
(which described it) is deprecated.

**Two parallel visualization tracks publish into `docs/onlineoutput/` — know which is whose
before editing either.**
- `docs/EnricoVis/` (`grant_atlas`, `topic_islands`, `topic_hierarchy`) is a **parallel effort
  by the PI (Enrico)** — read-only reference, not something to modify. Its BERTopic/SPECTER2
  output is consumed as a read-only upstream input by the other track.
- `docs/TopicVizPrototypes/` (`what_we_can_see.html`, `topic_flow.html`) is **the final
  deliverable of this project** — reuses EnricoVis's canonical embedding output but writes
  only into its own directory. See `README.md` for what it shows and how to run it.

Sanity-check names (known-good faculty for spot-checking joins): **Saiph Savage** (resolves
correctly to Khoury College), **Michael Ann DeVito**, **Benjamin Gyori** — the latter two are
not matched as a PI on any grant in the current corpus, so PI-keyed joins legitimately come up
empty for them (not a bug). ID-reconciliation running example: **Chris Martens**
(`faculty_id 2963712`).

## Repository layout

```
DataSet/            Raw .xlsx / .csv inputs (see caveat below — these ARE committed)
src/                ETL pipeline (build_dataset.py) + SPECTER2 embedder + topic-model/viz code
data/processed/     Pipeline output: *.parquet (+ shareable *.csv) — GITIGNORED
data/nih_nsf_backfill/  NIH RePORTER / NSF Award Search backfill outputs — TRACKED (deliberate
                    .gitignore exception; see Conventions & gotchas)
notebooks/          Numbered EDA notebooks 01–09, run in order
scripts/            generate_index.py (docs) + underscore-prefixed ad-hoc diagnostics
docs/               Reference docs (*.md), published HTML, EnricoVis/ (PI's parallel work) +
                    TopicVizPrototypes/ (the final dashboard) + NedaNotebooks/ (parallel EDA)
outputs/            Generated PNG/CSV figures — GITIGNORED (except outputs/topic_labels.json)
figures/            Duplicate of some topic figures
```

## Setup & core commands

**Viewing the dashboard needs none of this.** `docs/TopicVizPrototypes/data/*.json` — the
dashboard's own final built output — is committed, specifically so a fresh clone works
immediately: `python -m http.server 8000 --directory docs/TopicVizPrototypes`, then open
`what_we_can_see.html`. Everything below is only for *regenerating* that data (after a raw-data
change) or for working with the pipeline/notebooks/topic model directly.

```bash
pip install -r requirements.txt          # Python 3.11+; CPU-only for everything
python src/build_dataset.py              # ~30s; regenerates ALL data/processed/*.parquet
python src/build_specter2_embeddings.py  # one-shot SPECTER2 cache for the topic-model refit
jupyter lab notebooks/01_schema_overview.ipynb   # run notebooks 01→09 in order

# The dashboard's lighter build path (pandas/pyarrow/openpyxl/rapidfuzz only, not the
# full torch/bertopic stack). Bare `python3.11 -m venv` FAILS on this machine (uv-managed
# Python is a relocatable build that needs uv's own wiring) — use uv instead:
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -r requirements-viz.txt
python -m src.refresh_topicviz           # build_viz_data (if stale) + build_viz_aggregates +
                                          # _check_topicviz --data-only, in one command (~1s)
python -m http.server 8000 --directory docs/TopicVizPrototypes   # the dashboard pages
                                          # fetch() their JSON — they need HTTP, NOT file://
```

Full topic-model refit pipeline (heavy deps, local-only — see
`docs/TOPIC_MODEL_REFIT_CHECKLIST.md` for the complete swap-in contract): `build_dataset.py` →
`reconcile_orphans.py` → `build_specter2_embeddings.py` → `topics_bertopic.py` →
`classify_by_keywords.py` → `refresh_topicviz.py`. In practice this shouldn't need to run again
unless the underlying grant/abstract data changes materially — see "Topic modeling" below for
why the keyword classifier, not BERTopic, is what actually needs re-running on new data.

Abstract backfill (`src/backfill_nih_reporter.py`, `src/backfill_nsf_awards.py`) is a
**separate, rarer, rate-limited step** — run it standalone (network + `--offline`/`--limit`
flags, see the scripts' own docstrings) to (re)populate `data/nih_nsf_backfill/`.
`build_dataset.py` then adopts whatever's there automatically, gap-fill only, on every normal
run.

`build_dataset.py` flags (both optional): `--input-dir DataSet --output-dir data/processed`.

Publishing (GitHub Pages via `.github/workflows/deploy-notebooks.yml`): on push to `main`,
notebooks are `nbconvert`ed to HTML into `docs/onlineoutput/`, `scripts/generate_index.py`
rebuilds the index there, and `docs/onlineoutput/` (not `docs/` itself) deploys — the workflow
also copies `docs/TopicVizPrototypes/{data,shared,what_we_can_see,topic_flow}/` into
`onlineoutput/` at matching relative paths. Local equivalent:
`python -m nbconvert --to html notebooks/*.ipynb --output-dir=docs/onlineoutput`.

**Moving this to a different repo (ownership transfer, fork, or the PI's own GitHub Pages
project — see "Open threads" #6).** Verified: the workflow and every published page are
**repo-agnostic** — no hardcoded owner/repo name or absolute URL anywhere in
`deploy-notebooks.yml`, `scripts/generate_index.py`, or any HTML/JS under `docs/` (checked via
`grep` for `github.io`, leading-`/` absolute paths, and the current repo/owner strings; the only
hits were in already-flagged-stale `docs/PUBLISHING.md` and an unrelated external doc link).
`actions/configure-pages` + `actions/upload-pages-artifact` + `actions/deploy-pages` all deploy
to whatever repo the workflow runs in, using GitHub's ambient repo context — nothing to edit in
the workflow itself. To move it:
1. Transfer/fork the repo as normal (git remote change, GitHub's own transfer/fork feature).
2. In the **new** repo's Settings → Pages, set "Build and deployment" source to **"GitHub
   Actions"** — this is a per-repository setting that does **not** carry over automatically on a
   transfer or fork, and is the one manual step actually required. Without it, the workflow can
   run without erroring but nothing will serve.
3. Push to `main` (or run the workflow manually via `workflow_dispatch`) and confirm the
   `deploy-pages` step reports a live URL.
4. The site's URL changes to the new owner/repo's default Pages URL
   (`https://<owner>.github.io/<repo-name>/`, or repo root if the new repo is itself named
   `<owner>.github.io`) — update any external links/bookmarks separately; this is not a code
   change.
5. Do not follow `docs/PUBLISHING.md` — it describes an old `docs/index.html`/`--output-dir=docs`
   setup this workflow no longer uses (see "stale/secondary" docs below).

## The data pipeline (`src/build_dataset.py`)

Reads 6 raw files from `DataSet/`, cleans/joins, and writes 7 tables to `data/processed/`
(each as `.parquet` snappy **and** `.csv` utf-8-sig for Excel), plus `PIPELINE_VALIDATION.txt`
(authoritative row counts + coverage). Run it whenever raw data or logic changes; notebooks
auto-pick up the new parquets.

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

**Note on the dashboard's own faculty-grant table:** `docs/TopicVizPrototypes/` does NOT read
`faculty_grants.parquet` directly — it reads an *augmented* copy (built by
`build_viz_aggregates.py`'s `load_augmented_faculty_grants()`) that additionally fills in a PI
for 13 of the 312 grants that have no internal PI match, sourced from the NIH/NSF backfill's
investigator data. This is a **dashboard-only enrichment** — it never writes back to
`faculty_grants.parquet` or `build_dataset.py`, specifically so it can't reorder any
funding-credit leaderboard computed elsewhere (notebooks, EnricoVis). See "Topic modeling —
state of play" below for what it does and its known limits.

## Identifiers — read this, it's the #1 source of bugs

- **Canonical keys: `faculty_id` and `grant_id`.**
  - `faculty_id` = HR `Employee ID` = `ClientFacultyId` in grant tables.
  - `grant_id` = `grantid` in grant tables = `sourceactivityid` in the abstract table.
- **`"00000"`** is the reserved sentinel for grant rows whose `ClientFacultyId` was missing (currently resolves to 0 rows after cleaning, but the code path exists).
- **The `PersonId` trap:** two raw files have a `PersonId` column that are *different ID spaces with zero overlap* — `grants-with-coPI.PersonId` is the **AAUID** (Academic Analytics vendor id), `grants-with-abstract.PersonId` is an **internal upload-system id**. Neither joins directly to `faculty_id`. To go from an abstract `personid` to a faculty, use `personid_to_faculty.parquet` only.
- **AAUID** is preserved on `faculty_id_lookup` for future enrichment but is **never a join key**.
- **`is_pi`/`is_copi` are mutually exclusive and exhaustive** on every `faculty_grants.parquet` row (verified) — never both, never neither. Any code (including the dashboard's augmented frame above) that adds or edits a row must preserve this invariant.

## Analytical caveats — must be disclosed in any deliverable

1. **`$2.18B headline ≠ money NEU raised.** Grants get attributed to a faculty member even if the award predates their NEU hire (source marks everyone "Northeastern"). Use **`faculty_grants.neu_status == 'earned_at_neu'`** for external/NEU-work reporting:
   - `earned_at_neu` (start ≥ hire): 2,098 rows / ~$1,408M
   - `prior_institution` (start < hire): 866 rows / ~$685M — does NOT count as NEU work
   - `unknown` (missing dates): 180 rows / ~$153M
2. **Funding-credit model matters.** PI-only vs full-credit vs fractional split materially reorder faculty leaderboards — always state which model a chart uses. (`src/README.md` has the three canonical snippets.)
3. **Data is NSF/NIH-skewed** (~88% of dollars). Internal/foundation/industry funding is largely invisible.
4. **Abstract coverage: 2,390 of 2,676 grants (89%)** have usable abstract text as of the NIH RePORTER + NSF Award Search backfill (`src/backfill_nih_reporter.py`, `src/backfill_nsf_awards.py`, adopted gap-fill-only via `build_dataset.py`'s `_apply_abstract_backfill`). The NIH abstract "cliff" (near-0% coverage 2020+) was a data-collection artifact, not a funding decline, and is now closed (94–100% coverage 2020–2025). 5 grants (`abstract_source == 'nih_reporter_parent'`) have displayed-but-model-excluded text — see `src.clean_text.LOW_TRUST_ABSTRACT_SOURCES`. See `notebooks/08_abstract_recovery_and_refit.ipynb`.
5. **"Unassigned" (no confident topic) is a small bucket, not the dominant one.** Under the canonical curated keyword classifier: 36 grants / ~1.3% of dollars, individually accounted for (see "Topic modeling" below) — down from BERTopic's 697 grants / 26.7% of dollars. Any topic-based chart must still show it, just not treat it as the headline story.
6. Prefer `startdate`/`startdateyear` over `awarddate` (98% null). Use `totaldollars` from `ri_matches`, not the abstract file's unreliable `Dollar Amount`.
7. **External collaborators are invisible.** Every grant record is stamped "Northeastern" regardless of who else worked on it. The dashboard's PI-backfill enrichment (above) surfaces *some* external co-investigator names on a grant's own detail card (disclosed as "not matched to an NEU faculty record"), but never adds them anywhere they'd look like NEU people — collaboration-network analysis from this data is still NEU-internal only.
8. **312 of 2,676 grants have no PI at all** in the canonical pipeline (only a co-PI, or nobody). The dashboard fills 13 of these from backfill data; 299 remain genuinely PI-less — see "Topic modeling — state of play" for the matching-bug and unmatched-name context behind this number.

## Notebooks (`notebooks/`, run 01→09 in order)

All share a bootstrap: `warnings.filterwarnings('ignore')`, walk up parents to find `data/processed` as `REPO_ROOT`, load the parquets, `sns.set_theme(style='whitegrid', palette='muted')`. Figures saved `dpi=150, bbox_inches='tight'` to `outputs/` (and topic figures also to `notebooks/figures/`).

| # | Notebook | Covers |
|---|---|---|
| 01 | schema_overview | Load/profile all tables, nulls/schemas, join sanity checks, abstract-coverage diagnostics |
| 02 | funding_landscape | Baseline distributions: grant size (linear+log), duration, per-year, agency, rank/tenure, co-PI rate |
| 03 | funding_over_time | Annual/cumulative funding 2000–2025, rolling avg, college×year heatmap, agency mix, pre/post-COVID |
| 04 | who_gets_funded | Concentration (**Gini ≈ 0.632**, top-10 ≈19.6%), top-25 faculty, top-15 depts, agency×dept, `neu_status` attribution |
| 05 | collaboration_network | Co-PI NetworkX graph, degree/PageRank/betweenness, Louvain communities, cross-college matrix |
| 06 | research_topics | **LDA k=8** over abstracts — historical/legacy, kept standalone for comparison, feeds nothing downstream. Writes `outputs/topic_assignments.csv` |
| 07 | topic_deep_dive | **BERTopic** — historical/comparison-only, not the pipeline's canonical topic source; still loads `topic_assignments.parquet` (32 topics + "Unassigned") independently for its own analysis. College profiles, 8-parent-theme hierarchy, SPECTER2-centroid dendrogram, UMAP. |
| 08 | abstract_recovery_and_refit | Light-deps-only report on the NIH RePORTER + NSF Award Search abstract backfill and the BERTopic refit it fed — recovery rates, excluded parent-fallback grants, awardee-org attribution audit, `min_cluster_size` sweep. |
| 09 | keyword_classifier_validation | Validates the canonical curated keyword classifier against a hand-labeled 180-row gold set and against BERTopic agreement; embedding-centroid independent-signal check; title-only calibration analysis. |

## Topic modeling — state of play (canonical, final)

The **curated keyword classifier (BM25F)**, scored by `src/classify_by_keywords.py`
(stdlib/pandas only — no torch/bertopic/umap/hdbscan, fully offline and reproducible), is the
**canonical topic source**, replacing BERTopic. **31 leaves / 8 parents**
(`outputs/topic_keywords.json`, verified 0 errors via `kw_curation.py --check`). Output:
`data/processed/topic_keyword_assignments.parquet`, joined into the dashboard via
`kw_leaf_id`/`kw_parent_id`. `PARENT_NAMES` (`src/build_viz_aggregates.py`, byte-identical to
`docs/TopicVizPrototypes/shared/enrico.js`'s copy): Biomedical Sciences · Public & Behavioral
Health · Environmental Science & Ecology · Social Science, Public Policy & Education Research ·
Materials Science & Structural/Civil Engineering · Mathematics & Fundamental Physics ·
Computing, Networking & Robotic Systems · Workforce Development & Institutional Partnerships.

**A final hybrid layer sits on top and is what the dashboard actually renders**
(`assignmentSource` field, `final_leaf_id`/`final_parent_id`): a bounded LLM adjudication pass
(`src/adjudicate_low_confidence.py`, run live via the Anthropic Batches API) resolves the
low-confidence tail and can override a confident-but-wrong keyword match (e.g. a pedagogy-signal
false positive). Final `final_source` distribution over all 2,676 grants: `keyword_classifier`
78.3%, `llm_adjudication` 11.4%, `keyword_classifier_low_confidence` 8.9% (kept visible, not
silently dropped to Unassigned), `unassigned` 1.3% (36 grants). BERTopic's own assignment is
kept as a `bertopicDom`/`bertopicNoise` comparison column, not deleted, and LDA (`nb06`) is
historical-only — neither feeds the dashboard.

**Validated performance** (`notebooks/09_keyword_classifier_validation.ipynb`,
`src/validate_keyword_classifier.py`, 180-row hand-labeled gold set): keyword classifier 68.9%
accuracy (95% CI 61.8–75.2%) vs. BERTopic-equivalent 34.4% on the same rows — a decisive ~2x
margin. Confidence tiers calibrate correctly (high 81.2% > low 53.3%). BM25F constants
(`K1=1.5, B=0.75, ALPHA=0.5, W_TITLE=2.0`) were swept against the gold set and confirmed
already-optimal — don't re-tune these without new labeled data.

**Dashboard-only PI backfill (2026-08-31, final piece of this project's work):**
`load_augmented_faculty_grants()` in `build_viz_aggregates.py` fills 13 of the 312 no-PI grants
using NIH RePORTER / NSF Award Search investigator data (`data/nih_nsf_backfill/
investigator_faculty_proposals*.parquet`), tagging every filled row `link_source="backfill"`
(surfaced on the dashboard as `piSrc`/a grant-detail provenance note). Two modes: **promote** (a
matched person already linked as co-PI on that grant — flip `is_pi`/`is_copi`, no team-size
change) and **add** (matched person not linked at all — new row, `neu_status="unknown"`, a
deliberate simplification). Investigator names that don't resolve to any roster faculty are
disclosed only on the grant detail card they're mentioned on ("other investigators... not
matched to an NEU faculty record") — **never** added to the Every-PI roster, since most of that
population (~800-900 names) is genuinely external collaborators, not missing NEU people. Fixed a
real bug in the matcher along the way: `propose_faculty_matches()`
(`src/backfill_nih_reporter.py`) was comparing investigator names against the roster's raw
`"LAST, First"` string without stripping the comma, inflating apparent edit distance and
suppressing real matches — fixed by comparing against a comma-stripped `cmp_name`. Lowering the
match threshold below 90 was tried and **reverted** — it produced confirmed different-person
collisions (see `scripts/_refresh_investigator_matches.py`'s docstring for the specific false
matches found).

**Known, unresolved limitations of that backfill merge** (see "Open threads"):
- A **second matcher bug** (surname-blocking only on the last whitespace token, breaking
  multi-word surnames like "Di Pierro"/"Le Dantec") was found but **not fixed** — a small,
  named population still falls into the "unmatched" disclosure bucket instead of being properly
  linked.
- **22 grants** where an existing internal PI genuinely disagrees with the backfill's contact
  PI were **not auto-resolved** — almost always a collaborative-award/subaward granularity
  mismatch, not an error, and judged too subtle to correct automatically.
- Added rows' `neu_status="unknown"` means those grants' dollars don't cleanly sort into the
  `earned_at_neu`/`prior_institution` split used elsewhere on the dashboard.
- The broader investigator/co-PI proposal set from the backfill (~1,356 NSF + ~433 NIH proposed
  links, covering grants that already HAVE an internal PI, not just the 312 gap grants) was
  **never merged anywhere** — adopting it would add co-PIs to grants that already look complete
  and would reorder funding-credit leaderboards; deliberately out of scope for a dashboard-only
  enrichment.

## `docs/` reference map

- `data_dictionary.md` — per-column reference for raw files + join keys.
- `data_quality_report.md` — flagged issues (NSF/NIH bias, pre-hire attribution, roster gaps, abstract coverage).
- `ID_RECONCILIATION.md` — authoritative account of the 4-ids-per-person problem and the personid bridge.
- `INSIGHTS.md` — narrative findings across all notebooks (local-only, not published).
- `TOPIC_ANALYSIS_COMPENDIUM.md` — definitive LDA parameters, coverage bias, follow-ups (historical).
- `TOPIC_WORK_FORWARD_PLAN.md` / `TOPIC_WORK_EXECUTION_REPORT.md` — the BERTopic migration + orphan-reconciliation roadmap and what actually shipped (historical; superseded by the keyword classifier above, kept for context on *why* things are the way they are).
- `TOPIC_MODEL_REFIT_CHECKLIST.md` — the runbook for redoing the topic model from scratch, including which parts are automatic (`src/refresh_topicviz.py`) vs. need a human (parent-theme curation, `PARENT_NAMES`/`PARENT_COLORS` sync, `CAVEATS` prose).
- `TOPIC_CLASSIFICATION_BRAINSTORM.md` — the PI's original proposal for a transparent keyword→classifier method; marked resolved (the built system matches his proposed architecture, using a deterministic BM25F scorer rather than the LLM his brainstorm first floated).
- `EnricoVis/` — the PI's parallel visualization effort (read-only reference). `grants_visualization_work_breakdown.md` is his own handoff doc.
- `TopicVizPrototypes/` — **the final deliverable**; see `README.md` (repo root) for a plain-language tour and `docs/TopicVizPrototypes/README.md` for exact run commands. Two pages: `what_we_can_see.html` (Every grant / Every PI / About this data & what's missing — three tabs) and `topic_flow.html` (funding over time by topic). Built from ES modules under `what_we_can_see/`, fetching JSON from `data/` at load time (never inlined). `src/build_viz_aggregates.py` is the sole producer of that `data/` directory.
- `onlineoutput/` — the actual published site (nbconverted notebooks + EnricoVis apps + TopicVizPrototypes apps + index.html); committed to git despite being CI build output.
- **Deprecated:** `WEEKLY_PLAN.md` (superseded Dash kiosk/browser plan) and `07_grant_projection_specter2.html` (superseded interactive BERTopic projection).
- **Stale / secondary — do not treat as current:** `SETUP_GUIDE_WEEK3_OLD.md`, `PUBLISHING.md` (describes an old `docs/index.html` setup the workflow no longer uses), and `NedaNotebooks/` (a parallel EDA track with a different conda env and different numbers; not the canonical pipeline).

## Conventions & gotchas

- **Never commit notebook outputs.** Use `nbstripout` (in requirements) or "Restart kernel & clear outputs" before `git add`. Notebooks are committed with outputs stripped; the CI executes/renders them.
- **`data/processed/` and `outputs/` are gitignored** (`*.parquet` too), with two targeted exceptions: `outputs/topic_labels.json` (un-ignored via `!outputs/topic_labels.json`) and `data/nih_nsf_backfill/*.parquet` (deliberately tracked so the rate-limited live fetch never has to be re-run). Note a bare directory-level ignore can't be selectively un-ignored by a file-level negation alone; the *parent pattern* has to already be a wildcard-on-contents for a file-level `!` to work at all. Regenerate everything else with `build_dataset.py`; don't hand-edit parquets.
- **A bare directory-name `.gitignore` entry (`lib/`, `build/`, `dist/`, `var/`, `target/`, `parts/`, `env/`, `venv/`, `instance/`, `cover/` — all present in this repo's `.gitignore`, from the Python-packaging template) matches at ANY depth**, not just the repo root. Before adding a new directory anywhere under `docs/`, check `git check-ignore -v <path>` first.
- **Caveat — raw `DataSet/*.xlsx` ARE committed** despite `DataSet/ReadMe.md` stating raw data should not be. Treat the committed raw files as sensitive; confirm before adding/removing them.
- `scripts/_*.py` are **ad-hoc diagnostics**, not part of the pipeline — but `_diagnose_orphans.py`, `_orphan_faculty_overlap.py`, and `_check_new_abstracts.py` do write CSVs/parquets into `data/processed/`, so they aren't purely read-only.
- Several legacy parquets (`grant_faculty`, `grant_text`, `faculty_id_lookup`) still sit on disk from older pipeline versions; the current canonical tables are the 7 listed above.
- Join keys are frequently coerced to `str` before merging — do the same to avoid dtype-mismatch silent empty joins.
- Code-quality tools available: `ruff`, `black`, `nbstripout`.
- **A field's meaning, once shipped, has hidden callers — add a new field instead of redefining one.** `build_viz_data.py`'s `titleOnly` was once redefined mid-project and it cascaded into a wrong internal-reconciliation assertion, a wrong funnel total, and a display desync in the PI's own EnricoVis apps. Same lesson generalizes to any per-record provenance column (`asrc`, `piSrc`, `link_source`, `assignmentSource`): these are all additive, never redefinitions of an existing column's meaning.
- **When splitting/moving existing code across files, always pull the exact original text (e.g. `git show HEAD:path`) rather than reconstructing a block from inference** — a prior module split rewrote one facet-definition constant from inference instead of from source, silently dropping 46 faculty; caught only by an independent diff against git history, not by any static check.
- **NIH RePORTER / NSF Award Search API integration gotchas**: NSF's `awardeeName` parameter silently ignores an unquoted multi-word value (returns unfiltered nationwide results, no error) — must be wrapped in literal double quotes. NSF's `coPDPI` field's real format (`"First Last email@domain"`, sometimes with `", Jr."` or `"(Former)"`) never matched what the written API docs implied — always verify a guessed external API field format against one real live response.
- **D3/SVG panels:** a fixed-CSS-height container paired with a dynamically-sized `viewBox` silently scales all content down as it grows. Size the container to content (with a sensible floor), not a fixed `vh`.
- **D3's keyed `enter().append()` inserts a new node at the end of its parent** when nothing follows it in that selection — joining several different-kind sections (headers/cells/marks/selection-ring) onto one shared parent `<g>` breaks paint/hit-test order once any section's join set changes shape across renders. `grid.js`'s `createGrid()` uses a persistent, fixed-order layer `<g>` per section (`hdrLayer`/`emptyLayer`/`cellLayer`/`markLayer`/`ringLayer`) — don't flatten this back to one parent.
- **CSS scoping across the two dashboard pages:** `docs/TopicVizPrototypes/what_we_can_see/style.css` is loaded ONLY by `what_we_can_see.html`, never by `topic_flow.html` (confirmed via grep of its `<head>`). This means a rule in `style.css` using the exact same selector as one in the shared `shared/enrico.css` safely overrides it *only* on `what_we_can_see.html` — used repeatedly to fix issues (alignment, text color) on one page without touching the other. Check `topic_flow.html`'s `<head>` before assuming a shared-CSS change is safe for both pages.
- **A real browser IS usable in this working environment**, via headless Chrome + the DevTools Protocol: `Google Chrome.app --headless --remote-debugging-port=<port>` exposes a CDP JSON API (`http://localhost:<port>/json/new` etc.) that a plain Node script can drive with native `fetch`/`WebSocket` — no puppeteer/playwright needed. This gives real console-exception capture, real screenshots (`Page.captureScreenshot`), and real DOM/computed-style interrogation via `Runtime.evaluate` (including dispatching real `MouseEvent`s to confirm hover/click actually fire). Always serve the directory first (`python -m http.server`, never `file://`). `scripts/_check_topicviz.py` is a fast static first pass (tag balance, ES-module syntax/exports/cycles, id cross-reference, dataset-wiring reconcile) but cannot see rendering/layout/interaction — treat any visual or interaction change as needing a real-browser pass before calling it done.

## Tech stack

Python 3.11+ · pandas / numpy / pyarrow · matplotlib / seaborn / plotly · scikit-learn / gensim / nltk / wordcloud (topic modeling) · networkx / python-louvain (network) · rapidfuzz (fuzzy matching) · requests (NIH RePORTER / NSF Award Search backfill) · umap-learn + `allenai/specter2_base` (embeddings, local-only) · jupyterlab · d3 (dashboard).

## Open threads (handoff checklist)

Roughly ordered by how likely a new team is to hit them first.

1. **Multi-word-surname matcher bug (not fixed).** `propose_faculty_matches()`'s surname
   blocking only checks the last whitespace-separated token, so names like "Di Pierro" or "Le
   Dantec" never get proposed as a match even when correct. A small, named population falls into
   the dashboard's "unmatched investigator" disclosure instead of being properly linked. Fast
   follow, not urgent — affects a handful of people, not overall correctness.
2. **22 genuine PI disagreements between the internal roster and the backfill's contact PI**
   are surfaced nowhere except implicitly (the internal PI always wins, no flag). Worth a human
   pass if PI-credit accuracy on those specific 22 grants matters for a future analysis —
   they're a mix of collaborative-award sibling records and NIH parent-center-vs-subproject
   cases, not simple errors.
3. **299 of 2,676 grants still have no PI at all** (312 minus the 13 the dashboard backfills).
   The broader NIH/NSF investigator proposal set (~1,356 NSF + ~433 NIH links) that could
   plausibly fill more of these was deliberately not adopted anywhere, canonical or dashboard —
   see "Topic modeling — state of play" for why (leaderboard-reordering risk).
4. **8 grants remain `no_keyword_evidence` / genuinely unassigned** after three curation passes
   — each is individually accounted for (ambiguous titling, admin boilerplate, model-invisible
   low-trust abstract text), not a mystery, but a future curation pass could still try the 2
   `nih_reporter_parent` cases if their real (masked) text is ever recovered by another means.
5. **A topic-reliability / manual-inspection panel is blocked on the PI.** He's confirmed the
   architecture (transparent keyword→classifier, which is what got built) but a brainstorming
   session on presentation details, and naming a student from related prior work to loop in,
   never happened. The dashboard's existing "topic-keyword fingerprint" view (`detail.js`) is a
   working prototype of what this panel could become.
6. **Moving TopicVizPrototypes hosting to the PI's own GitHub Pages project** is blocked on his
   invite — not a code task, just needs him to send it.
7. **"Round 2" chart ideas were never picked up**: a money-vs-volume slope chart, a treemap, and
   an agency→theme→college Sankey were sketched as follow-on visualization ideas but not built.
8. **Dead code**: `barList()` and its `.barlist`/`.barrow` CSS in
   `what_we_can_see/about.js`/`style.css` are confirmed unused (superseded by the agency
   dumbbell chart and college-collaboration matrix) — safe to delete in a cleanup pass.
9. **The AcAn refreshed abstract export's 3 net-new-recoverable grants**
   (`data/processed/new_abstract_recovery.parquet`, via `scripts/_check_new_abstracts.py`) were
   measured but never adopted, given the tiny yield — low priority unless a similar refresh
   arrives with a bigger yield.

Everything else that was open earlier in this project (gold-set labeling, the Phase 4c LLM
adjudication run, the PI-backfill merge with provenance disclosure, the About-section rebuild,
the no-grey-text accessibility pass) is **done** — see "Topic modeling — state of play" above
and `.claude/sessions/` for how each was resolved.
