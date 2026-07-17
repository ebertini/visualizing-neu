# Data Dictionary

Living document. Updated as new fields are discovered or normalized.
Generated from `notebooks/01_schema_overview.ipynb` against the raw `.xlsx` files (as of 2026-05-28).

Legend:
- **Type** — observed pandas dtype (post-coercion type planned for processed parquet shown in *italics* when different).
- **Null %** — fraction of rows where the value is missing.
- **Unique** — distinct non-null values.

---

## `faculty-list-2025.xlsx` — Faculty roster

> Current Northeastern faculty directory. One row per faculty member. Primary source for college/department affiliation, academic rank, tenure status, and country. Join to grants tables via `Employee ID` = `clientfacultyid`.

Shape: **2,232 rows × 9 cols**. Single sheet (`Sheet1`). One row per current faculty member.

| Column | Type | Null % | Unique | Notes |
|---|---|---|---|---|
| `Employee ID` | int64 → *string* | 0% | 2,232 | Primary key in this file. Range 26,501 – 3,189,672 (non-sequential; treat as opaque ID). **= `ri_matches_grants_2026.clientfacultyid` and `grants-with-coPI.ClientFacultyId`** — confirmed cross-file join key to both structured grants tables. |
| `Superior_Academic_Unit` | object → *category* | 0% | 12 | Top-level college. Top 5: College of Engineering (356), Science (332), Social Sciences & Humanities (304), Bouvé Health Sciences (269), D'Amore-McKim Business (215). Also includes NU London (126) and Mills College (40). |
| `Superior_Academic_Unit_Code` | object → *category* | 0% | 12 | `CCxxx` code, 1:1 with `Superior_Academic_Unit`. Redundant — drop or use as join key. |
| `Academic Unit` | object → *category* | 0% | 80 | Department / school within a college. Examples: Khoury College of Computer Sciences (210), Electrical and Computer Engineering (98), Mechanical and Industrial Engineering (81). |
| `Academic Track Type` | object → *category* | 0% | 7 | Non-Tenure (1,079), Tenure Track (958), Teaching and Scholarship (81), Visiting Lecturers (53), Teaching and Research (47), Teaching Only (10), Research Only (4). |
| `Academic Rank` | object → *category* | 0% | 35 | Free-form rank string. Top 5: Professor (433), Associate Professor (268), Assistant Professor (257), Associate Teaching Professor (251), Assistant Teaching Professor (232). Likely needs normalization (collapse 35 → ~8 buckets) in Week 2. |
| `Tenure Status` | object → *category* | 57% | 3 | Tenured (646), Tenure Track (288), Tenure On Entry (24). Null is expected for non-tenure-track faculty — interpret null as "not on a tenure path" rather than missing. |
| `Location_Address_Country` | object → *category* | 0% | 3 | USA (2,054), United Kingdom (142, NU London), Canada (36, Mills/Oakland — verify). |
| `black` | float64 | 100% | 0 | **Drop.** Empty legacy column. |

---

## `grants-with-abstract.xlsx` — Grants with text content

> Largest grant file by row count, but primarily useful for its `Title` and `Abstract` text fields. Structured financial/agency fields are mostly null — those live in the structured grant tables. Use as a text-enrichment join.

Shape: **8,075 rows × 25 cols**. Sheet: `Grants with abstract (2).csv`. **Role:** text-content companion to the structured grant tables; differentiator is `Title` + `Abstract`. Many structured fields are 100% null on purpose (live in `grants-with-coPI` / `ri_matches`). Use as enrichment, not as fact table.

| Column | Type | Null % | Unique | Notes |
|---|---|---|---|---|
| `Id` | int64 | 0% | 8,075 | Primary key in this file. Range 91,518 – 158,405 — **distinct ID space** from `grants-with-coPI.GrantId` (38,584 – 1,795,307). Join path TBD (advisor question #3). |
| `PersonId` | int64 → *string* | 0% | 1,042 | **⚠ Column-name collision.** This `PersonId` is a **different ID space** from `grants-with-coPI.PersonId`. Values are from an internal profile-upload system (probably Symplectic Elements / internal-CV database); range overlaps numerically with the coPI file's values but the two do NOT share meaning — confirmed 0% direct-value overlap with `faculty.faculty_id`, `faculty_id_lookup.faculty_id`, and `faculty_grants.faculty_id` in [`scripts/_orphan_faculty_overlap.py`](../scripts/_orphan_faculty_overlap.py). Cannot be joined directly. Reachable to `faculty_id` only through the observational bridge in [`personid_to_faculty.parquet`](../data/processed/personid_to_faculty.parquet). See [`ID_RECONCILIATION.md`](ID_RECONCILIATION.md). |
| `Sourcetype` | object → *category* | 0% | 2 | `Institution` (4,492) vs `AA` (3,583). Likely "Institution-reported" vs "Academic Analytics" feed; investigate impact on duplication. |
| `SourceActivityId` | object | <1% | 7,475 | Upstream source-system ID. Possible bridge to `grants-with-coPI.GrantId` / `AgencyGrantId` — check in Week 2. |
| `DesiredVisibility` | int64 → *category* | 0% | 2 | Values: 0, 2. Display-permission flag from the source system. Ignore for analysis. |
| `CreatedDate` | datetime64 | 0% | 4,356 | Record-creation timestamp (2018-02-27 → 2025-11-30). Reflects when the row entered the system, not when the grant happened. |
| `UpdatedDate` | datetime64 | 62% | 1,692 | Record-update timestamp (2019-11 → 2026-01). Null = never updated since creation. |
| `DeprecatedDate` | float64 | 100% | 0 | **Drop.** |
| `Start Date` | datetime64 | 0% | 1,569 | Grant start (1995-06-01 → 2026-01-01). **Use this for time-series.** |
| `End Date` | datetime64 | <1% | 795 | Grant end (1998-05-31 → 2031-09-30). |
| `Ongoing` | float64 | 100% | 0 | **Drop.** |
| `Title` | object | 0% | 5,614 | Grant title — **key text field**. Some generic values ("Grant" appears 35×) and repeats reflect program continuation. |
| `Sponsor` | float64 | 100% | 0 | **Drop.** Sponsor info lives in `AgencyName` in the other files. |
| `Dollar Amount` | int64 | 0% | 2,384 | **Unreliable.** Range 0 – 39,845,551 with **median = 0** — most rows are zero. Prefer `TotalDollars` / `DollarsPerYear` from the structured files. |
| `Funding Status` | float64 → *category* | 28% | 2 | Values 1.0, 2.0. Semantics TBD (likely funded / pending). |
| `Proposal/Award/Contract ID` | float64 | 100% | 0 | **Drop.** |
| `University Grant ID` | float64 | 100% | 0 | **Drop.** |
| `URL/Link` | float64 | 100% | 0 | **Drop.** |
| `Abstract` | object | 64% | 2,234 | **Key text field** — feeds Week 8 NLP / topic modeling. Only ~36% of grants have abstracts; analysis must report and account for this coverage. |
| `AACSB - Type of Intellectual Contribution` | float64 | 100% | 0 | **Drop.** D'Amore-McKim business-school-specific field, never populated. |
| `AACSB - Mission` | float64 | 100% | 0 | **Drop.** |
| `AACSB - Portfolio of Intellectual Contribution` | float64 | 100% | 0 | **Drop.** |
| `Type of Funding` | float64 | 100% | 0 | **Drop.** |
| `Funding Source` | float64 | 100% | 0 | **Drop.** |
| `Community-engaged activity?` | float64 | 100% | 0 | **Drop.** |

**Keep after pruning:** `Id`, `PersonId`, `Sourcetype`, `SourceActivityId`, `Start Date`, `End Date`, `Title`, `Abstract`, (optionally `CreatedDate`, `Funding Status`).

---

## `grants-with-coPI.xlsx` — Structured grants with PI/co-PI rows

> Structured grant fact table with funding amounts, agency, and PI/co-PI designation. Likely an earlier export of the same underlying data as `ri_matches_grants_2026` — it has 10 fewer rows and 6 fewer distinct grants. Use for diff/verification only; prefer `ri_matches_grants_2026` for analysis.

Shape: **3,136 rows × 22 cols**. Sheet: `Grants with co PI indicator (1)`. **Grain:** one row per (grant × faculty member) — only **2,670 distinct `GrantId`s** (avg ~1.17 faculty per grant). All institution = Northeastern.

| Column | Type | Null % | Unique | Notes |
|---|---|---|---|---|
| `GrantId` | int64 | 0% | 2,670 | Grant identifier in this file. Range 38,584 – 1,795,307. Duplicates across rows = multi-faculty grants. **Composite key:** `(GrantId, PersonId)`. |
| `AgencyCode` | object → *category* | 0% | 21 | Funder code. Top: NSF (2,123), NIH (568), NIH-SUB (104), Navy (87), NASA (49), Army (48), DOE (37), AFRO (31), NEH (22). Long tail of UK funders (Wellcome, BBSRC, MRC, ESRC, AHRC). 1:1 with `AgencyName`. |
| `AgencyGrantId` | object | 3% | 2,572 | External award number (e.g., NSF 1638302). Best join key to public funder databases. |
| `GrantName` | object | 0% | 2,459 | Title of the grant. Some generic ("Grant" 28×). |
| `DurationInYears` | float64 | 0% | 170 | 1.0 – 20.08, median 3.33. Compute as `(EndDate - StartDate) / 365` if it disagrees. |
| `AwardDate` | datetime64 | 98% | 14 | **Effectively unusable** — almost entirely null and the few non-null values cap at 2012-09-14 (with `1900-01-02` sentinels). Use `StartDate` instead. |
| `DollarsPerYear` | int64 | 0% | 2,322 | USD/year. Range 527 – 3,625,548; median 126,357. |
| `StartDate` | datetime64 | 0% | 767 | Grant start (1995-06-01 → 2026-01-01). **Primary time-series axis.** |
| `EndDate` | datetime64 | 0% | 440 | Grant end (1998-05-31 → 2030-09-30). |
| `PersonId` | int64 → *string* | 0% | 567 | **⚠ Column-name collision** with `grants-with-abstract.PersonId` — that column holds a **different** internal ID space. Here `PersonId` = **`AAUID`** (Academic Analytics User ID; renamed in [`ri_matches_grants_2026.xlsx`](../DataSet/ri_matches_grants_2026.xlsx)). 1:1 with `ClientFacultyId` at all 570 observed pairs. |
| `ClientFacultyId` | int64 → *string* | 0% | 567 | Same values as HR `Employee ID` (= canonical `faculty_id` in processed data). This is the join key to the faculty roster. |
| `PersonName` | object | 0% | 567 | `LAST, FIRST [MIDDLE]` form (e.g., `MELODIA, TOMMASO`). Use for human-readable display and as fallback fuzzy-join key. |
| `OrcidId` | object | 10% | 473 | ORCID identifier — globally unique researcher ID. **Best cross-institution join key**, where present. |
| `InstitutionName` | object | 0% | 1 | Always "Northeastern University". **Drop** (constant). |
| `PI` | object | 0% | 1,496 | Full PI string — **inconsistent format** ("Tommaso  Melodia", "Cheng, Hai-Ping", "MAKOWSKI, LEE"). Needs normalization. May represent the lead PI when this row is a co-PI. |
| `TotalDollars` | int64 | 0% | 2,170 | Total grant value, USD. Range 527 – 38,461,679; median 429,134. **Use for total funding analyses** (not `Dollar Amount` from abstract file). |
| `IsResearch` | int64 → *bool* | 0% | 2 | 0/1 flag. |
| `AgencyName` | object → *category* | 0% | 21 | Human-readable funder. 1:1 with `AgencyCode`. |
| `CountryCode` | object → *category* | 0% | 2 | US (3,128) / UK (8). |
| `IsGovernment` | int64 → *bool* | 0% | 2 | 0/1 — distinguishes federal vs private/foundation sponsors. |
| `IsCoPI` | int64 → *bool* | 0% | 2 | 0 = lead PI on this row, 1 = co-PI. Drives the collaboration-network construction (Week 7). |
| `StartDateYear` | int64 | 0% | 30 | Year extracted from `StartDate`. 1995 – 2026. Convenience column; derivable. |

---

## `ri_matches_grants_2026.xlsx` — Research-interest matched grants ⭐ PRIMARY TABLE

> Most likely a newer export of the same underlying system as `grants-with-coPI`, with 10 additional rows and ~6 more grants. Snake_case column names and `AAUID` in place of `PersonId` are the only structural differences. **Using this as the canonical structured grants table.** Use this file as the source of truth for all grant analyses maybe. `grants-with-coPI` should only be used for diffing/verification.

Shape: **3,146 rows × 22 cols**. Sheet: `ri_matches_grants_2026-2-1_3-50`. **Schema is essentially identical to `grants-with-coPI`** but with snake_case columns and 10 additional rows. Same grain (one row per grant × faculty), 2,676 distinct grants.

| Column | Type | Null % | Unique | Notes |
|---|---|---|---|---|
| `grantid` | int64 | 0% | 2,676 | Same range/semantics as `grants-with-coPI.GrantId`. 2,670 of 2,676 likely overlap; ~6 new grants here. |
| `agencycode` | object → *category* | 0% | 21 | Same vocabulary as `grants-with-coPI.AgencyCode`. Counts differ by ≤8 per category. |
| `agencygrantid` | object | 3% | 2,578 | Same as `grants-with-coPI.AgencyGrantId`. |
| `grantname` | object | 0% | 2,468 | Same as `grants-with-coPI.GrantName`. |
| `durationinyears` | float64 | 0% | 175 | 1.0 – 21.08, median 3.67. |
| `awarddate` | datetime64 | 98% | 14 | Same unusable column. |
| `dollarsperyear` | int64 | 0% | 2,332 | 527 – 3,625,548; median 124,962. |
| `startdate` | datetime64 | 0% | 769 | 1995-06-01 → 2026-01-01. |
| `enddate` | datetime64 | 0% | 451 | 1998-05-31 → 2030-09-30. |
| `AAUID` | int64 → *string* | 0% | 570 | **Renamed from `PersonId`** in this file. Same value range. |
| `clientfacultyid` | int64 → *string* | 0% | 570 | **= `faculty-list-2025.Employee ID`.** Confirmed cross-file join key to the faculty roster. Same as `grants-with-coPI.ClientFacultyId`. |
| `orcid` | object | 10% | 476 | Same as `grants-with-coPI.OrcidId`. |
| `personname` | object | 0% | 570 | Same as `grants-with-coPI.PersonName`. |
| `institutionname` | object | 0% | 1 | Always "Northeastern University". **Drop.** |
| `pi` | object | 0% | 1,504 | Same as `grants-with-coPI.PI`. |
| `totaldollars` | int64 | 0% | 2,174 | 527 – 38,591,094; median 431,876. |
| `isresearch` | int64 → *bool* | 0% | 2 | 0/1. |
| `agencyname` | object → *category* | 0% | 21 | 1:1 with `agencycode`. Note: `"Medical Research Council "` has a trailing space (clean in Week 2). |
| `countrycode` | object → *category* | 0% | 2 | US (3,138) / UK (8). |
| `isgovernment` | int64 → *bool* | 0% | 2 | 0/1. |
| `iscopi` | int64 → *bool* | 0% | 2 | 0/1. |
| `startdateyear` | int64 | 0% | 30 | 1995 – 2026. |

**Confirmed:** `ri_matches_grants_2026` is the newer/superset version and is the canonical structured grants table. Use `grants-with-coPI` only to diff/verify.

---

## Cross-file join keys (working hypotheses)

| Join | Candidate key(s) | Confidence | Notes |
|---|---|---|---|
| `grants-with-coPI` ↔ `ri_matches_grants_2026` | `GrantId` = `grantid`; `PersonId` = `AAUID` | High | Schemas mirror each other; row counts and value ranges align. |
| structured grants ↔ `faculty-list-2025` | `clientfacultyid` (`ri_matches`) / `ClientFacultyId` (`grants-with-coPI`) **= `Employee ID`** (confirmed) | **High** | Confirmed join key. `faculty-list-2025.Employee ID` is equivalent to `clientfacultyid` / `ClientFacultyId` in both structured grant files. |
| `grants-with-abstract` ↔ structured grant files | `SourceActivityId` = `grantid` (`ri_matches`) / `GrantId` (`coPI`). Split into matched / orphaned in [`build_dataset.py`](../src/build_dataset.py); ~37% match rate. | **High** | `SourceActivityId` **is** the grant id in the structured tables when it matches. `Id` is a distinct file-local key; do not join on it. |
| `grants-with-abstract.PersonId` ↔ any faculty ID | **Zero direct overlap** (verified in [`scripts/_orphan_faculty_overlap.py`](../scripts/_orphan_faculty_overlap.py)). | **N/A** | `abstract.PersonId` is a **different ID space** from every other faculty identifier in the corpus. Reach `faculty_id` via the observational bridge in [`personid_to_faculty.parquet`](../data/processed/personid_to_faculty.parquet), not by direct join. Same column name as `grants-with-coPI.PersonId`, different meaning. |
| External agency databases (NSF, NIH) | `AgencyGrantId` + `AgencyCode` | High | For enrichment in later phases if needed. |

---

## ID crosswalk — the four identifiers for one person

> **Read [`ID_RECONCILIATION.md`](ID_RECONCILIATION.md) before using any of these fields.**

One person (e.g. Chris Martens) appears in the raw data under **four distinct
identifiers** originating from three source systems:

| ID space | Raw column(s) | Example (Martens) | Owner / origin |
|---|---|---:|---|
| HR `Employee ID` / `ClientFacultyId` — the **canonical `faculty_id`** used in every processed parquet | `faculty-list-2025.Employee ID`, `ri_matches.clientfacultyid`, `grants-with-coPI.ClientFacultyId` | **2963712** | Northeastern HR |
| `AAUID` — external vendor ID (unused in analysis; preserved on `faculty_id_lookup.parquet` for future enrichment) | `ri_matches.AAUID`, `grants-with-coPI.PersonId` | 799620 | Academic Analytics (external vendor) |
| `abstract.PersonId` — internal upload-system ID; **not directly joinable to anything else** | `grants-with-abstract.PersonId` | 110082 | Internal abstract-upload system |

**The `PersonId` collision:** `grants-with-coPI.xlsx` and
`grants-with-abstract.xlsx` both have a column named `PersonId`, but they
hold **different ID spaces** (`AAUID` vs the internal upload-system ID).
They cannot be joined on `PersonId`. Same name, different meaning.

**Reaching from `abstract.PersonId` to canonical `faculty_id`** requires the
observational bridge captured in
[`data/processed/personid_to_faculty.parquet`](../data/processed/personid_to_faculty.parquet)
— walks through `SourceActivityId → grant_id → faculty_grants.faculty_id`,
resolves via strict 100% co-occurrence majority vote, and marks each row
with a `resolution_method` audit column. Build details in
[`ID_RECONCILIATION.md`](ID_RECONCILIATION.md#4--why-the-orphan-bridge-in-personid_to_facultycsv-still-works).

---## Empirical questions to answer in Week 2 (no advisor input needed)

- Confirm currency is USD throughout (sample a few NSF awards against public records).
- Calendar year vs fiscal year for `StartDate` (compare distribution of `Start Date.month`).
- Whether to apply an inflation deflator (CPI) for 20-year comparisons.
- Reconcile `DurationInYears` vs `EndDate - StartDate`.
- Verify the 6-grant delta between `grants-with-coPI` and `ri_matches_grants_2026`.
- Quantify abstract coverage by year/college (only 36% of `grants-with-abstract` rows have an `Abstract`).
