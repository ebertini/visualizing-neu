# NIH RePORTER Backfill Report (M5a)

NIH-family (NIH / NIH-SubAward / HHS / VA) text-less grants going in: **320**
Recovered abstracts for those grants: **311** (97.2% of the above)
  (plus 340 grants that already had text and got an updated/longer version — not counted in the % above)
  - via `nih_reporter` (record's own text): 646
  - via `nih_reporter_parent` (parent-center fallback — EXCLUDED from the fit by default): 5

## By funder
- National Institutes of Health: 529
- National Institutes of Health - SubAward: 105
- Dept. Health and Human Services: 17

## Unmatched / unparsed
- award numbers that didn't parse: 4
- cores with no RePORTER record found: 19

## Awardee-organization audit
Grants where RePORTER's own `organization.org_name` is NOT Northeastern (independent check on the pre-hire attribution caveat): **250**

## Investigator proposals
Raw multi-PI rows extracted: 841
Matched to a faculty_id (score >= 90): 433
  - proposed as co-PI (not the contact PI): 41

NOT auto-merged into grants.parquet or faculty_grants.parquet — see module
docstring. Review backfill_nih_abstracts.parquet / investigator_faculty_proposals.parquet before adopting.
