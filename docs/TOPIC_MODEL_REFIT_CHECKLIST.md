# Topic Model Refit Checklist

The runbook for redoing the BERTopic fit and getting `docs/TopicVizPrototypes/`
(and `docs/EnricoVis/`) to reflect it. Read this once before starting a refit —
it tells you exactly which commands to run, exactly which files constitute
"the topic model" if you'd rather drop in new artifacts than rerun from
scratch, and exactly what still needs a human afterward.

This is a companion to [`TOPIC_WORK_FORWARD_PLAN.md`](TOPIC_WORK_FORWARD_PLAN.md)
/ [`TOPIC_WORK_EXECUTION_REPORT.md`](TOPIC_WORK_EXECUTION_REPORT.md) (what M1–M4
built) — this doc is specifically about *doing it again*.

---

## 1. The full command sequence

```bash
python -m src.build_dataset               # raw .xlsx -> canonical parquets (~30s, light deps)
python -m src.reconcile_orphans           # recover orphan abstracts + abstract_source (light deps)
python -m src.build_specter2_embeddings   # SPECTER2 cache — HEAVY deps, HF network, ~5-8 min CPU
python -m src.topics_bertopic             # fit BERTopic — HEAVY deps, local-only
                                           #   -> data/processed/bertopic_model/
                                           #   -> data/processed/topic_assignments.parquet
                                           #   -> data/processed/specter2_umap_2d.npy
                                           #   -> outputs/bertopic_diagnostics.json
                                           #   -> outputs/topic_labels.json (SEED, only if absent)

# --- optional, human, in between: curate outputs/topic_labels.json ---
# (parent-theme grouping + nicer labels — see §3 below. Skip this and the
# rest of the pipeline still works; you just get c-TF-IDF labels and no
# parent groupings until you come back to it.)

python -m src.refresh_topicviz            # build_viz_data (if stale) + build_viz_aggregates
                                           # + _check_topicviz --data-only, in one command —
                                           # LIGHT deps only, ~seconds
```

**Heavy deps** (`requirements.txt`: torch, transformers, adapters, sentence-transformers,
bertopic, umap-learn, hdbscan) are only needed for the two `HEAVY` steps above.
**Light deps** (`requirements-viz.txt`: pandas, pyarrow, rapidfuzz) cover everything
else, including the entire `refresh_topicviz` step — see `CLAUDE.md`'s Setup section
for the `uv venv` incantation (bare `python3.11 -m venv` fails on this machine).

`refresh_topicviz` only re-runs `build_viz_data` if `data/processed/topic_assignments.parquet`
is newer than `docs/EnricoVis/data/topics.json` (an mtime check) — it prints which
branch it took. Verify the result with:

```bash
python scripts/_check_topicviz.py          # data wiring + JS/HTML structural checks
```

The three prototype pages `fetch()` their JSON from `data/` as ES modules, so they
need an HTTP origin — they will **not** load over `file://`. Serve the directory to
actually look at them:

```bash
python -m http.server 8000 --directory docs/TopicVizPrototypes
# http://localhost:8000/{what_we_can_see,topic_flow,about}.html
```

---

## 2. What "swap out the data" means, precisely

If you'd rather drop in artifacts from elsewhere than rerun the pipeline locally,
these four files are the exact, complete definition of "a new topic model":

| File | What it is |
|---|---|
| `data/processed/bertopic_model/` | the fitted BERTopic model (`BERTopic.save`, pickle) |
| `data/processed/topic_assignments.parquet` | `doc_id, topic_id, is_noise, is_extra` — every doc's assignment |
| `data/processed/specter2_umap_2d.npy` | the 2-D projection used for the scatterplot views |
| `outputs/topic_labels.json` | topic labels + parent-theme grouping (committed — see §3) |

Drop in new versions of all four (matching doc-id order/count with
`data/processed/specter2_ids.txt`), then run `python -m src.refresh_topicviz`.
Nothing else needs to change by hand for the build to succeed — see §4 for what's
still worth a human glance afterward, as distinct from what's required.

---

## 3. What still needs a human, and why it's not automated

- **Parent-theme grouping and nicer labels in `outputs/topic_labels.json`.**
  `topics_bertopic.py` seeds this file automatically (every topic's label defaults
  to its c-TF-IDF top-3 terms, `parent: null`) so the pipeline is never *blocked*
  on curation — but grouping ~25 topics into a handful of coherent parent themes,
  and writing labels a reader will actually recognize, is real analytical
  judgment, not something this checklist tries to automate. Edit
  `outputs/topic_labels.json` directly: give some topics a `parent` key
  (`"P0"`, `"P1"`, …) and add a matching entry under `"parents"` (see the
  currently-committed file for the shape, or `scripts/_reconstruct_topic_labels.py`
  for how it's assembled from EnricoVis's committed JSON).
  Once curated, **the file is protected** — `topics_bertopic.py` refuses to
  overwrite an existing `outputs/topic_labels.json` on a rerun (delete it first
  if you deliberately want a fresh seed instead).

- **`PARENT_NAMES` / `PARENT_COLORS` in `src/build_viz_aggregates.py`**, and their
  manually-synced copy in `docs/TopicVizPrototypes/shared/enrico.js` (these two
  must stay byte-identical — the file's own header comment says so; a plain
  diff of the two arrays is the fastest way to check) — these are a deliberate,
  hand-maintained palette, not derived from the model. `build_viz_aggregates.py`'s
  `validate()` prints a loud warning if the topic model's actual parent count
  disagrees with `len(PARENT_NAMES)`, so you'll know exactly when this needs
  updating (a parent count that stays at 8 needs no changes here at all).
  Nothing crashes either way — an unaccounted-for parent theme falls back to
  the "Unassigned" bucket / a repeated color until you update these.

  **Both `PARENT_COLORS` copies now carry 4 SPARE colors past the 8 real
  names** (indices 8-11) — pre-picked headroom so a 9th+ parent theme, once
  you write its name into `PARENT_NAMES` (parent themes are always a manual
  grouping of leaf topics — BERTopic itself never produces them, see §1
  above), immediately gets a real, distinct color instead of silently
  reusing color 0. You still have to write the name and re-sync both copies;
  you no longer separately have to go pick a matching color for it too,
  as long as you're adding 4 or fewer new parents at once. A 5th+ new parent
  in one refit exhausts the buffer and falls back to color reuse again —
  same as today, just a higher ceiling. `docs/EnricoVis/topic_hierarchy.html`
  (the PI's own file) was deliberately **not** extended — its palette stays
  at 8 unless the PI extends it separately; a genuinely new parent theme
  will render with a fresh color in this project's own pages but a reused
  one in the PI's, until/unless that file is updated too. Same for
  `docs/onlineoutput/topic_hierarchy.html`, which is a *published snapshot*
  of the PI's file (regenerated by the deploy workflow whenever that source
  changes) — not a fourth thing to hand-edit.

  **`docs/TopicVizPrototypes/what_we_can_see/constants.js`'s `TP_COLORS`**
  (a *third*, independent 8-entry — now 12-entry — hardcoded copy, used only
  by the "Every grant"/"Every PI" facet grids' small-mark color scale, not
  the same list as `PARENT_COLORS` above) was previously undocumented here.
  Same deal: already safe (`facets.js` indexes it with `% TP_COLORS.length`),
  now also carries 4 spare colors for the same reason. `PARENT_SHORT` in the
  same file (the hand-abbreviated parent-theme labels for that grid's row/
  column headers) is NOT similarly buffered — abbreviations are curated text,
  which can't be pre-invented the way a color can; a parent id past index 7
  falls back to its full, un-abbreviated name (`facets.js`'s `PARENT_SHORT[i]
  || name`), which is safe but may run long in a narrow label.

- **`ARTIFACT_TOPIC_ID` in `src/build_viz_aggregates.py`** (currently `11` — a
  flagged low-coherence/placeholder-title cluster from this fit). Whether *this*
  refit has an equivalent artifact bucket, and which topic id it is, is a
  judgment call — `validate()` warns if the constant no longer points at a real,
  unparented topic, but deciding the right new value (or that there isn't one
  this time) is manual.

- **The `CAVEATS` prose in `src/build_viz_aggregates.py`** (rendered on
  `about.html`). Sentences like *"The $2.18B headline…"*, *"808 grants (27.8%
  of dollars) carry no confident topic…"* are hand-written, not computed —
  `validate()`'s checks don't verify they still describe the data correctly.
  Re-read and update this list by hand after a refit; it's expected work, not
  a bug in the pipeline.

- **Frontend limitations — documented here, deliberately not touched by any of
  the above except where noted.** (Line numbers below point into
  `docs/TopicVizPrototypes/topic_flow.html` and
  `docs/TopicVizPrototypes/what_we_can_see/missing.js` — the latter was split
  out of `what_we_can_see.html`'s single inline script; re-point these after
  any further restructuring. Also re-check these numbers if the file changes
  again — they've already drifted once, from an earlier `file://` guard
  added to the page's `<head>`.)

  - **`topic_flow.html`'s parent-theme axis is now data-driven — no manual
    step needed here after a refit.** `PARENT_KEYS` (`:137`) used to be a
    hardcoded 9-entry literal; it's now built from `VIZ_META.parents` at
    load time, so it can never list a parent id the aggregator's own output
    doesn't have. This mattered in both directions, not just one: a parent
    count *increase* used to silently drop the 9th+ theme from the chart;
    a *decrease* used to be a hard crash (`TOPIC_TIME.series.parent[k]` was
    `undefined` for a `k` the old literal still listed — verified with a
    throwaway Node repro during the fix). `bandColor`/`bandName` (`:143-144`)
    and the small-multiples fill/stroke (`:413`, `:416`) now delegate to
    `enrico.js`'s own `parentColor()`/`parentName()` instead of reimplementing
    the same lookup without their modulo/fallback safety. Residual, expected
    behavior once the palette buffer above is exhausted: a name renders as a
    raw `"P8"`-style fallback and a color repeats, until you re-curate — no
    crash, no silent drop.
  - The caveat-id whitelists in `topic_flow.html` (`:435-436`) and
    `what_we_can_see/missing.js` (`:332`) will silently stop showing a caveat
    if its `id` is renamed or removed from `CAVEATS`. Still a manual check —
    not fixed, since there's no safe default here (a caveat's `id` is content,
    not a count).
  - **Leaf topic count (25 → N) was separately audited and is already fully
    safe everywhere** — `enrico.js`'s `topicColor()`, `facets.js`'s `tid`
    facet, `topic_flow.html`'s small-multiples loop, `build_viz_data.py`'s
    `n_topics`-derived sizing, and even the PI's own `topic_islands.html` all
    either derive the count dynamically or wrap their color index with
    `% length`. `enrico.js`'s `TOPIC_COLORS` (25 in active use) also carries
    5 SPARE colors past the current 25 (indices 25-29), same buffer idea as
    `PARENT_COLORS` above — a 26th-30th leaf topic gets a real, distinct
    color automatically, with no human step at all (unlike a new parent
    theme, a new leaf topic count is a direct, automatic output of the
    refit itself). The one loose end is **cosmetic prose**, not logic:
    `topic_flow.html`'s `<h2>The 25 leaf topics</h2>` heading and its "a
    25-band stack is unreadable, 25 sparklines are fine" caption will read
    wrong after a count change. Worth a manual glance and hand-edit if you
    want the copy to match — not fixed here, since (unlike the crash above)
    this is a wording/content choice, not a safety issue.

  Worth a manual glance after a refit that changes the parent count or renames
  a caveat id. The crash/silent-drop risk above is now fixed; what's left here
  is genuinely optional polish — the visualization's own HTML/JS is otherwise
  frozen as the final prototype; see the rest of this repo's history for why.

---

## 4. Sanity-check the result

1. `python -m src.build_viz_aggregates --check-only` — read the printed report.
   Every ⚠ line names something from §3 above that needs your attention; every
   other line is informational (the numbers are *expected* to move after a
   refit) except the handful of internal-reconciliation asserts, which fail
   loudly (not silently wrong) if something is actually broken.
2. `python scripts/_check_topicviz.py` — confirms every dataset the three pages
   `fetch()` exists in `data/` and parses, and that the aggregator emits nothing
   no page reads. The old "ran the aggregator but forgot to re-inline" failure
   mode no longer exists: `data/*.json` is what the pages load, there's no
   second copy to fall out of sync.
3. Serve the directory and open all three pages — they `fetch()` their data as
   ES modules and will **not** load over `file://`:
   ```bash
   python -m http.server 8000 --directory docs/TopicVizPrototypes
   # http://localhost:8000/{what_we_can_see,topic_flow,about}.html
   ```
   Eyeball them with DevTools open — the automated checks catch structural
   drift, not "does this still read sensibly," and only the Network tab will
   tell you a dataset 404'd.
