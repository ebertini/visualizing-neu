# Faculty ID Reconciliation

**Status:** under review — do not act on the recommendations at the bottom yet.
**Trigger:** while building the orphan-abstract bridge we discovered the raw
datasets carry three distinct identifiers for the same person, plus a column
name (`PersonId`) that means different things in different files.
**Concrete example throughout:** Chris Martens (Robin), Khoury College of
Computer Sciences.

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

## 4 · Why the orphan bridge in `personid_to_faculty.csv` still works

The bridge we built in [scripts/_orphan_faculty_overlap.py](../scripts/_orphan_faculty_overlap.py)
does not try to translate `abstract.PersonId → AAUID` or
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
is a downstream artefact, not an ID-space problem — majority-vote across
shared grants resolves it cleanly (verified on the Amato example below).

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
co-PI got attributed alongside him. Majority-vote picks Amato correctly.
The current `personid_to_faculty.csv` stores all 4 candidates and the
downstream code takes the first (alphabetically-smallest `faculty_id`),
which happens to pick Amato here by luck — but for other personids the
first-in-list heuristic could easily pick a co-PI.

---

## 6 · Implications & open questions to review

**Confirmed / not broken:**

- The `faculty_id = 2963712` we've been using for Martens throughout is
  correct. `faculty.parquet`, `faculty_grants.parquet`, and every
  downstream analysis use the right canonical ID.
- The orphan → faculty bridge is valid; it just needs the majority-vote
  disambiguation to be trustworthy for the ambiguous 51%.

**Worth deciding before we go further:**

1. **Document `PersonId` collision in [`docs/data_dictionary.md`](data_dictionary.md).**
   Anyone unfamiliar with the source systems will trip on this. Small
   write-up saves future confusion. *(Recommend: yes.)*
2. **Decide whether `AAUID` is worth preserving anywhere in processed
   data.** It's Academic Analytics' external ID and we currently drop it.
   If we ever want to enrich topic modeling with AA-derived research
   interests, we'd need it back. *(Recommend: keep in
   `faculty_id_lookup.parquet` as an optional column; costs almost
   nothing.)*
3. **Handle the abstract-file duplicate risk before "recovery."** The
   Martens finding (orphan 1382460 ≈ matched grant 1471424) suggests some
   fraction of the 403 orphan-with-abstract rows are duplicates of grants
   already in the corpus. Recovery counts must be net-of-duplicates, or
   we'll double-count grants in the topic model. *(Requires: a title +
   PI + date check before folding in.)*
4. **Formalize the majority-vote disambiguation** and republish
   `personid_to_faculty.csv` so it stores the winning single faculty
   plus a confidence score, instead of a semicolon-separated candidate
   list. Downstream code becomes simpler and more correct.
5. **Consider capturing `abstract.PersonId → faculty_id` as a permanent
   lookup** alongside `faculty_id_lookup.parquet`. It's derived data
   (from the observational bridge above) but useful anywhere we want to
   attribute abstract-file records to faculty without re-running the
   crosswalk. *(Recommend: yes, once majority-vote is applied.)*

**Deliberately out of scope (do not tackle yet):**

- Whether to fuzzy-match orphan records to existing NEU grants at the
  grant level (Path 2 in prior discussion). Wait until decisions 1–4
  above are settled.
- Whether to fold recoverable orphan abstracts into the topic corpus
  (Path 1). Same — depends on 3 and 4.

---

## 7 · Files referenced

Raw:
- [DataSet/HR Snowflake faculty list…xlsx](../DataSet/HR%20Snowflake%20faculty%20list%202025%20fall%20update%206.15.2026.xlsx) — canonical `Employee ID`
- [DataSet/ri_matches_grants_2026.xlsx](../DataSet/ri_matches_grants_2026.xlsx) — `AAUID` + `clientfacultyid`
- [DataSet/grants-with-coPI.xlsx](../DataSet/grants-with-coPI.xlsx) — `PersonId` (= AAUID) + `ClientFacultyId`
- [DataSet/grants-with-abstract.xlsx](../DataSet/grants-with-abstract.xlsx) — `PersonId` (different ID space) + `SourceActivityId`

Processed:
- [data/processed/faculty.parquet](../data/processed/faculty.parquet)
- [data/processed/faculty_grants.parquet](../data/processed/faculty_grants.parquet)
- [data/processed/grants.parquet](../data/processed/grants.parquet)
- [data/processed/grant_orphaned_abstracts.parquet](../data/processed/grant_orphaned_abstracts.parquet)
- [data/processed/faculty_id_lookup.parquet](../data/processed/faculty_id_lookup.parquet)

Derived (from this investigation):
- [data/processed/personid_to_faculty.csv](../data/processed/personid_to_faculty.csv) — the observational bridge (639 personids)
- [data/processed/faculty_orphan_overlap.csv](../data/processed/faculty_orphan_overlap.csv) — all 2,247 NEU faculty with orphan counts
- [data/processed/faculty_orphan_overlap_both.csv](../data/processed/faculty_orphan_overlap_both.csv) — 359 faculty in both tables
- [data/processed/orphans_with_abstract_review.csv](../data/processed/orphans_with_abstract_review.csv) — 403 usable orphan abstracts

Scripts:
- [scripts/_diagnose_orphans.py](../scripts/_diagnose_orphans.py) — usability + date/agency mix
- [scripts/_orphan_faculty_overlap.py](../scripts/_orphan_faculty_overlap.py) — builds the bridge and the overlap tables
- [scripts/_bridge_examples.py](../scripts/_bridge_examples.py) — clean vs ambiguous personid trace
- [scripts/_id_reconciliation.py](../scripts/_id_reconciliation.py) — finds Martens across all four raw files
