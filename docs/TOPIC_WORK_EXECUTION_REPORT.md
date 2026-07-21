# Topic Modeling v2 — Execution Report (M1–M4)

Companion to [`TOPIC_WORK_FORWARD_PLAN.md`](TOPIC_WORK_FORWARD_PLAN.md). This documents
what was actually built and measured while executing milestones **M1–M4** of that plan:
retiring LDA as the canonical topic model in favour of **SPECTER2 → UMAP → HDBSCAN →
c-TF-IDF (BERTopic)**, reconciling orphan abstracts back into the corpus, and rendering
the result in the EnricoVis interactive apps. **M5 is not yet started.**

---

## TL;DR

- **Canonical topic model is now BERTopic**, fitted offline on precomputed SPECTER2
  embeddings. **25 topics + an honest "unassigned" (noise) cluster**, chosen at
  `min_cluster_size=25` (perfectly stable: 25 topics on all 3 seeds).
- **Corpus grew from 2,676 grants → 2,741 documents** by recovering orphan abstracts
  (8 backfilled onto existing grants, 65 added as attributable pseudo-docs; 19 duplicates
  dropped, 311 unattributable).
- **All text cleaning is unified** in one module (`src/clean_text.py`) with a regression
  test suite; the LDA path is kept as a labelled legacy module.
- **All three EnricoVis apps** (`grant_atlas`, `topic_islands`, `topic_hierarchy`) now
  render real SPECTER2 + BERTopic output with the 25 curated topic labels and an
  explicit "Unassigned" bucket.
- The BERTopic move **fixed LDA's cross-vocabulary mis-parenting** — verified on the
  Alshawabkeh Puerto-Rico environmental grants (LDA put them under Biomedical; BERTopic
  places them in water/coastal/environmental-health topics).

---

## Context

Two topic-modelling tracks existed before this work: the analytical notebooks
(`06_research_topics`, `07_topic_deep_dive`, LDA k=8) and the interactive EnricoVis HTML
apps (LDA k=12 + a hand hierarchy, shipping a TF-IDF/t-SNE *preview*). They duplicated
cleaning, embedding, and topic fitting. The forward plan unified them onto one embedding
cache, one topic model, one labels file, and one cleaner — which is what M1–M4 delivered.

Environment note: the SPECTER2 / UMAP / HDBSCAN stack runs **locally only** (needs the
Hugging Face model download). Embeddings and the fitted model are precomputed and cached;
notebooks and HTML apps consume the committed artifacts.

---

## M1 — Unified plumbing

**Goal:** one cleaner, one embedding path, BERTopic + legacy-LDA modules, dependencies.

- **`src/clean_text.py`** — merged the EnricoVis cleaner with the notebook-06 rules into
  one module with two depths:
  - *conservative* (`clean_title` / `clean_abstract` / `clean_document`) — strips program
    prefixes, NSF review-criteria boilerplate, leading grant-id/PI stubs, and mangled
    `andlt/andgt` markup while keeping real sentences; feeds SPECTER2.
  - *aggressive* (`clean_for_lda`) — letters-only lowercasing for bag-of-words; plus the
    shared `DOMAIN_STOPS` (124 terms) and the length filter (≥200 chars **and** ≥40 tokens).
- **`tests/test_clean_text.py`** — 5 historical offenders (mangled markup, NSF boilerplate,
  `9501172 Kaeli, David` id-stub, stacked `CAREER: Collaborative Research:` prefixes, HTML
  entities). **15 assertions, all passing** (`pytest.ini` added so `pytest` resolves `src`).
- **`src/build_specter2_embeddings.py`** — now cleans every title/abstract through the
  shared cleaner *before* encoding (boilerplate is out-of-distribution noise for SPECTER2),
  and was later extended to embed the M2 pseudo-docs too.
- **`src/topics_bertopic.py`** (canonical) — `fit(docs, embeddings, seed, min_cluster_size)`
  using the offline-embedding path (`UMAP n_components=5 → HDBSCAN → c-TF-IDF`), returning
  the model + a diagnostics dict; a `__main__` writes the model, `topic_assignments.parquet`,
  and `bertopic_diagnostics.json`.
- **`src/topics_lda.py`** (legacy) — faithful extraction of notebook-06's k=8 LDA, kept for
  continuity with previously-cited compendium numbers.
- **`requirements.txt`** — added the local-only stack (`torch`, `transformers`, `adapters`,
  `sentence-transformers`, `bertopic`, `umap-learn`, `hdbscan`) + `pytest`.

---

## M2 — Orphan reconciliation

**Goal:** recover the 403 usable orphan abstracts using the strict ID crosswalk, before
finalising the corpus BERTopic tunes on. Implemented in **`src/reconcile_orphans.py`**.

**Method:** attribute each usable orphan (abstract ≥200 chars) to a faculty via
`personid_to_faculty.parquet` filtered to `strict_100pct`, then fuzzy-match it against that
faculty's grants — title `token_set_ratio ≥ 85`, date within ±365 days, amount within 15%
(non-veto when the unreliable abstract-file dollar amount is 0).

**Outcome buckets:**

| bucket | n | meaning |
|---|---:|---|
| `update` | **8** | orphan matched an **abstract-less** NEU grant → abstract backfilled (`abstract_source='orphan_recovered'`) |
| `extra` | **65** | resolved faculty, no grant match → pseudo-doc (`orphan-<id>`) for the topic model |
| `duplicate` | **19** | matched a grant that **already had** an abstract → dropped (not double-counted) |
| `unattributed` | **311** | personid not strict-resolved (143 ambiguous + 168 orphan-only) → dropped |

**Findings / deviations from the plan's estimates:**
- The plan's "235 of 403 resolve" was never reachable — the 403 rows come from only **150
  distinct personids**, and the strict-100% rule (which the plan mandates) resolves 53 of
  them = 92 rows.
- The plan's method lacked a **`duplicate` bucket**; without it, 19 re-uploads of
  already-abstracted grants would have been re-added as pseudo-docs, double-counting
  research already in the corpus (the Martens duplicate problem). Added.
- Grant abstract coverage moved modestly (1,928 → **1,936** of 2,676); the bigger effect is
  the corpus growing to **2,741 documents** (2,676 grants + 65 extras).
- Added an **idempotency guard**: re-running on already-reconciled grants aborts rather than
  silently reclassifying the 8 updates as duplicates.

Artifacts: enriched `grants.parquet` (+`abstract_source`), `extra_neu_abstracts.parquet` (65),
`grant_orphan_recovery.parquet` (403-row audit), `outputs/orphan_recovery_report.md`.

---

## M3 — BERTopic tuning

**Goal:** tune HDBSCAN on the unified corpus, pick a configuration, commit labels.

- Re-embedded the **2,741-doc** corpus through SPECTER2 (grants + extras), ~7.4 min CPU.
- **`src/tune_bertopic.py`** swept `min_cluster_size ∈ {15,20,25,30,40} × 3 seeds`:

| min_cluster_size | topics (mean ±sd) | noise % | largest | intra-cosine |
|---:|---|---:|---:|---:|
| 15 | 39.7 ±2.4 | 24.7 | 281 | 0.938 |
| 20 | 27.7 ±0.9 | 23.8 | 277 | 0.934 |
| **25** | **25.0 ±0.0** | 25.8 | 272 | 0.933 |
| 30 | 22.0 ±0.8 | 27.3 | 267 | 0.932 |
| 40 | 10.7 ±6.2 | 17.6 | 1162 | 0.921 |

- **Chose `min_cluster_size=25, seed=42`.** It produced exactly 25 topics on every seed
  (std 0.0 — stability by construction), largest topic only ~10% of docs, tight clusters.
  `mcs=40` was degenerate (one seed collapsed to 2 topics / a 2,610-doc blob).
- Final model: **25 topics, 28.3% noise, mean intra-cluster cosine 0.934**.
- **Sanity checks (all passed):**
  - *Title-only grants don't degenerate* — noise rate 27.6% (title-only) vs 28.0%
    (abstract-bearing); they cluster on their titles alone, so no special handling needed.
  - *Alshawabkeh spot-check* — her environmental grants land in the structural (t10),
    water/flood (t17), and environmental-health (t22) topics, **not** biomedical (the LDA
    failure the plan flagged).
- **Noise decision (§5.4):** kept as an honest "Unassigned" cluster rather than forcing
  assignments — this is the core advantage over LDA's argmax.
- **Labels:** 25 topics hand-curated in `outputs/topic_labels.json`; **t11** flagged as an
  artifact bucket (28/62 are placeholder `"Grant"` title-only ONR/NIH-sub records). Then 8
  parent super-groups derived by clustering topic centroids and curated (the plan's ~8-parent
  hierarchy).

The **25 topics + 8 parents** are listed at the end of this report.

---

## M4 — Interactive visualisation rewire

**Goal:** retire the TF-IDF/t-SNE preview; render real SPECTER2 + BERTopic in the 3 apps.

- **`src/build_viz_data.py`** emits the JSON the apps consume:
  - `grants_umap.json` — 2,676 grant points (2-D SPECTER2 UMAP coords, agency bucket, amount,
    year, `titleOnly`, one-hot 25-topic vector, dominant topic, `isNoise`).
  - `topics.json` — 25 topics (label, top terms, share, parent) + a noise entry.
  - `grants_hier.json` — points with `parent`/`leaf` + the 9-parent / 26-leaf `HIER` object.
- A 2-D UMAP of the embeddings (`specter2_umap_2d.npy`) was generated for the coordinates.
- **All three apps wired** (point/topic schema kept a superset of the originals, so the D3
  logic is unchanged — only the data source and topic count change):
  - **`grant_atlas.html`** — real coords + 25 topics; hover shows **"Unassigned"** for the
    746 noise grants; a greyed **"Unassigned (746)"** legend row toggles them. *Confirmed
    working in-browser.*
  - **`topic_islands.html`** — palette expanded 12→25 colours via a `topColor()` helper that
    greys the noise cluster; noise island labelled "Unassigned".
  - **`topic_hierarchy.html`** — points carry `parent`(0–7)/`leaf`; an "Unassigned" parent/leaf
    (id −1) absorbs the noise + t11 artifact; `pColor` greys negative ids.

**Deviation from the plan:** the apps still **inline** their data (via substitution) rather
than `fetch()`-ing the JSON. Inline substitution is schema-identical and zero-risk to the
D3 logic; the `fetch()` conversion (a ~1 MB → ~30 KB file-size win) is deferred. The JSON
files already exist, so that conversion is a follow-up whenever wanted.

`.bak` copies of all three HTMLs are kept for one-command revert until visually verified.

---

## Key decisions & deviations (at a glance)

| Area | Decision | Why |
|---|---|---|
| Topic model | BERTopic (mcs=25) canonical; LDA kept as legacy module | semantic clustering fixes cross-vocabulary mis-parenting; LDA retained for compendium continuity |
| Noise | Keep as honest "Unassigned" (~28%) | forcing assignments is what broke LDA |
| Orphans | Strict-100% bridge + new `duplicate` bucket | avoid wrong attribution and double-counting |
| Orphan yield | 8 update / 65 extra (below plan's guess) | only 150 personids behind 403 rows; strict rule resolves 53 |
| Viz wiring | Inline data substitution, not `fetch()` | schema-identical, zero-risk; fetch is a deferred file-size optimisation |
| Extras in viz | Excluded from the scatter (grants only) | keeps the atlas 1:1 with grants; badge/show is a §5.2 decision left open |

---

## Outcomes at a glance

- Documents modelled: **2,741** (2,676 grants + 65 recovered pseudo-docs)
- Topics: **25** + Unassigned; grouped under **8** parent themes
- Noise: **28.3%** (746 grant points) — honest "unassigned", not forced
- Cluster quality: mean intra-cluster cosine **0.934**; largest topic ~10% of docs
- Abstract coverage: **1,936 / 2,676** grants (72.3%), provenance-tagged via `abstract_source`
- Regression tests: **15/15** passing

---

## Files produced / changed

**New modules:** `src/clean_text.py`, `src/reconcile_orphans.py`, `src/topics_bertopic.py`,
`src/topics_lda.py`, `src/tune_bertopic.py`, `src/build_viz_data.py`, `tests/test_clean_text.py`,
`pytest.ini`.
**Changed:** `src/build_specter2_embeddings.py` (clean + extras), `requirements.txt`,
`notebooks/07_topic_deep_dive.ipynb` (§0 loads the fitted model).
**Data (`data/processed/`, git-ignored):** enriched `grants.parquet` (+`abstract_source`),
`extra_neu_abstracts.parquet`, `grant_orphan_recovery.parquet`, `specter2_embeddings.npy`,
`specter2_umap_2d.npy`, `specter2_ids.txt`, `bertopic_model/`, `topic_assignments.parquet`.
**Outputs:** `topic_labels.json`, `bertopic_diagnostics.json`, `bertopic_sweep.json`,
`orphan_recovery_report.md`.
**Viz:** `docs/EnricoVis/{grant_atlas,topic_islands,topic_hierarchy}.html` + `docs/EnricoVis/data/*.json`.

## Reproduce (local machine, in order)

```bash
python -m src.build_dataset            # raw .xlsx -> canonical parquets
python -m src.reconcile_orphans        # recover orphan abstracts (+abstract_source)
python -m src.build_specter2_embeddings# SPECTER2 cache (grants + extras)  [local-only]
python -m src.topics_bertopic          # fit + save the 25-topic model
python -m src.build_viz_data           # emit docs/EnricoVis/data/*.json
pytest tests/test_clean_text.py        # cleaner regression tests
```

---

## What remains (M5, not started)

- **M5a** NIH RePORTER abstract backfill — the only path to fix the NIH 2020+ abstract cliff.
- **M5b** LDA-vs-BERTopic agreement crosstab (compendium continuity).
- **M5c** Sub-topic / leaf label curation.
- **M5d** Faculty-embedding UMAP (`08_faculty_embedding.ipynb` + a `faculty_atlas.html`).
- **M5e** Topic × dollars-per-year trends.
- **M5f** Report notebook + **compendium correction** (it still calls the orphans "5,095
  external abstracts" — they are NEU-internal, 403 with text).
- Housekeeping: update `src/README.md` + `CLAUDE.md`, fix the stale `build_dataset.py`
  docstring, optional `fetch()` conversion of the HTMLs, one-shell rebuild script.

---

## Appendix — the 25 topics and 8 parents

**Parents:** P0 Life Sciences & Biomedicine · P1 Physical Sciences & Engineering ·
P2 Environment, Ocean & Climate · P3 Computing & Cybersecurity · P4 Networks, Signals &
Control · P5 AI, Robotics & Cognition · P6 Society, Health & Mobility · P7 Education & Learning.

| topic | label | parent |
|---:|---|---|
| 0 | Materials & Condensed-Matter Physics | P1 |
| 1 | Machine Learning, Robotics & Cognition | P5 |
| 2 | Mathematics & Theoretical Physics | P1 |
| 3 | Molecular & Computational Biology | P0 |
| 4 | Cancer & Drug Delivery / Therapeutics | P0 |
| 5 | Marine Ecology & Biogeochemistry | P2 |
| 6 | Wireless Networks & Communications | P4 |
| 7 | STEM Education & Faculty/Workforce Development | P7 |
| 8 | Security, Privacy & Cryptography | P3 |
| 9 | Public & Behavioral Health | P6 |
| 10 | Structural & Earthquake Engineering | P1 |
| 11 | Mixed / low-coherence (fisheries + thin-metadata) — *artifact* | — |
| 12 | Neurophysiology & Ion Channels | P0 |
| 13 | Programming Languages & Formal Methods | P3 |
| 14 | Tissue Engineering & Regenerative Medicine | P0 |
| 15 | Network Science & Complex Systems | P4 |
| 16 | Neuropharmacology & Addiction | P0 |
| 17 | Coastal Resilience & Flood Hazards | P2 |
| 18 | Antimicrobial & Infectious Disease | P0 |
| 19 | Underwater Acoustic Networks | P2 |
| 20 | Mobility, Supply Chains & Illicit Networks | P6 |
| 21 | Control Theory & Distributed Optimization | P4 |
| 22 | Environmental Health Policy & Chemical Exposure | P2 |
| 23 | Cloud & High-Performance Computing | P3 |
| 24 | Learning Games & Computational Thinking | P7 |
| −1 | Unassigned (noise) — 746 grants | — |
