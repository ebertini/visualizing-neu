# Data Dictionary

Living document. Updated as new fields are discovered or normalized.
One section per source file; one table per logical entity.

Legend:
- **Type** — inferred dtype after coercion (`string`, `int`, `float`, `date`, `bool`, `category`).
- **Nullable** — Y/N based on observed nulls.
- **Notes** — units, value ranges, normalization rules, join keys.

---

## `faculty-list-2025.xlsx`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| _TBD_ | | | Fill from `notebooks/01_schema_overview.ipynb` output |

---

## `grants-with-abstract.xlsx`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| _TBD_ | | | |

---

## `grants-with-coPI.xlsx`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| _TBD_ | | | |

---

## `ri_matches_grants_2026.xlsx`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| _TBD_ | | | |

---

## Cross-file join keys (to be confirmed Week 2)
- Faculty identity: candidate keys — full name (normalized), email, internal NU id.
- Grant identity: candidate keys — grant/award number, agency + start date.
