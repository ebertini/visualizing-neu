# Topic Model Refit Checklist

The runbook for redoing the topic model and getting `docs/TopicVizPrototypes/`
(and `docs/EnricoVis/`) to reflect it. Read this once before starting — it
tells you exactly which commands to run, exactly which files constitute "the
topic model" if you'd rather drop in new artifacts than rerun from scratch,
and exactly what still needs a human afterward.

**As of 2026-08-29 there are TWO independent tracks**, not one — read this
paragraph before picking a section below:

- **Track A — the REFIT track** (§1A): re-running BERTopic/SPECTER2 itself
  (heavy deps, local-only, HuggingFace network for the embedding step). This
  is the *original* content of this checklist and is unchanged in substance.
- **Track B — the RE-CURATE/RE-SCORE track** (§1B): re-running the curated
  keyword taxonomy (`outputs/topic_keywords.json`) and/or the deterministic
  BM25F classifier (`src/classify_by_keywords.py`) that now produces the
  **canonical** topic labels this pipeline publishes. Light deps only, fully
  offline, no HuggingFace network, typically seconds to low minutes.

**Track B's classifier output is canonical; BERTopic's own assignment is kept
only as a comparison column** (`bertopicDom`/`bertopicNoise` on every point,
`agrees_with_bertopic` in `data/processed/topic_keyword_assignments.parquet`).
A pure Track A refit (no re-curation) still matters — it changes the
`bertopicDom` comparison column and the SPECTER2/UMAP coordinates every point
is plotted at — but it does **not**, by itself, change which leaf/parent a
grant is labeled with anymore. Changing labels requires Track B.

This is a companion to [`TOPIC_WORK_FORWARD_PLAN.md`](TOPIC_WORK_FORWARD_PLAN.md)
/ [`TOPIC_WORK_EXECUTION_REPORT.md`](TOPIC_WORK_EXECUTION_REPORT.md) (what M1–M4
built) — this doc is specifically about *doing it again*.

---

## 1A. The REFIT track — full command sequence

```bash
python -m src.build_dataset               # raw .xlsx -> canonical parquets (~30s, light deps)
python -m src.reconcile_orphans           # recover orphan abstracts + abstract_source (light deps)
python -m src.build_specter2_embeddings   # SPECTER2 cache — HEAVY deps, HF network, ~5-8 min CPU
python -m src.topics_bertopic             # fit BERTopic — HEAVY deps, local-only
                                           #   -> data/processed/bertopic_model/
                                           #   -> data/processed/topic_assignments.parquet
                                           #   -> data/processed/specter2_umap_2d.npy
                                           #   -> outputs/bertopic_diagnostics.json
                                           #   -> outputs/topic_labels.json (SEED, only if absent —
                                           #      see the note in §1B: this file is now normally
                                           #      OWNED by Track B, not by this seed step)

# --- Track B (below) is where labels actually come from now. A refit alone
# only updates topic_assignments.parquet (the bertopicDom/bertopicNoise
# comparison column) and the SPECTER2/UMAP coordinates. ---

python -m src.refresh_topicviz            # classify_by_keywords --check-only (if a curated
                                           # taxonomy exists) + build_viz_data (if stale) +
                                           # build_viz_aggregates + _check_topicviz --data-only —
                                           # LIGHT deps only, ~seconds to ~30s
```

**Heavy deps** (`requirements.txt`: torch, transformers, adapters, sentence-transformers,
bertopic, umap-learn, hdbscan) are only needed for the two `HEAVY` steps above.
**Light deps** (`requirements-viz.txt`: pandas, pyarrow, rapidfuzz) cover everything
else, including the entire `refresh_topicviz` step — see `CLAUDE.md`'s Setup section
for the `uv venv` incantation (bare `python3.11 -m venv` fails on this machine).

`refresh_topicviz` re-runs `build_viz_data` if ANY of
`{data/processed/topic_keyword_assignments.parquet, data/processed/topic_assignments.parquet,
outputs/topic_keywords.json, outputs/topic_labels.json}` is newer than
`docs/EnricoVis/data/topics.json` (an mtime check over all four, not just one) — it
prints which input triggered the rebuild. Verify the result with:

```bash
python scripts/_check_topicviz.py          # data wiring + parent/palette/caveat consistency
                                            # + JS/HTML structural checks
```

The three prototype pages `fetch()` their JSON from `data/` as ES modules, so they
need an HTTP origin — they will **not** load over `file://`. Serve the directory to
actually look at them:

```bash
python -m http.server 8000 --directory docs/TopicVizPrototypes
# http://localhost:8000/{what_we_can_see,topic_flow,about}.html
```

---

## 1B. The RE-CURATE/RE-SCORE track — full command sequence

This is the track that actually changes which leaf/parent a grant is labeled
with. See `docs/TOPIC_CLASSIFICATION_BRAINSTORM.md` and `/Users/uttkarshnarayan/.claude/plans/mossy-popping-pony.md`
(outside this repo) for the full design; this section is only the mechanical
runbook.

```bash
# --- only if re-curating the taxonomy itself (leaves/parents/keyword lists) ---
cp outputs/keyword_topics.draft.json outputs/topic_keywords.json   # or start from
                                                                    # keyword_topics.suggested.json
$EDITOR outputs/topic_keywords.json          # hand curation — see src/kw_review_sheet.py's
                                              # generated outputs/KEYWORD_REVIEW.md
python3 -m src.kw_curation --check           # exit 1 until genuinely curated (0 errors required)

# --- promote the curated taxonomy into the pipeline ---
python3 -m src.classify_by_keywords --write-topic-labels
                                              # writes data/processed/topic_keyword_assignments.parquet
                                              # AND outputs/topic_labels.json (the schema build_viz_data.py
                                              # reads) in one command — this IS the "new topic model" swap
                                              # for this track (compare to Track A's 4-file table in §2A)

python -m src.refresh_topicviz               # same command as Track A — it re-detects the
                                              # new topic_keywords.json/topic_labels.json mtimes
                                              # and rebuilds everything downstream
python scripts/_check_topicviz.py            # same verification command as Track A
```

**If you only want to re-run scoring** (no taxonomy changes — e.g. after a
corpus refresh that doesn't touch curation), skip the `kw_curation`/`$EDITOR`
steps and just re-run `classify_by_keywords --write-topic-labels` + `refresh_topicviz`.

**`outputs/topic_labels.json` changed ownership.** It used to be seeded once by
`topics_bertopic.py` (Track A) and then hand-curated in place. It is now
**mechanically regenerated** by `classify_by_keywords --write-topic-labels`
from `outputs/topic_keywords.json` — do not hand-edit `topic_labels.json`
directly anymore; edit `topic_keywords.json` (the real curated source) and
re-run the write command. `topics_bertopic.py`'s own seeding behavior (write
only if absent) is unchanged and still relevant for a **BERTopic-only**
environment that hasn't adopted Track B at all.

---

## 2A. Track A: what "swap out the data" means, precisely

If you'd rather drop in artifacts from elsewhere than rerun the pipeline locally,
these four files are the exact, complete definition of "a new BERTopic fit":

| File | What it is |
|---|---|
| `data/processed/bertopic_model/` | the fitted BERTopic model (`BERTopic.save`, pickle) |
| `data/processed/topic_assignments.parquet` | `doc_id, topic_id, is_noise, is_extra` — every doc's BERTopic assignment (comparison column only — see the intro above) |
| `data/processed/specter2_umap_2d.npy` | the 2-D projection used for the scatterplot views |
| `outputs/topic_labels.json` | **only relevant here in a BERTopic-only environment** — see §1B, this file is normally owned by Track B now |

Drop in new versions of all three/four (matching doc-id order/count with
`data/processed/specter2_ids.txt`), then run `python -m src.refresh_topicviz`.

## 2B. Track B: what "swap out the data" means, precisely

| File | What it is |
|---|---|
| `outputs/topic_keywords.json` | the curated taxonomy (leaves, parents, keyword lists, weights, `df_corpus`) — committed, the real source of truth |
| `data/processed/topic_keyword_assignments.parquet` | `doc_id, kw_leaf_id, kw_parent_id, score1, score2, conf_tier, unassigned_reason, matched_terms, ...` — every doc's canonical assignment |
| `outputs/topic_labels.json` | mechanically derived from `topic_keywords.json` via `--write-topic-labels` — don't hand-edit |

Both are produced together by one command (`classify_by_keywords --write-topic-labels`),
so there's no multi-file drop-in step the way Track A has — just re-run it.

---

## 3. What still needs a human, and why it's not automated

### Track A (BERTopic refit)

- **`ARTIFACT_TOPIC_ID` in `src/build_viz_aggregates.py` is now `None` (retired), not a BERTopic topic id.**
  Under Track B (canonical), there is no single "flagged low-coherence cluster" —
  every leaf is a deliberate human curation decision, and the 28 ONR
  placeholder-title "Grant" records that used to define this bucket are now
  tracked per-point via `unassignedReason == "placeholder_title_only"`
  instead of one hardcoded topic id. **This constant only has meaning again
  in a BERTopic-only environment that has never adopted Track B** — if you
  are in that situation, set it back to a real topic id (`validate()` warns
  if it no longer points at a real, unparented topic) rather than leaving it
  `None`. (Historical note, corrected here: this section previously said the
  value was "currently 11" — the code's actual value before this rewrite was
  `14`, re-identified after the 2026-08-20 backfill; both are now moot under
  Track B.)

### Track B (re-curate/re-score)

- **Curation itself** (`outputs/topic_keywords.json`'s leaves/parents/keyword
  lists) is real analytical judgment — `src/kw_curation.py --check` only
  validates structural well-formedness (dense ids, non-empty notes, no
  phantom `df_corpus==0` terms, bidirectional leaf↔parent references), never
  curation *quality*. See `docs/TOPIC_CLASSIFICATION_BRAINSTORM.md`.
- **BM25F constants (`K1`, `B`, `ALPHA`, `W_TITLE`) and the `conf_tier`
  thresholds — CALIBRATION DONE (2026-08-30), keep the literature defaults.**
  The 180-row gold set (`data/gold/topic_gold_set.csv`) is now fully labeled.
  A bounded sweep (`src/tune_bm25f.py`, match-once/rescore-many over 108
  configurations, guarded against overfitting an n=180 set) found NONE beat
  baseline gold accuracy by more than its own 95% CI half-width — the
  constants stay exactly as written. The title-only-normalization check's
  earlier failure (title-only docs scoring a *higher* mean margin) turned out
  to be caused almost entirely by 65 unassigned title-only grants (a
  curation-coverage gap, not a `W_TITLE` over-boost) plus a structural
  `HIGH_MIN_TERMS=3` term-count gate title-only docs can rarely clear — a
  curation pass (not a constants change) closed most of the coverage gap and
  brought the gap from 12.1pp to 1.0pp. See CLAUDE.md's "Title-only
  calibration — RESOLVED" entry for the full account, including why no
  constant value could have fixed this on its own.

### Shared (both tracks)

- **`PARENT_NAMES` / `PARENT_COLORS` in `src/build_viz_aggregates.py`**, and their
  manually-synced copy in `docs/TopicVizPrototypes/shared/enrico.js` (these two
  must stay value-identical — `scripts/_check_topicviz.py`'s
  `check_parent_taxonomy()` now asserts this mechanically on every run, and
  `tests/test_viz_schema.py` re-asserts it under plain `pytest`; no more "a
  plain diff is the fastest way to check") — these are a deliberate,
  hand-maintained palette, not derived from the model. `build_viz_aggregates.py`'s
  `validate()` prints a loud warning if the topic model's actual parent count
  disagrees with `len(PARENT_NAMES)`.
  Nothing crashes either way — an unaccounted-for parent theme falls back to
  the "Unassigned" bucket / a repeated color until you update these.

  **SUPERSEDED (2026-08-29, same day, later in the session) — `PARENT_NAMES`
  is 8 entries, not 7.** The paragraph immediately below this note originally
  described a 7-parent state (the initial Track B promotion, which merged
  workforce/career-pipeline content into one combined social-science parent).
  A same-day follow-up review found that combined parent's largest leaf by
  both count and dollars was actually career-pipeline/institutional content,
  not social science — so it was split into a redefined P3 ("Social Science,
  Public Policy & Education Research") plus a new P7 ("Workforce Development
  & Institutional Partnerships"), landing back at 8 parents (a coincidental
  same count as the retired BERTopic-era 8, entirely different parents — see
  CLAUDE.md's "Parent-theme count is now 8" entry for the full account). The
  historical 7-parent paragraph is left below for the record of what Track B
  actually did in sequence, not as current state:

  **As of the 2026-08-29 Track B promotion's FIRST pass, `PARENT_NAMES` was
  briefly 7 entries**
  (`Biomedical Sciences`, `Public & Behavioral Health`, `Environmental Science
  & Ecology`, `Social Science, Public Policy & Workforce Development`,
  `Materials Science & Structural/Civil Engineering`, `Mathematics &
  Fundamental Physics`, `Computing, Networking & Robotic Systems`) — down
  from the prior 8-parent BERTopic-era set (`Life Sciences & Biomedicine`,
  ... `Education & Learning`), which is retired, not kept as unused history.
  **`PARENT_COLORS` stays at 12 entries** (8 real + 4 spare, after the
  follow-up split above) — the array itself never needed to shrink, only
  `PARENT_NAMES`'s content did.
  `docs/EnricoVis/topic_hierarchy.html` (the PI's own file) was deliberately
  **not** touched — it still shows the old 8-parent BERTopic palette/labels,
  since (see the correction already elsewhere in `CLAUDE.md`) his apps don't
  fetch this project's JSON at all and are unaffected either way.

  **`docs/TopicVizPrototypes/what_we_can_see/constants.js`'s `TP_COLORS`**
  (a *third*, independent 12-entry hardcoded copy, used only by the "Every
  grant"/"Every PI" facet grids' small-mark color scale, not the same list as
  `PARENT_COLORS` above) is unaffected either way (already safely
  modulo-indexed, still has spare headroom). **`PARENT_SHORT`** in the same
  file was updated for the current 8 names (keys `0`-`7`) — this one isn't
  buffered the way colors are (abbreviations are curated text, can't be
  pre-invented), so it needed a real edit, already done.

- **The `CAVEATS` prose in `src/build_viz_aggregates.py`** (rendered in full,
  grouped by severity, on `what_we_can_see.html`'s "About this data & what's
  missing" tab — `about.html` merged into it 2026-08-30, see CLAUDE.md — and
  as filtered subsets on `topic_flow.html`/that same tab's coverage section
  via a per-page id whitelist). Sentences are hand-written, not computed —
  `validate()`'s checks don't verify they still describe the data correctly
  (only that `by_reason` sums correctly, etc. — the *numbers cited in prose*
  are not cross-checked against real numbers by any assert). Re-read and
  update this list by hand after either track changes what it describes.
  As of 2026-08-29 (Track B promotion): `"unassigned"` was rewritten with the
  real current numbers (100 grants / 3.7% of grants / $53.7M / 2.5% of
  dollars — down from BERTopic's 697 grants / 26.7% of dollars; this doc
  previously and incorrectly cited "808 grants (27.8%)" here, which never
  matched the actually-committed `viz_meta.json` either); `"t14_artifact"`
  was renamed `"placeholder_titles"` (same underlying 28 ONR records, no
  longer framed as an HDBSCAN artifact); two new caveats were added,
  `"keyword_classifier"` (states the method change plainly) and
  `"low_confidence"` (712 grants / 26.6% in the `low` confidence tier, with
  the thresholds' calibration status noted).
  **The caveat-id whitelists** in `topic_flow.html`'s and
  `what_we_can_see/missing.js`'s `renderCaveats(...)` calls are now
  mechanically cross-checked against `CAVEATS` by both
  `scripts/_check_topicviz.py` and `tests/test_viz_schema.py` — a renamed or
  removed id that isn't updated in both places now **fails loudly** instead
  of silently dropping the caveat, closing the gap this checklist used to
  just warn about manually.

- **Leaf topic count is fully safe everywhere** (unchanged conclusion from
  before this rewrite) — `enrico.js`'s `topicColor()`, `facets.js`'s `tid`
  facet, `topic_flow.html`'s small-multiples loop (now also its heading text,
  made data-driven off `VIZ_META.frozen_inputs.n_topics` as of 2026-08-29 —
  previously hardcoded "The 32 leaf topics" and now correctly reads "The 31
  leaf topics"), `build_viz_data.py`'s `n_topics`-derived sizing, and the
  PI's own `topic_islands.html` all either derive the count dynamically or
  wrap their color index with `% length`. `enrico.js`'s `TOPIC_COLORS` has 32
  entries — the current 31 curated leaves fit with exactly 1 spare; a 32nd+
  leaf in a future re-curation would need this array extended (checked
  automatically now — see `check_parent_taxonomy()`/`test_topic_colors_capacity_covers_leaf_count`
  above, which fail loudly rather than silently repeating colors).

---

## 4. Sanity-check the result

1. `python -m src.build_viz_aggregates --check-only` — read the printed report.
   Every ⚠ line names something from §3 above that needs your attention; every
   other line is informational (the numbers are *expected* to move after either
   track) except the internal-reconciliation asserts (including the newer
   `by_reason` / `parent_id == parent_of(leaf_id)` / palette-capacity checks),
   which fail loudly (not silently wrong) if something is actually broken.
2. `python scripts/_check_topicviz.py` — confirms every dataset the three pages
   `fetch()` exists in `data/` and parses, that `PARENT_NAMES`/`PARENT_COLORS`
   stay value-identical between `build_viz_aggregates.py` and `enrico.js`,
   that every caveat-id whitelist entry exists in `CAVEATS`, and that the
   aggregator emits nothing no page reads.
3. `python -m pytest tests/test_viz_schema.py` — the same three checks as #2,
   re-asserted as plain pytest so a bare `pytest -q` run catches a regression
   without a separate script invocation.
4. Serve the directory and open all three pages — they `fetch()` their data as
   ES modules and will **not** load over `file://`:
   ```bash
   python -m http.server 8000 --directory docs/TopicVizPrototypes
   # http://localhost:8000/{what_we_can_see,topic_flow,about}.html
   ```
   Eyeball them with DevTools open — the automated checks catch structural
   drift, not "does this still read sensibly," and only the Network tab will
   tell you a dataset 404'd. **No browser is available in this working
   environment as of 2026-08-29** — this step is still outstanding for the
   Track B promotion described throughout this rewrite; say so plainly rather
   than implying it happened.
