"""
backfill_nih_reporter.py — M5a of docs/TOPIC_WORK_FORWARD_PLAN.md.

Recover abstract text (and, as a side effect of the same API call, investigator
data) for NEU grants attributed to NIH / NIH-SubAward / Dept. HHS / VA from the
public NIH RePORTER Project Search API. This is the ONLY documented path to
close the 2020+ NIH abstract coverage cliff (see docs/data_quality_report.md
§9) — the internal upload-system export never carried post-2019 NIH abstracts
and the AcAn 2026-08-13 refresh only narrows the cliff, per that same section.

Two things this script does NOT do, by design:
  - It never merges recovered abstracts into grants.parquet directly. That is
    Phase 2 of the refit plan (build_dataset.py layering abstract_source
    precedence). This script only produces reviewable Parquet + a report.
  - It never merges investigator data into faculty_grants.parquet. RePORTER
    only publishes the multi-PI list (never non-PI co-investigators), and
    adding PI/co-PI links would reorder every funding-credit-model leaderboard
    (docs/CLAUDE.md caveat #2). investigator_faculty_proposals.parquet is a
    reviewable proposal, not an adopted join.

Scope note — the NIH-SubAward slice is the highest-yield target (105 grants,
100% text-less) but the highest-risk one: subproject-level abstracts in
RePORTER are patchy for the older NCRR resource-center mechanisms (P41/M01/
P51, ~2005-2010), which often only carry the PARENT CENTER's abstract. Using a
center-level blurb as a specific subproject's abstract would inject a
fabricated topic signal — worse than the honest title-only status quo. Any
such fallback is tagged `abstract_source='nih_reporter_parent'` and EXCLUDED
from the topic-model corpus by default (see build_dataset.py Phase 2).

Pipeline position (see docs/TOPIC_MODEL_REFIT_CHECKLIST.md for the full
runbook this feeds into):
    python -m src.build_dataset
    python -m src.backfill_nih_reporter   # <- this file (network; run outside
                                           #    any sandbox that blocks
                                           #    api.reporter.nih.gov)
    python -m src.backfill_nsf_awards     # companion script, NSF side
    # ... then Phase 2 (adopt) + Phase 3 (refit) per the checklist.

Method
------
1. Parse every grant's `agencygrantid` into (core_project_num, suffix,
   suffix_kind) — NIH award numbers appear in this corpus in at least 6 raw
   shapes (see `parse_award_num`). `suffix_kind` is a length heuristic
   ("subproject" for a >=4-digit trailing group, else "support_year") — a
   heuristic, not a guarantee; mismatches against what RePORTER itself
   reports are surfaced in the report, not silently trusted.
2. Fetch NEU's awards in bulk (`org_names` search, paged), plus a targeted
   `project_nums` wildcard search for any grant whose core wasn't in the bulk
   pull — this covers pre-hire awards held at a prior institution AND every
   NIH-SubAward core (which is NOT NEU-awarded; NEU is the sub-recipient).
3. Match each grant to the best RePORTER record for its core (+ subproject id
   when the grant's suffix looks like one), preferring the fiscal year
   closest to the grant's own startdateyear; tag the abstract source
   accordingly (`nih_reporter` vs the parent-fallback `nih_reporter_parent`).
4. Extract the full multi-PI list (with contact-PI flag) and awardee
   organization from the same records — free enrichment, written to separate,
   NOT-auto-merged tables (see module docstring above).

Outputs (data/processed/, all gitignored/regenerable)
------------------------------------------------------
    nih_reporter_raw.parquet              one row per raw API result record
                                           (raw_json string) — --offline
                                           replays entirely from this cache.
    backfill_nih_abstracts.parquet         grant_id, project_num,
                                           core_project_num, subproject_id,
                                           fiscal_year, abstract,
                                           abstract_source, awardee_org
    grant_nih_investigators.parquet        grant_id, project_num, profile_id,
                                           full_name, is_contact_pi, org_name,
                                           rank_order  (raw multi-PI list;
                                           NEW grain, not merged into
                                           faculty_grants.parquet)
    investigator_faculty_proposals.parquet the above fuzzy-matched to
                                           faculty.parquet, for human review
    outputs/nih_reporter_backfill_report.md

Run:
    python -m src.backfill_nih_reporter                 # live fetch
    python -m src.backfill_nih_reporter --offline        # replay cache only
    python -m src.backfill_nih_reporter --limit 20        # smoke test
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

try:
    import requests
except ImportError:  # only needed for the live fetch; --offline works without it
    requests = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
OUTPUTS = REPO_ROOT / "outputs"

API_URL = "https://api.reporter.nih.gov/v2/projects/search"
ORG_NAME = "NORTHEASTERN UNIVERSITY"
PAGE_LIMIT = 500
OFFSET_CEILING = 14_999          # RePORTER's own paging ceiling
REQUEST_DELAY_S = 1.0            # "no more than one request per second" (API docs)
PROJECT_NUM_BATCH = 50

# PROC-relative paths (nih_reporter_raw.parquet, backfill_nih_abstracts.parquet,
# grant_nih_investigators.parquet, investigator_faculty_proposals.parquet) are
# resolved in main() from --proc, not fixed here, so --proc actually redirects
# every output, not just the input reads.
OUT_REPORT = OUTPUTS / "nih_reporter_backfill_report.md"

FACULTY_MATCH_MIN = 90  # stricter than build_dataset.py's agency-name threshold (85)


# ──────────────────────────────────────────────────────────────────────────
# 1. Award-number normalizer (pure — no network)
# ──────────────────────────────────────────────────────────────────────────

# [appl_type]? + activity code (3 chars: letter, then letter-or-digit, then
# digit — covers both all-digit codes like R01/P30 and the letter-second
# codes like DP1/UH2/RF1/UF1/UG3/IK2, all confirmed present in this corpus'
# 2016+ grants, i.e. exactly the abstract-cliff cohort this backfill exists
# to fix) + IC (2 letters) + serial (5 or 6 digits) [-suffix]?. Covers every
# raw shape sampled from grants.parquet.agencygrantid: R01DK035090,
# P30CA118100-4, P41RR000862-6313, P01HL081427-9001, M01RR000054-706,
# R01 HS13591 (AHRQ, 5-digit serial), DP2CA174495, UH3AA026214.
_AWARD_RE = re.compile(
    r"^(?P<appl>[3-9])?"
    r"(?P<activity>[A-Z][A-Z0-9]\d)"
    r"(?P<ic>[A-Z]{2})"
    r"(?P<serial>\d{5,6})"
    r"(?:-(?P<suffix>\d+))?$",
    re.ASCII,  # \d/[A-Z] would otherwise also match non-ASCII Unicode digits/letters
)

SUBPROJECT_MIN_DIGITS = 4  # trailing group this long or longer -> subproject id


@dataclass(frozen=True)
class ParsedAward:
    core: str | None          # activity + ic + serial, no padding, no suffix
    suffix: str | None        # raw trailing digits, or None
    suffix_kind: str | None   # "subproject" | "support_year" | None
    valid: bool


def normalize_award_num(raw) -> str | None:
    """Uppercase, whitespace-collapsed award number, or None if empty/NaN."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = re.sub(r"\s+", "", str(raw).strip().upper())
    return s or None


def parse_award_num(raw) -> ParsedAward:
    """Split a raw agencygrantid into (core_project_num, suffix, suffix_kind).

    `suffix_kind` is a LENGTH HEURISTIC (see module docstring) — treat it as a
    query hint, not ground truth; the matching step verifies against what
    RePORTER's own records report and the recovery report surfaces
    disagreements rather than silently trusting this classification.
    """
    s = normalize_award_num(raw)
    if s is None:
        return ParsedAward(None, None, None, False)
    m = _AWARD_RE.match(s)
    if not m:
        return ParsedAward(None, None, None, False)
    core = f"{m.group('activity')}{m.group('ic')}{m.group('serial')}"
    suffix = m.group("suffix")
    kind = None
    if suffix is not None:
        kind = "subproject" if len(suffix) >= SUBPROJECT_MIN_DIGITS else "support_year"
    return ParsedAward(core, suffix, kind, True)


def core_key(core: str) -> tuple[str, str, int] | None:
    """Numeric-tolerant comparison key for a core project number, so a
    locally-parsed core (unpadded) matches RePORTER's own `core_project_num`
    (which may be zero-padded differently) as long as activity/IC/serial
    agree numerically.
    """
    m = re.match(r"^([A-Z]\d{2})([A-Z]{2})(\d+)$", core or "")
    if not m:
        return None
    return (m.group(1), m.group(2), int(m.group(3)))


# ──────────────────────────────────────────────────────────────────────────
# 2. Fetch (network — skipped entirely under --offline)
# ──────────────────────────────────────────────────────────────────────────

def _post(session, criteria: dict, offset: int, limit: int) -> dict:
    resp = session.post(
        API_URL,
        json={"criteria": criteria, "offset": offset, "limit": limit,
              "sort_field": "project_start_date", "sort_order": "asc"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_by_org(session, org_name: str = ORG_NAME, cap: int | None = None,
                  sleep: float = REQUEST_DELAY_S) -> list[dict]:
    """Bulk pull every NIH project RePORTER attributes to `org_name`."""
    out: list[dict] = []
    offset = 0
    while offset <= OFFSET_CEILING:
        page = _post(session, {"org_names": [org_name]}, offset, PAGE_LIMIT)
        results = page.get("results", [])
        out.extend(results)
        if cap is not None and len(out) >= cap:
            return out[:cap]
        if len(results) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(sleep)
    return out


def fetch_by_project_nums(session, cores: list[str], cap: int | None = None,
                           sleep: float = REQUEST_DELAY_S) -> list[dict]:
    """Targeted lookup by wildcarded core project number, batched and PAGED.

    Covers awards RePORTER doesn't attribute to NEU as the awardee org — every
    NIH-SubAward core (NEU is the sub-recipient, not the prime awardee) and
    any pre-hire award held at a prior institution. A single center core
    (P41/P42/P01/...) can carry 20+ subprojects across many fiscal years, so
    a 50-core batch can exceed one page (500) on its own — paging per batch
    is required or the subproject-level records (exactly what the parent-
    fallback logic in `match_grants` needs) get silently truncated.
    """
    out: list[dict] = []
    patterns = [f"{c}*" for c in cores]
    for i in range(0, len(patterns), PROJECT_NUM_BATCH):
        batch = patterns[i:i + PROJECT_NUM_BATCH]
        offset = 0
        while offset <= OFFSET_CEILING:
            page = _post(session, {"project_nums": batch, "exclude_subprojects": False},
                         offset, PAGE_LIMIT)
            results = page.get("results", [])
            out.extend(results)
            if cap is not None and len(out) >= cap:
                return out[:cap]
            if len(results) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT
            time.sleep(sleep)
        time.sleep(sleep)
    return out


def fetch_all(grants: pd.DataFrame, limit: int | None = None) -> list[dict]:
    """`limit`, when given, caps EACH fetch path independently (not a shared
    budget) so a smoke test still exercises the targeted-core path — the one
    covering the NIH-SubAward slice and pre-hire awards, which a shared
    budget would starve since the bulk org pull always runs first.
    """
    if requests is None:
        raise RuntimeError(
            "requests is not installed — `pip install requests` (or use --offline "
            "to replay the cached response instead of fetching live)."
        )
    session = requests.Session()
    session.headers.update({"content-type": "application/json"})

    bulk = fetch_by_org(session, cap=limit)
    bulk_cores = {core_key(r["core_project_num"]) for r in bulk
                  if r.get("core_project_num") and core_key(r["core_project_num"])}

    parsed = grants["agencygrantid"].apply(parse_award_num)
    all_cores = {p.core for p in parsed if p.valid and p.core}
    missing_cores = sorted(c for c in all_cores if core_key(c) not in bulk_cores)

    targeted = fetch_by_project_nums(session, missing_cores, cap=limit) if missing_cores else []
    return bulk + targeted


# ──────────────────────────────────────────────────────────────────────────
# 3. Parse RePORTER's response schema (pure — testable on synthetic JSON)
# ──────────────────────────────────────────────────────────────────────────

def parse_record(rec: dict) -> dict:
    """Flatten one RePORTER project-search result to the fields we need."""
    org = rec.get("organization") or {}
    return {
        "project_num": rec.get("project_num") or "",
        "core_project_num": rec.get("core_project_num") or "",
        "subproject_id": rec.get("subproject_id"),
        "fiscal_year": rec.get("fiscal_year"),
        "abstract": (rec.get("abstract_text") or "").strip(),
        "title": (rec.get("project_title") or "").strip(),
        "org_name": (org.get("org_name") or "").strip(),
        "is_neu_org": _norm_org(org.get("org_name")) == _norm_org(ORG_NAME),
    }


def extract_investigators(rec: dict) -> list[dict]:
    core = rec.get("core_project_num") or ""
    proj = rec.get("project_num") or ""
    org_name = ((rec.get("organization") or {}).get("org_name") or "").strip()
    is_neu = _norm_org(org_name) == _norm_org(ORG_NAME)
    pis = rec.get("principal_investigators") or []
    return [
        {
            "project_num": proj,
            "core_project_num": core,
            "profile_id": pi.get("profile_id"),
            "full_name": (pi.get("full_name") or "").strip(),
            "is_contact_pi": bool(pi.get("is_contact_pi")),
            "org_name": org_name,
            "is_neu_org": is_neu,
            "rank_order": i,
        }
        for i, pi in enumerate(pis)
    ]


def _norm_org(name) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip().upper())


# ──────────────────────────────────────────────────────────────────────────
# 4. Match grants <-> RePORTER records
# ──────────────────────────────────────────────────────────────────────────

def _granularity_rank(candidate_subproject_id, sub_id: str | None, want_sub: bool) -> int:
    """How well a candidate record's granularity fits what the grant asked
    for — lower is better. Used as the PRIMARY sort key (ahead of fiscal-year
    closeness) so a grant is never matched to a record at the wrong
    granularity just because its fiscal year happens to line up.

    want_sub=True  (grant's suffix parsed as a subproject id):
        0 = this record IS that exact subproject
        1 = this record is the core/parent-level record (no subproject_id) —
            the intended, tagged fallback when the exact subproject has no
            text of its own
        2 = this record is a DIFFERENT subproject under the same core — a
            worse fallback than the parent (unrelated subproject content),
            used only if neither of the above has any text at all

    want_sub=False (grant's suffix is a support year, or there is none):
        0 = this record is core/parent-level (no subproject_id) — correct
        1 = this record is some subproject under the same core — last
            resort; using a narrow subproject's text for a whole-center
            grant carries the same "wrong granularity" risk as the reverse
            case, so it is tagged the same way (nih_reporter_parent) below.
    """
    p_sub = str(candidate_subproject_id or "")
    if want_sub:
        if sub_id and p_sub == sub_id:
            return 0
        return 1 if not p_sub else 2
    return 0 if not p_sub else 1


def match_grants(grants: pd.DataFrame, records: list[dict]) -> dict:
    """For every NIH-family grant, pick the best RePORTER record for its
    core (+ subproject id when the parsed suffix looks like one): granularity
    fit first (see `_granularity_rank`), fiscal-year closeness to break ties.

    Returns {"abstracts": df, "investigators": df, "unparsed": list[str],
    "unmatched_cores": list[str], "parent_fallback_n": int}.
    """
    # (parsed, raw) pairs, grouped by core — keeping `raw` alongside lets
    # investigator extraction use the exact record the abstract came from
    # without a second, O(records) rescan per grant.
    pairs = [(parse_record(r), r) for r in records]
    by_core: dict[tuple, list[tuple[dict, dict]]] = {}
    for p, r in pairs:
        k = core_key(p["core_project_num"])
        if k:
            by_core.setdefault(k, []).append((p, r))

    abstract_rows: list[dict] = []
    investigator_rows: list[dict] = []
    unparsed: list[str] = []
    unmatched_cores: list[str] = []
    parent_fallback_n = 0

    for _, g in grants.iterrows():
        parsed_award = parse_award_num(g["agencygrantid"])
        if not parsed_award.valid:
            unparsed.append(str(g.get("agencygrantid")))
            continue
        key = core_key(parsed_award.core)
        candidates = by_core.get(key, [])
        if not candidates:
            unmatched_cores.append(parsed_award.core or "")
            continue

        target_year = g.get("startdateyear")
        want_sub = parsed_award.suffix_kind == "subproject"
        sub_id = parsed_award.suffix if want_sub else None

        def _sort_key(pair: tuple[dict, dict]) -> tuple[int, int]:
            p, _ = pair
            rank = _granularity_rank(p.get("subproject_id"), sub_id, want_sub)
            fy = p.get("fiscal_year")
            dist = abs(int(fy) - int(target_year)) if (fy and pd.notna(target_year)) else 10_000
            return (rank, dist)

        # `pi_pair` reflects the best-fitting record REGARDLESS of whether it
        # has abstract text — a subproject's own PI list still wins even if
        # its abstract has to be borrowed from elsewhere (see below).
        pi_pair = min(candidates, key=_sort_key)
        # `abstract_pair` is the best-fitting record AMONG those that
        # actually have text — this is what can trigger the parent-fallback
        # tag, since it may rank worse than `pi_pair` on granularity alone.
        with_text = [pair for pair in candidates if pair[0]["abstract"]]
        abstract_pair = min(with_text, key=_sort_key) if with_text else None

        if abstract_pair is None:
            unmatched_cores.append(parsed_award.core or "")
            continue

        best, best_raw = abstract_pair
        used_wrong_granularity = _granularity_rank(
            best.get("subproject_id"), sub_id, want_sub) != 0
        source = "nih_reporter_parent" if used_wrong_granularity else "nih_reporter"
        if used_wrong_granularity:
            parent_fallback_n += 1

        abstract_rows.append({
            "grant_id": g["grant_id"],
            "project_num": best["project_num"],
            "core_project_num": best["core_project_num"],
            "subproject_id": best.get("subproject_id"),
            "fiscal_year": best.get("fiscal_year"),
            "abstract": best["abstract"],
            "abstract_source": source,
            "awardee_org": best["org_name"],
        })

        pi_parsed, pi_raw = pi_pair
        for row in extract_investigators(pi_raw):
            investigator_rows.append({"grant_id": g["grant_id"], **row})

    return {
        "abstracts": pd.DataFrame(abstract_rows),
        "investigators": pd.DataFrame(investigator_rows),
        "unparsed": unparsed,
        "unmatched_cores": unmatched_cores,
        "parent_fallback_n": parent_fallback_n,
    }


# ──────────────────────────────────────────────────────────────────────────
# 5. Investigator <-> faculty proposal matching
# ──────────────────────────────────────────────────────────────────────────

def propose_faculty_matches(investigators: pd.DataFrame, faculty: pd.DataFrame,
                             min_score: float = FACULTY_MATCH_MIN) -> pd.DataFrame:
    """Fuzzy-match RePORTER investigator names ('First Last') against
    faculty.parquet's 'LAST, FIRST[ MIDDLE]' names. Stricter than
    build_dataset.py's agency-name match (85): requires the same last name
    AND token_set_ratio >= min_score, since a wrong PI match would
    misattribute a grant, not just mislabel an agency.

    `min_score` defaults to the module constant (used by both scripts' own
    live/offline runs, unchanged) but can be overridden — see
    scripts/_refresh_investigator_matches.py, which reruns this at a
    verified-safe 75 (not the module default) purely to recover real
    matches the comma bug below was hiding; it does not change what a
    normal `python -m src.backfill_nih_reporter` run does.
    """
    if investigators.empty:
        return pd.DataFrame(columns=[
            "grant_id", "full_name", "faculty_id", "faculty_name",
            "match_score", "proposed_is_copi",
        ])

    fac = faculty[["faculty_id", "faculty_name"]].copy()
    fac = fac[fac["faculty_name"].fillna("") != ""]
    fac["last"] = fac["faculty_name"].str.split(",").str[0].str.strip().str.upper()
    # token_set_ratio was scoring against the raw "LAST, First Middle" string,
    # whose comma has no counterpart in an investigator's "First Last" name —
    # that stray token inflates the apparent edit distance for no real reason
    # (e.g. "Aron Stubbins" vs "STUBBINS, ARON PAUL" scored 81.25, well below
    # FACULTY_MATCH_MIN, purely because of the comma). Verified against the
    # real corpus: comparing against a comma-stripped "First Last Middle" form
    # instead recovers 216 further real NEU faculty at the existing >=90
    # threshold alone, with zero change to the matching LOGIC — same surname
    # blocking, same token_set_ratio, just a fairer string on one side of it.
    fac["cmp_name"] = fac["faculty_name"].str.replace(",", " ", regex=False).str.strip()

    rows = []
    for _, inv in investigators.iterrows():
        name = str(inv["full_name"]).strip()
        if not name:
            continue
        parts = name.split()
        last = parts[-1].upper() if parts else ""
        cands = fac[fac["last"] == last]
        best_id, best_name, best_score = "", "", 0
        for _, f in cands.iterrows():
            score = fuzz.token_set_ratio(name.upper(), f["cmp_name"].upper())
            if score > best_score:
                best_id, best_name, best_score = f["faculty_id"], f["faculty_name"], score
        if best_score >= min_score:
            rows.append({
                "grant_id": inv["grant_id"],
                "full_name": name,
                "faculty_id": best_id,
                "faculty_name": best_name,
                "match_score": best_score,
                "proposed_is_copi": not inv.get("is_contact_pi", False),
            })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────
# 6. Report
# ──────────────────────────────────────────────────────────────────────────

def write_report(grants: pd.DataFrame, result: dict, proposals: pd.DataFrame,
                  report_path: Path = OUT_REPORT) -> str:
    abstracts = result["abstracts"]
    nih_family = grants[grants["agencyname"].astype(str).str.contains(
        "Health|HHS|Veterans Affairs", case=False, na=False, regex=True)]
    textless = nih_family[nih_family["abstract"].isna()
                           | (nih_family["abstract"].astype(str).str.len() < 40)]

    by_agency = (abstracts.merge(grants[["grant_id", "agencyname"]], on="grant_id", how="left")
                 ["agencyname"].value_counts().to_dict()) if not abstracts.empty else {}

    non_neu = abstracts[abstracts["awardee_org"].apply(
        lambda o: _norm_org(o) != _norm_org(ORG_NAME))] if not abstracts.empty else abstracts

    # Recovered-% denominator must be the SAME population as the numerator:
    # grants that were text-less going in. `abstracts` also covers grants
    # that already had text (match_grants runs over the whole nih_family),
    # so filter before dividing or the percentage can exceed 100%.
    textless_ids = set(textless["grant_id"])
    recovered_textless = abstracts[abstracts["grant_id"].isin(textless_ids)] \
        if not abstracts.empty else abstracts
    n_also_updated = len(abstracts) - len(recovered_textless)

    lines = [
        "# NIH RePORTER Backfill Report (M5a)",
        "",
        f"NIH-family (NIH / NIH-SubAward / HHS / VA) text-less grants going in: "
        f"**{len(textless)}**",
        f"Recovered abstracts for those grants: **{len(recovered_textless)}** "
        f"({0 if len(textless) == 0 else 100*len(recovered_textless)/len(textless):.1f}% "
        f"of the above)",
        f"  (plus {n_also_updated} grants that already had text and got an "
        f"updated/longer version — not counted in the % above)",
        f"  - via `nih_reporter` (record's own text): "
        f"{(abstracts['abstract_source'] == 'nih_reporter').sum() if not abstracts.empty else 0}",
        f"  - via `nih_reporter_parent` (parent-center fallback — EXCLUDED from "
        f"the fit by default): {result['parent_fallback_n']}",
        "",
        "## By funder",
        *(f"- {k}: {v}" for k, v in sorted(by_agency.items(), key=lambda kv: -kv[1])),
        "",
        "## Unmatched / unparsed",
        f"- award numbers that didn't parse: {len(result['unparsed'])}",
        f"- cores with no RePORTER record found: {len(result['unmatched_cores'])}",
        "",
        "## Awardee-organization audit",
        f"Grants where RePORTER's own `organization.org_name` is NOT Northeastern "
        f"(independent check on the pre-hire attribution caveat): **{len(non_neu)}**",
        "",
        "## Investigator proposals",
        f"Raw multi-PI rows extracted: {len(result['investigators'])}",
        f"Matched to a faculty_id (score >= {FACULTY_MATCH_MIN}): {len(proposals)}",
        f"  - proposed as co-PI (not the contact PI): "
        f"{int(proposals['proposed_is_copi'].sum()) if not proposals.empty else 0}",
        "",
        "NOT auto-merged into grants.parquet or faculty_grants.parquet — see module",
        "docstring. Review backfill_nih_abstracts.parquet / "
        "investigator_faculty_proposals.parquet before adopting.",
    ]
    report = "\n".join(lines) + "\n"
    report_path.parent.mkdir(exist_ok=True, parents=True)
    report_path.write_text(report, encoding="utf-8")
    return report


# ──────────────────────────────────────────────────────────────────────────
# Orchestrate
# ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--proc", type=Path, default=PROC)
    ap.add_argument("--offline", action="store_true",
                     help="Replay the cached raw response; no network.")
    ap.add_argument("--limit", type=int, default=None,
                     help="Cap each fetch path independently (smoke test). Writes to a "
                          "*_smoke cache file, never overwriting a full cache.")
    args = ap.parse_args()

    # A --limit smoke run writes EVERY output (cache + derived tables +
    # report) to a "_smoke"-suffixed sibling path, never the canonical
    # ones — a smoke test must never overwrite a real full run's
    # review-ready files (this bit us once already on the NSF module).
    suffix = "_smoke" if args.limit else ""
    raw_cache = args.proc / f"nih_reporter_raw{suffix}.parquet"
    out_abstracts = args.proc / f"backfill_nih_abstracts{suffix}.parquet"
    out_investigators = args.proc / f"grant_nih_investigators{suffix}.parquet"
    out_proposals = args.proc / f"investigator_faculty_proposals{suffix}.parquet"
    out_report = OUTPUTS / f"nih_reporter_backfill_report{suffix}.md"

    grants = pd.read_parquet(args.proc / "grants.parquet")
    grants["grant_id"] = grants["grant_id"].astype(str)
    nih_family = grants[grants["agencyname"].astype(str).str.contains(
        "Health|HHS|Veterans Affairs", case=False, na=False, regex=True)].copy()

    if args.offline:
        if not raw_cache.exists():
            raise SystemExit(f"--offline requires an existing cache at {raw_cache}")
        cached = pd.read_parquet(raw_cache)
        records = [json.loads(s) for s in cached["raw_json"]]
    else:
        records = fetch_all(nih_family, limit=args.limit)
        pd.DataFrame({"raw_json": [json.dumps(r) for r in records]}).to_parquet(
            raw_cache, index=False)
        print(f"wrote {raw_cache} ({len(records)} raw records)")

    result = match_grants(nih_family, records)
    faculty = pd.read_parquet(args.proc / "faculty.parquet")
    proposals = propose_faculty_matches(result["investigators"], faculty)

    result["abstracts"].to_parquet(out_abstracts, index=False)
    result["investigators"].to_parquet(out_investigators, index=False)
    proposals.to_parquet(out_proposals, index=False)

    report = write_report(nih_family, result, proposals, report_path=out_report)
    print(report)
    print(f"wrote {out_abstracts} ({len(result['abstracts'])} rows), "
          f"{out_investigators} ({len(result['investigators'])} rows), "
          f"{out_proposals} ({len(proposals)} rows), {out_report}")


if __name__ == "__main__":
    main()
