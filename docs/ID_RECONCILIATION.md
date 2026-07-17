# Faculty ID Reconciliation

**Status:** decisions recorded (see §6); pipeline updated accordingly.
**Trigger:** while building the orphan-abstract bridge we discovered the raw
datasets carry three distinct identifiers for the same person, plus a column
name (`PersonId`) that means different things in different files.
**Concrete example throughout:** Chris Martens (Robin), Khoury College of
Computer Sciences → College of Arts, Media and Design (per HR).

---

## 1 · What we found

Chris Martens appears in the raw data under **four different identifiers**
across three source systems:

| Raw file | Column name | Value for Martens | What it actually is |
|---|---|---|---|
| [`HR Snowflake faculty list…xlsx`](../DataSet/HR%20Snowflake%20faculty%20list%202025%20fall%20update%206.15.2026.xlsx) | `Employee ID` | **2963712** | Northeastern HR employee ID (authoritative NEU-owned identifier). |
| [`ri_matches_grants_2026.xlsx`](../DataSet/ri_matches_grants_2026.xlsx) | `clientfacultyid` | **2963712** | Same value as HR `Employee ID`. |
| [`ri_matches_grants_2026.xlsx`](../DataSet/ri_matches_grants_2026.xlsx) | `AAUID` | 799620 | **Academic Analytics User ID** — from the vendor at [academicanalytics.com](https://academicanalytics.com/) that Northeastern uses to enrich faculty profiles. |
| [`grants-with-coPI.xlsx`](../DataSet/grants-with-coPI.xlsx) | `ClientFacultyId` | **2963712** | Same as HR `Employee ID`. |
| [`grants-with-coPI.xlsx`](../DataSet/grants-with-coPI.xlsx) | `PersonId` | 799620 | **Same value as `AAUID`** — just renamed. |
| [`grants-with-abstract.xlsx`](../DataSet/grants-with-abstract.xlsx) | `PersonId` | 110082 | A **different** internal ID from whatever profile-upload system produced the abstract records (probably a Symplectic Elements / internal-CV database). |

Three distinct identifiers, one person:

| ID space | Value for Martens | Owned by |
|---|---:|---|
| HR `Employee ID` / `ClientFacultyId` | **2963712** | Northeastern HR / core data |
| `AAUID` / `grants-with-coPI.PersonId` | 799620 | Academic Analytics (external vendor) |
| `grants-with-abstract.PersonId` | 110082 | Internal abstract-upload system |

There is **no lookup table** in the raw data linking these three ID spaces
directly. `[data/processed/faculty_id_lookup.parquet](../data/processed/faculty_id_lookup.parquet)` maps `faculty_id → college`, nothing more.

Verified by running [scripts/_id_reconciliation.py](../scripts/_id_reconciliation.py).

---

## 2 · The confusing part: `PersonId` collision

Both `grants-with-coPI.xlsx` and `grants-with-abstract.xlsx` have a column
named `PersonId`, but they hold **different ID spaces**:

- `grants-with-coPI.xlsx` / `PersonId` = **`AAUID`** = 799620 for Martens
- `grants-with-abstract.xlsx` / `PersonId` = **internal-profile-system ID** = 110082 for Martens

They share a column name, not a value system. This is the single most
likely tripwire for anyone new to this dataset. A reasonable person would
assume `PersonId` in the two grant files could be joined directly. **It
cannot.** Same column name, different upstream sources, non-overlapping
ID spaces (we verified zero overlap in [scripts/_orphan_faculty_overlap.py](../scripts/_orphan_faculty_overlap.py) —
`personid` in orphans has 0 overlap with any of `faculty.faculty_id`,
`faculty_id_lookup.faculty_id`, or `faculty_grants.faculty_id`).

---

## 3 · What [build_dataset.py](../src/build_dataset.py) actually does

The pipeline uses `clientfacultyid` (= HR `Employee ID` = **2963712** for
Martens) as the canonical `faculty_id`. This is a good choice because it's
the only ID that:

- Comes from an **authoritative NEU-owned system** (HR).
- Appears in **both** `ri_matches` and `grants-with-coPI` under the same
  name and same values.
- Has a name attached in `ri_matches` / `coPI` (via `personname`).

The other two IDs are **not used** by the pipeline:

- `AAUID` (= `coPI.PersonId` = 799620) is silently dropped — it's an external
  vendor's ID space that we have no downstream use for.
- `abstract.PersonId` (= 110082) is kept only inside
  [`grant_orphaned_abstracts.parquet`](../data/processed/grant_orphaned_abstracts.parquet)
  because those rows couldn't be joined via `sourceactivityid`.

The three matched-file join graph the pipeline actually walks:

```
HR Snowflake                ri_matches / grants-with-coPI
─────────────               ────────────────────────────────
Employee ID  ─── equals ─── ClientFacultyId
                                  │
                                  ▼
                            faculty_grants.faculty_id  (canonical)
                                  ▲
grants-with-abstract        │
──────────────────          │
SourceActivityId ── equals ─┤─── grants.grant_id
                            │
                            └── (used indirectly via grant_id, not PersonId)
```

`abstract.PersonId` never enters that graph — the abstract-file records are
joined to grants by `SourceActivityId → grant_id`. The matched half becomes
part of `grants.parquet`; the unmatched half becomes
`grant_orphaned_abstracts.parquet`.

---

## 4 · Why the orphan bridge works — and how it's persisted

The bridge in the pipeline
([`build_dataset.build_personid_to_faculty`](../src/build_dataset.py)) does
not try to translate `abstract.PersonId → AAUID` or
`abstract.PersonId → ClientFacultyId` directly (there is no such lookup).
Instead it walks the graph through the grants themselves, using the
**matched** subset of `grants-with-abstract.xlsx` as an observational bridge:

```
abstract.PersonId (110082)
   │
   │  via abstract.SourceActivityId
   ▼
grant_id (1471424, 1550106, …)
   │
   │  via faculty_grants (built from ri_matches using ClientFacultyId)
   ▼
faculty_id (2963712) = HR Employee ID = "MARTENS, CHRIS ROBIN"
```

Every arrow in that chain is a real key-to-key join over data that already
exists in the pipeline. For Martens the bridge collapses to a single
faculty candidate on 5/5 shared grants (see [scripts/_bridge_examples.py](../scripts/_bridge_examples.py)),
so `personid 110082 → faculty_id 2963712` is unambiguous.

For 315 of 639 personids (49%) the bridge collapses to one candidate; for
the remaining 324 (51%) it produces 2–4 candidates because a single
personid uploaded grants that involve multiple NEU faculty (co-PIs). This
is a downstream artefact, not an ID-space problem — the strict 100%
majority-vote rule adopted in §6 resolves it safely (verified on the Amato
example below).

---

## 5 · Worked examples

### 5.1 Clean case — `abstract.PersonId 110082` → Martens

5 matched abstracts, all 5 grants attributed to a single faculty:

| grant_id | title | faculty | role |
|---|---|---|---|
| 1550106 | Simulating Social Influence…Emergent Narratives | MARTENS, CHRIS ROBIN | PI |
| 1471424 | CAREER: Explorable Formal Models of Privacy Policies… | MARTENS, CHRIS ROBIN | PI |
| 1306866 | CRII: SHF: Supporting Domain-Specific Inquiry… | MARTENS, CHRIS ROBIN | PI |
| 1460237 | Intelligent Support for Creative, Open-ended Programming Projects | MARTENS, CHRIS ROBIN | co-PI |
| 1675413 | FMitF Track I: Formal Methods in Software Support… | MARTENS, CHRIS ROBIN | co-PI |

`MARTENS, CHRIS ROBIN` co-occurs on **5/5** shared grants → 100% → single
unambiguous faculty.

**Bonus finding:** the one orphan-with-abstract row under this personid is
titled *"CAREER: Explorable Formal Models of Privacy Policies and
Regulations"* (orphan `sourceactivityid = 1382460`). That's nearly
identical to matched grant `1471424` (same title, same PI). This orphan is
almost certainly a **duplicate upload of an existing NEU grant under a
different `sourceactivityid`**. Similar duplicates likely exist across the
403 usable orphans and would inflate any "we recovered N new abstracts"
count. Needs to be quantified before we lean on it.

### 5.2 Ambiguous case — `abstract.PersonId 15082` → 4 candidates

11 matched abstracts, all on multi-agent reinforcement learning / robotics.
The bridge stores 4 faculty candidates, but co-occurrence tells the story:

| Candidate | Co-occurs on | Share |
|---|---:|---:|
| **AMATO, CHRISTOPHER JD** | 11 / 11 | **100%** |
| TRYPAKIS, STAVROS | 2 / 11 | 18% |
| MARSELLA, STACY C | 1 / 11 | 9% |
| PLATT, ROBERT J | 1 / 11 | 9% |

Amato uploaded 11 abstracts: 8 solo grants + 3 collaborations where a
co-PI got attributed alongside him. The **strict 100% rule** in
[`build_personid_to_faculty`](../src/build_dataset.py) requires exactly
one candidate at 100% co-occurrence; Amato is the only faculty on all 11
grants, so he alone survives the vote. Persisted in
`personid_to_faculty.parquet` as:

```
personid=15082  faculty_id=1234224  resolution_method=strict_100pct
n_shared_grants=11  n_candidate_faculty_ids=4  winner_share=1.0
```

---

## 6 · Decisions & what changed in the pipeline

**Confirmed / not broken:**

- The `faculty_id = 2963712` we've been using for Martens throughout is
  correct. `faculty.parquet`, `faculty_grants.parquet`, and every
  downstream analysis use the right canonical ID.
- The orphan → faculty bridge is valid; the strict 100% majority-vote
  variant is now the pipeline default.

**Decisions (all five resolved):**

1. ✅ **Document `PersonId` collision** in
   [`docs/data_dictionary.md`](data_dictionary.md). Done — the `PersonId`
   entries in both `grants-with-abstract` and `grants-with-coPI` sections
   now carry an explicit "column-name collision" warning, the cross-file
   join-keys table calls out that `abstract.PersonId` has **zero direct
   overlap** with any faculty ID, and a new *"ID crosswalk — the four
   identifiers for one person"* section maps everything in one place.
2. ✅ **Preserve `AAUID`.** New [`faculty_id_lookup.parquet`](../data/processed/faculty_id_lookup.parquet)
   (built by [`src/build_dataset.py`](../src/build_dataset.py) via
   `build_faculty_id_lookup`) is a proper crosswalk: one row per canonical
   `faculty_id`, with `college`, `academic_unit`, and the optional
   `aauid` populated for the 557 faculty (24.8%) who appear in
   `ri_matches`. AAUID is not used as a join key anywhere; it exists as an
   optional handle for future enrichment with Academic Analytics data.
3. ⏸ **Duplicate-vs-update check deferred.** The Martens example in §5.1
   suggests some orphan-with-abstract rows may be updates to older
   grants rather than fresh records. Before any "fold into the topic
   corpus" step, we still need a title + PI + date match against
   existing NEU grants. Not implemented yet; called out here so it isn't
   forgotten.
4. ✅ **Strict 100% majority-vote disambiguation.** New
   [`personid_to_faculty.parquet`](../data/processed/personid_to_faculty.parquet)
   (built by `build_personid_to_faculty`) uses the safe rule: a personid
   resolves to a `faculty_id` **only when exactly one candidate faculty
   co-occurs on every one of that personid's shared grants**. Anything
   less is flagged, not guessed. Results on the full 1,042 personids:

   | `resolution_method` | Count | Share |
   |---|---:|---:|
   | `strict_100pct` (resolved) | 538 | 51.6% |
   | `ambiguous_no_winner` (had shared grants, no candidate at 100%) | 101 | 9.7% |
   | `no_shared_grants` (personid appears only in orphan half) | 403 | 38.7% |

   Verified spot-checks:
   - Martens (personid `110082`) → `faculty_id = 2963712`, 5 shared
     grants, 1 candidate, share = 1.0 (clean case).
   - Amato (personid `15082`) → `faculty_id = 1234224`, 11 shared
     grants, **4 candidates**, share = 1.0. The strict rule correctly
     picks Amato and rejects the three co-PIs (Trypakis, Marsella,
     Platt) whose shares were 18%, 9%, 9% respectively.
5. ✅ **Persist the bridge with an audit column.** The new parquet has
   `resolution_method` (categorical), `n_shared_grants`, `n_candidate_faculty_ids`,
   and `winner_share` alongside `personid` and `faculty_id`. Downstream
   code can filter on `resolution_method == 'strict_100pct'` for high-
   confidence use, or examine the audit columns to make its own call
   (e.g. accept `n_shared_grants >= 2` even if only one candidate exists).

**Note on faculty_id_lookup coverage — and the missing-metadata report.**
The lookup has 557 AAUID entries but `ri_matches` contains 570 unique
`clientfacultyid` values. The 13-row gap is faculty who appear in
`ri_matches` (and `grants-with-coPI`) with valid IDs but are **not** in HR
Snowflake or `UnmatchedFaculty.csv`.

**Their grants are NOT dropped.** Grants are keyed by `grant_id`, and
`faculty_grants.parquet` preserves the attribution because those faculty
have valid `clientfacultyid` values. What's missing is only the
faculty-level metadata (`college`, `academic_unit`, `hire_date`,
`academic_rank`) — any downstream join to `faculty.parquet` returns NULL
for these fields on those 13 faculty.

The gap is now surfaced as a first-class pipeline output:
[`faculty_missing_metadata.parquet`](../data/processed/faculty_missing_metadata.parquet)
(built by `build_faculty_missing_metadata` in
[`src/build_dataset.py`](../src/build_dataset.py); also written as CSV).
Current run: **13 faculty, 68 (faculty, grant) rows affected, $61.1M in
grants**. All 13 appear in both raw grant files (`source_files=both`), so
this is a stable HR-side gap rather than data freshness. To backfill,
add entries for anyone on the list to `DataSet/UnmatchedFaculty.csv` and
re-run the pipeline.

**Still deferred (do not tackle yet):**

- Fuzzy-match orphan records to existing NEU grants at the grant level.
  Depends on decision 3.
- Fold recoverable orphan abstracts into the topic corpus. Depends on
  decisions 3 and 4.

---

## 7 · Files referenced

Raw:
- [DataSet/HR Snowflake faculty list…xlsx](../DataSet/HR%20Snowflake%20faculty%20list%202025%20fall%20update%206.15.2026.xlsx) — canonical `Employee ID`
- [DataSet/ri_matches_grants_2026.xlsx](../DataSet/ri_matches_grants_2026.xlsx) — `AAUID` + `clientfacultyid`
- [DataSet/grants-with-coPI.xlsx](../DataSet/grants-with-coPI.xlsx) — `PersonId` (= AAUID) + `ClientFacultyId`
- [DataSet/grants-with-abstract.xlsx](../DataSet/grants-with-abstract.xlsx) — `PersonId` (different ID space) + `SourceActivityId`

Processed (canonical outputs of [`src/build_dataset.py`](../src/build_dataset.py)):
- [data/processed/faculty.parquet](../data/processed/faculty.parquet)
- [data/processed/faculty_grants.parquet](../data/processed/faculty_grants.parquet)
- [data/processed/grants.parquet](../data/processed/grants.parquet)
- [data/processed/grant_orphaned_abstracts.parquet](../data/processed/grant_orphaned_abstracts.parquet)
- [data/processed/faculty_id_lookup.parquet](../data/processed/faculty_id_lookup.parquet) — **new**: `faculty_id` → `college` / `academic_unit` / `aauid`
- [data/processed/personid_to_faculty.parquet](../data/processed/personid_to_faculty.parquet) — **new**: `abstract.PersonId` → `faculty_id` with strict 100% majority vote + audit columns
- [data/processed/faculty_missing_metadata.parquet](../data/processed/faculty_missing_metadata.parquet) — **new**: faculty who have grants but no HR record (backfill via `DataSet/UnmatchedFaculty.csv`)

Exploratory (from the review — kept for reference, not part of the pipeline):
- [data/processed/faculty_orphan_overlap.csv](../data/processed/faculty_orphan_overlap.csv) — all 2,247 NEU faculty with orphan counts
- [data/processed/faculty_orphan_overlap_both.csv](../data/processed/faculty_orphan_overlap_both.csv) — 359 faculty in both tables
- [data/processed/orphans_with_abstract_review.csv](../data/processed/orphans_with_abstract_review.csv) — 403 usable orphan abstracts

Scripts (diagnostic; not part of the canonical build):
- [scripts/_diagnose_orphans.py](../scripts/_diagnose_orphans.py) — usability + date/agency mix
- [scripts/_orphan_faculty_overlap.py](../scripts/_orphan_faculty_overlap.py) — initial (loose) bridge exploration; superseded by `build_dataset.build_personid_to_faculty`
- [scripts/_bridge_examples.py](../scripts/_bridge_examples.py) — clean vs ambiguous personid trace
- [scripts/_id_reconciliation.py](../scripts/_id_reconciliation.py) — finds Martens across all four raw files
