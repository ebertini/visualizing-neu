# Topic Analysis Compendium

A self-contained walk-through of the topic-modeling work in
[`notebooks/06_research_topics.ipynb`](../notebooks/06_research_topics.ipynb)
and [`notebooks/07_topic_deep_dive.ipynb`](../notebooks/07_topic_deep_dive.ipynb).
Written so that a new collaborator can (a) understand what was built and why,
(b) rerun everything from scratch, and (c) know exactly which follow-ups are
worth their time.

---

## 1. What was built

Two notebooks, run in sequence:

- **Notebook 06 — `06_research_topics.ipynb`** — the base topic model.
  Preprocess grant abstracts, fit a k=8 Latent Dirichlet Allocation (LDA)
  model, validate it, then link topic labels back to `grants` and
  `faculty_grants` to answer downstream "who / when / where / how much"
  questions. Exports `outputs/topic_assignments.csv` — one row per matched
  grant with its dominant topic, label, and probability.
- **Notebook 07 — `07_topic_deep_dive.ipynb`** — four follow-up analyses
  triggered by PI questions. Depends on the CSV produced by nb06.
  - §1 Row-normalised topic × college heatmap + per-college profile cards
  - §2 Sub-topics inside each parent (refit LDA(k=4) per parent bucket)
  - §3 Topic dendrogram (Jensen-Shannon distance over topic word-distributions)
  - §4  UMAP projection of every grant, TF-IDF baseline
  - §4b UMAP projection using SPECTER2 embeddings (scientific-paper transformer)

Everything runs end-to-end via `nbclient` under Python 3.11. The only heavy
step is the one-time SPECTER2 encoding (~5 min on CPU, cached to disk).

---

## 2. The data that feeds the topic model

The topic model operates on **grants that have both a matched Northeastern
`grant_id` and non-trivial abstract text** (≥ 200 characters, ≥ 40 tokens after
cleaning). Under the current schema in
[`data/processed/grants.parquet`](../data/processed/grants.parquet) this
is **1,928 of 2,676 total grants (72%)**.

The abstract text now lives directly on `grants` — the pipeline picks the
most-recently-updated abstract record per grant. Abstracts that did not
match any NEU `grant_id` (the external NSF/NIH crawl of collaborators + non-NU
awards, ~5,000 records) are kept separately in
[`data/processed/grant_orphaned_abstracts.parquet`](../data/processed/grant_orphaned_abstracts.parquet)
in case anyone wants to enrich the topic-model vocabulary later. They are
**not** used in the current pipeline.

### Coverage caveats — very important for interpretation

Abstract coverage is deeply uneven across three axes; see the diagnostic
cells at the bottom of
[`notebooks/01_schema_overview.ipynb`](../notebooks/01_schema_overview.ipynb)
for the full breakdown. Key facts:

- **Only NSF has reliable coverage across every period** (79–100%).
- **NIH shows a cliff from 87% (2015–2019) to 1% (2020–2024) to 0% (2025)** —
  something in the internal upload pipeline broke in 2020.
- **NIH SubAward, ONR, Army Research Office, Air Force Research Office, HHS,
  Department of Education**: **0% abstract coverage in every period**. Together
  that's ~285 grants (11% of the corpus) permanently invisible to the model.
- **Faculty upload compliance varies wildly** — Felleisen (94%), Sternad (86%),
  Cheng (82%) at the top; Makowski (12%), Makris (32%), Alshawabkeh (43%),
  Makriyannis (48%) at the bottom. Alshawabkeh and Makriyannis are #2 and #3 by
  total funding — their low coverage means environmental engineering and
  drug/pharma are systematically under-represented in the topic tables.

**Bottom line for any report drawing on the topic model:** the model's picture
of NEU research is biased toward (a) NSF, (b) pre-2020 NIH, (c) PIs who
diligently upload. Add a footnote whenever you cite topic-share numbers.

---

## 3. The topic model itself (Notebook 06)

### 3.1 Preprocessing

Applied to each abstract before vectorising:

1. HTML unescape + strip tags — many NSF abstracts have `<p>` and `&lt;` residue
   that leaks tokens like `andgt`, `andlt`.
2. **Remove NSF boilerplate** — the paragraph *"This award reflects NSF's
   statutory mission … Broader Impacts review criteria"* appears on ~40% of
   NSF abstracts and completely dominates the topic model if left in.
3. Keep letters only, lowercase.
4. Length filter: require ≥ 40 tokens after cleaning.

### 3.2 Vocabulary

`CountVectorizer(max_df=0.6, min_df=15, ngram_range=(1,2), stop_words='english')`
plus a hand-curated `DOMAIN_STOPS` set that removes:

- Boilerplate research vocabulary (`research`, `project`, `study`, `abstract`, …).
- Institution words (`northeastern`, `university`, `professor`, …).
- Overly broad academic words (`science`, `engineering`, `technology`, `design`,
  `students`, `information`) — these were merging otherwise-distinct topics.

Resulting vocabulary is ~2,500 terms.

### 3.3 Choice of k

We fit LDA for k ∈ {5, 6, 7, 8, 9, 10, 12} and inspect perplexity. Perplexity
monotonically decreases with k, so we look for an elbow, not a minimum. **k=8**
sits at the elbow and produces topics that are individually interpretable;
larger k splits topics into duplicates rather than revealing new themes.

### 3.4 The 8 topics

Labels are **human-curated after inspecting the top-12 terms per topic**.
`TOPIC_LABELS` in the notebook maps topic-id → label:

| id | Label | Representative terms |
|---:|---|---|
| 0 | Mathematics & theoretical physics | theory, physics, quantum, spin, groups |
| 1 | Biomedical (drug/disease/cancer) | drug, brain, disease, cancer, patients |
| 2 | Software, data & ML systems | data, software, algorithms, learning, tools |
| 3 | Cell & molecular biology | cell, cells, molecular, protein, dna |
| 4 | Environmental & public health | social, health, community, environmental |
| 5 | Hardware, energy & wireless systems | energy, devices, networks, power, wireless |
| 6 | HCI, learning & applied research | learning, human, design, water, visual |
| 7 | STEM education & outreach | students, program, education, engineering |

**⚠ Label drift — the single biggest gotcha.** LDA is initialised randomly,
so topic-id ↔ label mapping is **not stable across corpus changes**. When we
last rebuilt the pipeline (schema refactor: `grant_abstracts.parquet` merged
into `grants.parquet`) the topic IDs reshuffled and the hardcoded
`TOPIC_LABELS` dict silently produced wrong labels for every downstream
chart. If you rerun `01–06` after any change to the abstract corpus:

1. Look at the top-12 terms printout in nb06 (the cell right before
   `TOPIC_LABELS = { … }`).
2. Manually rewrite the labels dict.
3. Re-run downstream cells and nb07.

Notebook 07 attempts to auto-align via majority-vote crosstab against
`topic_assignments.csv`, so the labels there stay in sync provided you rerun
nb06 first.

### 3.5 Validation

Two independent checks:

- **UMass coherence** — measures how often the top words for each topic
  co-occur in the training documents. Range −1 to −3 = coherent; more negative
  = incoherent. Current model's mean is around −1.7.
- **Assignment confidence** — probability of the dominant topic per document.
  Current model: **mean 0.68, and 78% of grants have their top topic at ≥ 0.5
  confidence**. The remaining 22% are legitimately mixed (grants that span two
  themes).

---

## 4. Sub-topics (Notebook 07, §2)

**Motivation.** The PI observed that "Biomedical" is too broad — what *kind*
of biomedical research does NEU actually do? We answer this with a two-level
LDA cascade.

**Method.** For each of the 8 parent buckets:

1. Slice the abstracts assigned to that parent by nb06.
2. Refit LDA with `k=4` on that slice only (smaller vocab, `min_df=5`).
3. Take top-12 terms per sub-topic.
4. Auto-generate a label from the top 3 non-filler terms (e.g.
   `drug · cancer · tumor`).
5. Join sub-topic docs back to `grants` and `faculty_grants` to enrich with $
   totals, top grants, and top faculty.

Loop over 8 parents → **32 sub-topics** written to
[`outputs/subtopics.csv`](../outputs/subtopics.csv).

**Why not just fit LDA(k=32) once?** Because a flat k=32 model would freely
mix biomedical and CS terms in the same topic. The two-level cascade guarantees
every sub-topic lives inside one parent's semantic space, at the cost of
losing possible cross-parent themes.

**Why auto-generated labels?** LDA sub-topic indices are randomly assigned per
fit, so a hand-curated `sub_id → name` dict would be wrong after every
rerun. Auto-labels are honest ("drug · cancer · tumor") but ugly. A human
should overwrite `subtopics_final.subtopic_label` after inspecting `top_terms`
if the labels are going into a slide deck.

**Known limitation.** The parent-topic bucketing is a hard argmax; a grant with
0.35/0.35/0.30 topic mixture is arbitrarily placed under whichever came out
highest. Low-confidence docs contribute noise to sub-topic clusters — you'll
see this as an occasional obvious mis-parented grant (e.g. protein-chemistry
work landing under Environmental).

---

## 5. Dendrogram (Notebook 07, §3)

**Question.** Which of the 8 parent topics are semantic cousins?

**Method.** Treat each topic's word distribution (`lda.components_[k]`
normalised to a probability vector over the vocabulary) as a point in
2,500-D space. Compute pairwise **Jensen–Shannon distance** — a symmetrised
KL divergence, bounded on [0, 1] — then run scipy's average-linkage
hierarchical clustering.

**Output.** [`outputs/w7_topic_dendrogram.png`](../outputs/w7_topic_dendrogram.png).
Three natural super-groups emerge:

1. **Life sciences** — Biomedical (drug/disease) + Cell & molecular biology.
2. **Engineering / systems** — Hardware/wireless + Software/data/ML +
   (loosely) Materials.
3. **Everything else** — Environmental, STEM-ed, and Math sit as three
   loose leaves.

**Practical use.** If someone wants a k=3–4 exec-summary version of the topic
picture, the dendrogram gives the natural cuts: life-sciences, engineering-
systems, environment+policy, basic-science/education.

---

## 6. UMAP projections (Notebook 07, §4 and §4b)

Two independent projections of the same ~1,900 abstracts so we can
cross-check the topic structure.

### 6.1 TF-IDF baseline

- Vectorise with `TfidfVectorizer(max_df=0.6, min_df=5, ngram_range=(1,2),
  max_features=15000)`.
- Reduce 15,000-D → 2-D via `umap.UMAP(n_neighbors=15, min_dist=0.1,
  metric='cosine', random_state=42)`.
- Points are individual abstracts; colours are LDA topics / colleges / agencies
  (applied *after* the projection, not as inputs).
- Runs in ~10 s. No model download.

Outputs: static [`outputs/w7_umap_grants.png`](../outputs/w7_umap_grants.png)
(4-panel: topic, college, agency, year × $) and interactive
[`docs/07_grant_projection.html`](07_grant_projection.html).

### 6.2 SPECTER2 embeddings

- **Model:** [`allenai/specter2_base`](https://huggingface.co/allenai/specter2_base)
  (BERT-base sized, ~440 MB) + the *proximity* adapter for retrieval-style
  similarity. Trained on 6M citation-linked scientific-paper triplets.
- **Input format:** `title + [SEP] + abstract`, truncated to 512 tokens.
- **Output:** 768-dim CLS embedding per grant.
- **Pipeline:**
  [`src/build_specter2_embeddings.py`](../src/build_specter2_embeddings.py)
  encodes every matched grant once, caches to
  `data/processed/specter2_embeddings.npy` + `specter2_ids.txt`. Takes ~5 min
  on CPU. Notebook 07 loads the cache and only re-runs UMAP.
- **UMAP hyperparameters identical to TF-IDF** so differences come from the
  embedding, not the reducer.

Outputs: static [`outputs/w7_umap_grants_specter2.png`](../outputs/w7_umap_grants_specter2.png)
and interactive [`docs/07_grant_projection_specter2.html`](07_grant_projection_specter2.html).

### 6.3 What the comparison shows

- **Same LDA topic colours, different embeddings.** SPECTER2 groups them into
  visibly tighter, well-separated blobs; TF-IDF smears them across a big
  central blob. This is **independent validation of the k=8 LDA topics**: two
  totally different similarity signals (surface vocabulary vs.
  citation-based semantic embedding) both group the same abstracts into
  recognisably similar clusters.
- **SPECTER2 reveals sub-structure inside parents** that the TF-IDF layout
  misses — you can visually pick out drug/cell/brain sub-clusters inside
  Biomedical without any sub-topic model.
- The interactive Plotly is the artefact worth actually sending to the PI —
  hover for title / PI / college / agency / $ / year, toggle colour between
  topic / college / agency using the buttons above the plot.

### 6.4 Plot conventions

Both interactive HTMLs share:

- Locked axis ranges and `scaleanchor='y'` — toggling categories doesn't
  rescale or stretch the plot.
- Fixed 260-pixel right margin — the legend column stays put regardless of how
  many categories the current colouring produces.

---

## 7. Cross-cutting caveats

Grouped by severity. Anyone extending this work should read all of these.

### Blockers for external reporting

- **Label instability under corpus changes** (§3.4). Rerun nb06 → visually
  inspect top-terms → rewrite `TOPIC_LABELS` → rerun downstream.
- **Abstract coverage bias** (§2). NIH after 2019 is invisible; DoD is 100%
  invisible; per-faculty compliance varies from 12% to 94%. Cite topic-share
  numbers with a footnote.
- **The report should say which credit model it uses.** Notebook 07 defaults
  to full-credit (PI and every co-PI get the full grant $). PI-only or
  fractional produce noticeably different faculty leaderboards. See
  [`src/README.md`](../src/README.md#choosing-a-funding-credit-model).

### Analysis choices worth revisiting

- **k=8 is a defensible elbow but not a proof.** Try k=6 (should merge
  drug/cell + wireless/hardware) or k=10 (should split software/data/ML)
  before committing to the report's final view.
- **LDA is bag-of-words.** It can't distinguish "neural networks" as ML from
  "neural networks" as neuroscience, and it visibly mis-parents grants that
  cross vocabularies (e.g. Alshawabkeh's Puerto Rico environmental-health
  work landing under "Biomedical" at high confidence). The SPECTER2 UMAP
  makes this failure mode obvious. See §9 for the BERTopic alternative.
- **Hard-assignment noise.** Every downstream chart uses `argmax` on the
  doc-topic matrix. About 22% of grants have < 0.5 confidence on their top
  topic; these should arguably be excluded or shown with reduced weight in
  topic-mix trends.
- **Time-window choice.** The "topic mix has shifted over time" analysis
  compares 2005–2014 vs 2015–2024. The NIH 2020+ cliff distorts the late
  window for anything biomedical. Consider comparing 2005–2014 vs 2015–2019
  instead.

### Known imperfections we accepted

- **The parent → sub-topic bucketing is a hard argmax** even for
  low-confidence grants. Fix would be to require confidence ≥ 0.5 before
  bucketing.
- **Sub-topic labels are auto-generated** from top-3 terms. Ugly but honest;
  the alternative is to hand-curate every rerun.
- **Notebook 07 refits LDA in §0** rather than loading the fitted model from
  nb06. This is redundant compute (~1 min) but avoids a pickle dependency;
  it also lets us align topic IDs to nb06's exported labels via majority
  vote, which is more robust than relying on `random_state` to reproduce
  exactly.

---

## 8. File map

Inputs to the topic model:

| File | What it is |
|---|---|
| [`data/processed/grants.parquet`](../data/processed/grants.parquet) | Grants + abstract text (1,928 non-empty). |
| [`data/processed/grant_orphaned_abstracts.parquet`](../data/processed/grant_orphaned_abstracts.parquet) | 5,095 external abstracts. Not currently fed to the model; kept for optional vocab enrichment. |
| [`data/processed/faculty.parquet`](../data/processed/faculty.parquet) | Faculty roster with hire dates, colleges. |
| [`data/processed/faculty_grants.parquet`](../data/processed/faculty_grants.parquet) | Faculty ↔ grant links with `is_pi`, `is_copi`, `neu_status`. |

Notebooks:

| File | What it does |
|---|---|
| [`notebooks/01_schema_overview.ipynb`](../notebooks/01_schema_overview.ipynb) | Schema + abstract-coverage diagnostics (§2 caveats). |
| [`notebooks/06_research_topics.ipynb`](../notebooks/06_research_topics.ipynb) | k=8 LDA + validation + all "who / when / where / how much" cross-tabs. |
| [`notebooks/07_topic_deep_dive.ipynb`](../notebooks/07_topic_deep_dive.ipynb) | Sub-topics, dendrogram, UMAP × 2. |

Scripts:

| File | What it does |
|---|---|
| [`src/build_dataset.py`](../src/build_dataset.py) | Rebuilds the four parquet files from the raw `.xlsx` inputs. |
| [`src/build_specter2_embeddings.py`](../src/build_specter2_embeddings.py) | One-time SPECTER2 encoding; caches embeddings + ids. |

Outputs the notebooks produce:

| File | Produced by |
|---|---|
| [`outputs/topic_assignments.csv`](../outputs/topic_assignments.csv) | nb06 §13 |
| [`outputs/subtopics.csv`](../outputs/subtopics.csv) | nb07 §2 |
| [`outputs/college_profiles.csv`](../outputs/college_profiles.csv) | nb07 §1 |
| [`docs/college_profiles.html`](college_profiles.html) | nb07 §1 (rendered cards) |
| [`outputs/w6_*.png`](../outputs/) | nb06 static figures |
| [`outputs/w7_*.png`](../outputs/) | nb07 static figures |
| [`outputs/w7_umap_grants.png`](../outputs/w7_umap_grants.png) | nb07 §4 (TF-IDF UMAP 2×2 panel) |
| [`outputs/w7_umap_grants_specter2.png`](../outputs/w7_umap_grants_specter2.png) | nb07 §4b (SPECTER2 UMAP 2×2 panel) |
| [`outputs/w7_topic_dendrogram.png`](../outputs/w7_topic_dendrogram.png) | nb07 §3 |
| [`docs/07_grant_projection.html`](07_grant_projection.html) | nb07 §4 (interactive Plotly, TF-IDF) |
| [`docs/07_grant_projection_specter2.html`](07_grant_projection_specter2.html) | nb07 §4b (interactive Plotly, SPECTER2) |
| [`data/processed/specter2_embeddings.npy`](../data/processed/specter2_embeddings.npy) | build_specter2_embeddings.py (2,676 × 768) |

---

## 9. Suggested follow-ups

Ranked by expected impact per hour of work.

### High leverage — change what the report can say

1. **Backfill NIH abstracts from RePORTER (~5 min of network calls).** NIH
   RePORTER exposes all funded abstracts publicly via API. Match on grant
   number; recover ~150 grants of missing 2020+ NIH coverage. Would restore
   the biomedical signal to the late-window topic-mix analysis and probably
   change several headline numbers.
2. **Swap LDA for BERTopic** (`pip install bertopic`). BERTopic runs
   SPECTER2 → UMAP → HDBSCAN → c-TF-IDF for labels. It's the exact stack
   we're already using except it clusters directly on the SPECTER2 embeddings
   rather than fitting a separate bag-of-words model. Expected wins:
   (a) semantically coherent clusters — no more Alshawabkeh-mis-parented,
   (b) stable labels across reruns (HDBSCAN is deterministic given the seed),
   (c) auto-labels via c-TF-IDF. ~1 hour to prototype in a new section of
   nb07 alongside the LDA output for direct comparison.
3. **30-minute label curation session.** Rewrite the 32 sub-topic labels in
   `outputs/subtopics.csv` from auto-generated ("drug · cancer · tumor") to
   readable ("Cancer therapeutics"). Trivial but changes how the sub-topic
   table reads on a slide.

### Medium leverage — better inputs, better model

4. **Enrich vocabulary with the 5,095 orphan abstracts.** Fit the LDA
   vectorizer on matched + orphans, then predict topics only on matched.
   Bigger vocab, cleaner topics; the orphan corpus is roughly the same
   scientific domain as the NEU corpus so this is safe.
5. **Coherence-per-sub-topic diagnostic.** Compute UMass coherence for each
   of the 32 sub-topics and flag those below a threshold as noise clusters.
   Prevents over-interpreting artefacts like the "students · protein · molecular"
   sub-topic under Environmental & public health.
6. **Pickle the fitted LDA model.** Save `lda` + `vectorizer` after nb06 so
   nb07 loads it directly instead of refitting + label-aligning. Removes the
   `random_state` fragility and speeds nb07 by ~1 min.

### Extensions worth proposing to the PI

7. **Faculty-embedding UMAP.** Concatenate each PI's abstracts, encode with
   SPECTER2, project to 2-D. Would show which PIs cluster together and
   answer "who could Prof. X collaborate with?" — a natural extension of the
   grant-level UMAP.
8. **Topic × dollar-per-year trends.** We currently have topic × year in
   %-of-grants. Running the same chart in $ terms would reveal whether the
   biomed *dollar* share is falling (it isn't — the remaining grants are
   larger) or rising.
9. **Report-mode notebook.** Everything in nb06 and nb07 is exploratory.
   A final report deck would benefit from a stripped-down report notebook
   that reads only the exports (`topic_assignments.csv`, `subtopics.csv`,
   `college_profiles.csv`), applies the earned-at-NEU filter throughout, and
   produces publication-ready figures without any modeling. ~2 hours.

---

## 10. How to reproduce from scratch

```bash
# Build parquets from raw .xlsx (30 s)
python src/build_dataset.py

# One-time SPECTER2 encoding — ~5 min on CPU, ~500 MB model download
python src/build_specter2_embeddings.py

# Run the notebooks in order (each takes 1–3 min)
jupyter nbconvert --to notebook --execute --inplace notebooks/01_schema_overview.ipynb
jupyter nbconvert --to notebook --execute --inplace notebooks/06_research_topics.ipynb
jupyter nbconvert --to notebook --execute --inplace notebooks/07_topic_deep_dive.ipynb
```

Or run the whole pipeline non-interactively:

```bash
python -c "
import nbformat
from nbclient import NotebookClient
from pathlib import Path
for p in sorted(Path('notebooks').glob('0*.ipynb')):
    nb = nbformat.read(str(p), as_version=4)
    NotebookClient(nb, timeout=900, kernel_name='python3').execute()
    print(f'{p.name}: OK')
"
```

### Dependencies

```
pandas, numpy, matplotlib, seaborn
scikit-learn        # LDA, TF-IDF, CountVectorizer
scipy               # dendrogram, jensenshannon
umap-learn          # UMAP
plotly              # interactive projections
rapidfuzz           # agency fuzzy-matching (build_dataset only)

# SPECTER2 only:
transformers        # tokenizer, base model
adapters            # SPECTER2 proximity adapter
torch               # inference
```

Everything is CPU-friendly. No GPU needed.

---

## 11. Who to ask

- **Data pipeline / schema questions** → see [`src/README.md`](../src/README.md).
- **Attribution rules (`neu_status`, `is_pi`, credit models)** →
  [`src/README.md`](../src/README.md) and
  [`notebooks/04_who_gets_funded.ipynb`](../notebooks/04_who_gets_funded.ipynb) §6.
- **Non-topic analyses** (funding landscape, temporal, collaboration graph) →
  notebooks 02–05.
- **The report narrative** → [`docs/INSIGHTS.md`](INSIGHTS.md) (local-only,
  not published).
