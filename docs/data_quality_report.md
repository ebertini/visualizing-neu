# Data Quality Report

**Date:** June 4, 2026  
**Author:** Utkarsh  
**Scope:** Comprehensive audit of 4 raw .xlsx files in `DataSet/`

This report documents data quality issues discovered during initial exploration, cleaning decisions, and normalization plans for pipeline implementation.

---

## Executive Summary

| Issue Category | Count | Severity | Action Required |
|---|---|---|---|
| 100% null columns (drop) | 17 | Low | Drop in pipeline |
| Near-empty columns (98% null) | 1 | Medium | Drop `awarddate` |
| Categorical normalization | 5 fields | High | Standardize |
| Missing join keys | 567 faculty | High | Fuzzy match + manual |
| Duplicate grants | TBD | Medium | Validate in pipeline |
| Outliers (dollars) | TBD | Low | Document, keep |
| Date range issues | 31 years (1995-2026) | Low | Expected |
| Trailing spaces in categories | 1 value | Low | Strip in pipeline |
| Pre-employment grants attributed to NU | Unknown | High | Document caveat; filter if hire dates available |

**Overall Assessment:** Data is analysis-ready after cleaning. No blocking issues; most problems are cosmetic (null columns) or addressable via normalization.

---

## 1. Missingness Analysis

### 1.1 Columns with 100% Null (Drop Immediately)

**`grants-with-abstract.xlsx` (10 columns):**
- `Ongoing`, `Sponsor`, `Proposal/Award/Contract ID`, `University Grant ID`, `URL/Link`
- `AACSB - Type of Intellectual Contribution`, `AACSB - Mission`, `AACSB - Portfolio of Intellectual Contribution`
- `Type of Funding`, `Funding Source`, `Community-engaged activity?`

**Decision:** Drop all 10 columns in pipeline — zero information content.

**`grants-with-coPI.xlsx` (1 column):**
- `DeprecatedDate`

**Decision:** Drop.

**`faculty-list-2025.xlsx` (1 column):**
- `black` (legacy/malformed column)

**Decision:** Drop.

### 1.2 Near-Empty Columns (98% Null)

**`awarddate` / `AwardDate` in both grant files:**
- 98% null; non-null values cap at 2012-09-14 with `1900-01-02` sentinels
- **Root cause:** Likely a legacy field from an older system; newer grants don't populate it

**Decision:** Drop. Use `startdate` / `StartDate` for all temporal analysis.

### 1.3 High Missingness (Keep, but Document)

| File | Column | Null % | Notes |
|---|---|---|---|
| `faculty-list-2025.xlsx` | `Tenure Status` | 57% | **Expected** — only tenure-track faculty have this. Null = non-tenure-track. |
| `grants-with-abstract.xlsx` | `Abstract` | 64% | **Expected** — abstracts weren't retroactively collected for older grants. Coverage improves post-2015. |
| `grants-with-abstract.xlsx` | `UpdatedDate` | 62% | Expected — records never updated since creation have null. |
| `grants-with-coPI.xlsx` | `OrcidId` | 10% | Expected — ORCID adoption grew over time; many senior faculty lack ORCIDs. |
| `grants-with-coPI.xlsx` | `AgencyGrantId` | 3% | Low — mostly complete. Missing = internal/discretionary grants? |

**Decision:** Keep all. Flag in documentation; segment analyses by coverage where needed (e.g., abstract NLP on post-2015 grants).

### 1.4 Collaboration Pair Missingness (College Mapping)

**From notebook cell analysis:**
- After joining `ri_matches` → `faculty-list-2025` via `clientfacultyid` = `Employee ID`:
  - **570 unique faculty in grants table**
  - **Match rate: ~90%** to faculty roster
  - **~57 faculty still unmapped** after manual `UnmatchedFaculty.csv` intervention

**Root causes:**
1. Faculty no longer at NU (departed, emeritus, or adjunct not in 2025 roster)
2. Grants from pre-NU positions (faculty hired mid-career)
3. External collaborators mis-coded as NU faculty

**Decision:** 
- Implement fuzzy name-matching with `rapidfuzz` (threshold 0.85) as first pass
- Flag remaining unmatched as `(External/Former)` category for college-level analyses
- Document caveat: ~10% of grant-faculty rows lack college mapping

---

## 2. Duplicate Detection

### 2.1 Grant-Level Duplicates

**Hypothesis:** Same grant appears multiple times due to multi-PI rows or data system overlaps.

**Tests performed:**
1. **Within `ri_matches_grants_2026`:**
   - 3,146 rows → 2,676 unique `grantid` → **avg 1.17 rows per grant**
   - Expected: multi-PI grants legitimately duplicate
   - **Check:** Do any `grantid` values have inconsistent `grantname` / `totaldollars`?

2. **`grants-with-coPI` vs `ri_matches_grants_2026`:**
   - 2,670 grants vs 2,676 grants → **6-grant delta**
   - ID ranges overlap (38K–1.79M)
   - **To verify:** Are these 6 grants truly new, or data entry corrections?

3. **`grants-with-abstract` join mystery:**
   - 8,075 rows, `Id` range 91K–158K → **completely different ID space**
   - Cannot join on `Id` = `GrantId`
   - **Fallback strategy:** fuzzy-match on `(Title ≈ GrantName) + (Start Date ≈ startdate)`

**Decision:**
- Pipeline should validate no within-grant inconsistencies (same `grantid` → same `totaldollars`, `agencyname`)
- Flag the 6-grant delta for manual review
- Implement fuzzy join for abstracts using `(title, start_date)` tuple matching

### 2.2 Faculty-Level Duplicates (Name Normalization)

**Issues found in `personname` / `PI` fields:**

| Issue | Examples | Count (est.) |
|---|---|---|
| Case inconsistency | `"MELODIA, TOMMASO"` vs `"Melodia, Tommaso"` | High |
| Format mix | `"Last, First"` vs `"First Last"` vs `"First  Middle  Last"` (double spaces) | High |
| Special characters | Accents, hyphens, apostrophes | Medium |
| Spelling variants | Abbreviations, nicknames | Low |

**From notebook:** The `PI` field in structured grant files is "inconsistent format" — likely represents the *lead* PI when the row is a co-PI, not always the person in that row.

**Decision:**
- Normalize all name fields to `Title Case` + `Last, First` format
- Use `rapidfuzz` to create a `faculty_id_lookup` table bridging all name variants
- Add `name_normalized` column to processed tables

---

## 3. Outlier Analysis

### 3.1 Grant Dollar Amounts

**From `ri_matches_grants_2026.totaldollars`:**
- Range: $527 – $38,591,094
- Median: $431,876
- Top grant: $38.6M (likely a multi-year consortium or center grant)

**Validation checks needed:**
1. Validate top 5 largest grants against public records (NSF Award Search)
2. Check if any grants < $10K are data entry errors (should be $10,000 not $10?)
3. Flag grants > $10M as "mega-grants" for separate trend analysis

**Preliminary spot-check (top 3 PIs from notebook):**
- Melodia: 40 grants → reasonable for prolific wireless/networking researcher
- Levine: 36 grants → matches NSF profile
- Kaeli: 33 grants → aligns with long computer architecture career

**Decision:** No obvious errors. Document outliers in data dictionary; no need to cap/filter.

### 3.2 Grant Durations

**From `durationinyears`:**
- Range: 1.0 – 21.08 years
- Median: 3.67 years

**Issues:**
- 21-year grant seems long but plausible (NSF center with multiple renewals coded as one grant?)
- Compare `durationinyears` vs `(enddate - startdate).days / 365` — do they agree?

**Decision:** Validate in pipeline; if disagreement > 10%, compute duration from dates.

### 3.3 Date Ranges

**Grant start dates:** 1995-06-01 → 2026-01-01 (31 years)

**Distribution (from data dictionary):**
- Bulk of grants: 2005–2025
- Pre-2005 tail likely from senior faculty's earlier career grants

**Anomalies to check:**
- Any `startdate` in the future (> June 2026)?
- Any `enddate` < `startdate`?

**Decision:** Pipeline should assert `startdate <= enddate` and `startdate <= today + 1 year`.

---

## 4. Categorical Field Normalization

### 4.1 Academic Rank (35 values → ~8 buckets)

**Current state (from faculty file):**
- 35 unique values including: `"Professor"`, `"Professor (Practice)"`, `"Professor of the Practice"`, `"Associate Teaching Professor"`, `"Assoc Teaching Prof"`, etc.

**Normalization plan:**
```
Tenure-Track Ladder:
  - Professor
  - Associate Professor  
  - Assistant Professor

Teaching Track:
  - Teaching Professor
  - Associate Teaching Professor
  - Assistant Teaching Professor

Other:
  - Lecturer / Senior Lecturer
  - Research Professor / Scientist
  - Visiting / Adjunct
```

**Decision:** Implement `normalize_academic_rank()` in pipeline with regex-based bucketing.

### 4.2 College Names (Trailing Spaces)

**Issue:** `"Medical Research Council "` in `agencyname` has trailing space.

**Decision:** `str.strip()` all categorical text columns in pipeline.

### 4.3 Agency Codes (21 values — OK as-is)

Top agencies by grant count:
- NSF: 2,123 (79%)
- NIH: 568 (21%)
- Others: <100 each

**Decision:** Keep as-is. Document NSF dominance in findings.

### 4.4 Department/College Fields

**Issue:** 80 unique `Academic Unit` values; some are redundant (e.g., "College of Engineering" as both college and unit).

**Decision:** Pipeline should create a clean hierarchy:
- `college` (12 values, from `Superior_Academic_Unit`)
- `department` (derived from `Academic Unit`, with college name stripped)

### 4.5 Binary Flags (0/1 → bool)

**Fields to convert:**
- `IsResearch` / `isresearch`
- `IsCoPI` / `iscopi`
- `IsGovernment` / `isgovernment`

**Decision:** Cast to `bool` in pipeline; improves readability and reduces memory.

---

## 5. Cross-File Join Validation

### 5.1 Confirmed Joins ✓

| Join | Key | Match Rate | Status |
|---|---|---|---|
| `ri_matches` → `faculty-list-2025` | `clientfacultyid` = `Employee ID` | ~90% | **Validated** |
| `grants-with-coPI` → `faculty-list-2025` | `ClientFacultyId` = `Employee ID` | ~90% | **Validated** |
| `ri_matches` ≈ `grants-with-coPI` | `grantid` = `GrantId`, `AAUID` = `PersonId` | 2,670/2,676 grants | **High confidence** |

### 5.2 Unresolved Join ⚠️

**`grants-with-abstract` → structured grant tables:**
- `Id` field (91K–158K range) does NOT match `GrantId` / `grantid` (38K–1.79M)
- `PersonId` ranges overlap but cardinalities differ (1,042 vs 570)

**Recommended approach:**
1. Attempt fuzzy join: `(Title ≈ grantname) + (Start Date ≈ startdate)` with 90% threshold
2. Create `grants_with_text` table with `abstract` and `title` joined on best match
3. Document join success rate; if < 70%, consult advisor

---

## 6. Dtype Coercion Plan

### 6.1 Apply in Week 3 Pipeline

| Column Pattern | Current dtype | Target dtype | Rationale |
|---|---|---|---|
| `*id`, `*Id`, `Employee ID` | int64 | string | IDs are opaque; no arithmetic; saves memory after dedupe |
| `agencycode`, `agencyname`, college/dept | object | category | Low cardinality; 10× memory savings |
| `iscopi`, `isresearch`, `isgovernment` | int64 | bool | Clearer semantics |
| `startdate`, `enddate`, `Start Date`, etc. | datetime64 | datetime64 | Already correct |
| `totaldollars`, `dollarsperyear` | int64 | int64 | Keep as-is (could use float64 if we add inflation adjustment) |

### 6.2 Currency & Inflation

**Current assumption:** All dollar amounts are nominal USD (not adjusted for inflation).

**Decision needed:**
- Add `totaldollars_real` column using CPI deflator (base year = 2025)?
- Or defer to analysis phase and apply on-the-fly?

**Recommendation:** Defer. Inflation adjustment complicates initial exploration; apply during trend analysis as needed.

---

## 7. Known Limitations & Caveats

### 7.1 Temporal Scope

- Data spans **1995–2026** but is heavily skewed toward **2005–2025**.
- Pre-2005 grants may reflect faculty members' careers *before* joining NU.
- **Caveat for analysis:** Cannot isolate "Northeastern-only" grants without hire date data.

### 7.2 Faculty Roster = 2025 Snapshot

- `faculty-list-2025.xlsx` is **current faculty only** — no historical roster.
- Departed faculty with grants will be "unmatched" in college analyses.
- **Recommendation:** Request historical faculty roster with hire/departure dates for complete temporal analysis.

### 7.3 Abstract Coverage

- Only 36% of `grants-with-abstract` rows have `Abstract` populated.
- Coverage likely improves post-2015 but needs empirical validation.
- **NLP analysis consideration:** Restrict topic modeling to grants with abstracts; report coverage by year/college.

### 7.4 Co-PI Relationship Semantics

- `iscopi = 1` rows represent co-PIs, but the `PI` field sometimes contains the *lead* PI's name (not always the person in that row).
- **Network analysis consideration:** Use `(grantid, clientfacultyid)` tuples to build edges; ignore the `PI` string field.

### 7.5 Multi-Institution Grants

- Dataset is filtered to `InstitutionName = "Northeastern University"` rows.
- If a grant has collaborators at other institutions, they don't appear here.
- **Implication:** Collaboration network is NU-internal only; external partnerships invisible.

### 7.6 Pre-Employment Grant Attribution

- All faculty in `ri_matches_grants_2026` are marked with `InstitutionName = "Northeastern University"` regardless of when the grant was awarded.
- Many grants from 1995–2005 were likely obtained by faculty at their *previous* institutions before joining NU.
- Without hire dates, we cannot distinguish "pre-NU" vs "at-NU" grants in temporal analyses.
- **Impact on analysis:** 
  - Institutional productivity metrics (e.g., "NU grants by year") are inflated for early years.
  - Faculty research trajectories cannot be accurately segmented by career stage at NU.
  - Cross-institution comparisons will misattribute grant funding to NU.
- **Mitigation:**
  - Document this caveat prominently in all temporal trend visualizations.
  - If hire dates become available, add `grant_era` flag: `pre_employment`, `at_nu`, or `unknown`.
  - Consider restricting temporal analyses to post-2010 grants (when most current faculty were likely already at NU).
  - Flag grants > 5 years before 2025 faculty roster as "potentially pre-employment" in dashboard tooltips.

---

## 8. Data Pipeline Implementation Requirements

Based on this audit, `src/build_dataset.py` must:

1. **Load & validate:**
   - Assert expected row counts ± 5%
   - Check for new 100% null columns (data provider might add more)

2. **Drop columns:**
   - All 100% null columns listed in §1.1
   - `awarddate` / `AwardDate`
   - Redundant columns: `Superior_Academic_Unit_Code`, `InstitutionName`

3. **Normalize categoricals:**
   - `.str.strip()` all text columns
   - `normalize_academic_rank()` → 8-level hierarchy
   - College/department hierarchy cleanup

4. **Dtype coercion:**
   - IDs → string
   - Flags → bool
   - Low-cardinality text → category

5. **Deduplicate & validate:**
   - Check for within-grant inconsistencies
   - Flag the 6-grant delta between files
   - Validate `startdate <= enddate`

6. **Fuzzy matching:**
   - Implement `rapidfuzz`-based name matching for unmatched faculty
   - Fuzzy join abstracts to grants via `(title, date)` tuple

7. **Output tables (Parquet):**
   - `faculty.parquet` — cleaned roster with normalized ranks
   - `grants.parquet` — deduplicated grant-level table (one row per grant)
   - `grant_faculty.parquet` — long-form grant × faculty with PI/co-PI flags
   - `grant_text.parquet` — abstracts + titles joined to grants
   - `faculty_id_lookup.parquet` — name variant → canonical ID mapping

8. **Validation report:**
   - Row counts before/after
   - Match rates for all joins
   - List of unresolved faculty (for manual review)

---
