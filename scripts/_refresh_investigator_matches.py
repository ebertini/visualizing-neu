"""
_refresh_investigator_matches.py — regenerate the NIH/NSF investigator ->
faculty match tables with the comma-normalization fix (see
propose_faculty_matches's own docstring in src/backfill_nih_reporter.py),
without re-fetching anything or touching the abstract backfill at all.

Context: both backfill_nih_reporter.py's and backfill_nsf_awards.py's
`--offline` replay path re-derives EVERYTHING (abstracts, investigators,
proposals) from the raw API cache, and expects `grants.parquet`/
`faculty.parquet` under the SAME --proc directory as its own raw cache — but
those canonical tables live in data/processed/ while the tracked backfill
artifacts live in data/nih_nsf_backfill/ (the raw-fetch cache was moved there
for git tracking after the original live run; the two directories were never
meant to be the same --proc root). Rather than fight that directory
mismatch, this script does the one thing that actually changed — rerun
propose_faculty_matches() over the ALREADY-CACHED investigator tables — and
leaves the raw JSON cache and the abstract backfill completely untouched.

Runs at FACULTY_MATCH_MIN (90), the module's own default — NOT a lowered
threshold. A lowered 75 was tried and rejected during this pass: it looked
safe in aggregate (the 75-90 band was characterized as "legitimate
nickname/initial variants" project-wide), but a direct spot-check of the
specific matches this script's own comma-fix newly surfaced in the 75-90
band showed the opposite for exactly the highest-stakes population (grants
with no PI at all) — e.g. "Julie Chen" (77.8) resolved to roster entry
"CHEN, JIM JIM", "Guido Mueller" (77.8) to "MUELLER, AMY", "John Williams"
(76.2) to "WILLIAMS, MARK C", "Lara Anderson" (76.2) to "ANDERSON, ERIC
WILLIAM" — four different-first-name collisions, not nicknames. Every
match at >=90 in this same batch, by contrast, was a clean exact-name hit.
Kept the comma fix (independently verified safe and valuable on its own —
it alone recovers 5 more of these no-PI grants at the unchanged >=90
threshold) and dropped the threshold change entirely, rather than ship a
"more complete" merge that trades real coverage gains for real false
positives. `propose_faculty_matches`'s `min_score` parameter is still
available for future analysis, just not used here.

Usage:
    python -m scripts._refresh_investigator_matches
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.backfill_nih_reporter import FACULTY_MATCH_MIN, propose_faculty_matches

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
BACKFILL = REPO_ROOT / "data" / "nih_nsf_backfill"
MIN_SCORE = FACULTY_MATCH_MIN


def _refresh(label: str, investigators_path: Path, out_path: Path, faculty: pd.DataFrame) -> None:
    if not investigators_path.exists():
        print(f"{label}: skipped, {investigators_path} not found")
        return
    investigators = pd.read_parquet(investigators_path)
    before_n = pd.read_parquet(out_path)["faculty_id"].nunique() if out_path.exists() else 0
    proposals = propose_faculty_matches(investigators, faculty, min_score=MIN_SCORE)
    after_n = proposals["faculty_id"].nunique() if not proposals.empty else 0
    proposals.to_parquet(out_path, index=False)
    proposals.to_csv(out_path.with_suffix(".csv"), index=False)
    print(f"{label}: {len(investigators)} investigator rows -> {len(proposals)} proposal rows "
          f"({before_n} -> {after_n} distinct faculty matched) -> wrote {out_path}")


def main() -> None:
    faculty = pd.read_parquet(PROC / "faculty.parquet")
    _refresh("NIH", BACKFILL / "grant_nih_investigators.parquet",
              BACKFILL / "investigator_faculty_proposals.parquet", faculty)
    _refresh("NSF", BACKFILL / "grant_nsf_investigators.parquet",
              BACKFILL / "investigator_faculty_proposals_nsf.parquet", faculty)


if __name__ == "__main__":
    main()
