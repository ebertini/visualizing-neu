"""Trace two personids end-to-end for illustration:
  A. one that resolves to exactly one faculty (clean case)
  B. one that resolves to multiple faculty (ambiguous case)
"""
from pathlib import Path
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 60)

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "DataSet" / "grants-with-abstract.xlsx"
PROC = REPO / "data" / "processed"

raw = pd.read_excel(RAW)
raw.columns = [c.strip().lower().replace(" ", "_") for c in raw.columns]
raw["personid"] = raw["personid"].fillna("").astype(str).str.strip()
raw["sourceactivityid"] = raw["sourceactivityid"].fillna("").astype(str).str.strip()

grants = pd.read_parquet(PROC / "grants.parquet")
grants["grant_id"] = grants["grant_id"].astype(str)
fg = pd.read_parquet(PROC / "faculty_grants.parquet")
fg["grant_id"] = fg["grant_id"].astype(str)
fg["faculty_id"] = fg["faculty_id"].astype(str)
fac = pd.read_parquet(PROC / "faculty.parquet")
fac["faculty_id"] = fac["faculty_id"].astype(str)
orph = pd.read_parquet(PROC / "grant_orphaned_abstracts.parquet")
orph["personid"] = orph["personid"].fillna("").astype(str).str.strip()

neu_ids = set(grants["grant_id"])


def trace(pid: str, label: str):
    print("=" * 78)
    print(f"{label}   personid = {pid}")
    print("=" * 78)

    # 1. Matched abstract rows this personid uploaded (shared with NEU grants)
    matched = raw[
        (raw["personid"] == pid)
        & (raw["sourceactivityid"].isin(neu_ids))
        & (raw["sourceactivityid"] != "")
    ][["sourceactivityid", "title", "start_date"]].copy()
    matched = matched.rename(columns={"sourceactivityid": "grant_id"})
    matched["grant_id"] = matched["grant_id"].astype(str)
    print(f"\n[1] Matched abstract rows this personid uploaded: {len(matched)}")
    print(matched.to_string(index=False))

    # 2. For each matched grant, who does faculty_grants say is on it?
    print(f"\n[2] Who does faculty_grants say is on those grants?")
    joined = matched.merge(
        fg[["grant_id", "faculty_id", "faculty_name", "is_pi", "is_copi"]],
        on="grant_id",
        how="left",
    )
    print(joined[["grant_id", "title", "faculty_id", "faculty_name",
                  "is_pi", "is_copi"]].to_string(index=False))

    # 3. Distinct faculty candidates (what the bridge stores)
    cands = sorted(set(joined["faculty_id"].dropna()))
    print(f"\n[3] Distinct faculty_id candidates for personid {pid}: {len(cands)}")
    for fid in cands:
        row = fac[fac["faculty_id"] == fid]
        name = row["faculty_name"].iloc[0] if len(row) else "(not in faculty.parquet)"
        college = row["superior_academic_unit"].iloc[0] if len(row) else ""
        # How often does this candidate co-occur with our personid?
        co_count = (joined["faculty_id"] == fid).sum()
        share = co_count / len(matched) if len(matched) else 0
        print(f"    {fid}  {name:<32s}  {college:<40s}  "
              f"co-occurs on {co_count}/{len(matched)} shared grants ({share*100:.0f}%)")

    # 4. What ORPHAN abstracts under this personid are we trying to recover?
    orph_here = orph[orph["personid"] == pid].copy()
    orph_here["_has_abs"] = orph_here["abstract"].fillna("").str.len() >= 200
    print(f"\n[4] Orphan rows under this personid: {len(orph_here)} total, "
          f"{orph_here['_has_abs'].sum()} with usable abstract")
    show = orph_here[orph_here["_has_abs"]][["sourceactivityid", "title", "start_date"]].head(5)
    if len(show):
        print("    (showing first 5 with abstract)")
        print(show.to_string(index=False))
    print()


# Case A: unambiguous — from the CSV, personid 110082 -> exactly one faculty
trace("110082", "CASE A — CLEAN (1 candidate)")

# Case B: ambiguous — personid 15082 -> 4 faculty candidates
trace("15082", "CASE B — AMBIGUOUS (4 candidates)")
