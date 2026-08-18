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
| **1. Possible funding source bias toward NSF/NIH** | High | Underrepresents internal, foundation, and industry grants |
| **2. Pre-employment grants attributed to NU** | High | Inflates historical institutional productivity metrics |
| **3. Faculty roster = 2025 snapshot only** | High | Cannot track departures, sabbaticals, or historical affiliations |
| **4. Grant abstracts missing for 28% of grants** | Medium | Only 72% (1,928 of 2,676) grants have non-empty abstract text available for NLP/topic analysis |

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
   - Other Government entities (DAPRA, Navy, etc.)

2. This skew suggests the data **only captures these two federal research grants** submitted through specific systems (likely NSF's Research.gov and NIH's eRA Commons).

3. **Impact on analysis:**
   - Cannot measure true institutional research productivity
   - Cannot analyze funding diversity across colleges
   - Interdisciplinary grants from non-traditional sources are invisible
   - Business school, law school, and social science grants possibly are drastically underrepresented

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
- Example: A 2017 NSF grant attributed to a faculty member (Prof. Enrico Bertini) who joined NU in 2022
- Without hire dates, we cannot distinguish "pre-NU" vs "at-NU" grants in temporal analyses.
- If a grant has collaborators at other institutions, they possibly don't appear here and there is no way to confirm this since everyone is marked as a NU member. 
  - Collaboration network is NU-internal only; external partnerships invisible.

**Why this is a problem:**
1. **Inflates historical metrics:** Earlier grant fundings listed includes grants obtained at other institutions
2. **Cannot segment career stages:** Unable to distinguish "hired with grant" vs "won grant at NU"
3. **Misleads institutional comparisons:** NU's historical productivity appears higher than actual

**Current workaround:**
- We can document this caveat and restrict temporal analyses to grants listed in later years but this is also not a perfect solution. 
  - However, this arbitrary cutoff loses 15+ years of data
- We can cross reference names with their `linkedin` information, but this requires scrapping information which might yield imprecise informatino. 


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
| **Total grants (`ri_matches`)** | **2,676** | 100% |
| **With abstract record** | 2,410 | 90.1% |
| **Without abstract record** | 266 | 9.9% |

- 2,676 grants were identified through `ri_matches`.
- 90.1% of those grants (2,410) can be linked to an entry in the `grants-with-abstract` table.
- 9.9% of grants (266) have **no record** in the abstract table at all.

### 4.2 Abstract Text Availability (within `grants-with-abstract`)

| Status | Count | Percentage |
|---|---|---|
| **Total rows in `grants-with-abstract`** | **8,075** | 100% |
| **Has abstract text** | 2,873 | 35.6% |
| **Empty / missing text** | 5,202 | 64.4% |

- Of all rows in the `grants-with-abstract` table, only **35.6% contain actual abstract text**.
- 64.4% of rows exist but have an empty or null abstract field.
- Note: The table has 8,075 rows but only 2,676 unique grants (multiple entries per grant exist).

### 4.3 **KEY METRIC:** Grants with Usable Abstract Text

| Status | Count | Percentage |
|---|---|---|
| **Total unique grants** | **2,676** | 100% |
| **With ≥1 non-empty abstract** | 1,928 | 72.0% |
| **No non-empty abstract** | 748 | 28.0% |

This is the most relevant metric for analysis purposes:
- **72% of grants (1,928)** have at least one non-empty abstract available for text analysis
- **28% of grants (748)** either have no record (266) or have records with empty text (482)

**Why this is a problem:**
1. **NLP/topic modeling** is limited to the 72% subset with text — results may not generalize to all grants.
2. **Keyword and theme analysis** will be biased toward grants that include text (potentially skewing toward certain agencies, years, or research areas).
3. The three-layer gap (record match + text availability + unique grants) must all be reported when presenting text analysis results.

**Questions for data team:**
- Why do 64.4% of `grants-with-abstract` rows exist without abstract text?
- Can missing abstracts be backfilled from NSF Award Search or NIH RePORTER public APIs?
- Is abstract collection mandatory for current grant submissions?

---

## 5. Summary: Questions for Northeastern Data Team Meeting

### Critical Questions that Impact Analysis Validity

1. **Funding source coverage:**
   - Is this dataset intentionally favoring NSF/NIH federal grants for a particular reason?
   - Can we access data on internal grants, corporate partnerships, and foundation funding?
   - What percentage of total institutional research funding does this dataset represent?

2. **Pre-employment grant attribution:**
   - Can you provide faculty hire dates to segment "pre-NU" vs "at-NU" grants?
   - Is there a flag indicating grants that were transferred from other institutions?

3. **Historical faculty roster:**
   - Can you provide a faculty roster with hire/departure dates and department changes?
   - For departed faculty, can we append their last known college/department?

### Moderate Questions to Expand Analysis Capability

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
   > "Only 72% (1,928 of 2,676) grants have usable abstract text for topic analysis or text mining purposes."
   > "Abstract availability breakdown: 90.1% have records in the abstracts table, but many records are empty. Among all 8,075 rows in the abstracts table (multiple per grant), only 35.6% contain actual text."
   - Coverage likely improves post-2015 but needs empirical validation.
   - **NLP analysis consideration:** Restrict topic modeling to grants with non-empty abstracts; report coverage by year/college.

---

## 9. New abstract export cross-check (2026-08-17)

The data team dropped a refreshed abstract export, `DataSet/AcAn Grants 2026-08-13.xlsx`
(11,785 rows vs. the pipeline's current `grants-with-abstract.xlsx`, 8,075 rows — identical
25-column schema, not a new table). `scripts/_check_new_abstracts.py` cross-checked it against
the 740 NEU grants that currently have no abstract text, **without adopting it into the
pipeline** (see below for why).

**Findings:**
- **198 of the 740 text-less grants gain usable abstract text** from the new export —
  187 NIH, 11 NSF.
- **The NIH post-2019 coverage cliff narrows but does not close.** Of the NIH/NIH-SUB grants
  missing an abstract in each post-cliff year, the new export recovers: 2020 — 24/29, 2021 —
  29/30, 2022 — 37/42, 2023 — 27/31, 2024 — 23/25, 2025 — 16/16. That's a much larger recovery
  than the pre-check estimate (~198 total was in the right range, but the concentration in
  2020–2025 — 161 of the 198 — was not anticipated going in). It is still not a full fix: a
  public NIH RePORTER backfill (the existing recommendation above) remains the only way to
  close the cliff completely, and the recovered grants still need a topic assignment, since
  the frozen BERTopic corpus (2,676 docs) doesn't include this new text yet.
- **151 already-matched grants get updated/longer abstract text** on top of the 198 net-new
  recoveries (285 raw upload records, pre-grant-matching, gained text on an `Id` shared with
  the old export).
- By BERTopic parent theme, the 198 recoverable grants split: 67 Unassigned, 63 Life Sciences
  & Biomedicine, 40 AI/Robotics/Cognition, 16 Society/Health/Mobility, 5 Physical
  Sciences/Engineering, 4 Education & Learning, 3 Environment/Ocean/Climate — consistent with
  NIH's biomedical/health skew.

**Why not adopted into the pipeline yet:** repointing `src/build_dataset.py` at the new file
would fire roughly eight hardcoded assertions in `src/build_viz_aggregates.py`'s `validate()`
(2,676 grants, $2.18B total, 1,936 grants with abstract text, 808 Unassigned, three
zero-coverage agencies) and would desync the recovered text from the PI's frozen
SPECTER2/UMAP/HDBSCAN output, which can't be re-run in this environment (no HuggingFace network
access — see `CLAUDE.md`). A newly-recovered abstract would have no topic assignment until the
model is re-fit locally. That re-fit, plus deciding how the recovered text feeds the
still-unspecced keyword→classifier method (`docs/TOPIC_CLASSIFICATION_BRAINSTORM.md`), is the
next real step here — this cross-check is meant to make that decision evidence-backed, not to
make it.

**Where this surfaces today:** `docs/TopicVizPrototypes/what_we_can_see.html`'s "What's missing
& where it goes" tab shows the 198 recoverable grants as a distinct segment on the "Abstract
text" row (known / recoverable / still missing), sourced from
`data/processed/new_abstract_recovery.parquet`.

---
