# Week 3 Setup Guide: Running the Data Pipeline

## Quick Start

The Week 3 pipeline converts raw `.xlsx` files into clean Parquet tables that all notebooks use.

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Verify installation:
```bash
python -c "import pandas, rapidfuzz, pyarrow; print('✓ All required packages installed')"
```

### 2. Run the Pipeline

From the repository root:

```bash
python src/build_dataset.py
```

**Options:**
```bash
# Specify input/output directories (default: DataSet and data/processed)
python src/build_dataset.py --input-dir DataSet --output-dir data/processed
```

### 3. Verify Output

After running, check that these files exist in `data/processed/`:
```
faculty.parquet
grants.parquet
grant_faculty.parquet
grant_text.parquet
faculty_id_lookup.parquet
PIPELINE_VALIDATION.txt
```

View validation report:
```bash
cat data/processed/PIPELINE_VALIDATION.txt
```

### 4. Use Cleaned Data in Notebooks

All notebooks now automatically load from `data/processed/*.parquet`:

```bash
jupyter notebook notebooks/01_schema_overview.ipynb
```

No changes needed — the notebook has been refactored to use clean Parquet files.

---

## What the Pipeline Does

**Input:** 4 raw `.xlsx` files in `DataSet/`
- `faculty-list-2025.xlsx`
- `grants-with-abstract.xlsx`
- `grants-with-coPI.xlsx`
- `ri_matches_grants_2026.xlsx`

**Processing (per `docs/data_quality_report.md`):**
1. ✓ Drops 17 completely empty columns
2. ✓ Normalizes 35 academic ranks → 8 canonical buckets
3. ✓ Coerces dtypes (IDs → string, flags → bool, low-cardinality → category)
4. ✓ Validates date ranges (`startdate <= enddate`) and dollar amounts
5. ✓ Fuzzy-matches ~10% unmatched faculty using `rapidfuzz`
6. ✓ Deduplicates by primary key (one row per unique grant, per unique faculty)
7. ✓ Confirms join keys and cross-file consistency
8. ✓ Generates validation report with match rates

**Output:** 5 clean, deduplicated Parquet tables in `data/processed/`

| Table | Rows | Purpose |
|---|---|---|
| `faculty.parquet` | 2,232 | Faculty roster with normalized ranks |
| `grants.parquet` | 2,676 | Grant-level data (one row per grantid) |
| `grant_faculty.parquet` | 3,146 | Grant × faculty relationships (PI/co-PI flags) |
| `grant_text.parquet` | 8,075 | Grant titles + abstracts (for NLP) |
| `faculty_id_lookup.parquet` | 570 | Faculty ID → college mapping (including fuzzy-matched unmatched) |

---

## Data Quality Improvements

### Before Pipeline
- 17 empty columns taking up space
- 35 different academic rank values (inconsistent)
- ID columns as integers (not suitable for IDs)
- ~10% unmatched faculty (after manual UnmatchedFaculty.csv)
- Mixed categorical formats (spaces, case inconsistency)

### After Pipeline
- ✓ Empty columns removed
- ✓ Ranks normalized to 8 canonical values
- ✓ IDs as strings (memory-efficient, semantically correct)
- ✓ Fuzzy-matched additional faculty
- ✓ All text standardized (`.strip()`, consistent case)
- ✓ Data types correct (bool for flags, category for low-cardinality text)
- ✓ Date ranges validated
- ✓ Cross-file joins confirmed

---

## Workflow: Data Updates

If the raw data changes:

1. Replace files in `DataSet/` with new versions
2. Re-run the pipeline: `python src/build_dataset.py`
3. All notebooks automatically pick up cleaned data on next run

No need to update notebooks or analysis code.

---

## Troubleshooting

### PowerShell Execution Policy

If you see `[V] Never run [D] Do not run [R] Run once [A] Always run`:

**Option 1 (one-time):** Press `R` to run once  
**Option 2 (persistent):** In PowerShell, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Import Errors

If you see `ModuleNotFoundError: No module named 'rapidfuzz'`:

```bash
# Reinstall requirements
pip install --upgrade -r requirements.txt

# Verify
python -c "import rapidfuzz; print(rapidfuzz.__version__)"
```

### Missing Data Directory

If you see `FileNotFoundError: data/processed folder not found`:

The directory is auto-created by the pipeline. Just run:
```bash
python src/build_dataset.py
```

---

## Next Steps

- **Week 4:** Univariate exploration on clean data
- **Week 5:** Temporal trends (time-series charts)
- **Week 6:** Segmentation and concentration analysis

All existing analysis code in `notebooks/01_schema_overview.ipynb` continues to work — it now operates on clean, deduplicated data.
