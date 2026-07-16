"""Bridge orphan personid to NEU faculty_id via the matched abstracts.

Recipe:
  1. Load raw grants-with-abstract.xlsx (has personid + sourceactivityid).
  2. Rows with sourceactivityid in NEU grants roster are the *matched* set.
  3. Cross-reference matched sourceactivityid -> grant_id -> faculty_id
     via faculty_grants.parquet. Build personid -> {faculty_ids} multimap.
  4. Apply that mapping to the orphan personids and produce an overlap
     table: faculty_id, faculty_name, college, n_neu_grants, n_orphan_records,
     n_orphan_with_abstract.
"""
from pathlib import Path
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 60)

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "DataSet" / "grants-with-abstract.xlsx"
PROC = REPO / "data" / "processed"

print(f"loading raw {RAW.name}...")
raw = pd.read_excel(RAW)
raw.columns = [c.strip().lower().replace(" ", "_") for c in raw.columns]
print(f"  raw shape: {raw.shape}")
print(f"  raw columns: {list(raw.columns)}")

grants = pd.read_parquet(PROC / "grants.parquet")
fg = pd.read_parquet(PROC / "faculty_grants.parquet")
fac = pd.read_parquet(PROC / "faculty.parquet")
orph = pd.read_parquet(PROC / "grant_orphaned_abstracts.parquet")

grants["grant_id"] = grants["grant_id"].astype(str)
fg["grant_id"] = fg["grant_id"].astype(str)
fg["faculty_id"] = fg["faculty_id"].astype(str)
fac["faculty_id"] = fac["faculty_id"].astype(str)

raw["sourceactivityid"] = raw["sourceactivityid"].fillna("").astype(str).str.strip()
raw["personid"] = raw["personid"].fillna("").astype(str).str.strip()

neu_ids = set(grants["grant_id"])
matched_raw = raw[raw["sourceactivityid"].isin(neu_ids) & (raw["sourceactivityid"] != "")].copy()
print(f"\nmatched raw rows: {len(matched_raw)}  "
      f"({matched_raw['sourceactivityid'].nunique()} unique grants, "
      f"{matched_raw['personid'].nunique()} unique personids)")

# Bridge: personid -> set(faculty_id) via matched sourceactivityid -> faculty_grants
bridge = (
    matched_raw[["personid", "sourceactivityid"]]
    .rename(columns={"sourceactivityid": "grant_id"})
    .merge(fg[["grant_id", "faculty_id"]], on="grant_id", how="inner")
)
print(f"personid <-> grant <-> faculty_id links: {len(bridge)}")

pid_to_fids = (
    bridge.groupby("personid")["faculty_id"]
    .agg(lambda s: sorted(set(s)))
    .to_dict()
)
print(f"personids with at least one faculty_id inferred: {len(pid_to_fids)}")
print(f"personids with EXACTLY one faculty_id:            "
      f"{sum(1 for v in pid_to_fids.values() if len(v) == 1)}")

# Diagnostic: how many personids resolve unambiguously? Ambiguously?
multi = {p: v for p, v in pid_to_fids.items() if len(v) > 1}
print(f"personids that resolve to >1 faculty_id (ambiguous): {len(multi)}")
if multi:
    print("  sample ambiguous:")
    for p, v in list(multi.items())[:5]:
        print(f"    personid {p} -> {len(v)} faculty_ids: {v}")

# Which orphan personids have a faculty_id resolution?
orph["personid"] = orph["personid"].fillna("").astype(str).str.strip()
orph_pids = set(orph["personid"]) - {""}
resolvable = orph_pids & set(pid_to_fids.keys())
print(f"\norphan personids resolvable to faculty_id: {len(resolvable)} / {len(orph_pids)} "
      f"({len(resolvable)/max(len(orph_pids),1)*100:.1f}%)")

# Assign primary faculty_id per orphan (take first if ambiguous — flag it)
def _primary(pid):
    v = pid_to_fids.get(pid, [])
    return (v[0], len(v)) if v else (None, 0)

orph[["faculty_id", "n_candidate_fids"]] = orph["personid"].apply(
    lambda p: pd.Series(_primary(p))
)
orph["_has_abstract"] = orph["abstract"].fillna("").str.strip().str.len() >= 200

# Roll up: per faculty, how many NEU grants / orphan rows / orphan-with-abstract
neu_per_fac = fg.groupby("faculty_id")["grant_id"].nunique().rename("n_neu_grants")
orph_per_fac = (
    orph[orph["faculty_id"].notna()]
    .groupby("faculty_id")
    .agg(n_orphan_rows=("id", "count"),
         n_orphan_with_abstract=("_has_abstract", "sum"))
)

overlap = (
    fac[["faculty_id", "faculty_name", "superior_academic_unit", "academic_unit"]]
    .merge(neu_per_fac, left_on="faculty_id", right_index=True, how="left")
    .merge(orph_per_fac, left_on="faculty_id", right_index=True, how="left")
    .fillna({"n_neu_grants": 0, "n_orphan_rows": 0, "n_orphan_with_abstract": 0})
)
for c in ("n_neu_grants", "n_orphan_rows", "n_orphan_with_abstract"):
    overlap[c] = overlap[c].astype(int)

# Only faculty that appear in BOTH tables
both = overlap[(overlap["n_neu_grants"] > 0) & (overlap["n_orphan_rows"] > 0)].copy()
both = both.sort_values(
    ["n_orphan_with_abstract", "n_orphan_rows", "n_neu_grants"],
    ascending=[False, False, False],
).reset_index(drop=True)

print(f"\n=== FACULTY IN BOTH TABLES ===")
print(f"faculty with >=1 NEU grant AND >=1 orphan row: {len(both)}")
print(f"total NEU faculty:                              {(overlap['n_neu_grants'] > 0).sum()}")
print(f"faculty w/ orphans but NO matched NEU grants:   "
      f"{((overlap['n_neu_grants'] == 0) & (overlap['n_orphan_rows'] > 0)).sum()}")

print("\nTop 25 faculty by n_orphan_with_abstract:")
print(both[["faculty_id", "faculty_name", "superior_academic_unit",
            "n_neu_grants", "n_orphan_rows", "n_orphan_with_abstract"]]
      .head(25)
      .to_string(index=False))

# Also: how many orphan-abstract rows in total map to a resolvable faculty?
n_orph_abs = orph["_has_abstract"].sum()
n_orph_abs_mapped = orph[orph["_has_abstract"] & orph["faculty_id"].notna()].shape[0]
print(f"\n=== RECOVERY BUDGET FOR OPTION B ===")
print(f"orphan rows with abstract:                                     {n_orph_abs}")
print(f"orphan rows with abstract AND resolvable faculty_id:           {n_orph_abs_mapped}")
print(f"orphan rows with abstract but personid NOT in NEU faculty:     "
      f"{n_orph_abs - n_orph_abs_mapped}")

out_overlap = PROC / "faculty_orphan_overlap.csv"
overlap.sort_values(["n_orphan_with_abstract", "n_neu_grants"],
                    ascending=[False, False]).to_csv(out_overlap, index=False)
print(f"\nwrote {out_overlap}  ({len(overlap)} rows, all NEU faculty)")

out_both = PROC / "faculty_orphan_overlap_both.csv"
both.to_csv(out_both, index=False)
print(f"wrote {out_both}  ({len(both)} rows, faculty in BOTH tables)")

out_pid_map = PROC / "personid_to_faculty.csv"
pd.DataFrame([
    {"personid": p, "n_candidate_faculty_ids": len(v), "faculty_ids": ";".join(v)}
    for p, v in pid_to_fids.items()
]).to_csv(out_pid_map, index=False)
print(f"wrote {out_pid_map}  ({len(pid_to_fids)} rows)")
