"""
_check_new_abstracts.py — diagnostic: does DataSet/AcAn Grants 2026-08-13.xlsx
close part of the abstract-coverage gap?

Context (docs/TOPIC_CLASSIFICATION_BRAINSTORM.md, "open questions"): the data
team dropped a refreshed export of the same abstract table the pipeline
already uses (DataSet/grants-with-abstract.xlsx, 8,075 rows). The new file
has the identical 25-column schema but 11,785 rows. This script quantifies
what it would add WITHOUT touching the pipeline:

  - how many of the 740 NEU grants that currently have no abstract text gain
    one from the new file ("recoverable"),
  - their breakdown by agency / start year / BERTopic parent theme,
  - whether the recovered grants move the NIH post-2019 coverage cliff (the
    single loudest caveat on the dashboard) — since if they don't, adopting
    the new file wouldn't fix the headline problem it's tempting to credit
    it with,
  - how much backfill (already-matched grants getting a longer/updated
    abstract) the new file offers on top of net-new recovery.

Decision this pass (see the plan): do NOT repoint src/build_dataset.py at
the new file — that would fire ~8 hardcoded assertions in
build_viz_aggregates.validate() and desync from the PI's frozen BERTopic
output (title-only flags baked in for 2,676 docs). Adopting it into the
pipeline, and re-running the topic model over the newly-recovered text, is
future work tracked in TOPIC_CLASSIFICATION_BRAINSTORM.md.

Writes data/processed/new_abstract_recovery.parquet — one row per grant_id
that is recoverable (has no abstract in grants.parquet today, but the new
file has usable text for it), read as an optional input by
build_viz_aggregates.py to show a "recoverable" segment in the missingness
view. This script does not modify grants.parquet or any pipeline output.

Run:
    .venv/bin/python scripts/_check_new_abstracts.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # so `from src...` works whether this is run
                                     # as a bare script or as a module

from src.build_dataset import _lower_cols  # noqa: E402
from src.build_viz_aggregates import _parent_index  # noqa: E402
DATASET = REPO_ROOT / "DataSet"
PROC = REPO_ROOT / "data" / "processed"
ENRICOVIS_DATA = REPO_ROOT / "docs" / "EnricoVis" / "data"
OUT_PATH = PROC / "new_abstract_recovery.parquet"

OLD_FILE = DATASET / "grants-with-abstract.xlsx"
NEW_FILE = DATASET / "AcAn Grants 2026-08-13.xlsx"
NEW_SOURCE_LABEL = "acan_2026-08-13"


def _load_abstract_export(path: Path, grant_ids: set[str]) -> pd.DataFrame:
    """Mirror src.build_dataset.Pipeline._split_abstracts' matching logic:
    one row per grant_id (the most-recently-updated record), restricted to
    rows whose sourceactivityid hits an NEU grant_id. Returns a DataFrame
    indexed by grant_id with an `abstract` column (possibly empty string).
    """
    df = _lower_cols(pd.read_excel(path))
    df["id"] = df["id"].astype(str)
    df["sourceactivityid"] = df["sourceactivityid"].astype(str)
    df["abstract"] = df["abstract"].fillna("").astype(str)
    for c in ("updateddate", "createddate"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    matched = df[df["sourceactivityid"].isin(grant_ids) & (df["sourceactivityid"] != "")].copy()
    sort_keys = [c for c in ("updateddate", "createddate") if c in matched.columns]
    if sort_keys:
        matched = matched.sort_values(sort_keys, ascending=False, na_position="last")
    matched = matched.drop_duplicates(subset=["sourceactivityid"], keep="first")
    return matched.set_index("sourceactivityid")[["abstract"]].rename_axis("grant_id")


def main() -> None:
    grants = pd.read_parquet(PROC / "grants.parquet", columns=["grant_id", "abstract"])
    grants["grant_id"] = grants["grant_id"].astype(str).str.strip()
    grant_ids = set(grants["grant_id"])

    missing_now = set(grants.loc[grants["abstract"].fillna("").str.strip() == "", "grant_id"])
    print(f"NEU grants with no abstract text today: {len(missing_now)} (expect 740)")

    old = _load_abstract_export(OLD_FILE, grant_ids)
    new = _load_abstract_export(NEW_FILE, grant_ids)

    old_has = set(old.index[old["abstract"].str.strip() != ""])
    new_has = set(new.index[new["abstract"].str.strip() != ""])

    recoverable = sorted(missing_now & new_has)
    print(f"\nRecoverable — currently missing, has text in the new export: {len(recoverable)}")

    backfillable = sorted((old_has & new_has) - missing_now)
    changed_text = [
        gid for gid in backfillable
        if old.loc[gid, "abstract"].strip() != new.loc[gid, "abstract"].strip()
    ]
    print(f"Already-matched grants where the new export's text differs: {len(changed_text)}")

    # Raw-record-level backfill (any Id shared between the two exports that
    # gained abstract text) — a looser, file-level version of the same
    # question, independent of NEU grant matching.
    old_raw = _lower_cols(pd.read_excel(OLD_FILE))[["id", "abstract"]].copy()
    new_raw = _lower_cols(pd.read_excel(NEW_FILE))[["id", "abstract"]].copy()
    old_raw["id"] = old_raw["id"].astype(str)
    new_raw["id"] = new_raw["id"].astype(str)
    old_raw["abstract"] = old_raw["abstract"].fillna("").astype(str).str.strip()
    new_raw["abstract"] = new_raw["abstract"].fillna("").astype(str).str.strip()
    old_abs_by_id = dict(zip(old_raw["id"], old_raw["abstract"]))
    shared_ids = set(old_raw["id"]) & set(new_raw["id"])
    gained_raw = sum(
        1 for _, r in new_raw[new_raw["id"].isin(shared_ids)].iterrows()
        if not old_abs_by_id.get(r["id"], "") and r["abstract"]
    )
    print(f"Shared raw records ({len(shared_ids)}) that gained abstract text: {gained_raw}")

    if not recoverable:
        print("\nNo recoverable grants — nothing further to report.")
        _write_output([])
        return

    # Breakdown by agency / start year / BERTopic parent theme, via the
    # frozen EnricoVis output (same corpus, same ids) — no topic re-fit.
    points = json.loads((ENRICOVIS_DATA / "grants_umap.json").read_text(encoding="utf-8"))["points"]
    topics = json.loads((ENRICOVIS_DATA / "topics.json").read_text(encoding="utf-8"))
    parent_of_topic = {t["id"]: _parent_index(t.get("parent")) for t in topics}
    by_id = {str(p["id"]).strip(): p for p in points}

    rec_points = [by_id[gid] for gid in recoverable if gid in by_id]
    missing_ids = [gid for gid in recoverable if gid not in by_id]
    if missing_ids:
        print(f"  (warning: {len(missing_ids)} recoverable grant_ids not found in the frozen UMAP corpus)")

    def counts(key_fn, points_):
        out: dict = {}
        for p in points_:
            k = key_fn(p)
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    print("\nRecoverable grants by agency:")
    for k, v in counts(lambda p: p["agency"], rec_points).items():
        print(f"  {k:10s} {v}")

    print("\nRecoverable grants by start year:")
    by_year = counts(lambda p: p["year"] if p["year"] is not None else "unknown", rec_points)
    for k in sorted(by_year, key=lambda y: (y == "unknown", y)):
        print(f"  {k}  {by_year[k]}")

    print("\nRecoverable grants by BERTopic parent theme (index, -1 = Unassigned):")
    for k, v in counts(lambda p: parent_of_topic.get(p["dom"], -1), rec_points).items():
        print(f"  parent {k}  {v}")

    # The NIH cliff check — the one caveat this file's adoption is most
    # likely to get credited with fixing whether or not it actually does.
    nih_missing_by_year: dict[int, int] = {}
    nih_recovered_by_year: dict[int, int] = {}
    for p in points:
        if p["agency"] not in ("NIH", "NIH-SUB") or p["year"] is None:
            continue
        gid = str(p["id"]).strip()
        if gid in missing_now:
            nih_missing_by_year[p["year"]] = nih_missing_by_year.get(p["year"], 0) + 1
        if gid in recoverable:
            nih_recovered_by_year[p["year"]] = nih_recovered_by_year.get(p["year"], 0) + 1

    print("\nNIH/NIH-SUB missing-abstract grants by year, and how many the new export recovers:")
    cliff_years = [y for y in sorted(nih_missing_by_year) if y >= 2019]
    any_recovered_post_cliff = False
    for y in cliff_years:
        miss = nih_missing_by_year.get(y, 0)
        rec = nih_recovered_by_year.get(y, 0)
        if y >= 2021 and rec:
            any_recovered_post_cliff = True
        print(f"  {y}: {miss} missing, {rec} recovered by the new export")
    if any_recovered_post_cliff:
        print("  -> The new export DOES recover some 2021+ NIH abstracts — the cliff narrows, doesn't vanish.")
    else:
        print("  -> The new export recovers NOTHING for NIH 2021+ — the post-2019 cliff is UNCHANGED. "
              "Only an NIH RePORTER backfill (per the existing caveat) can fix that.")

    _write_output(recoverable)


def _write_output(recoverable_ids: list[str]) -> None:
    out = pd.DataFrame({
        "grant_id": recoverable_ids,
        "recoverable": True,
        "source": NEW_SOURCE_LABEL,
    })
    PROC.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)
    print(f"\nwrote {OUT_PATH.relative_to(REPO_ROOT)}  ({len(out)} rows)")


if __name__ == "__main__":
    main()
