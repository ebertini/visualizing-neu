# `src/` — Data Pipeline

## `build_dataset.py`

Reproducible ETL: loads raw `.xlsx` files from `DataSet/`, cleans them, and
writes **4 Parquet files** (plus matching CSVs, for sharing) to
`data/processed/`. The core outputs are `faculty`, `grants`, and
`faculty_grants`; `grant_orphaned_abstracts` holds abstract records from the
external NSF/NIH crawl that don't match any NEU grant.

```bash
python src/build_dataset.py --input-dir DataSet --output-dir data/processed
```

Each run produces `<name>.parquet` (analysis-friendly, snappy-compressed)
and `<name>.csv` (UTF-8 with BOM, opens correctly in Excel) side by side.

### Raw inputs (`DataSet/`)

| File | Used for |
|---|---|
| `HR Snowflake faculty list 2025 fall update 6.15.2026.xlsx` | faculty roster + hire dates (supersedes `faculty-list-2025.xlsx`) |
| `ri_matches_grants_2026.xlsx` | grants metadata (one row per grant × faculty) |
| `grants-with-coPI.xlsx` | grant ↔ PI / co-PI relationships |
| `grants-with-abstract.xlsx` | grant titles + abstract text |
| `aad_2024_federal_grant_coverage_list.xlsx` | federal-agency coverage flags (PI / co-PI availability, DB coverage years) |
| `UnmatchedFaculty.csv` | manual supplement — 15 faculty who appear in grant tables but not in the HR snapshot (usually departed faculty with historical grants) |

---

## Identifier conventions

The pipeline standardizes on **`faculty_id`** and **`grant_id`** as the canonical
join keys across all outputs.

| Where you see... | It's the same as... | Notes |
|---|---|---|
| `faculty_id` (in `faculty.parquet`, `faculty_grants.parquet`) | `Employee ID` in HR Snowflake, `ClientFacultyId` / `clientfacultyid` in the grant tables | Canonical faculty key. `"00000"` is the reserved bucket for grant rows where the raw `ClientFacultyId` was missing. |
| `grant_id` (in `grants.parquet`, `faculty_grants.parquet`) | `GrantId` / `grantid` in the raw grant tables, and `sourceactivityid` in the raw abstract table | Canonical grant key. Abstracts are now merged into `grants.parquet` on this key. |
| `personid` (in `grant_orphaned_abstracts.parquet` only) | **NOT the same as `faculty_id`.** It comes from a different source system (Faculty Activities DB) and does not overlap with HR `Employee ID`. | Do NOT join orphan abstracts to faculty on `personid`. |

---

## Outputs (`data/processed/`)

### 1. `faculty.parquet` — faculty roster

One row per faculty member. Built from the HR Snowflake export (2,232 rows),
then supplemented with 15 rows from `UnmatchedFaculty.csv` for faculty who
appear in grant records but are missing from the HR snapshot.

Use this whenever you need faculty metadata (college, rank, hire date). Every
HR row has a hire date — use it to filter grants relative to a faculty
member's tenure at Northeastern.

| Column | Type | Description |
|---|---|---|
| `faculty_id` | str | Primary key. Joins to `faculty_grants.faculty_id`. Same as `Employee ID` / `ClientFacultyId` in raw files. |
| `faculty_name` | str | Person name pulled from grant tables (`personname`). Populated only for faculty who appear in at least one grant (~557 of 2,247). |
| `superior_academic_unit` | category | College (e.g. "College of Engineering"). |
| `academic_unit` | category | Department within the college. |
| `academic_track_type` | category | Tenure / Non-Tenure / etc. |
| `academic_rank` | category | Normalized to ~8 buckets (Professor, Associate Professor, Assistant Professor, Teaching Professor, …). |
| `tenure_status` | category | Tenured / On tenure path / Not on tenure path. |
| `location_address_country` | category | Country of primary appointment. |
| `hire_date` | datetime | Date of hire (populated for all 2,232 HR rows; null for the 15 supplement rows). |
| `terminal_degrees` | str | PhD / EdD / MD / etc. |
| `termination_date` | datetime | Null if still active. |
| `termination_status` | category | Null if still active. |

Rows: **2,247** (2,232 from HR + 15 from UnmatchedFaculty supplement)

---

### 2. `grants.parquet` — grants (one row per grant, with abstract text)

Built from `ri_matches_grants_2026`, deduplicated to one row per `grantid`,
left-joined with the AAD federal-grant-coverage sheet on agency name
(fuzzy-matched, threshold 85), and further left-joined with the
most-recently-updated abstract record per grant from `grants-with-abstract`.

| Column | Type | Description |
|---|---|---|
| `grant_id` | str | Primary key. Joins to `faculty_grants.grant_id`. |
| `grantname` | str | Grant title from the RI system. |
| `agencycode` | str | Funding agency short code. |
| `agencyname` | str | Funding agency name. |
| `agencygrantid` | str | Agency's own grant identifier. |
| `totaldollars` | float | Total awarded dollars over the life of the grant. |
| `dollarsperyear` | float | Per-year dollar amount. |
| `durationinyears` | float | Duration in years. |
| `startdate` | datetime | Grant start. |
| `enddate` | datetime | Grant end. |
| `awarddate` | datetime | Date the award was issued. |
| `startdateyear` | int | Convenience year column. |
| `countrycode` | category | Funding country. |
| `isgovernment` | bool | Government funder flag. |
| `isresearch` | bool | Research-classified flag. |
| `pi_names_available` | str | From AAD: "Yes" / "No". |
| `db_coverage` | str | From AAD: year range of database coverage. |
| `copi_available` | str | From AAD: "Yes" / "No". |
| `title_from_abstract` | str | Grant title as recorded on the abstract record (often longer / more descriptive than `grantname`). Empty when no abstract matched. |
| `abstract` | str | Free-text abstract, most-recently-updated per grant. Empty when no abstract matched. |
| `funding_status` | str | From abstracts: Awarded / Pending / etc. Empty when no abstract matched. |
| `type_of_funding` | str | From abstracts: Research grant / Contract / Gift / Fellowship / etc. |
| `funding_source` | str | From abstracts: Federal / State / Private / Foundation / etc. |

Rows: **2,676** unique grants. **1,928 (72%)** have a non-empty abstract; the
remainder are grants without a matched abstract record.

---

### 3. `faculty_grants.parquet` — faculty ↔ grants lookup

The unified lookup. **Union** of (faculty, grant) pairs from
`ri_matches_grants_2026` and `grants-with-coPI`, deduplicated on
`(faculty_id, grant_id)`. Use this whenever you need to go from a faculty
member to their grants or vice versa.

| Column | Type | Description |
|---|---|---|
| `faculty_id` | str | Joins to `faculty.faculty_id`. `"00000"` when the raw `ClientFacultyId` was missing. |
| `faculty_name` | str | Person name as it appears in the grant records. |
| `grant_id` | str | Joins to `grants.grant_id`. |
| `is_pi` | bool | `True` if this faculty member is the lead PI on the grant. |
| `is_copi` | bool | `True` if this faculty member is a co-PI on the grant. `is_pi` and `is_copi` are exact complements. |
| `source` | category | Which raw table the pair came from: `ri_matches`, `grants_with_copi`, or `both`. |
| `hire_date` | datetime | Faculty hire date (copied from `faculty.hire_date`; NaT for supplement rows). |
| `grant_startdate` | datetime | Grant start date (copied from `grants.startdate`). |
| `neu_status` | category | 3-way attribution bucket (see below). |

Rows: **3,144** unique (faculty, grant) pairs (2,368 PI rows, 776 co-PI rows).
Rows where the raw `ClientFacultyId` is missing get `faculty_id = "00000"`;
deduplication then keys on `(personname, grant_id)` for those unresolved
rows so distinct un-IDed PIs remain separate.

#### The three `neu_status` buckets

A grant listed against a faculty member is not always research *done at NEU*.
When a senior PI joins from another institution, their historical grants get
pulled into the reporting system. We split each row by comparing
`grant_startdate` to `hire_date`:

| Bucket | Rule | Rows | $ (dedup) | Interpretation |
|---|---|---:|---:|---|
| `earned_at_neu`     | start ≥ hire date         | 2,098 | $1,408M | Money NEU raised. |
| `prior_institution` | strictly before hire date   |   866 |   $685M | Purely historical; does *not* count as NEU work. |
| `unknown`           | hire or start date missing |   180 |   $153M | Cannot classify. |

```python
fg = pd.read_parquet("data/processed/faculty_grants.parquet")

# "What NEU raised" / "what research is happening at NEU"
#   — the number to put in most external reports.
neu_work = fg[fg["neu_status"] == "earned_at_neu"]

# "Career funding of NEU faculty" — everything, useful for CV-style profiles
career = fg

# Explicit prior-institution attribution (context for talent-acquisition stories)
prior = fg[fg["neu_status"] == "prior_institution"]
```

#### Choosing a funding-credit model

This is the table to use when computing per-faculty funding totals. You
**must pick a credit model** — different choices produce very different
rankings:

```python
import pandas as pd
fg = pd.read_parquet("data/processed/faculty_grants.parquet")
g  = pd.read_parquet("data/processed/grants.parquet")

joined = fg.merge(g[["grant_id", "totaldollars"]], on="grant_id")

# (a) PI-only credit: full $ to lead PI, $0 to co-PIs
pi_only = (joined[joined["is_pi"]]
           .groupby("faculty_name")["totaldollars"].sum())

# (b) Full credit to every contributor (PI and co-PIs each get full amount)
full_credit = joined.groupby("faculty_name")["totaldollars"].sum()

# (c) Fractional split: amount / number of investigators on the grant
n_inv = joined.groupby("grant_id")["faculty_id"].transform("nunique")
joined["fractional"] = joined["totaldollars"] / n_inv
fractional = joined.groupby("faculty_name")["fractional"].sum()
```

---

### 4. `grant_orphaned_abstracts.parquet` — external abstract corpus

Abstract records from `grants-with-abstract` that do **not** match any
Northeastern `grant_id`. These come from an external NSF/NIH crawl that
captures collaborators' and non-NU awards, and are kept separately so
downstream text analyses can optionally use them to enrich vocabulary.

| Column | Type | Description |
|---|---|---|
| `id` | str | Primary key (abstract record id). |
| `personid` | str | Faculty Person ID from source system (see identifier conventions above — **not** joinable to `faculty_id`). |
| `sourceactivityid` | str | Would join to `grants.grant_id` if present — but for orphans, by definition, it does not. |
| `title`, `abstract` | str | Grant title and free-text abstract. |
| `sponsor`, `funding_status`, `type_of_funding`, `funding_source` | str | Funding metadata. |
| `dollar_amount` | float | Dollar amount as entered by faculty. |
| `start_date`, `end_date`, `createddate`, `updateddate`, `deprecateddate` | datetime | Grant / record lifecycle dates. |
| plus other source-system fields | | |

Rows: **5,095** orphan records. Ignore for any NEU-attribution analysis;
useful only for expanded topic-model vocabulary.

---

## Validation report

Each run writes `data/processed/PIPELINE_VALIDATION.txt` with row counts,
hire-date coverage, AAD agency match rate, and per-source pair counts for
the faculty↔grants union.

---

## Note on renamed outputs

The original pipeline produced `grant_faculty.parquet`,
`faculty_id_lookup.parquet`, `grant_text.parquet`, and later
`grant_abstracts.parquet`. Those have been superseded:

- `faculty_id_lookup` → dropped (HR Snowflake is the single source of truth).
- `grant_faculty` / `grant_text` → renamed to `faculty_grants` / merged into `grants`.
- `grant_abstracts` → the matched portion is merged into `grants` (abstract,
  title, funding_status, type_of_funding, funding_source columns); the
  ~5,000 unmatched "orphan" abstract records are kept in
  `grant_orphaned_abstracts.parquet` for anyone who wants the extended
  NSF/NIH corpus.
