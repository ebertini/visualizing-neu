# Topic Work — Forward Plan

Bridges the two topic-modeling tracks currently in the repo and lays out
what to build next.

- **Analytical track** — [`notebooks/06_research_topics.ipynb`](../notebooks/06_research_topics.ipynb),
  [`notebooks/07_topic_deep_dive.ipynb`](../notebooks/07_topic_deep_dive.ipynb),
  documented in [`TOPIC_ANALYSIS_COMPENDIUM.md`](TOPIC_ANALYSIS_COMPENDIUM.md).
- **Interactive track** — [`docs/EnricoVis/grant_atlas.html`](EnricoVis/grant_atlas.html),
  [`docs/EnricoVis/topic_islands.html`](EnricoVis/topic_islands.html),
  [`docs/EnricoVis/topic_hierarchy.html`](EnricoVis/topic_hierarchy.html),
  documented in [`docs/EnricoVis/grants_visualization_work_breakdown.md`](EnricoVis/grants_visualization_work_breakdown.md).

The two tracks currently duplicate text cleaning, embedding, and
topic fitting. This plan unifies them, **retires LDA as the canonical
topic model** in favor of SPECTER2 → UMAP → HDBSCAN → c-TF-IDF (via
BERTopic), retires the TF-IDF/t-SNE preview in EnricoVis, and picks up
the prioritized follow-ups from
[Compendium §9](TOPIC_ANALYSIS_COMPENDIUM.md#9-suggested-follow-ups).
It also inserts a new **orphan-abstract reconciliation** step (M2
below) using the ID crosswalk built in
[`ID_RECONCILIATION.md`](ID_RECONCILIATION.md).

> **Why the switch away from LDA.** LDA is bag-of-words; it treats
> "neural network" (ML) and "neural network" (neuroscience) as the
> same token, mis-parents grants that cross vocabularies (compendium
> flags Alshawabkeh's Puerto Rico environmental-health work landing
> under Biomedical at high confidence), and its topic IDs drift on
> every rerun. HDBSCAN over SPECTER2 embeddings clusters on
> citation-informed semantics instead of surface vocabulary, is
> deterministic given a seed, and emits an honest "noise" cluster
> instead of forcing low-confidence grants into whichever topic wins
> the argmax coin flip.

> **Why orphan reconciliation moved into the plan.** The compendium
> described [`grant_orphaned_abstracts.parquet`](../data/processed/grant_orphaned_abstracts.parquet)
> as "~5,000 external abstracts from an NSF/NIH crawl of collaborators
> + non-NU awards." Investigation ([`ID_RECONCILIATION.md`](ID_RECONCILIATION.md))
> shows that description is wrong: **only 403 of 5,095 rows actually
> carry an abstract** (7.9%); the rest are title-only. And those 403
> are **not external work** — they're NEU faculty's own grant records
> that failed the `SourceActivityId → grant_id` join. The new
> [`personid_to_faculty.parquet`](../data/processed/personid_to_faculty.parquet)
> bridge resolves 235 of the 403 to a specific NEU faculty. Some are
> likely updates/duplicates of grants already in the corpus (see the
> Martens example in [ID_RECONCILIATION.md §5.1](ID_RECONCILIATION.md#51-clean-case--abstractpersonid-110082--martens));
> the rest are genuinely new NEU abstracts. Both need to be handled
> before BERTopic tuning, since they change what the model sees.

---

## 0 · Gap analysis (current state)

| Concern | Analytical (nb06/07) | Interactive (EnricoVis) | Reconciliation |
|---|---|---|---|
| Text cleaning | inline in nb06 (HTML unescape + NSF boilerplate + `DOMAIN_STOPS`) | [`clean_text.py`](EnricoVis/clean_text.py) (mechanism prefixes + mangled `andlt`/`andgt` + leading ID stub) | Merge into single `src/clean_text.py` used by everything, and **run it before SPECTER2 encoding, not just before LDA** (boilerplate is out-of-distribution noise for SPECTER2). |
| Embedding | SPECTER2 via [`src/build_specter2_embeddings.py`](../src/build_specter2_embeddings.py) → cached npy | Not run yet; HTMLs shipped with TF-IDF→t-SNE preview coords inlined as `const DATA` | Both tracks read the cached npy. Preview is retired. |
| Topic model | LDA k=8 (nb06) | LDA k=12 (EnricoVis) | **Replace both** with BERTopic on precomputed SPECTER2 embeddings (SPECTER2 → UMAP → HDBSCAN → c-TF-IDF). LDA survives only inside the report notebook for continuity with previously-cited numbers. |
| Hierarchy | 8 parents × 4 leaves = 32 (nb07 §2, LDA-of-LDA) | 8 parents → 25 leaves proportional (LDA-of-LDA) | Use BERTopic's native `hierarchical_topics()` (condensed HDBSCAN tree). Cut at 2 levels; no LDA-of-LDA hack. |
| Label stability | Hand-curated `TOPIC_LABELS`, drifts across reruns | Auto-named from anchor terms in `topics.py` (does not exist yet) | c-TF-IDF top terms are derived from the cluster and stable given the seed; a single `outputs/topic_labels.json` still overrides them with human-curated names when we care. |
| Noise handling | 22% of grants argmax-assigned below 0.5 confidence, pollute topics | same | HDBSCAN emits a native `-1` noise cluster; low-confidence grants are labeled "unassigned" honestly and greyed out in the viz. |
| Orphan abstracts | Compendium describes them as "5,095 external abstracts" but they're actually NEU records that failed a join; only 403 have real abstract text | Not used | New M2 milestone runs `src/reconcile_orphans.py` to (a) fuzzy-match orphan abstracts to abstract-less NEU grants (title + faculty via bridge + date) and backfill, (b) attach the remainder to their resolved `faculty_id` as extra NEU documents flagged `has_grant_record=False`. |
| Faculty attribution for extra docs | n/a (LDA only saw matched grants) | n/a | Use [`personid_to_faculty.parquet`](../data/processed/personid_to_faculty.parquet) (strict 100% majority vote), filter to `resolution_method == 'strict_100pct'`. Everything else is silently dropped. |
| Pipeline scripts | live in notebooks | referenced in work breakdown but **not present in repo** | Materialize as `src/` modules that both notebooks and EnricoVis import. |
| Data location | `data/processed/grants.parquet` (~2,676 rows; ~1,928 with abstract) | expects `grants.csv` in same folder as HTMLs | EnricoVis reads from `data/processed/` directly (build step writes JSON to `docs/EnricoVis/data/`). |

---

## 1 · Guiding principles

1. **One source of truth per stage.** One cleaner, one embedding cache,
   one topic model, one hierarchy, one labels file. Notebooks and
   HTML apps both consume these.
2. **Semantics come from the embedding, not the vocabulary.** SPECTER2
   is trained on 6M citation-linked scientific paper triplets; that
   citation signal is what makes conceptually-related grants embed
   near each other regardless of surface vocabulary. LDA has no such
   signal.
3. **Precompute offline, render in the browser.** The container/env
   constraint that shaped EnricoVis (no HuggingFace, no `torch`, no
   `umap-learn` at render time) still holds. Everything heavy runs in
   `src/`, checked-in artifacts are lightweight JSON/parquet.
4. **Stability by construction.** HDBSCAN is deterministic given the
   seed and inputs; c-TF-IDF labels are derived from cluster membership.
   Human overrides live in `outputs/topic_labels.json`.
5. **Never re-fit if inputs are unchanged.** File-hash gates on
   `grants.parquet` + `clean_text.py`; make targets are cheap when
   nothing changed.
6. **Coverage caveats travel with the numbers.** Every figure/HTML that
   uses the topic model links to
   [Compendium §2](TOPIC_ANALYSIS_COMPENDIUM.md#2-the-data-that-feeds-the-topic-model)
   or embeds the caveat inline.

---

## 2 · Target architecture

```
src/
  clean_text.py               # unified cleaner (merge of nb06 rules + EnricoVis/clean_text.py)
  build_dataset.py            # already exists; already emits personid_to_faculty + faculty_id_lookup + faculty_missing_metadata
  reconcile_orphans.py        # NEW (M2): fuzzy-match orphan abstracts to abstract-less NEU grants and backfill
  build_specter2_embeddings.py# already exists; call src/clean_text.py before encoding
  topics_bertopic.py          # CANONICAL: BERTopic on precomputed SPECTER2 → UMAP → HDBSCAN → c-TF-IDF
  topics_lda.py               # LEGACY: LDA kept only for report-notebook continuity
  build_viz_data.py           # writes docs/EnricoVis/data/*.json from cached artifacts

data/processed/
  grants.parquet              # existing; M2 enriches abstract-less rows with recovered orphan abstracts
  grant_orphaned_abstracts.parquet  # existing (5,095 rows, 403 with abstract); untouched by M2 (audit source of truth)
  personid_to_faculty.parquet # existing (from build_dataset); strict-100% bridge
  faculty_id_lookup.parquet   # existing (from build_dataset); college + aauid
  faculty_missing_metadata.parquet  # existing; 13 faculty with grants but no HR record
  grant_orphan_recovery.parquet     # NEW (M2): audit trail — which orphans matched which NEU grants, plus scores
  extra_neu_abstracts.parquet       # NEW (M2): orphan abstracts NOT matched to a NEU grant but with resolvable faculty
  specter2_embeddings.npy     # existing (regenerated after clean_text + M2 recovery)
  specter2_umap_2d.npy        # NEW: 2-D UMAP for viz (n_components=2, cached, seeded)
  specter2_umap_5d.npy        # NEW: 5-D UMAP for HDBSCAN clustering (cached, seeded)
  bertopic_model/             # NEW: BERTopic .save() artifact (topics, c-TF-IDF, tree)
  topic_assignments.parquet   # NEW: doc_id → topic_id, topic_prob, is_noise, parent_id

outputs/
  topic_labels.json           # single source of truth: {id: {label, palette, top_terms, parent}}
  topic_assignments.csv       # regenerated from BERTopic; superset of the old nb06 export
  subtopics.csv               # regenerated from BERTopic hierarchical_topics()
  bertopic_diagnostics.json   # cluster sizes, %-noise, mean intra-cluster distance, seed
  orphan_recovery_report.md   # NEW (M2): human-readable summary of what was recovered vs left as extras

docs/EnricoVis/data/          # NEW folder — the HTMLs stop inlining data
  grants_umap.json
  topics.json
  grants_hier.json
  hier_topics.json
```

### Why BERTopic (vs. hand-rolling the same four steps)

BERTopic **is** SPECTER2 → UMAP → HDBSCAN → c-TF-IDF. Using the
library gets us `hierarchical_topics()`, `topics_over_time()`,
`find_topics("cancer")`, MMR keyword diversification, and a stable
`.save()`/`.load()` format for free. The only integration wrinkle is
that SPECTER2's proximity adapter isn't a `SentenceTransformer` — so
we follow the [documented offline path](https://maartengr.github.io/BERTopic/getting_started/embeddings/embeddings.html#custom-backend)
and call `topic_model.fit_transform(docs, embeddings=X)` where `X` is
the precomputed npy. If BERTopic ever becomes a friction point, the
plain pipeline is a 2-hour port to `hdbscan` + a 15-line c-TF-IDF.

### The HTML apps stop inlining data

They `fetch('./data/grants_umap.json')` at load. Drops file size from
~1 MB per HTML to ~30 KB and lets every build swap fresh data in
without editing the HTML files.

---

## 3 · Milestones

Each milestone is a self-contained PR-sized unit. Sequenced by
dependency; parallelizable pieces are marked.

### M1 — Unify the plumbing (foundational; blocks everything else)

- Move [`docs/EnricoVis/clean_text.py`](EnricoVis/clean_text.py) to
  `src/clean_text.py`. Fold in the nb06 rules (HTML unescape,
  `DOMAIN_STOPS`, length filter). Add a tiny pytest fixture with 5
  known-bad abstracts (mangled `andlt`, NSF boilerplate, `9501172
  Kaeli, David` stub) asserting the cleaner strips them.
- Teach [`src/build_specter2_embeddings.py`](../src/build_specter2_embeddings.py)
  to call `src/clean_text.clean_document` **before** encoding. This is
  critical — NSF boilerplate and mechanism prefixes are
  out-of-distribution noise for SPECTER2 (trained on published papers,
  not funding proposals). Bust the embedding cache after this change.
- Add `src/topics_bertopic.py` with a single public function:
  - `fit(docs, embeddings, seed, min_cluster_size=25) -> BERTopic`
    that runs `UMAP(n_components=5) → HDBSCAN → BERTopic.fit_transform`
    with `embeddings=X` (offline embedding path), returning the fitted
    model plus a diagnostics dict (cluster sizes, %-noise, mean
    intra-cluster cosine).
- Add `src/topics_lda.py` — a thin extraction of nb06's LDA fit,
  kept only so the report notebook (M4f) can regenerate the legacy
  k=8 numbers for continuity. Not used by EnricoVis.

**Deliverable:** `python -m src.topics_bertopic` fits BERTopic from
the cached SPECTER2 embeddings and writes
`data/processed/bertopic_model/` + `outputs/bertopic_diagnostics.json`.
Rerunning nb07 imports the fitted model instead of refitting inline.

### M2 — Reconcile orphan abstracts back into the NEU corpus

**Prerequisite for M3.** The corpus BERTopic tunes against must be
finalized before we sweep `min_cluster_size`. This milestone recovers
the 403 usable orphan abstracts using the ID crosswalk built in
[`ID_RECONCILIATION.md`](ID_RECONCILIATION.md).

**Inputs**

- [`data/processed/grant_orphaned_abstracts.parquet`](../data/processed/grant_orphaned_abstracts.parquet)
  — filter to rows with `len(abstract) >= 200` → 403 candidates.
- [`data/processed/personid_to_faculty.parquet`](../data/processed/personid_to_faculty.parquet)
  — filter to `resolution_method == 'strict_100pct'` → 235 of the 403
  orphans acquire a `faculty_id`. The remaining 168 (personid ambiguous
  or orphan-only) are silently dropped for now — no attribution, no
  entry.
- [`data/processed/grants.parquet`](../data/processed/grants.parquet)
  — the 748 abstract-less NEU grants are the fuzzy-match target pool.
- [`data/processed/faculty_grants.parquet`](../data/processed/faculty_grants.parquet)
  — to restrict candidate NEU grants to those the resolved faculty
  actually has on record.

**Method** (implemented in new `src/reconcile_orphans.py`):

1. For each of the 235 attributable orphan-with-abstract rows, look up
   the resolved `faculty_id` and pull the abstract-less NEU grants
   attributed to that faculty via `faculty_grants`.
2. Score every (orphan, candidate NEU grant) pair on:
   - **Title similarity** — `rapidfuzz.fuzz.token_set_ratio` (already a
     dependency of `build_dataset.py`). Threshold: **>= 85**.
   - **Date proximity** — `abs(orphan.start_date - neu.startdate).days`.
     Threshold: **<= 365 days** (grants get re-uploaded up to a year
     out from award date).
   - **Amount overlap** — if orphan.dollar_amount is non-zero,
     `abs(o - n) / max(o, n) <= 0.15`. Note: `Dollar Amount` in the
     abstract file is unreliable (median 0 per
     [data_dictionary.md](data_dictionary.md#grants-with-abstractxlsx--grants-with-text-content));
     if zero, this check contributes nothing (not a veto).
3. **Match rule:** best candidate above title threshold with date OK
   and (if dollar available) amount OK is treated as a match.
4. **Outcome buckets:**
   - **`update`** — orphan matches an existing abstract-less NEU grant.
     Backfill the abstract onto that NEU grant. Set
     `abstract_source = 'orphan_recovered'` (existing rows keep
     `abstract_source = 'internal'`).
   - **`extra`** — orphan has resolved faculty but no NEU grant match.
     Write to `extra_neu_abstracts.parquet` as a pseudo-doc with
     `doc_id = f'orphan-{id}'`, carrying `faculty_id`, `title`,
     `abstract`, `start_date` (no `grant_id`, no dollars, no agency).
     BERTopic sees these; downstream $/agency crosstabs skip them.
   - **`unattributed`** — no resolved faculty. Not touched; audit-only.
5. Full trace of every orphan (input signals, chosen bucket, matched
   NEU grant if any, all scores) written to
   `grant_orphan_recovery.parquet` and summarized in
   `outputs/orphan_recovery_report.md`.

**Expected outcome**

Based on the Martens example in
[ID_RECONCILIATION.md §5.1](ID_RECONCILIATION.md#51-clean-case--abstractpersonid-110082--martens),
we expect a meaningful chunk to fall into `update` (grants that got
re-uploaded with a different `SourceActivityId`). Ballpark going in
(before running):

- **update:** ~100–180 abstracts backfilled onto existing NEU grants.
  These raise NEU's native abstract coverage from **1,928 → ~2,050–2,100 of 2,676** (72% → ~77–79%).
- **extra:** ~50–130 new pseudo-docs (attributable but unmatched).
  Corpus BERTopic sees grows to **~2,150–2,250 documents**.
- **unattributed:** ~168 orphans with no resolved faculty — dropped
  from the topic model, kept in `grant_orphaned_abstracts.parquet`.

Actual numbers land at M2 execution; the report notebook (M5f) cites
whichever ones we get.

**Not covered by M2 (still deferred):**

- The 4,692 title-only orphans. No abstract text → nothing for the
  topic model to eat. They stay in `grant_orphaned_abstracts.parquet`
  as reference data.
- NIH 2020+ abstract cliff. Orphans can't fix this because the 2020+
  orphans are ~99% title-only. **M5a (RePORTER backfill) is now the
  only path** to close that gap.

**Deliverable:** updated `grants.parquet` with recovered abstracts,
`extra_neu_abstracts.parquet` for topic model consumption,
`grant_orphan_recovery.parquet` for audit, and
`outputs/orphan_recovery_report.md` for the humans.

### M3 — Tune BERTopic on the unified corpus

- Two knobs matter: `min_cluster_size` (HDBSCAN) and `min_topic_size`
  (BERTopic's post-hoc merge). Sweep
  `min_cluster_size ∈ {15, 20, 25, 30, 40}` over 3 seeds each.
- Report per configuration: number of topics, %-noise (`-1` cluster
  size / N), size of the largest topic, mean intra-cluster cosine
  similarity, and a visual check on the SPECTER2 2-D UMAP.
- **Sanity check the two known failure modes:**
  - **Title-only grants (748 of 2,676).** Confirm they don't all pile
    into one degenerate cluster. If they do, either fit BERTopic on
    the abstract-only subset (~1,928) and mark title-only grants as
    `predicted` via `.transform()`, or accept them as noise.
  - **Alshawabkeh's Puerto Rico environmental-health grants** (the
    LDA mis-parent example from [Compendium §7](TOPIC_ANALYSIS_COMPENDIUM.md#7-cross-cutting-caveats)).
    Spot-check that they now land in an environmental/public-health
    cluster, not a biomedical one.
- Pick the configuration. Expected outcome: **20–35 topics** at
  `min_cluster_size ≈ 25` (comparable granularity to LDA k=12 flat +
  a first-cut hierarchy), with a two-level `hierarchical_topics()`
  cut giving ~8 parents.
- Optional ablation: rerun with **SciNCL** (`malteos/scincl`)
  embeddings and report adjusted-Rand-index against the SPECTER2
  clusters. If SciNCL wins clearly, swap the embedding cache. If it's
  a tie, SPECTER2 wins on inertia.
- Commit human labels for the ~8 parents + top ~20 leaves to
  `outputs/topic_labels.json`. Anything below that stays on the
  auto-generated c-TF-IDF top-3 label.

**Deliverable:** committed `bertopic_model/`, committed
`outputs/topic_labels.json`, committed diagnostics JSON.

### M4 — Retire the TF-IDF/t-SNE preview in EnricoVis

- Add `src/build_viz_data.py` that reads:
  - `data/processed/specter2_umap_2d.npy` + `specter2_ids.txt`
  - `data/processed/grants.parquet` (metadata: title, agency,
    year, amount, `hasAbstract`, PIs)
  - `data/processed/bertopic_model/` (loaded via `BERTopic.load()`)
  - `outputs/topic_labels.json`
- Emits the four JSON files the HTMLs already know how to eat:
  - `grants_umap.json` — per-grant `{id, x, y, title, agency,
    agencyLabel, amount, year, hasAbstract, topicId, topicProb,
    isNoise}`. `topicWeights` is dropped (BERTopic assigns hard;
    per-topic probabilities are only meaningful for the top few).
  - `topics.json` — topic metadata + palette + c-TF-IDF top terms +
    human label if present in `topic_labels.json`
  - `grants_hier.json` — parent/leaf assignments from BERTopic's
    `hierarchical_topics()`
  - `hier_topics.json` — the tree with parent/child names
- Edit the three HTMLs so they `fetch(...)` these files instead of
  inlining `const DATA`. Keep the `const DATA` fallback commented for
  local file:// use.
- Add a **noise/unassigned bucket** to the topics list and legend.
  Renders greyed at ~30% opacity so viewers can see it's the residual
  22% or so, not silently absorbed.
- Flip the header credits from *"t-SNE preview · swap grants_umap.json
  for SPECTER2 + UMAP output"* → *"SPECTER2 + UMAP + HDBSCAN · N=2,676
  grants (748 title-only, K unassigned)"*.
- Regenerate all three HTMLs; verify:
  - clusters visibly regroup vs preview (this is the whole point);
  - Alshawabkeh's Puerto Rico grants land in the right region;
  - noise bucket highlights sensibly (interdisciplinary + title-only);
  - color-by-funding legend still composes with topic highlight and
    year slider.

**Deliverable:** the three HTMLs render real SPECTER2 semantics with
the same UI. Preview scripts (`build_preview.py`) are not resurrected.

### M5 — Pick up the highest-leverage Compendium follow-ups

Ordered by expected impact per hour (matching
[Compendium §9](TOPIC_ANALYSIS_COMPENDIUM.md#9-suggested-follow-ups)).

#### M5a — NIH RePORTER abstract backfill *(now the only path to fix the 2020+ NIH cliff)*

- Orphan reconciliation (M2) does not help here — 2,987 of the 5,095
  orphans are 2020+ but only ~80 of those carry abstract text. The
  RePORTER API is the only way to recover the missing NIH 2020+
  abstracts.
- Write `src/backfill_nih_abstracts.py` that:
  - reads `grants.parquet`, selects NIH rows with empty abstract and
    year ≥ 2020 (~150 rows);
  - hits the [NIH RePORTER v2 API](https://api.reporter.nih.gov/) by
    project number (`agencygrantid`);
  - merges recovered abstracts back into `grants.parquet` with
    `abstract_source = 'reporter'` (M2-recovered rows keep
    `abstract_source = 'orphan_recovered'`; native rows stay
    `abstract_source = 'internal'`);
  - re-invokes SPECTER2 encoding only for the touched rows.
- Re-run M3 tuning and confirm the biomedical late-window signal
  returns.
- Add the recovered count to the coverage table in
  [`01_schema_overview.ipynb`](../notebooks/01_schema_overview.ipynb).

#### M5b — LDA-vs-BERTopic agreement report *(compendium continuity)*

- Add a nb07 section that loads both the fitted BERTopic model and
  the legacy LDA k=8 fit, computes the topic-agreement crosstab
  (`crosstab(lda_topic, bertopic_topic)`), and reports which LDA
  topics were split, merged, or reclassified by BERTopic.
- Purpose: give the compendium reader a bridge between the old
  numbers and the new ones. Not a live pipeline component; runs once
  per major topic-model revision.

#### M5c — Sub-topic label curation

- The old "per-subtopic coherence gate" is no longer needed —
  HDBSCAN's condensed tree already surfaces coherent sub-clusters and
  drops the noise into `-1`. What remains is a one-shot label
  curation session on the ~20 largest leaves surfaced by
  `hierarchical_topics()`; commit human labels to
  `outputs/topic_labels.json` under a `subtopics` key so future
  reruns keep them.

#### M5d — Faculty-embedding UMAP *(natural extension for the PI)*

**Numbering note (2026-08-20):** `08` was taken by `notebooks/08_abstract_recovery_and_refit.ipynb`
(the NIH RePORTER / NSF Award Search backfill + refit report notebook, unrelated to M5d). If M5d
is ever picked up, its notebook becomes `09`, not `08`.

- New notebook `notebooks/09_faculty_embedding.ipynb`:
  - group SPECTER2 vectors by `faculty_id` (mean-pooled, weighted by
    dollars where available; extra pseudo-docs from M2 contribute
    unweighted since they have no dollar figure);
  - resolve faculty attribution via `faculty_grants.parquet` for real
    grants and directly via `extra_neu_abstracts.faculty_id` for
    pseudo-docs;
  - UMAP to 2-D; render interactive Plotly with hover (name,
    college via `faculty_id_lookup.parquet`, top topic, total \$);
  - answers the standing PI question *"who could Prof. X
    collaborate with?"*.
- Also emit `docs/EnricoVis/data/faculty_umap.json` and build a
  fourth EnricoVis app `docs/EnricoVis/faculty_atlas.html` on the
  same D3 canvas template as `grant_atlas.html`.

#### M5e — Topic × dollar-per-year trends

- Add a nb06 section computing per-topic *dollars* by year (not just
  grant count) using BERTopic assignments. This is a one-groupby
  edit; commit a plot alongside the existing count trend.
- BERTopic's `topics_over_time(docs, timestamps)` gives this for
  grant counts natively; the dollar version is a weighted variant.
- **Extras pseudo-docs are excluded** from this crosstab (no dollar
  figure).

#### M5f — Report-mode notebook (also: LDA legacy view)

- `notebooks/09_report_figures.ipynb` reads only the committed CSVs +
  JSON (`topic_assignments.csv`, `subtopics.csv`,
  `topic_labels.json`, `college_profiles.csv`,
  `bertopic_diagnostics.json`, `orphan_recovery_report.md`)
  and produces publication-ready figures. Zero model fitting; runs
  in seconds.
- Includes a **"legacy LDA view"** section that regenerates the
  compendium's k=8 numbers via `src/topics_lda.py`, so any figure
  previously cited under the old model is reproducible on demand.
- Every figure caption includes the coverage caveat one-liner —
  updated post-M2 to cite the new native-vs-recovered-vs-extra split.

---

## 4 · What "done" looks like

- `python -m src.build_dataset && python -m src.reconcile_orphans
  && python -m src.build_specter2_embeddings
  && python -m src.topics_bertopic && python -m src.build_viz_data`
  rebuilds everything from raw `.xlsx` in one shell script.
- `grants.parquet` carries an `abstract_source` column with values
  `internal | orphan_recovered | reporter`, so any downstream analysis
  can filter or footnote by provenance.
- `extra_neu_abstracts.parquet` exists as the sink for orphan
  abstracts that couldn't be matched to an existing NEU grant but do
  have a resolved `faculty_id`; BERTopic sees them, dollar/agency
  crosstabs skip them.
- All three EnricoVis HTMLs render **real SPECTER2 + BERTopic** without
  any code edits after a rebuild, and expose the noise/unassigned
  bucket honestly instead of hiding it in a real topic.
- Notebook 07 imports the fitted BERTopic model from
  `data/processed/bertopic_model/` and shares `topic_labels.json`
  with EnricoVis. Renaming a topic there updates every downstream
  artifact.
- `outputs/orphan_recovery_report.md` documents the M2 outcome
  (how many `update` / `extra` / `unattributed`).
- NIH 2020+ biomedical grants are visible in the topic model
  (M5a done).
- Notebook 07 has an LDA-vs-BERTopic agreement crosstab documenting
  which old topics were split/merged (M5b done).
- A one-page report notebook (`09_report_figures.ipynb`) exists that
  the PI can rerun without touching any modeling code, with a
  legacy-LDA section for continuity with the compendium (M5f done).

---

## 5 · Risks / open decisions to close before starting

1. **Orphan match thresholds** (M2). Title `token_set_ratio >= 85` +
   date within ±365d is the recommended starting point. Too strict →
   too few `update` matches, over-attributed pseudo-docs bloat the
   `extra` bucket. Too loose → false-positive matches attach wrong
   abstracts to NEU grants. Recommendation: run once at 85/365, spot-
   check 10 random matches in the resulting `grant_orphan_recovery.parquet`,
   adjust if needed. **Decision needed at M2 execution.**
2. **What to do with `extra_neu_abstracts` pseudo-docs in the viz.**
   Options: (a) render them alongside real grants but with a distinct
   "no grant record" hover badge (recommended — honest); (b) hide them
   from the viz entirely, still use them in BERTopic training only
   (loses signal in faculty-per-topic profiles). **Decision needed
   before M4.**
3. **`min_cluster_size` for HDBSCAN.** The single biggest knob for
   BERTopic. Too low → 60+ tiny clusters, unusable in a legend; too
   high → one giant "CS" cluster and everything else noise. M3 sweeps
   this; expected landing zone is 20–30 for ~2.1k documents.
4. **What to do with the noise cluster.** HDBSCAN will put ~15–25% of
   grants in `-1`. Options: (a) leave as "unassigned" (recommended,
   honest), (b) `.transform()` them to the nearest real cluster with
   a low confidence flag, (c) drop from the viz. **Decision needed
   before M4.**
5. **Title-only grants.** 748 of 2,676 (28%) have no abstract and
   M2 doesn't fix that (title-only NEU grants aren't part of the
   orphan pool). Recommendation: fit BERTopic on documents with real
   abstracts (post-M2: ~2,050–2,150 real + ~50–130 extras), then
   `.transform()` the 748 title-only grants via SPECTER2 nearest-
   cluster with a low-confidence flag. **Decision needed before M3.**
6. **Embedding choice.** SPECTER2 vs SciNCL — M3 runs the ablation.
   Decide before M4 which cache the viz build reads from.
7. **Hierarchy depth.** BERTopic's `hierarchical_topics()` returns a
   full tree; EnricoVis currently renders two levels (parent → leaf).
   Confirm two levels reads well with 25–35 leaves; if not, cut at
   three levels (super-group → parent → leaf).
8. **NIH SubAward keeps its own funder bucket** (per EnricoVis
   decision #2). Confirm this survives into the report figures — some
   published NEU comms fold NIH-SUB into NIH.
9. **`NAMED_MIN = 30` cutoff** hides NEH (19 grants) in "Other."
   Lower to `19` for humanities visibility, or accept the hide.
   **Decision needed before M4 palette is frozen.**
10. **File-size budget for the HTMLs.** After M4, JSON is fetched
    rather than inlined. Committed JSON should stay under ~2 MB
    uncompressed each; if it doesn't, gzip and serve via a tiny
    `docs/EnricoVis/index.html` shim.
11. **Container limitation persists.** SPECTER2 + UMAP + HDBSCAN will
    not run in Copilot Workspace / any sandbox without HF network
    access; every rerun is a local-machine step. All CI must consume
    the cached `.npy` / `bertopic_model/` / `.json` artifacts, never
    regenerate them.
12. **Compendium correction.** [`TOPIC_ANALYSIS_COMPENDIUM.md`](TOPIC_ANALYSIS_COMPENDIUM.md#2-the-data-that-feeds-the-topic-model)
    still describes orphans as "5,095 external abstracts." That's
    wrong — 5,095 records, only 403 with abstracts, all NEU-internal.
    Fix as part of M5f (report-mode notebook) so the corrected
    numbers land in one place.
---

## 6 · Suggested execution order (short version)

1. Land **M1** (unify plumbing + wire up BERTopic module). No
   user-visible change yet, but the embedding cache is regenerated
   with clean text.
2. Land **M2** (orphan reconciliation). Small user-visible change:
   NEU abstract coverage bumps ~72% → ~78%; `grants.parquet` gets an
   `abstract_source` column. **Review
   `outputs/orphan_recovery_report.md` before proceeding to M3.**
3. Land **M3** (tune BERTopic, commit labels + fitted model).
   Internal-only change.
4. Land **M4** (retire preview + wire HTMLs to BERTopic JSON). **Big
   user-visible viz upgrade** — first PI demo moment.
5. Land **M5a** (RePORTER backfill). Second demo moment — NIH 2020+
   signal returns (orphans can't do this) and headline numbers change.
6. Land **M5b** (LDA-vs-BERTopic agreement report) so the compendium
   reader can trace old-to-new. Do this before showing the report
   notebook to any external stakeholder.
7. Land **M5c–f** in parallel.
