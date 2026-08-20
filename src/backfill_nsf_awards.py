"""
backfill_nsf_awards.py — NSF companion to src/backfill_nih_reporter.py
(both feed M5a of docs/TOPIC_WORK_FORWARD_PLAN.md, "NIH RePORTER abstract
backfill" — extended here to NSF, since NSF Award Search offers the same
kind of public per-award record and NSF is 1,686 of our 2,676 grants).

Recovers abstract text AND co-PI data (NSF's `coPDPI` field — real
co-investigator data, unlike NIH RePORTER which only ever publishes named
PIs) for NEU's NSF grants from the public NSF Award Search API
(api.nsf.gov, no key required).

Two data problems specific to NSF, found while sizing this backfill (see
docs/data_quality_report.md and the refit plan for the write-up):

1. **Leading zeros lost.** NSF award numbers are always 7 digits, but ours
   are stored numerically: of ~1,600 non-null ids, 1,246 are 7 chars, 350
   are 6 (`853685` -> really `0853685`), and 4 are 5 (ambiguous — a 5-digit
   NSF number would imply an award from before 1976, inconsistent with our
   2001-2003 start dates for those rows, so these are flagged LOW confidence
   for manual review rather than auto-padded and trusted).
2. **86 grants have no `agencygrantid` at all** — disproportionately CAREER
   awards in the text-less sample — so they can't be id-matched. These need
   an org-scoped bulk pull, fuzzy-matched on title + start year at a
   STRICTER threshold than build_dataset.py's agency-name match (85), with
   near-misses reported rather than silently accepted.

As with the NIH module: nothing here is auto-merged into grants.parquet or
faculty_grants.parquet. Outputs are reviewable proposals (see Phase 2 of the
refit plan for adoption into build_dataset.py's abstract_source layering).

The org-scoped bulk-search path for grants with no award id
(`fetch_by_org_year`) was live-verified after an initial --limit smoke test
returned 20 "bulk" records from UMass, Northwestern, U. Washington, etc. —
not NEU at all. Cause: api.nsf.gov's `awardeeName` silently IGNORES an
unquoted multi-word value (no error — it just returns unfiltered nationwide
results for the date range) and requires the value wrapped in literal
double quotes as an exact-phrase filter. Confirmed live: unquoted
`Northeastern+University` returns other schools; quoted
`"Northeastern+University"` returns only NEU, and paging behaves normally
(a 25-record page followed by a shorter final page). Always re-run a
`--limit` smoke test and eyeball the cached "bulk" records after any change
near this path — this exact failure mode (silent misinterpretation, not an
error) is invisible without inspecting output, which is exactly how it was
caught here.

Outputs (data/processed/, gitignored/regenerable)
---------------------------------------------------
    nsf_awards_raw.parquet                 one row per raw API response
                                            (raw_json string) — --offline
                                            replays from this cache.
    backfill_nsf_abstracts.parquet          grant_id, award_num, abstract,
                                            abstract_source, awardee_org,
                                            match_score (id-matched: 100;
                                            fuzzy-matched: the token_set_ratio)
    grant_nsf_investigators.parquet         grant_id, award_num, full_name,
                                            is_contact_pi, rank_order (PI +
                                            coPDPI; NEW grain, not merged)
    investigator_faculty_proposals_nsf.parquet  matched to faculty.parquet
    outputs/nsf_backfill_report.md

Run:
    python -m src.backfill_nsf_awards
    python -m src.backfill_nsf_awards --offline
    python -m src.backfill_nsf_awards --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import pandas as pd

from src.backfill_nih_reporter import FACULTY_MATCH_MIN, propose_faculty_matches

try:
    import requests
except ImportError:  # only needed for the live fetch; --offline works without it
    requests = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
OUTPUTS = REPO_ROOT / "outputs"

BASE_URL = "https://api.nsf.gov/services/v1"
AWARDEE_NAME = "Northeastern University"
REQUEST_DELAY_S = 0.5
BULK_PAGE_SIZE = 25   # documented per-page max for the org-scoped search
TITLE_MATCH_MIN = 90  # stricter than build_dataset.py's 85 (agency names, not PIs)
TITLE_REPORT_FLOOR = 75  # near-misses at/above this land in the report, not the data

# PROC-relative paths (nsf_awards_raw.parquet, backfill_nsf_abstracts.parquet,
# grant_nsf_investigators.parquet, investigator_faculty_proposals_nsf.parquet)
# are resolved in main() from --proc, not fixed here, so --proc actually
# redirects every output, not just the input reads.
OUT_REPORT = OUTPUTS / "nsf_backfill_report.md"


# ──────────────────────────────────────────────────────────────────────────
# 1. Award-number normalizer (pure — no network)
# ──────────────────────────────────────────────────────────────────────────

def normalize_nsf_award_num(raw) -> tuple[str | None, str]:
    """Zero-pad an NSF award number to 7 digits.

    Returns (padded_id_or_None, confidence):
      "exact"       - already 7 digits, no padding needed
      "padded_high" - 6 digits; padding by exactly one leading zero is the
                      unambiguous fix for float storage eating a single
                      leading zero
      "padded_low"  - 5 digits; padding by TWO zeros is a guess, not a fact
                      (would imply a pre-1976 award, inconsistent with the
                      2001-2003 start years actually observed) — flag for
                      manual review rather than trust
      "invalid"     - anything else (null, non-digits, wrong length)
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, "invalid"
    s = str(raw).strip()
    s = re.sub(r"\.0$", "", s)  # pandas float coercion artifact, e.g. "853685.0"
    # str.isdigit() accepts non-ASCII Unicode digit characters (e.g. Arabic-
    # Indic digits) that would still "look" numeric but produce a nonsense
    # URL path segment rather than a rejection — isascii() closes that.
    if not (s.isascii() and s.isdigit()):
        return None, "invalid"
    if len(s) == 7:
        return s, "exact"
    if len(s) == 6:
        return s.zfill(7), "padded_high"
    if len(s) == 5:
        return s.zfill(7), "padded_low"
    return None, "invalid"


# ──────────────────────────────────────────────────────────────────────────
# 2. Fetch (network — skipped entirely under --offline)
# ──────────────────────────────────────────────────────────────────────────

def fetch_by_id(session, award_num: str) -> dict | None:
    resp = session.get(f"{BASE_URL}/awards/{award_num}.json", timeout=30)
    resp.raise_for_status()
    results = resp.json().get("response", {}).get("award", [])
    return results[0] if results else None


NSF_RESULT_CAP = 3_000  # NSF's own documented per-query cap
MAX_BULK_PAGES = NSF_RESULT_CAP // BULK_PAGE_SIZE + 1


def fetch_by_org_year(session, awardee_name: str, year: int, sleep: float = REQUEST_DELAY_S
                       ) -> list[dict]:
    """Org-scoped bulk pull for a single start year, paged.

    `awardeeName` MUST be wrapped in literal double quotes (an exact-phrase
    filter) — verified live against api.nsf.gov: an unquoted multi-word value
    is silently IGNORED (the endpoint returns unfiltered nationwide results
    for the date range, not an error), while `"Northeastern University"`
    correctly restricts to NEU. This was caught by inspecting a --limit
    smoke-test cache before the first full run: the "bulk" records it
    returned were from UMass, Northwestern, U. Washington, etc. — not NEU at
    all — so fuzzy-matching them against NEU's own no-id grants would have
    matched nothing (as observed) or, worse, occasionally cross-matched a
    wrong-institution grant's abstract onto one of ours.

    Bounded defensively regardless (max page count + identical-consecutive-
    page bail-out), since the API's behavior on a malformed/unexpected
    parameter is silent misinterpretation rather than an error — the same
    class of failure that made the quoting bug invisible until inspected.
    """
    out: list[dict] = []
    prev_first_id = None
    offset = 0
    for _ in range(MAX_BULK_PAGES):
        resp = session.get(f"{BASE_URL}/awards.json", params={
            "awardeeName": f'"{awardee_name}"',
            "dateStart": f"01/01/{year}",
            "dateEnd": f"12/31/{year}",
            "offset": offset,
        }, timeout=30)
        resp.raise_for_status()
        page = resp.json().get("response", {}).get("award", [])
        if not page:
            break
        first_id = page[0].get("id")
        if first_id is not None and first_id == prev_first_id:
            break  # `offset` isn't advancing the result set — bail rather than loop forever
        prev_first_id = first_id
        out.extend(page)
        if len(page) < BULK_PAGE_SIZE:
            break
        offset += BULK_PAGE_SIZE
        time.sleep(sleep)
    return out


def fetch_all(grants: pd.DataFrame, limit: int | None = None) -> tuple[list[dict], list[dict]]:
    """Returns (id_records, bulk_records) — kept SEPARATE, not merged, since
    `match_by_fuzzy_title` must only ever see the org-scoped bulk pool (an
    id-matched record from a DIFFERENT grant must never be fuzzy-matchable
    to a second one). `limit`, when given, caps each path independently so a
    smoke test still exercises both.
    """
    if requests is None:
        raise RuntimeError(
            "requests is not installed — `pip install requests` (or use --offline "
            "to replay the cached response instead of fetching live)."
        )
    session = requests.Session()

    id_records: list[dict] = []
    with_id = grants[grants["agencygrantid"].notna()]
    for raw in with_id["agencygrantid"]:
        padded, conf = normalize_nsf_award_num(raw)
        if padded is None:
            continue
        rec = fetch_by_id(session, padded)
        if rec is not None:
            id_records.append(rec)
        time.sleep(REQUEST_DELAY_S)
        if limit is not None and len(id_records) >= limit:
            break

    bulk_records: list[dict] = []
    without_id = grants[grants["agencygrantid"].isna()]
    years = sorted(without_id["startdateyear"].dropna().astype(int).unique())
    for year in years:
        page = fetch_by_org_year(session, AWARDEE_NAME, int(year))
        bulk_records.extend(page)
        if limit is not None and len(bulk_records) >= limit:
            bulk_records = bulk_records[:limit]
            break
    return id_records, bulk_records


# ──────────────────────────────────────────────────────────────────────────
# 3. Parse NSF's response schema (pure — testable on synthetic JSON)
# ──────────────────────────────────────────────────────────────────────────

def parse_record(rec: dict) -> dict:
    return {
        "award_num": rec.get("id") or "",
        "title": (rec.get("title") or "").strip(),
        "abstract": (rec.get("abstractText") or "").strip(),
        "awardee_org": (rec.get("awardeeName") or "").strip(),
        "start_date": rec.get("startDate") or "",
    }


_COPDPI_EMAIL_RE = re.compile(r"\S+@\S+")
_COPDPI_PAREN_RE = re.compile(r"\([^)]*\)")
_COPDPI_SUFFIX_RE = re.compile(r",\s*(Jr\.?|Sr\.?|I{1,3}|IV)\s*$", re.IGNORECASE)


def _co_pdpi_to_first_last(raw: str) -> str:
    """Clean one NSF `coPDPI` entry into a bare 'First [Middle] Last' name.

    Live-verified real shape: "First [Middle] Last[, Suffix] email@domain",
    optionally with a "(Former)"-style annotation before the email (e.g.
    "Christopher Martens (Former) c.martens@northeastern.edu") and
    occasionally a name suffix attached with a comma (e.g. "Albert Sacco,
    Jr. asacco@coe.neu.edu"). This is NOT the "Last, First" shape guessed
    from written API docs before a live response was available — that
    shape was never observed live and, worse, would have misparsed the
    ", Jr."-style suffix as a Last/First separator (surname would have come
    out as "Jr."). propose_faculty_matches takes the final whitespace token
    as the surname, so every non-name suffix must be stripped, not just the
    email.
    """
    s = str(raw or "").strip()
    if not s:
        return ""
    s = _COPDPI_EMAIL_RE.sub("", s)
    s = _COPDPI_PAREN_RE.sub("", s)
    s = _COPDPI_SUFFIX_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_investigators(rec: dict) -> list[dict]:
    rows: list[dict] = []
    pi_first, pi_last = rec.get("piFirstName", ""), rec.get("piLastName", "")
    pi_name = f"{pi_first} {pi_last}".strip()
    if pi_name:
        rows.append({"full_name": pi_name, "is_contact_pi": True, "rank_order": 0})
    for i, raw in enumerate(rec.get("coPDPI") or [], start=1):
        name = _co_pdpi_to_first_last(raw)
        if name:
            rows.append({"full_name": name, "is_contact_pi": False, "rank_order": i})
    return rows


# ──────────────────────────────────────────────────────────────────────────
# 4. Match grants <-> NSF records
# ──────────────────────────────────────────────────────────────────────────

def match_by_id(grants: pd.DataFrame, records: list[dict]) -> dict:
    raw_by_id = {r.get("id"): r for r in records if r.get("id")}
    parsed = {rid: parse_record(r) for rid, r in raw_by_id.items()}
    abstract_rows, investigator_rows, low_confidence, unmatched = [], [], [], []

    for _, g in grants.iterrows():
        padded, conf = normalize_nsf_award_num(g.get("agencygrantid"))
        if padded is None:
            continue
        rec = parsed.get(padded)
        if rec is None or not rec["abstract"]:
            unmatched.append(str(g.get("agencygrantid")))
            continue
        if conf == "padded_low":
            low_confidence.append(g["grant_id"])
        abstract_rows.append({
            "grant_id": g["grant_id"], "award_num": rec["award_num"],
            "abstract": rec["abstract"], "abstract_source": "nsf_api",
            "awardee_org": rec["awardee_org"], "match_score": 100,
            "id_confidence": conf,
        })
        raw = raw_by_id.get(padded)
        if raw:
            for row in extract_investigators(raw):
                investigator_rows.append({"grant_id": g["grant_id"], "award_num": padded, **row})

    return {"abstracts": abstract_rows, "investigators": investigator_rows,
            "low_confidence": low_confidence, "unmatched": unmatched}


def match_by_fuzzy_title(grants_no_id: pd.DataFrame, bulk_records: list[dict]) -> dict:
    """For grants with no award id, match on title + start year against the
    org-scoped BULK pool only (never `records` in general — an id-matched
    record belonging to a different grant must never be adopted here too).
    Reuses build_dataset.py's rapidfuzz discipline but stricter in two ways:

    1. The acceptance score is `min(ratio, token_set_ratio)`, not
       `token_set_ratio` alone. `token_set_ratio` scores ANY short,
       generic-prefix title (e.g. "CAREER: Sensor networks") at 100 against
       a much longer title that merely CONTAINS those tokens — exactly the
       shape of most of these no-id grants (overwhelmingly CAREER awards).
       `ratio` penalizes the length mismatch that `token_set_ratio` ignores,
       so the combined score only accepts a genuinely close title.
    2. One award number can be claimed by only one grant — collisions are
       resolved by keeping the higher-scoring claim and demoting the loser
       to a reported near-miss, the same pattern reconcile_orphans.py uses
       for orphan-abstract collisions.
    """
    from rapidfuzz import fuzz  # local import: only this path needs it

    raw_by_id = {r.get("id"): r for r in bulk_records if r.get("id")}
    parsed = [parse_record(r) for r in bulk_records]
    claims: list[dict] = []  # every grant's best candidate, before collision resolution
    near_misses: list[tuple] = []

    for _, g in grants_no_id.iterrows():
        title = g.get("grantname")
        title = "" if pd.isna(title) else str(title)
        year = g.get("startdateyear")
        best, best_score = None, 0
        for rec in parsed:
            if not rec["abstract"]:
                continue
            score = min(
                fuzz.ratio(title.upper(), rec["title"].upper()),
                fuzz.token_set_ratio(title.upper(), rec["title"].upper()),
            )
            rec_year = rec["start_date"][-4:] if rec["start_date"] else None
            if rec_year and pd.notna(year) and rec_year != str(int(year)):
                score -= 5  # small penalty, not a veto — start dates can drift by a year
            if score > best_score:
                best, best_score = rec, score
        if best is None:
            continue
        if best_score >= TITLE_MATCH_MIN:
            claims.append({"grant_id": g["grant_id"], "award_num": best["award_num"],
                            "abstract": best["abstract"], "match_score": best_score,
                            "awardee_org": best["awardee_org"]})
        elif best_score >= TITLE_REPORT_FLOOR:
            near_misses.append((g["grant_id"], best["award_num"], best_score, best["title"][:70]))

    claims_df = pd.DataFrame(claims)
    if claims_df.empty:
        return {"abstracts": [], "investigators": [], "near_misses": near_misses}

    claims_df = claims_df.sort_values("match_score", ascending=False)
    winners = claims_df.drop_duplicates("award_num", keep="first")
    losers = claims_df.loc[claims_df.index.difference(winners.index)]
    for _, r in losers.iterrows():
        near_misses.append((r["grant_id"], r["award_num"], r["match_score"],
                             "(dropped: award already claimed by a higher-scoring grant)"))

    abstract_rows = [
        {"grant_id": r["grant_id"], "award_num": r["award_num"], "abstract": r["abstract"],
         "abstract_source": "nsf_api", "awardee_org": r["awardee_org"],
         "match_score": r["match_score"]}
        for _, r in winners.iterrows()
    ]
    investigator_rows = []
    for _, r in winners.iterrows():
        raw = raw_by_id.get(r["award_num"])
        if raw:
            for row in extract_investigators(raw):
                investigator_rows.append({"grant_id": r["grant_id"], "award_num": r["award_num"], **row})

    return {"abstracts": abstract_rows, "investigators": investigator_rows,
            "near_misses": near_misses}


# ──────────────────────────────────────────────────────────────────────────
# 5. Report
# ──────────────────────────────────────────────────────────────────────────

def write_report(grants: pd.DataFrame, id_result: dict, fuzzy_result: dict,
                  proposals: pd.DataFrame, report_path: Path = OUT_REPORT) -> str:
    nsf = grants[grants["agencyname"].astype(str).eq("National Science Foundation")]
    textless = nsf[nsf["abstract"].isna() | (nsf["abstract"].astype(str).str.len() < 40)]
    textless_ids = set(textless["grant_id"])

    # % denominator must match the numerator's population: match_by_id /
    # match_by_fuzzy_title run over ALL id-bearing / no-id NSF grants (an
    # already-covered grant can still get an updated/longer abstract), not
    # just the text-less ones, so the raw counts alone would let the
    # percentage exceed 100%.
    all_abstracts = id_result["abstracts"] + fuzzy_result["abstracts"]
    recovered_textless = [r for r in all_abstracts if r["grant_id"] in textless_ids]
    n_also_updated = len(all_abstracts) - len(recovered_textless)

    lines = [
        "# NSF Award Search Backfill Report",
        "",
        f"NSF text-less grants going in: **{len(textless)}**",
        f"Recovered abstracts for those grants: **{len(recovered_textless)}** "
        f"({0 if len(textless) == 0 else 100*len(recovered_textless)/len(textless):.1f}% "
        f"of the above)",
        f"  (plus {n_also_updated} grants that already had text and got an "
        f"updated/longer version — not counted in the % above)",
        f"  - via id lookup: {len(id_result['abstracts'])} "
        f"(of which low-confidence 5-digit-id padding: {len(id_result['low_confidence'])})",
        f"  - via title+year fuzzy match (score >= {TITLE_MATCH_MIN}): "
        f"{len(fuzzy_result['abstracts'])}",
        "",
        f"## Unmatched (id lookup found nothing): {len(id_result['unmatched'])}",
        "",
        f"## Near-misses (fuzzy score {TITLE_REPORT_FLOOR}-{TITLE_MATCH_MIN-1} — "
        f"NOT adopted, listed for manual review): {len(fuzzy_result['near_misses'])}",
    ]
    for gid, award, score, title in fuzzy_result["near_misses"][:15]:
        lines.append(f"  - grant {gid} <-> NSF {award} (score {score}): {title}")
    lines += [
        "",
        "## Investigator proposals",
        f"Matched to a faculty_id (score >= {FACULTY_MATCH_MIN}): {len(proposals)}",
        f"  - proposed as co-PI: "
        f"{int(proposals['proposed_is_copi'].sum()) if not proposals.empty else 0}",
        "",
        "NOT auto-merged into grants.parquet or faculty_grants.parquet — see module docstring.",
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

    # A --limit smoke run writes EVERY output (cache + derived tables + report)
    # to a "_smoke"-suffixed sibling path, never the canonical ones — a smoke
    # test must never overwrite a real full run's review-ready files.
    suffix = "_smoke" if args.limit else ""
    raw_cache = args.proc / f"nsf_awards_raw{suffix}.parquet"
    out_abstracts = args.proc / f"backfill_nsf_abstracts{suffix}.parquet"
    out_investigators = args.proc / f"grant_nsf_investigators{suffix}.parquet"
    out_proposals = args.proc / f"investigator_faculty_proposals_nsf{suffix}.parquet"
    out_report = OUTPUTS / f"nsf_backfill_report{suffix}.md"

    grants = pd.read_parquet(args.proc / "grants.parquet")
    grants["grant_id"] = grants["grant_id"].astype(str)
    nsf = grants[grants["agencyname"].astype(str).eq("National Science Foundation")].copy()

    if args.offline:
        if not raw_cache.exists():
            raise SystemExit(f"--offline requires an existing cache at {raw_cache}")
        cached = pd.read_parquet(raw_cache)
        id_records = [json.loads(s) for s in cached.loc[cached["source"] == "id", "raw_json"]]
        bulk_records = [json.loads(s) for s in cached.loc[cached["source"] == "bulk", "raw_json"]]
    else:
        id_records, bulk_records = fetch_all(nsf, limit=args.limit)
        cache_df = pd.DataFrame({
            "source": ["id"] * len(id_records) + ["bulk"] * len(bulk_records),
            "raw_json": [json.dumps(r) for r in id_records + bulk_records],
        })
        cache_df.to_parquet(raw_cache, index=False)
        print(f"wrote {raw_cache} ({len(id_records)} id records, {len(bulk_records)} bulk records)")

    nsf_with_id = nsf[nsf["agencygrantid"].notna()]
    nsf_no_id = nsf[nsf["agencygrantid"].isna()]

    id_result = match_by_id(nsf_with_id, id_records)
    fuzzy_result = match_by_fuzzy_title(nsf_no_id, bulk_records)

    abstracts = pd.DataFrame(id_result["abstracts"] + fuzzy_result["abstracts"])
    investigators = pd.DataFrame(id_result["investigators"] + fuzzy_result["investigators"])

    faculty = pd.read_parquet(args.proc / "faculty.parquet")
    proposals = propose_faculty_matches(investigators, faculty) if not investigators.empty \
        else pd.DataFrame(columns=["grant_id", "full_name", "faculty_id", "faculty_name",
                                    "match_score", "proposed_is_copi"])

    abstracts.to_parquet(out_abstracts, index=False)
    investigators.to_parquet(out_investigators, index=False)
    proposals.to_parquet(out_proposals, index=False)

    report = write_report(nsf, id_result, fuzzy_result, proposals, report_path=out_report)
    print(report)
    print(f"wrote {out_abstracts} ({len(abstracts)} rows), "
          f"{out_investigators} ({len(investigators)} rows), "
          f"{out_proposals} ({len(proposals)} rows), {out_report}")


if __name__ == "__main__":
    main()
