# Reusable code package

## Core Pipeline

### `build_dataset.py` — Week 3 Data Pipeline (Primary)

Reproducible ETL pipeline that ingests raw `.xlsx` files and outputs clean Parquet tables.

**Run:**
```bash
python src/build_dataset.py --input-dir DataSet --output-dir data/processed
```

**Outputs (in `data/processed/`):**
- `faculty.parquet` — cleaned roster (2,232 rows; one per faculty member)
- `grants.parquet` — deduplicated grants (2,676 rows; one per grantid)
- `grant_faculty.parquet` — grant × faculty relationships (3,146 rows; PI/co-PI flags)
- `grant_text.parquet` — grant titles + abstracts (for NLP analysis)
- `faculty_id_lookup.parquet` — faculty ID → college mapping (includes fuzzy-matched unmatched faculty)
- `PIPELINE_VALIDATION.txt` — validation report (row counts, match rates, etc.)

**Cleaning applied (per `docs/data_quality_report.md`):**
- Drops 17 completely empty columns
- Normalizes 35 academic ranks → 8 buckets
- Coerces dtypes (IDs → string, flags → bool, low-cardinality → category)
- Validates date ranges and dollar amounts
- Fuzzy-matches ~10% unmatched faculty
- Confirms join keys (`clientfacultyid` = `Employee ID`)
- Validates 6-grant delta between file versions

**Integration:** All notebooks (`notebooks/*.ipynb`) automatically load from `data/processed/*.parquet` — no need to edit them.

---

## Optional Modules (Planned for future phases)

- `ingest.py` — load raw xlsx files (Week 2+)
- `clean.py` — normalization / dtype coercion (Week 2+)
