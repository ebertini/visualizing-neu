"""Reconcile the three ID spaces for Chris Martens.

User observations:
  - grants-with-abstract.xlsx    personid = 110082
  - grants-with-coPI.xlsx        AAUID    = 799620
  - ri_matches_grants_2026.xlsx  AAUID    = 799620
  - processed faculty.parquet    faculty_id = 2963712

Goal: understand which columns actually exist in each raw file and how
build_dataset.py chooses between them.
"""
from pathlib import Path
import pandas as pd

pd.set_option("display.width", 260)
pd.set_option("display.max_colwidth", 55)
pd.set_option("display.max_columns", 40)

RAW = Path(__file__).resolve().parent.parent / "DataSet"


def dump_martens(path: Path, sheet=None):
    print("=" * 90)
    print(f"FILE: {path.name}" + (f"   sheet={sheet}" if sheet else ""))
    print("=" * 90)
    df = pd.read_excel(path, sheet_name=sheet) if sheet else pd.read_excel(path)
    print(f"shape: {df.shape}")
    print(f"columns: {list(df.columns)}")
    # Find rows referencing Martens by name if any name-like column exists
    name_cols = [c for c in df.columns if any(k in c.lower()
                                              for k in ("name", "person"))]
    print(f"name-like columns: {name_cols}")
    hits = pd.DataFrame()
    for c in name_cols:
        m = df[c].astype(str).str.contains("MARTENS", case=False, na=False)
        if m.any():
            hits = pd.concat([hits, df[m]], ignore_index=True)
    hits = hits.drop_duplicates()
    print(f"rows matching 'MARTENS' by any name column: {len(hits)}")
    if len(hits):
        print(hits.head(5).to_string(index=False))
    return df


print()
ri   = dump_martens(RAW / "ri_matches_grants_2026.xlsx")
print()
copi = dump_martens(RAW / "grants-with-coPI.xlsx")
print()
abs_ = dump_martens(RAW / "grants-with-abstract.xlsx")
print()

# HR Snowflake is where faculty_id (== employee_id) comes from
hr = pd.read_excel(RAW / "HR Snowflake faculty list 2025 fall update 6.15.2026.xlsx")
print("=" * 90)
print(f"FILE: HR Snowflake faculty list")
print("=" * 90)
print(f"shape: {hr.shape}")
print(f"columns: {list(hr.columns)}")
# What's the primary key column?
id_cols = [c for c in hr.columns if "id" in c.lower() or "employee" in c.lower()]
print(f"id-like columns: {id_cols}")
# HR probably has a full name column
name_cols = [c for c in hr.columns if "name" in c.lower()]
print(f"name-like columns: {name_cols}")

# Try to find Martens in HR
hits = pd.DataFrame()
for c in name_cols:
    m = hr[c].astype(str).str.contains("MARTENS|Martens", na=False, regex=True)
    if m.any():
        hits = pd.concat([hits, hr[m]], ignore_index=True)
print(f"rows matching 'MARTENS': {len(hits)}")
if len(hits):
    show_cols = id_cols + name_cols
    print(hits[show_cols].head().to_string(index=False))

# Also — is 2963712 in HR? Is 799620?
if id_cols:
    idcol = id_cols[0]
    hr[idcol] = hr[idcol].astype(str)
    for candidate in ("2963712", "799620", "110082"):
        row = hr[hr[idcol] == candidate]
        print(f"  {idcol} == {candidate}: {len(row)} rows in HR")
        if len(row):
            print(row[id_cols + name_cols].to_string(index=False))
