# Northeastern Faculty & Grants — Weekly EDA & Visualization Plan

**Window:** June 1, 2026 → August 31, 2026 (13 weeks)
**Goal:** Explore, evaluate, and visualize 20 plus years of Northeastern faculty grant funding into an interactive visualization.

**Stack (locked in):** Python 3.11+, pandas, Plotly **Dash** (with `dash-cytoscape` for network views).
**Delivery targets (dual-mode, single codebase):**
  1. **Primary — Touchscreen kiosk:** visitors walk up and interact; fullscreen, touch-first, with attract/idle behavior.
  2. **Secondary — Public browser version:** same Dash app reachable via URL on desktop/tablet/phone; responsive layout, hover tooltips, deep-linkable views, for posterity and remote viewing.
**Team:** Solo build; weekly review with faculty advisors.

## Datasets (in `DataSet/`)
| File | Likely Contents | Primary Use |
|---|---|---|
| `faculty-list-2025.xlsx` | Faculty roster (name, dept, college, rank) | Dimension table — join key for grants |
| `grants-with-abstract.xlsx` | Grants + abstract text | Core fact table; enables topic / NLP analysis |
| `grants-with-coPI.xlsx` | Grants with co-PI relationships | Collaboration network analysis |
| `ri_matches_grants_2026.xlsx` | Research-interest ↔ grant matches | Topic alignment / interest mapping |

---

## Phase Overview
1. **Weeks 1–3 — Understand & Ingest** (foundations, schema, data quality)
2. **Weeks 4–6 — Explore** (univariate, bivariate, temporal trends)
3. **Weeks 7–9 — Evaluate** (deeper analytical questions, NLP, networks)
4. **Weeks 10–12 — Visualize** (design + build interactive dashboard)
5. **Week 13 — Polish & Deliver**

---

## Week 1 — Jun 1–7 · Project Setup & Schema Discovery
- Initialize a Python environment (`pandas`, `numpy`, `matplotlib`, `seaborn`, `plotly`, `jupyter`, `openpyxl`).
- Add `.gitignore` for `DataSet/` (per ReadMe).
- Create `notebooks/` folder; one notebook per dataset.
- Load each `.xlsx`, print: shape, dtypes, columns, sample rows, null counts.
- **Deliverable:** `notebooks/01_schema_overview.ipynb` + a `docs/data_dictionary.md` listing every column, type, and inferred meaning.

## Week 2 — Jun 8–14 · Data Quality Audit
- Per file: missingness matrix, duplicate detection, dtype coercion (dates, dollar amounts), categorical normalization (departments, agencies).
- Identify join keys across the 4 files (faculty ID / name normalization).
- Flag outliers in grant amounts, suspicious dates (outside 2005–2025).
- **Deliverable:** `docs/data_quality_report.md` with issues + decisions.

## Week 3 — Jun 15–21 · Unified Data Model
- Build canonical tables: `faculty`, `grants`, `grant_faculty` (PI/co-PI long form), `grant_topics`.
- Normalize names (case, accents, "Last, First" vs "First Last"); fuzzy-match across files (`rapidfuzz`).
- Persist as Parquet in `data/processed/`.
- Which corpus is good for scraping all faculty publication - maybe their google scholar but it can be pretty averse to bots
  - https://northeastern.discovery.academicanalytics.com/
  - OPENALEX is what is populating the current dataset - check the API for this
- **Deliverable:** `src/build_dataset.py` reproducible pipeline + ER diagram.

---

## Week 4 — Jun 22–28 · Univariate Exploration
- Distributions: grant amount (log scale), duration, count per year, agency frequency, department frequency.
- Faculty side: rank distribution, college breakdown, tenure proxy.
- **Deliverable:** `notebooks/04_univariate.ipynb` with 15–20 baseline charts.

## Week 5 — Jun 29–Jul 5 · Temporal Trends
- Annual & cumulative funding 2005–2025; rolling averages.
- Award counts vs total dollars (volume vs size).
- Pre/post-COVID, R1 designation effects, federal admin changes.
- **Deliverable:** time-series chart set + written observations.

## Week 6 — Jul 6–12 · Bivariate & Segmentation
- Funding by college × year heatmap; agency × department; faculty rank × award size.
- Top-N faculty/departments by total $; concentration (Gini, top-10 share).
- **Deliverable:** segmentation summary + candidate "headline" findings list.

---

## Week 7 — Jul 13–19 · Collaboration Network (co-PI)
- Build co-PI graph (`networkx`): nodes = faculty, edges weighted by joint grants/$.
- Compute degree, betweenness, communities (Louvain).
- Cross-college vs intra-college collaboration rates over time.
- **Deliverable:** network metrics CSV + draft node-link visualization.

## Week 8 — Jul 20–26 · Topic & Abstract Analysis
- Clean abstracts; TF-IDF + topic modeling (BERTopic or LDA, 15–25 topics).
- Topic prevalence over time; topics by college; topic ↔ agency affinity.
- Validate with `ri_matches_grants_2026` research-interest tags.
- **Deliverable:** topic table, topic-trend chart, top terms per topic.

## Week 9 — Jul 27–Aug 2 · Synthesis & Question Lock-in
- Consolidate findings into 5–8 "stories" the dashboard must tell (e.g., growth trajectory, interdisciplinary rise, agency dependency, emerging topics, star collaborators).
- Define KPIs and filter axes (year, college, department, agency, topic).
- **Deliverable:** `docs/narrative_brief.md` + wireframes (paper or Figma).

---

## Week 10 — Aug 3–9 · Visualization Architecture (Dash + Kiosk + Browser Foundations)
- Project scaffold: `app/`, modular pages (Overview, Trends, Collaborations, Topics, Faculty Explorer) using `dash.pages`.
- Wire processed Parquet → cached data layer (`flask-caching` or in-memory).
- **Dual-mode shell:** detect `?mode=kiosk` query param (or env var) → toggles fullscreen, hides browser-only chrome, enables attract mode. Default mode = browser.
- **Responsive layout:** CSS grid / `dash-bootstrap-components` breakpoints so the same views work at 1080p kiosk, desktop, tablet, and phone.
- **Touch ergonomics (kiosk mode):** tap targets ≥ 56 px, no hover-only tooltips, finger-friendly controls.
- **Browser affordances:** hover tooltips, keyboard navigation, copyable deep-link URLs (state in query string via `dcc.Location`).
- **Deliverable:** running skeleton app with navigation + one live chart, verified in both Chrome `--kiosk` and a normal browser window resized down to mobile.

## Week 11 — Aug 10–16 · Build Core Views
- Overview KPIs + annual funding trend (tap year to filter everything).
- College/department drilldown — treemap or sunburst (touch-friendly drill-in/out).
- Co-PI network view via `dash-cytoscape` (pinch-zoom, tap-to-focus a faculty member).
- Topic explorer (stream graph or stacked area; tap a topic to lock it).
- **Cross-filtering** via `dcc.Store` so every view reacts to selections.
- **Deliverable:** all primary views functional with cross-filtering on touch.

## Week 12 — Aug 17–23 · Faculty Explorer, Attract Mode & Polish
- Searchable faculty profile (on-screen keyboard friendly): grants timeline, collaborators, topics, funding mix.
- **Attract / idle mode (kiosk only):** after ~60 s of no interaction, reset filters and play a looping highlight reel. Disabled in browser mode.
- **Onboarding hint:** subtle "Tap to explore" (kiosk) / "Click to explore" (browser) prompt that adapts to mode.
- Tooltips on tap **and** hover, unified color system, loading skeletons, error states.
- **Browser polish:** page `<title>`, Open Graph meta tags for shareable links, favicon, About/Methodology page accessible from nav.
- Performance: precompute aggregates to Parquet; lazy-load network; cap initial payload < 2 MB.
- **Deliverable:** feature-complete dashboard in both modes, advisor review.

---

## Week 13 — Aug 24–31 · Finalize & Deliver
- Bug fixes, copy editing, methodology page (data sources, caveats, definitions).
- **Kiosk deployment package:** Dockerfile + `gunicorn` config + a `kiosk-launch.sh` that opens Chrome in `--kiosk --noerrdialogs --disable-pinch` pointing at `http://localhost:8050/?mode=kiosk`; auto-restart on crash.
- **Public browser deployment:** same container deployed to a public host (Render / Fly.io / NU internal) at a stable URL; HTTPS, basic analytics (Plausible or GA4 optional).
- Test on an actual touchscreen **and** on desktop/tablet/phone browsers — verify tap targets, responsive breakpoints, attract mode triggers only in kiosk mode, deep-links restore state.
- Export static screenshots + 2-min walkthrough video.
- Final write-up: `docs/final_report.md` summarizing findings + dashboard operator guide (kiosk + browser).

---

## Weekly Cadence (recommended)
- **Mon:** Plan week's questions; pull from backlog.
- **Tue–Thu:** Notebook work / coding.
- **Fri:** Commit findings + screenshots to `docs/weekly/wk{n}.md`; update backlog.
- **Risk buffer:** Reserve ~20% of each week for cleanup the prior phase missed.

## Tooling Checklist
- `uv` or `venv` for env; `requirements.txt` pinned.
- **Data:** `pandas`, `polars` (optional), `openpyxl`, `pyarrow`, `rapidfuzz`.
- **Analysis:** `networkx`, `scikit-learn`, `bertopic` or `gensim`, `spacy`.
- **Viz / app:** `plotly`, `dash`, `dash-cytoscape`, `dash-bootstrap-components`, `flask-caching`, `gunicorn`.
- **Quality:** `ruff`, `black`, `nbstripout` (avoid leaking data via notebook outputs).

## Suggested Repo Layout
```
.
├── DataSet/                  # raw (gitignored)
├── data/processed/           # parquet (gitignored)
├── notebooks/                # numbered EDA notebooks
├── src/                      # reusable code (ingest, clean, features)
├── app/                      # dashboard
├── docs/                     # data dictionary, reports, narrative
└── WEEKLY_PLAN.md
```

## Definition of Done (project)
- Reproducible pipeline from raw xlsx → processed parquet.
- Documented data dictionary + quality report.
- Interactive Dash dashboard covering: trends, segmentation, collaboration, topics, faculty explorer.
- **Kiosk-ready:** fullscreen, touch-first, attract mode, onboarding hint, one-command launch script.
- **Browser-ready:** responsive layout (desktop / tablet / phone), hover tooltips, deep-linkable URLs, deployed to a public host with a stable URL.
- Written narrative of 5–8 key findings with supporting visuals.

## Dual-Mode Design Rules (apply throughout Weeks 10–13)
**Shared (both modes):**
- Tap targets ≥ 56 px; spacing ≥ 16 px.
- Colorblind-safe palette; WCAG AA contrast minimum.
- All tooltips work on **tap and hover**.
- All views deep-linkable via query-string state (`dcc.Location`).

**Kiosk mode (`?mode=kiosk`):**
- Fullscreen, lock browser zoom/scroll, hide nav chrome.
- Base font 18–22 px; headings 32 px+ (viewed from standing distance).
- Idle reset after ~60 s; looping attract animation.
- Persistent "Reset" button always visible.
- Launch via Chrome `--kiosk` flag.

**Browser mode (default):**
- Responsive layout via `dash-bootstrap-components` breakpoints.
- Normal scroll, zoom, keyboard navigation enabled.
- Page title, favicon, Open Graph meta for shareable links.
- No idle reset (user controls their session).
