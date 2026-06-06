# Data Quality Report — Issues for Northeastern Data Team

**Date:** June 5, 2026  
**Author:** Uttkarsh  
**Audience:** Northeastern University Data Team  
**Purpose:** Document validated data issues requiring institutional clarification

This report separates **confirmed working aspects** of the dataset from **suspected data collection issues** that may require investigation or documentation by the data team.

---

## Executive Summary

### ✅ What Works (No Action Needed)

| Aspect | Status | Notes |
|---|---|---|
| Faculty ID joins | ✓ Validated | `ClientFacultyId` ↔ `Employee ID` joins work with ~90% match rate |
| Grant-faculty relationships | ✓ Validated | PI/co-PI flags (`iscopi`) consistently identify roles |
| Date formatting | ✓ Clean | All date fields parse correctly; `startdate`/`enddate` are reliable |
| Dollar amounts | ✓ Reasonable | No obvious data entry errors; outliers align with public records |
| Grant IDs | ✓ Unique | `GrantId` serves as reliable primary key |

### ⚠️ Suspected Data Collection Issues (Needs Clarification)

| Issue | Severity | Impact on Analysis |
|---|---|---|
| **1. Funding source bias toward NSF/NIH** | High | Underrepresents internal, foundation, and industry grants |
| **2. Pre-employment grants attributed to NU** | High | Inflates historical institutional productivity metrics |
| **3. Faculty roster = 2025 snapshot only** | High | Cannot track departures, sabbaticals, or historical affiliations |
| **4. Grant abstracts missing for 64% of abstract-linked grants** | Medium | 90.1% of `ri_matches` grants can be linked to an abstract, but only 35.6% of those have actual text |

**Overall Assessment:** Dataset is usable but has systematic gaps that need to be documented or corrected for accurate institutional-level analysis.

---

## 1. ⚠️ CRITICAL ISSUE: Funding Source Bias (NSF/NIH Dominance)

**Observation:**
- **NSF:** 2,123 grants (79%)
- **NIH:** 568 grants (21%)
- **All other agencies combined:** <100 grants

**Why this is a problem:**
1. Northeastern faculty secure funding from diverse sources not represented here:
   - Internal university grants
   - Corporate/industry partnerships
   - Private foundations (Gates, Sloan, etc.)
   - State/local government
   - International funding agencies

2. This skew suggests the data **only captures federal research grants** submitted through specific systems (likely NSF's Research.gov and NIH's eRA Commons).

3. **Impact on analysis:**
   - Cannot measure true institutional research productivity
   - Cannot analyze funding diversity across colleges
   - Interdisciplinary grants from non-traditional sources are invisible
   - Business school, law school, and social science grants drastically underrepresented

**Questions for data team:**
- Is this dataset intentionally limited to NSF/NIH grants only?
- Are internal grants, foundation grants, or industry contracts tracked in a separate system?
- Can data from other sources be integrated (e.g., university's financial research accounting system)?

---

## 2. ⚠️ CRITICAL ISSUE: Pre-Employment Grant Attribution

### 2.1 Multi-Institution Grants

**Observation:**
- All faculty in `ri_matches_grants_2026` are marked with `InstitutionName = "Northeastern University"` regardless of when the grant was awarded.
- Dataset spans **1995–2026**, but many current faculty joined NU after 2000
- Example: A 1998 NSF grant attributed to a faculty member who joined NU in 2005
- Many grants from 1995–2005 were likely obtained by faculty at their *previous* institutions before joining NU.
- Without hire dates, we cannot distinguish "pre-NU" vs "at-NU" grants in temporal analyses.
- If a grant has collaborators at other institutions, they don't appear here.
- Collaboration network is NU-internal only; external partnerships invisible.

**Why this is a problem:**
1. **Inflates historical metrics:** Grant funding from 1995–2005 includes grants obtained at other institutions
2. **Cannot segment career stages:** Unable to distinguish "hired with grant" vs "won grant at NU"
3. **Misleads institutional comparisons:** NU's historical productivity appears higher than actual

**Current workaround:**
- We can document this caveat and restrict temporal analyses to post-2010 grants
- However, this arbitrary cutoff loses 15+ years of data

**Questions for data team:**
- Does the university have faculty hire dates available?
- Can we add a `hire_date` field to distinguish pre-employment vs at-NU grants?
- Is there a flag in the source system indicating "external grant transferred to NU"?



---

## 3. ⚠️ MODERATE ISSUE: Faculty Roster = 2025 Snapshot Only

**Observation:**
- `faculty-list-2025.xlsx` contains **only current faculty** as of 2025
- Grants dataset includes **570 unique faculty**, but only ~90% match the roster
- ~57 faculty with grants cannot be mapped to departments/colleges

**Why this is a problem:**
1. Departed, retired, or renamed faculty are invisible — grants cannot be attributed to a college/department.
2. Cannot distinguish active vs. inactive faculty in network analysis.
3. ~10% of grant funding cannot be broken down by college.

**Questions for data team:**
- Can you provide a faculty roster with hire/departure dates and department changes?
- For departed faculty, can we append their last known college/department?

---

## 4. ⚠️ MODERATE ISSUE: Grant Abstract Coverage

### 4.1 Abstract Match Rate (`ri_matches` → `grants-with-abstract`)

| Status | Count | Percentage |
|---|---|---|
| **With abstract record** | 2,410 | 90.1% |
| **Without abstract record** | 266 | 9.9% |
| **Total grants (`ri_matches`)** | **2,676** | 100% |

- 2,676 grants were identified through `ri_matches`.
- 90.1% of those grants can be linked to an entry in the `grants-with-abstract` table.
- 266 grants (9.9%) have **no corresponding entry** in the abstract table at all.

### 4.2 Abstract Text Availability (within `grants-with-abstract`)

| Status | Count | Percentage |
|---|---|---|
| **Has abstract text** | 2,873 | 35.6% |
| **Empty / missing text** | 5,202 | 64.4% |
| **Total rows in `grants-with-abstract`** | **8,075** | 100% |

- Of all rows in the `grants-with-abstract` table, only **35.6% contain actual abstract text**.
- 64.4% of rows exist but have an empty or null abstract field.

**Why this is a problem:**
1. **NLP/topic modeling** is limited to the ~35.6% subset with text — results may not generalize to all grants.
2. **Keyword and theme analysis** will be biased toward grants that include text (potentially skewing toward certain agencies, years, or research areas).
3. The two-layer gap (match rate + text availability) must both be reported when presenting text analysis results.

**Questions for data team:**
- Why do 64.4% of `grants-with-abstract` rows exist without abstract text?
- Can missing abstracts be backfilled from NSF Award Search or NIH RePORTER public APIs?
- Is abstract collection mandatory for current grant submissions?

---

## 5. Summary: Questions for Northeastern Data Team

### Critical Questions (Impact Analysis Validity)

1. **Funding source coverage:**
   - Is this dataset intentionally limited to NSF/NIH federal grants?
   - Can we access data on internal grants, corporate partnerships, and foundation funding?
   - What percentage of total institutional research funding does this dataset represent?

2. **Pre-employment grant attribution:**
   - Can you provide faculty hire dates to segment "pre-NU" vs "at-NU" grants?
   - Is there a flag indicating grants that were transferred from other institutions?

3. **Historical faculty roster:**
   - Can you provide a faculty roster with hire/departure dates and department changes?
   - For departed faculty, can we append their last known college/department?

### Moderate Questions (Expand Analysis Capability)

4. **Grant abstracts:**
   - Is abstract collection mandatory for current submissions?
   - Can we backfill missing abstracts from NSF Award Search or NIH RePORTER?

5. **Additional context:**
   - Are there fields indicating grant subcategories (e.g., CAREER awards, center grants)?
   - Can you clarify the `grants-with-abstract.xlsx` ID space mismatch (different numbering system)?



---

## 8. Caveats We'll Document 

These limitations will be **prominently disclosed** in all deliverables:

1. **Funding analysis caveat:**
   > "This dataset primarily captures federal NSF/NIH grants and may underrepresent internal, foundation, and industry funding. Institutional productivity metrics should not be interpreted as comprehensive research output."

2. **Temporal analysis caveat:**
   > "Grant start dates span 1995–2026, but many pre-2010 grants were obtained by faculty at previous institutions before joining Northeastern. Historical trends may not accurately reflect institutional growth."

3. **Faculty coverage caveat:**
   > "Faculty roster is a 2025 snapshot. ~10% of grant records cannot be mapped to departments due to missing historical affiliation data for departed faculty."

4. **Text analysis caveat:**
   > "Of 2,676 ri_matches grants, 90.1% (2,410) can be linked to an entry in the abstracts table. Across the full abstracts table (8,075 rows), only 35.6% contain actual text. The effective share of grants with usable abstract text is unknown without a direct join, but is at most 90.1%."
- Coverage likely improves post-2015 but needs empirical validation.
- **NLP analysis consideration:** Restrict topic modeling to grants with non-empty abstracts; report coverage by year/college.

---
