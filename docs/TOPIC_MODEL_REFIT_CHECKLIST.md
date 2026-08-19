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
                                           # + _inline_topicviz_data, in one command —
                                           # LIGHT deps only, ~seconds
```

**Heavy deps** (`requirements.txt`: torch, transformers, adapters, sentence-transformers,
bertopic, umap-learn, hdbscan) are only needed for the two `HEAVY` steps above.
**Light deps** (`requirements-viz.txt`: pandas, pyarrow, rapidfuzz) cover everything
else, including the entire `refresh_topicviz` step — see `CLAUDE.md`'s Setup section
for the `uv venv` incantation (bare `python3.11 -m venv` fails on this machine).

`refresh_topicviz` only re-runs `build_viz_data` if `data/processed/topic_assignments.parquet`
is newer than `docs/EnricoVis/data/topics.json` (an mtime check) — it prints which
branch it took. Verify the result matches what's on disk with:

```bash
python scripts/_inline_topicviz_data.py --check
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
  manually-synced copies in `docs/TopicVizPrototypes/shared/enrico.js` (and,
  optionally, for visual consistency with the PI's read-only EnricoVis apps,
  `docs/EnricoVis/topic_hierarchy.html`) — these are a deliberate, hand-maintained
  palette, not derived from the model. `build_viz_aggregates.py`'s `validate()`
  now prints a loud warning if the topic model's actual parent count disagrees
  with `len(PARENT_NAMES)`, so you'll know exactly when this needs updating (a
  parent count that stays at 8 needs no changes here at all). Nothing crashes
  either way — an unaccounted-for parent theme falls back to the "Unassigned"
  bucket / a repeated color until you update these.

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
  the above.** Two things degrade *silently* (not a crash, just quietly wrong)
  if the topic model's shape changes and these aren't checked by hand:
  - `docs/TopicVizPrototypes/topic_flow.html`'s hardcoded 9-entry `PARENT_KEYS`
    list (`:126`) and its unguarded `PARENT_COLORS[t.parent]` indexing (`:390`,
    `:393`) will mis-render — not crash — a 9th parent theme.
  - The caveat-id whitelists in `topic_flow.html` (`:412-413`) and
    `what_we_can_see.html` (`:1820`) will silently stop showing a caveat if its
    `id` is renamed or removed from `CAVEATS`.

  Worth a manual glance after a refit that changes the parent count or renames
  a caveat id. Not fixed preemptively — the visualization's own HTML/JS is
  frozen as the final prototype; see the rest of this repo's history for why.

---

## 4. Sanity-check the result

1. `python -m src.build_viz_aggregates --check-only` — read the printed report.
   Every ⚠ line names something from §3 above that needs your attention; every
   other line is informational (the numbers are *expected* to move after a
   refit) except the handful of internal-reconciliation asserts, which fail
   loudly (not silently wrong) if something is actually broken.
2. `python scripts/_inline_topicviz_data.py --check` — confirms the three
   prototype HTML files actually reflect the freshly-built `data/*.json` (catches
   "ran the aggregator but forgot to re-inline").
3. Open `docs/TopicVizPrototypes/what_we_can_see.html`, `topic_flow.html`, and
   `about.html` locally and eyeball them — the automated checks above catch
   structural drift, not "does this still read sensibly."
