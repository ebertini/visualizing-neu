# `src/` — Data Pipeline

## `build_dataset.py`

Reproducible ETL: loads raw `.xlsx` files from `DataSet/`, cleans them, and
writes **4 Parquet files** to `data/processed/`.

```bash
python src/build_dataset.py --input-dir DataSet --output-dir data/processed
```

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
| `faculty_id` (in `faculty.parquet`, `faculty_grants.parquet`) | `Employee ID` in HR Snowflake, `ClientFacultyId` / `clientfacultyid` in the grant tables | Canonical faculty key. |
| `grant_id` (in `grants.parquet`, `faculty_grants.parquet`) | `GrantId` / `grantid` in the raw grant tables | Canonical grant key. |
| `personid` (in `grant_abstracts.parquet` only) | **NOT the same as `faculty_id`.** It comes from a different source system (Faculty Activities DB) and does not overlap with HR `Employee ID` (verified: only 1 of 1,042 abstract `personid`s matches any HR ID). | Do NOT join abstracts to faculty on `personid`. Link abstracts to grants via `title` / `sponsor` / `start_date`, then to faculty via `faculty_grants`. |

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

### 2. `grants.parquet` — grants (one row per grant)

Built from `ri_matches_grants_2026`, deduplicated to one row per `grantid`,
then **left-joined** with the AAD federal-grant-coverage sheet on agency
name (fuzzy-matched, threshold 85). Use this for grant-level analyses
(totals, agency mix, time trends).

| Column | Type | Description |
|---|---|---|
| `grant_id` | str | Primary key. Joins to `faculty_grants.grant_id`. |
| `grantname` | str | Grant title. |
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
| `pi_names_available` | str | From AAD: "Yes" / "No" — whether the agency publishes PI names. |
| `db_coverage` | str | From AAD: year range of database coverage (e.g. "2007–2016"). |
| `copi_available` | str | From AAD: "Yes" / "No" — whether the agency publishes co-PI names. |

Rows: **2,676** (≈ 68% have AAD coverage metadata; the rest are non-federal or unmatched agencies).

---

### 3. `grant_abstracts.parquet` — abstracts and titles

One row per grant from `grants-with-abstract`. Use this for topic modeling
and any text analysis. Note this table's primary key (`id`) is the
**abstract record** id, not the `grantid` from `grants.parquet`; join via
`title` / `sponsor` / `start_date` when you need to link the two.

| Column | Type | Description |
|---|---|---|
| `id` | str | Primary key (abstract record id). |
| `personid` | str | Faculty Person ID from source system — **NOT the same as `faculty_id`**. See "Identifier conventions" above. |
| `sourcetype` | str | Source category. |
| `sourceactivityid` | str | Source activity id. |
| `desiredvisibility` | mixed | Visibility flag from source. |
| `createddate` / `updateddate` / `deprecateddate` | datetime | Record lifecycle dates. |
| `start_date` / `end_date` | datetime | Grant period. |
| `ongoing` | bool/str | Ongoing flag. |
| `title` | str | Grant title. |
| `sponsor` | str | Sponsor name as entered by faculty. |
| `dollar_amount` | float | Dollar amount as entered. |
| `funding_status` | str | Awarded / Pending / etc. |
| `proposal/award/contract_id` | str | Source identifier. |
| `university_grant_id` | str | Internal grant id (sometimes joinable to `grants.grantid`). |
| `url/link` | str | Source URL. |
| `abstract` | str | Free-text abstract. |
| `type_of_funding` | str | Funding type label. |
| `funding_source` | str | Funding source label. |
| `community-engaged_activity?` | str | Y/N flag. |

Rows: **8,075** (abstract text populated on ~36%).

---

### 4. `faculty_grants.parquet` — faculty ↔ grants lookup

The unified lookup. **Union** of (faculty, grant) pairs from
`ri_matches_grants_2026` and `grants-with-coPI`, deduplicated on
`(faculty_id, grant_id)`. Use this whenever you need to go from a faculty
member to their grants or vice versa.

| Column | Type | Description |
|---|---|---|
| `faculty_id` | str | Joins to `faculty.faculty_id`. |
| `faculty_name` | str | Person name as it appears in the grant records. |
| `grant_id` | str | Joins to `grants.grant_id`. |
| `is_copi` | bool | `True` if this faculty member is a co-PI on the grant, `False` if lead PI. |
| `source` | category | Which raw table the pair came from: `ri_matches`, `grants_with_copi`, or `both`. |

Rows: **3,144** unique (faculty, grant) pairs.

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
pi_only = (joined[~joined["is_copi"]]
           .groupby("faculty_name")["totaldollars"].sum())

# (b) Full credit to every contributor (PI and co-PIs each get full amount)
full_credit = joined.groupby("faculty_name")["totaldollars"].sum()

# (c) Fractional split: amount / number of investigators on the grant
n_inv = joined.groupby("grant_id")["faculty_id"].transform("nunique")
joined["fractional"] = joined["totaldollars"] / n_inv
fractional = joined.groupby("faculty_name")["fractional"].sum()
```

---

## Validation report

Each run writes `data/processed/PIPELINE_VALIDATION.txt` with row counts,
hire-date coverage, AAD agency match rate, and per-source pair counts for
the faculty↔grants union.

---

## Note on renamed outputs

The previous pipeline produced `grant_faculty.parquet`,
`faculty_id_lookup.parquet`, and `grant_text.parquet`. Those have been
replaced by `faculty_grants.parquet` and `grant_abstracts.parquet`
(`faculty_id_lookup` is no longer needed — the HR Snowflake roster is the
single source of truth for faculty metadata). Notebooks that load the old
filenames (e.g. [notebooks/05_temporal_trends.ipynb](../notebooks/05_temporal_trends.ipynb),
[notebooks/07_collaboration_network.ipynb](../notebooks/07_collaboration_network.ipynb))
will need to be updated.
