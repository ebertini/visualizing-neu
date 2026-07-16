"""One-shot diagnostic: is grant_orphaned_abstracts.parquet worth using?

Answers two review questions:
  1. Orphan provenance — are they collaborators / non-NU awards?
  2. Date + agency overlap — does adding them broaden or bias the corpus?
"""
import pandas as pd

pd.set_option("display.max_colwidth", 80)
pd.set_option("display.width", 220)

orph = pd.read_parquet("data/processed/grant_orphaned_abstracts.parquet")
neu = pd.read_parquet("data/processed/grants.parquet")

EMPTY = "(empty)"

def clean_str(s):
    return s.fillna("").astype(str).str.strip().replace("", EMPTY)


print("=== 1. USABLE FOR EMBEDDING? ===")
orph["_has_title"] = orph["title"].fillna("").str.strip().str.len() > 0
orph["_has_abs"] = orph["abstract"].fillna("").str.strip().str.len() >= 200
print(f"  total orphan rows:           {len(orph):>5}")
print(f"  with title (non-empty):      {orph._has_title.sum():>5}  ({orph._has_title.mean()*100:.1f}%)")
print(f"  with abstract (>=200 chars): {orph._has_abs.sum():>5}  ({orph._has_abs.mean()*100:.1f}%)")

print()
print("=== 2. PERSONID PROVENANCE ===")
pid = clean_str(orph["personid"])
print(f"  unique personids:            {pid.nunique():>5}")
print(f"  non-empty personid:          {(pid != EMPTY).sum():>5}")
print()
print("  Top 15 personids by orphan row count:")
print(pid.value_counts().head(15).to_string())

print()
print("=== 3. SOURCE TYPE ===")
print(clean_str(orph["sourcetype"]).value_counts(dropna=False).head(10).to_string())

print()
print("=== 4. SPONSOR / AGENCY MIX ===")
print("  Top 20 orphan sponsors:")
print(clean_str(orph["sponsor"]).value_counts().head(20).to_string())

print()
print(f"  NEU grants columns: {list(neu.columns)}")

print()
print("=== 5. YEAR / DATE COVERAGE ===")
orph["_year"] = pd.to_datetime(orph["start_date"], errors="coerce").dt.year
neu_year_col = None
for c in ("start_date", "startdate", "startdateyear"):
    if c in neu.columns:
        neu_year_col = c
        break
print(f"  (using NEU year column: {neu_year_col})")

def year_bucket(y):
    if pd.isna(y):
        return "unknown"
    y = int(y)
    if y < 2000:
        return "<2000"
    if y < 2005:
        return "2000-04"
    if y < 2010:
        return "2005-09"
    if y < 2015:
        return "2010-14"
    if y < 2020:
        return "2015-19"
    return "2020+"

orph["_bucket"] = orph["_year"].apply(year_bucket)
if neu_year_col:
    neu_years = pd.to_datetime(neu[neu_year_col], errors="coerce").dt.year
    neu_bucket = neu_years.apply(year_bucket)
    year_tbl = pd.DataFrame({
        "orphans_all": orph["_bucket"].value_counts(),
        "orphans_with_abstract": orph.loc[orph._has_abs, "_bucket"].value_counts(),
        "neu": neu_bucket.value_counts(),
    }).fillna(0).astype(int)
    order = ["<2000", "2000-04", "2005-09", "2010-14", "2015-19", "2020+", "unknown"]
    year_tbl = year_tbl.reindex(order, fill_value=0)
    print(year_tbl.to_string())

print()
print("=== 6. SPONSOR MIX AMONG THE 403 THAT ACTUALLY HAVE AN ABSTRACT ===")
usable = orph[orph._has_abs].copy()
print(f"  usable rows: {len(usable)}")
print(clean_str(usable["sponsor"]).value_counts().head(20).to_string())

print()
print("=== 7. SAMPLE OF USABLE ROWS (first 10 titles + sponsor + year) ===")
sample = usable[["title", "sponsor", "_year", "personid"]].head(10)
print(sample.to_string(index=False))

print()
print("=== 8. WRITE ORPHAN-WITH-ABSTRACT INVENTORY FOR REVIEW ===")
review = usable[[
    "id", "personid", "sourcetype", "sourceactivityid",
    "title", "sponsor", "start_date", "end_date",
    "dollar_amount", "funding_status", "type_of_funding",
    "funding_source", "abstract",
]].copy().reset_index(drop=True)
out = "data/processed/orphans_with_abstract_review.csv"
review.to_csv(out, index=False)
print(f"  wrote {out}  ({len(review)} rows)")
