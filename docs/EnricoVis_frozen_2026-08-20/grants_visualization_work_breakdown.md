# Grants Visualization Project — Work Breakdown & Handoff

*Reconstructed from a Claude working session. This summarizes goals, methods, decisions, outputs, results, and everything needed to reproduce or continue the work.*

---

## 1. Overview & Goals

The overarching goal was to build **interactive tools for exploring a corpus of research grants**, using text embeddings of grant titles/abstracts and topic modeling, expressed through several complementary visualizations.

The original request (verbatim intent) was to build an app that:

1. Cleans grant title/abstract text of boilerplate terms (e.g. `CAREER`, "intellectual merit").
2. Transforms the cleaned text into embeddings using the **SPECTER2** model (with the **proximity** adapter option).
3. Projects the embeddings to 2D with **UMAP**.
4. Renders an **interactive visualization** with:
   - a white-background UI,
   - points colored by **funding source**,
   - a toggle to **scale point size by grant dollar amount**.

Over the session this expanded into a small **suite of three visualizations** plus a reproducible offline pipeline, driven by a series of user decisions (documented in §4).

---

## 2. The Data

Two project files were the inputs:

### `grants.csv` — 2,676 grants, 23 columns
Key columns used: `grantname` (title), `abstract`, `totaldollars`, `agencycode`, `agencyname`, `startdate`/`startdateyear`, plus `funding_source`, `db_coverage`.

Critical data findings that shaped the whole project:

- **All 2,676 grants have a title; only 1,928 have an abstract.**
- **`funding_source` is empty for every row.** The real funding-source signal lives in **`agencycode`**. Full-corpus agency counts:
  NSF (1,686), NIH (546), NIH-SUB (105), Navy (87), NASA (49), Army (48), DOE (37), AFRO (31), then a long tail (HHS, NEH, NOAA, USDA, singletons).
- **`totaldollars` is highly skewed** (~$500 to ~$38.6M), so any size encoding needs a **sqrt (or log) transform** for perceptual fairness.
- **NIH abstract coverage collapses after ~2019** (a *data artifact*, not a real funding trend). NIH grant records continue through 2025, but abstracts disappear: e.g. 2019 had 18/28 with abstracts, 2020 had 1/25, and **2021–2025 had 0 abstracts across 133 NIH grants**. `db_coverage` is blank for all of them. NSF, by contrast, keeps near-full abstract coverage throughout. This is why an abstract-only map made NIH look like it flatlined.
- **Abstracts contained mangled HTML entities** (`andlt`, `andgt`, `andamp` — the escaped forms of `<`, `>`, `&` — ~2,100 occurrences each). These dominated topic models until scrubbed.

### `faculty_grants.csv` — 3,144 rows, 9 columns
`faculty_id`, `faculty_name`, `grant_id`, `is_pi`, `is_copi`, `source`, `hire_date`, `grant_startdate`, `neu_status`. *(This file was catalogued but not directly consumed by the visualizations in this session — it is available for future PI/co-PI/faculty-level extensions.)*

---

## 3. Architecture

A hard environment constraint dictated the architecture: **SPECTER2 and UMAP cannot run in the build container** (network egress disabled → HuggingFace 403; `torch`, `transformers`/`adapters`, and `umap-learn` unavailable and uninstallable there).

Because embedding + projection is always a **precompute step** (never run live in a browser), the design split cleanly into two layers:

- **Offline pipeline layer (runs on the user's machine):** does text cleaning → embedding → 2D projection → topic modeling, and writes JSON artifacts.
- **Interactive app layer (self-contained HTML, works today):** loads the JSON and renders the visualizations. Uses D3 from CDN + canvas rendering for performance on ~2.7k points. White UI throughout.

To make the apps functional immediately, a **sklearn-based "preview" projection** was generated offline in-container (TF-IDF → TruncatedSVD → t-SNE — all available and verified). **The JSON schema is identical to the real pipeline's output**, so swapping in real SPECTER2+UMAP coordinates later requires *overwriting one file, no code changes*. Preview coordinates are clearly labeled in the UI so they aren't mistaken for the final semantic map.

> **Important fidelity caveat:** The preview (TF-IDF/t-SNE) keys on **lexical overlap**, so its clusters reflect shared vocabulary. SPECTER2 keys on **citation-informed semantics**, so the real map will regroup meaningfully. Treat the current layouts as a working harness for interaction design, **not** as final semantic structure.

---

## 4. Decisions Log (chronological)

These user decisions define the current state of the project:

| # | Decision | Effect |
|---|----------|--------|
| 1 | Build the sklearn preview now | Apps work end-to-end today; real pipeline swaps in later |
| 2 | **Do not** fold NIH sub-awards into NIH | `NIH-SUB` kept as its own category |
| 3 | Group small funding sources into an "Other" category | Palette stays legible |
| 4 | *(initially)* Drop grants without an abstract | Later reversed (see #6) |
| 5 | Keep aspect ratio fixed on resize | Uniform px-per-data-unit scaling |
| 6 | **Reverse #4** — include title-only grants (no separate phrase embedder) | All 2,676 grants included (748 title-only); NIH restored through 2025 |
| 7 | Do **not** color by topic; instead a topic **list** with hover-to-highlight (gray out the rest), **weighted** by p(topic\|doc) | Color channel stays reserved for funding source |
| 8 | Run a K-scan to choose the number of LDA topics | K=12 selected |
| 9 | Name topics in the list; show keywords on demand | Auto-named topics + toggleable keyword display |
| 10 | Remove the "Find" search box; make funding legend scrollable | More room for the topics list |
| 11 | Build a circle-packing view grouped by topic | `topic_islands.html` |
| 12 | Build a **hierarchical** topic model → nested-hull view | `topic_hierarchy.html` (see §7) |

Hierarchy-specific decisions (turn 12): hierarchy built **on flat LDA** (not native nested-CRP hLDA); **top-down / divisive**; **two levels**; **leaf K = 25**; **6–8 parents** (8 chosen); **not agglomerative**; **one leaf per grant** (hard assignment); **drives layout as nested hulls**.

---

## 5. Methods

### 5.1 Text cleaning (`clean_text.py` — shared by all paths)
Conservative removal so scientific content stays intact:

- **Program/mechanism prefixes** stripped (often stacked): `CAREER:`, `Collaborative Research:`, `RAPID:`, `EAGER`, `CRII`, `REU`, `RUI`, `SBIR`, `STTR`, `Conference:/Workshop:/Travel:/Symposium:`.
- **Leading NSF grant-ID / PI-name stub** removed from abstracts that begin with it.
- **NSF boilerplate** removed: "Intellectual Merit", "Broader Impacts", statutory-mission language (present in ~808 abstracts).
- **Mangled HTML markup scrubbed** (`andlt`/`andgt`/`andamp` and residual tags) — this was essential; before scrubbing it dominated every topic.
- **Document construction:** `cleaned title + [SEP] + cleaned abstract`; for title-only grants, the bare cleaned title is the document (empty abstract slot).

The removal list lives at the top of `clean_text.py` and is meant to be extended as new mechanism terms are spotted on the map.

### 5.2 Embedding
- **Preview (in-container):** TF-IDF → `TruncatedSVD` → **t-SNE** (2D).
- **Real (user machine, `pipeline.py`):** `allenai/specter2_base` + the **proximity adapter** loaded via the `adapters` library (the officially recommended proximity setup) → **UMAP** (2D).
- Both write the identical JSON schema, so the app's header flips from "t-SNE preview" to "SPECTER2 + UMAP" automatically.

**JSON record schema (per grant):**
`{ id, x, y, title, agency, agencyLabel, amount, year, hasAbstract }` plus topic weights / hierarchy assignments added by the topic steps.

### 5.3 Flat topic model (LDA, K=12)
- **K selection scan** (`scan_k.py`) over **K ∈ {8, 10, 12, 15, 20}** using: **UMass coherence** (intrinsic/corpus-based, since gensim/`C_v` unavailable offline), **topic diversity** (fraction of unique top-N terms), **topic-size distribution** (reject a giant catch-all + tiny litter), and **seed stability** across 3–5 runs. Perplexity deliberately **not** used for K (it anti-correlates with interpretability — the "reading tea leaves" result).
- **Result: K = 12.** Coherence −1.612, diversity 0.87, balanced sizes (largest topic 16%, no catch-all). K=12 makes the meaningful split K=10 misses (separating *Machine Learning & Algorithms* from *Computing Systems & Security*); K≥15 fragments (two materials topics, split health) with worse coherence/stability.
- Note on why K could go higher than a color palette allows: because topic is expressed via **highlighting, not color**, K is no longer constrained by a ~10–12 hue "color budget."

**The 12 flat topics** (auto-named by anchor terms; rules in `topics.py`):
Computing Systems & Security · Cell & Cancer Biology · STEM Education & Participation · Health & Behavioral Science · Energy/Power & Wireless · Machine Learning & Algorithms · Molecular & Structural Biology · Mathematics & Quantum Theory · Ocean/Climate & Environment · Mechanics/Structures & Control · Conferences & Workshops · Materials & Condensed Matter.

### 5.4 Hierarchical topic model (top-down, `hier.py`)
- **Level 1:** an **8-topic LDA** produces the parents (scanned P ∈ {6,7,8}; P=8 gave best coherence −1.577 and cleanest taxonomy). Each grant's parent = its dominant level-1 topic.
- **Level 2:** each parent's own documents are re-fit with a **second per-parent LDA**, with children allocated **proportional to parent size, min 2 each**, summing to exactly **25 leaves** → allocation **4/4/3/3/3/3/3/2**.
- **One hard path per grant** (dominant sub-topic within its dominant parent).
- Parents get distinct hues; children are **lightness variants** of the parent hue.

---

## 6. Outputs Produced

### Offline scripts (run on the user's machine)
| File | Purpose |
|------|---------|
| `clean_text.py` | Shared text cleaner (removal lists at top) — guarantees byte-identical text across preview & real paths |
| `build_preview.py` | In-container sklearn preview generator (TF-IDF → SVD → t-SNE) + LDA weights |
| `pipeline.py` | **Real** SPECTER2 (proximity adapter) + UMAP run; also emits flat topics + hierarchy. Writes identical schema |
| `scan_k.py` | K-scan diagnostics for flat LDA (coherence, diversity, size, stability) |
| `topics.py` | Flat LDA (K=12) fit + deterministic topic-naming rules |
| `hier.py` | Top-down hierarchy fit (8 parents → 25 leaves) + proportional allocation + parent/leaf naming |
| `build_hier.py` | Offline build of the hierarchy JSON |

### JSON data artifacts
| File | Contents |
|------|----------|
| `grants_umap.json` | Per-grant coordinates + metadata + flat-topic weights |
| `topics.json` | Flat 12-topic metadata (names, top terms, sizes) |
| `grants_hier.json` | Per-grant parent/leaf assignments for the hierarchy |
| `hier_topics.json` | Hierarchy tree metadata (parents, children, names, sizes) |

### Interactive apps (self-contained HTML)
| File | What it is |
|------|-----------|
| `grant_atlas.html` | **The main atlas.** 2D embedding scatter; the primary deliverable |
| `topic_islands.html` | **Circle-packing view** — grants packed into per-topic clusters with organic hull outlines |
| `topic_hierarchy.html` | **Nested-hull view** — parent hulls enclosing leaf hulls, driven by the hierarchy |

---

## 7. The Three Visualizations (feature detail)

### 7.1 `grant_atlas.html` — the atlas
- White UI; ~1,928→2,676 points rendered on canvas; D3 from CDN; embedding coordinates inlined in the file.
- **Color = funding source** (colorblind-aware, **red-free** qualitative palette).
- **Legend-as-filter:** clicking a funding-source row shows/hides that source. Legend is **scrollable/capped** (~5 rows) to save vertical space.
- **Size-by-amount toggle:** sqrt-scales point radius by `totaldollars` and reveals a size key; uniform dots when off.
- **Hover tooltip:** title, agency, year, amount, dominant topic, and a **"title only"** tag for the 748 abstract-less grants.
- **Zoom / pan** (scroll-zoom, drag-pan, reset).
- **Fixed aspect ratio on resize:** single px-per-data-unit factor `s = min(availW/dataW, availH/dataH)` applied to both axes, map centered — distances stay faithful under resize and zoom.
- **Collapsible control dock:** folds off the left edge via a "Controls" bar; a small opener button restores it. Focus management + Escape-to-fold; respects reduced-motion; mobile-friendly.
- **Year filter:** a **dual-thumb range slider** (data spans 1995–2026) where the **band between thumbs is itself draggable** (slide a fixed-width window across the timeline). Arrow keys nudge a focused handle. Out-of-range grants are **grayed out, not removed** (drawn faintly beneath in-range points) to preserve density context. Composes with legend + topic filters.
- **Topics list (not colored):** all 12 topics, sorted by prevalence with a size bar per row. **Hover = transient highlight; click = pin.** Highlighting is **weighted** — each dot's opacity scales with its relative `p(topic|doc)`, showing a topic's dense core and faint penumbra; everything else grays. A **keywords toggle** reveals each topic's top terms on demand. Composes with year + funding filters (a dot stays lit only if it's a topic member AND in the year window AND in an active source).
- The **Find/search box was removed** to reclaim space for topics.

### 7.2 `topic_islands.html` — circle packing
- Each grant is a circle, packed tightly into its **dominant-topic** cluster via d3 `packSiblings`.
- The 12 clusters are **placed by their average embedding position** (so topics adjacent in the atlas sit adjacent here), with a light force resolving island collisions.
- **Encapsulation via outlines:** perimeter points of each cluster's circles → convex hull → closed **Catmull-Rom** curve, giving an organic topic-colored boundary with faint fill + label.
- Interactions mirror the atlas (hover/pin topic; hover circle for details).
- Two toggles: **size by amount** (re-packs with sqrt radii) and **color by funding source** (recolors circles to the atlas palette while keeping topic hulls/placement — a cross-tab of topic region × funder).

### 7.3 `topic_hierarchy.html` — nested hulls
- Grants pack into their **leaf**, leaves pack **within their parent**, parents placed by average embedding centroid.
- Each leaf gets a thin dashed hull; each parent a bold enclosing hull. Parent hue + child lightness variants → read family by color, sub-topic by position.
- **Collapsible parent→child tree panel;** hover highlights/fades, click pins; leaf labels appear on parent focus or zoom-in.
- Size-by-amount and color-by-funding toggles as in the islands view.

---

## 8. Results

### Funding-source categorization (final, full corpus incl. title-only)
Eight named sources + Other (threshold `NAMED_MIN = 30`, a single constant):
NSF (1,686), NIH (546), **NIH-SUB (105, kept separate per decision #2)**, Navy (87), NASA (49), Army (48), DOE (37), AFRO (31), **Other (87** = HHS, NEH, NOAA, USDA, singletons**)**.

> NEH (19 grants) falls into "Other" at the current threshold. Lower `NAMED_MIN` to ~19 to give humanities its own hue.

### Flat topics
K=12, listed in §5.3. Coherence −1.612, diversity 0.87, balanced sizes.

### Hierarchy (8 parents → 25 leaves)
| Parent | Size | Example children |
|--------|------|------------------|
| Computing & Systems | 618 | Security / Networks / Software / Systems-Learning |
| Cell & Cancer Biology | 489 | Cancer / Cells / DNA-Proteins / Drug-Compounds |
| Health & Society | 424 | — |
| Engineering Education & Convening | 299 | — |
| Energy, Devices & Wireless | 292 | — |
| Ocean, Climate & Environment | 227 | — |
| Physics & Complex Systems | 188 | — |
| Materials & Quantum Matter | 139 | — |

### The NIH "cliff" resolution
Confirmed as a **data artifact** (missing abstracts), not a funding decline. Fixed by including title-only grants (decision #6), restoring NIH continuity 1995–2025.

---

## 9. How to Reproduce / Run the Real Pipeline

1. **Environment (on your own machine, with network access):**
   ```bash
   pip install torch transformers adapters umap-learn scikit-learn numpy pandas
   ```
   `adapters` is required for the SPECTER2 **proximity** adapter (`allenai/specter2_base` + proximity adapter).

2. **Keep the four inputs together:** `clean_text.py`, `topics.py`, `hier.py`, `pipeline.py` (plus `grants.csv`). `pipeline.py` imports `clean_text.py` so the text is byte-identical to the preview.

3. **Run the pipeline:**
   ```bash
   python pipeline.py
   ```
   This produces `grants_umap.json`, `topics.json`, `grants_hier.json`, `hier_topics.json` with the **same schema** the apps already expect.

4. **Swap into the apps:** drop the regenerated JSON next to the HTML files (or re-inline as the current builds do). No app code changes needed — the atlas header auto-flips to "SPECTER2 + UMAP," and the island/hierarchy placement updates to the real embedding automatically (packing itself is projection-independent; only placement shifts).

5. **(Optional) Re-choose K:** `python scan_k.py` prints coherence/diversity/size/stability and top terms per K. Validate visually: pin a topic in the atlas and check whether its members **pool into a contiguous region** — a viz-native check that flat coherence numbers can't give.

**Tunable constants worth knowing:**
- `NAMED_MIN = 30` (funding-source naming threshold; lower to ~19 to surface NEH).
- Removal lists at the top of `clean_text.py` (extend as you spot mechanism terms).
- `topics.py` / `hier.py` naming rules (so labels survive refits).

---

## 10. Known Caveats & Follow-up Items

- **Preview ≠ final semantics.** Current coordinates are TF-IDF→t-SNE (lexical). Expect regrouping under real SPECTER2+UMAP. Anything you conclude about *cluster meaning* should wait for the real run.
- **748 title-only grants** carry weak signal; they smear toward generic topics (Computing Systems, STEM Education) and their positions will shift most under the real embedding. They're tagged "title only" in tooltips.
- **Hard topic assignment in the packing/hierarchy views:** a grant straddling two topics lands wholly in its dominant one; the soft `p(topic|doc)` weights still exist in the data if you later want graded membership in those views too (the atlas already uses them for weighted highlighting).
- **`faculty_grants.csv` is untapped** — a natural next extension (PI/co-PI overlays, faculty-level filtering, college/department grouping using `neu_status`, `hire_date`, `is_pi`/`is_copi`).
- **Container limitation is not a soft one** — never attempt SPECTER2/UMAP in the sandbox; always precompute externally.
- The transcript mentions a one-time cleanup of **stale/mismatched files** from a parallel write; if reusing the code, verify `pipeline.py` matches the current `hier.py` API and that no leftover duplicate hierarchy files remain.

---

## 11. File Inventory (quick reference)

**Scripts:** `clean_text.py`, `build_preview.py`, `pipeline.py`, `scan_k.py`, `topics.py`, `hier.py`, `build_hier.py`
**Data:** `grants_umap.json`, `topics.json`, `grants_hier.json`, `hier_topics.json`
**Apps:** `grant_atlas.html`, `topic_islands.html`, `topic_hierarchy.html`
**Inputs:** `grants.csv`, `faculty_grants.csv`

---

*End of work breakdown.*
