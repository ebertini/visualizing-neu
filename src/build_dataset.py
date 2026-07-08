"""
Data Pipeline: load raw .xlsx files, clean them, and export the canonical
Parquet tables to `data/processed/`.

Outputs
-------
1. faculty.parquet
       Faculty roster from the HR Snowflake export (supersedes
       faculty-list-2025). Adds hire date, terminal degree, and
       termination info so downstream analyses can apply hire-date filters.

2. grants.parquet
       One row per grant from ri_matches_grants_2026, enriched with:
         - AAD federal-grant-coverage columns (DB Coverage, PI Names
           Available, Co-PI Available) joined on agency name,
         - the most-recently-updated abstract + title + funding metadata
           from grants-with-abstract, merged on grant id.

3. faculty_grants.parquet
       Faculty -> grants lookup. Union of (faculty, grant) pairs from BOTH
       ri_matches_grants_2026 and grants-with-coPI. Every `personname`
       is preserved as a row; rows missing a client faculty id get
       `faculty_id = "00000"` (unresolved-name bucket).

4. grant_orphaned_abstracts.parquet
       Abstract records from grants-with-abstract that do NOT match any
       Northeastern grant_id in grants.parquet. Kept as a separate table
       for anyone who wants the extended NSF/NIH corpus (used by the
       topic model to enrich vocabulary).

Run:
    python src/build_dataset.py --input-dir DataSet --output-dir data/processed
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _lower_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _normalize_rank(rank) -> str:
    if pd.isna(rank):
        return "Unknown"
    r = str(rank).strip().lower()
    if "teaching" in r:
        if "associate" in r or "assoc" in r:
            return "Associate Teaching Professor"
        if "assistant" in r:
            return "Assistant Teaching Professor"
        return "Teaching Professor"
    if "research" in r and "professor" in r:
        return "Research Professor"
    if "professor" in r:
        if "associate" in r:
            return "Associate Professor"
        if "assistant" in r:
            return "Assistant Professor"
        return "Professor"
    if "lecturer" in r:
        return "Lecturer"
    if "visiting" in r or "adjunct" in r:
        return "Visiting / Adjunct"
    return "Other"


def _normalize_agency(name) -> str:
    """Normalize agency names for fuzzy-joining ri_matches <-> AAD."""
    if pd.isna(name):
        return ""
    s = str(name).strip().lower()
    s = s.replace("dept.", "department").replace("dept ", "department ")
    s = re.sub(r"\s+", " ", s)
    return s


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────────────

class DataPipeline:
    INPUT_FILES = {
        "hr_faculty":    "HR Snowflake faculty list 2025 fall update 6.15.2026.xlsx",
        "ri_matches":    "ri_matches_grants_2026.xlsx",
        "grants_copi":   "grants-with-coPI.xlsx",
        "grants_abs":    "grants-with-abstract.xlsx",
        "aad_coverage":  "aad_2024_federal_grant_coverage_list.xlsx",
        "unmatched":     "UnmatchedFaculty.csv",
    }

    def __init__(self, input_dir: Path, output_dir: Path):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw: dict[str, pd.DataFrame] = {}
        self.processed: dict[str, pd.DataFrame] = {}
        self.validation_log: list[str] = []

    def _log_check(self, msg: str) -> None:
        log.info(msg)
        self.validation_log.append(msg)

    # ── Load ──────────────────────────────────────────────────────────────────

    def load_raw(self) -> None:
        log.info("Loading raw files...")
        for key, fname in self.INPUT_FILES.items():
            path = self.input_dir / fname
            if not path.exists():
                raise FileNotFoundError(f"Missing input file: {path}")
            if key == "aad_coverage":
                df = pd.read_excel(path, sheet_name="AAD2024 Federal Grants")
            elif key == "unmatched":
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)
            self.raw[key] = df
            log.info(f"  {key}: {df.shape}  ({fname})")

    # ── Build: faculty (HR Snowflake + UnmatchedFaculty supplement) ─────────

    def _faculty_name_lookup(self) -> dict[str, str]:
        """Build faculty_id -> most-common personname from the grant tables.

        HR Snowflake does not carry a name column, so faculty names come from
        the `personname` field in ri_matches / grants-with-coPI.
        """
        ri   = _lower_cols(self.raw["ri_matches"])[["clientfacultyid", "personname"]]
        copi = _lower_cols(self.raw["grants_copi"])[["clientfacultyid", "personname"]]
        combined = pd.concat([ri, copi], ignore_index=True)
        combined["clientfacultyid"] = combined["clientfacultyid"].astype(str)
        combined["personname"] = combined["personname"].fillna("").str.strip()
        combined = combined[combined["personname"] != ""]
        return (combined.groupby("clientfacultyid")["personname"]
                .agg(lambda s: s.mode().iloc[0])
                .to_dict())

    def build_faculty(self) -> pd.DataFrame:
        log.info("Building faculty.parquet (HR Snowflake + UnmatchedFaculty supplement)...")
        df = _lower_cols(self.raw["hr_faculty"])

        # Drop redundant code column (we keep the human-readable name)
        df = df.drop(columns=[c for c in ["superior_academic_unit_code"] if c in df.columns])

        # Standardize the primary key name across all outputs
        df = df.rename(columns={"employee_id": "faculty_id"})
        df["faculty_id"] = df["faculty_id"].astype(str)
        df["hire_date"] = pd.to_datetime(df["hire_date"], errors="coerce")
        df["termination_date"] = pd.to_datetime(df["termination_date"], errors="coerce")
        df["academic_rank"] = df["academic_rank"].apply(_normalize_rank)

        # Attach faculty_name derived from grant tables
        name_lookup = self._faculty_name_lookup()
        df["faculty_name"] = df["faculty_id"].map(name_lookup).fillna("")

        # UnmatchedFaculty supplement: faculty who appear in grant tables but
        # are not in the HR snapshot (usually departed faculty with historical
        # grants). Also fills academic_unit for any HR rows that were missing it.
        supp = self.raw["unmatched"].copy()
        supp.columns = [c.strip().lower() for c in supp.columns]
        supp["faculty_id"] = supp["faculty_id"].astype(str)
        for c in ["faculty_name", "superior_academic_unit", "academic_unit"]:
            supp[c] = supp[c].fillna("").astype(str).str.strip()

        # (1) Fill missing academic_unit on HR rows whose faculty_id is in supplement
        unit_fill = supp.set_index("faculty_id")["academic_unit"].to_dict()
        # cast out of category so we can assign, then re-cast below
        df["academic_unit"] = df["academic_unit"].astype("object")
        mask = df["academic_unit"].isna() & df["faculty_id"].isin(unit_fill)
        df.loc[mask, "academic_unit"] = df.loc[mask, "faculty_id"].map(unit_fill)

        # (2) Add supplement rows for faculty_ids not already present in HR
        existing_ids = set(df["faculty_id"])
        new_rows = supp[~supp["faculty_id"].isin(existing_ids)].copy()
        n_added = len(new_rows)
        for col in df.columns:
            if col not in new_rows.columns:
                new_rows[col] = pd.NA
        new_rows = new_rows[df.columns.tolist()]
        df = pd.concat([df, new_rows], ignore_index=True)

        # Reorder: identity columns first
        head = ["faculty_id", "faculty_name"]
        df = df[head + [c for c in df.columns if c not in head]]

        # Final type coercion (categories after all edits)
        for col in [
            "superior_academic_unit", "academic_unit", "academic_track_type",
            "academic_rank", "tenure_status", "location_address_country",
            "termination_status",
        ]:
            if col in df.columns:
                df[col] = df[col].astype("category")

        df = df.drop_duplicates(subset=["faculty_id"]).reset_index(drop=True)

        n_named = (df["faculty_name"].fillna("") != "").sum()
        self._log_check(
            f"faculty: {len(df)} rows ({n_added} added from UnmatchedFaculty) | "
            f"hire_date populated: {df['hire_date'].notna().sum()} | "
            f"faculty_name populated: {n_named}"
        )
        return df

    # ── Build: grants (ri_matches enriched with AAD coverage) ────────────────

    def build_grants(self) -> pd.DataFrame:
        log.info("Building grants.parquet (ri_matches + AAD coverage)...")
        df = _lower_cols(self.raw["ri_matches"])

        # Drop the constant "Northeastern University" column if present
        df = df.drop(columns=[c for c in ["institutionname"] if c in df.columns])

        # Dedupe to one row per grant (ri_matches has one row per grant×faculty)
        grants = df.drop_duplicates(subset=["grantid"]).reset_index(drop=True)

        # Type coercion — force string on mixed-type id columns
        for c in ["grantid", "agencygrantid", "agencycode"]:
            if c in grants.columns:
                grants[c] = grants[c].astype(str)
        grants["startdate"] = pd.to_datetime(grants["startdate"], errors="coerce")
        grants["enddate"] = pd.to_datetime(grants["enddate"], errors="coerce")
        grants["awarddate"] = pd.to_datetime(grants["awarddate"], errors="coerce")
        if "agencyname" in grants.columns:
            grants["agencyname"] = grants["agencyname"].str.strip()

        # Keep grant-level fields only (drop per-faculty fields like personname/iscopi
        # which belong in faculty_grants.parquet)
        keep = [
            "grantid", "grantname", "agencycode", "agencyname", "agencygrantid",
            "totaldollars", "dollarsperyear", "durationinyears",
            "startdate", "enddate", "awarddate", "startdateyear",
            "countrycode", "isgovernment", "isresearch",
        ]
        grants = grants[[c for c in keep if c in grants.columns]]

        # Merge AAD coverage by fuzzy-normalized agency name
        aad = self._build_agency_coverage()
        grants["_agency_key"] = grants["agencyname"].apply(_normalize_agency)

        matched = self._fuzzy_match_agencies(
            grants["_agency_key"].dropna().unique().tolist(),
            aad["_agency_key"].tolist(),
        )
        grants["_agency_match"] = grants["_agency_key"].map(matched)
        grants = grants.merge(
            aad.drop(columns=["agency"]),
            how="left",
            left_on="_agency_match",
            right_on="_agency_key",
            suffixes=("", "_aad"),
        )
        grants = grants.drop(columns=["_agency_key", "_agency_match", "_agency_key_aad"], errors="ignore")

        # Standardize primary key name
        grants = grants.rename(columns={"grantid": "grant_id"})

        cov_rate = grants["db_coverage"].notna().mean() * 100 if "db_coverage" in grants.columns else 0
        self._log_check(
            f"grants: {len(grants)} unique grants | "
            f"AAD coverage merged: {cov_rate:.1f}% of grants have agency metadata"
        )
        return grants

    def _build_agency_coverage(self) -> pd.DataFrame:
        """Collapse the AAD coverage sheet to one row per agency."""
        aad = self.raw["aad_coverage"].copy()
        aad.columns = [c.strip() for c in aad.columns]
        aad = aad.rename(columns={
            "Agency": "agency",
            "PI Names Available": "pi_names_available",
            "DB Coverage": "db_coverage",
            "Co-PI Available": "copi_available",
        })
        # Take first non-null value per agency across divisions
        agg = (
            aad.groupby("agency", as_index=False)
            .agg({
                "pi_names_available": lambda s: s.dropna().iloc[0] if s.dropna().size else None,
                "db_coverage":        lambda s: s.dropna().iloc[0] if s.dropna().size else None,
                "copi_available":     lambda s: s.dropna().iloc[0] if s.dropna().size else None,
            })
        )
        agg["_agency_key"] = agg["agency"].apply(_normalize_agency)
        return agg

    @staticmethod
    def _fuzzy_match_agencies(
        ri_keys: list[str], aad_keys: list[str], threshold: int = 85
    ) -> dict[str, str | None]:
        """Map each ri agency key -> best AAD agency key (or None if no match)."""
        out: dict[str, str | None] = {}
        for k in ri_keys:
            if not k:
                out[k] = None
                continue
            if k in aad_keys:
                out[k] = k
                continue
            best = process.extractOne(k, aad_keys, scorer=fuzz.token_set_ratio)
            out[k] = best[0] if best and best[1] >= threshold else None
        return out

    # ── Build: grant_abstracts split (merged into grants + orphans separately) ─

    UNMATCHED_ID = "00000"

    def _split_abstracts(self, grants_grant_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Split grants-with-abstract into (matched, orphaned).

        Matched rows are collapsed to one row per grant_id by picking the row
        with the most recent `updateddate` (fall back to `createddate`, then
        row order). Only the following columns are carried forward for the
        merge into grants.parquet:
            grant_id, title_from_abstract, abstract, funding_status,
            type_of_funding, funding_source.
        Orphans keep all their original columns.
        """
        df = _lower_cols(self.raw["grants_abs"])

        # Drop columns that are essentially empty
        drop = ["aacsb_-_type_of_intellectual_contribution",
                "aacsb_-_mission",
                "aacsb_-_portfolio_of_intellectual_contribution"]
        df = df.drop(columns=[c for c in drop if c in df.columns])

        df["id"] = df["id"].astype(str)
        df["personid"] = df["personid"].astype(str)
        for c in ["start_date", "end_date", "createddate", "updateddate", "deprecateddate"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
        for c in ["title", "abstract", "sponsor", "sourcetype",
                  "sourceactivityid", "proposal/award/contract_id",
                  "university_grant_id", "funding_status", "type_of_funding",
                  "funding_source", "url/link"]:
            if c in df.columns:
                df[c] = df[c].fillna("").astype(str)

        df["sourceactivityid"] = df["sourceactivityid"].astype(str)
        matched_mask = df["sourceactivityid"].isin(grants_grant_ids) & (df["sourceactivityid"] != "")

        matched_raw = df[matched_mask].copy()
        orphaned    = df[~matched_mask].reset_index(drop=True)

        # For each matched grant, pick the most-recently-updated abstract row.
        # Sort by (updateddate, createddate) descending, then drop_duplicates.
        sort_keys = [c for c in ["updateddate", "createddate"] if c in matched_raw.columns]
        if sort_keys:
            matched_raw = matched_raw.sort_values(sort_keys, ascending=False, na_position="last")
        matched = matched_raw.drop_duplicates(subset=["sourceactivityid"], keep="first")

        keep_cols = {
            "sourceactivityid": "grant_id",
            "title":            "title_from_abstract",
            "abstract":         "abstract",
            "funding_status":   "funding_status",
            "type_of_funding":  "type_of_funding",
            "funding_source":   "funding_source",
        }
        matched = (matched[[c for c in keep_cols if c in matched.columns]]
                   .rename(columns=keep_cols)
                   .reset_index(drop=True))

        self._log_check(
            f"grant_abstracts split: {len(matched)} matched (merged into grants), "
            f"{len(orphaned)} orphaned (saved separately). "
            f"Total abstract records: {len(df)}"
        )
        return matched, orphaned

    # ── Build: faculty_grants (union of ri_matches + grants-with-coPI) ───────

    def build_faculty_grants(self) -> pd.DataFrame:
        log.info("Building faculty_grants.parquet (union of ri_matches + grants-with-coPI)...")

        ri = _lower_cols(self.raw["ri_matches"])
        copi = _lower_cols(self.raw["grants_copi"])

        cols = ["grantid", "clientfacultyid", "personname", "iscopi"]
        ri_sub = ri[cols].copy()
        copi_sub = copi[cols].copy()

        for d in (ri_sub, copi_sub):
            d["grantid"] = d["grantid"].astype(str)
            # Preserve rows with missing clientfacultyid — stamp UNMATCHED_ID
            # ("00000") so we don't lose personnames that aren't in HR.
            d["clientfacultyid"] = (
                d["clientfacultyid"].astype(str)
                 .replace({"nan": self.UNMATCHED_ID, "None": self.UNMATCHED_ID, "": self.UNMATCHED_ID})
                 .fillna(self.UNMATCHED_ID)
            )
            d["personname"] = d["personname"].fillna("").str.strip()
            d["iscopi"] = d["iscopi"].fillna(False).astype(bool)

        ri_sub["source"] = "ri_matches"
        copi_sub["source"] = "grants_with_copi"

        combined = pd.concat([ri_sub, copi_sub], ignore_index=True)
        # Drop rows that have neither an id nor a name — those are truly empty.
        combined = combined[(combined["clientfacultyid"] != self.UNMATCHED_ID) |
                            (combined["personname"] != "")]

        # For unmatched-id rows we key on personname so distinct un-IDed PIs
        # remain separate; for matched-id rows we key on clientfacultyid.
        combined["_dedup_person"] = combined.apply(
            lambda r: r["personname"] if r["clientfacultyid"] == self.UNMATCHED_ID
                       else r["clientfacultyid"],
            axis=1,
        )

        agg = (
            combined.groupby(["_dedup_person", "grantid"], as_index=False)
            .agg(
                clientfacultyid=("clientfacultyid", "first"),
                personname=("personname", lambda s: s.dropna().iloc[0] if s.dropna().size else ""),
                iscopi=("iscopi", "max"),
                source=("source", lambda s: "both" if s.nunique() > 1 else s.iloc[0]),
            )
            .drop(columns=["_dedup_person"])
        )
        agg = agg.rename(columns={"clientfacultyid": "faculty_id", "grantid": "grant_id",
                                  "personname": "faculty_name", "iscopi": "is_copi"})
        agg["is_pi"] = ~agg["is_copi"]
        agg = agg[["faculty_id", "faculty_name", "grant_id", "is_pi", "is_copi", "source"]]

        # Quick stats
        n_pairs      = len(agg)
        n_pi         = int((~agg["is_copi"]).sum())
        n_copi       = int(agg["is_copi"].sum())
        n_only_copi  = int((agg["source"] == "grants_with_copi").sum())
        n_only_ri    = int((agg["source"] == "ri_matches").sum())
        n_both       = int((agg["source"] == "both").sum())
        n_unmatched  = int((agg["faculty_id"] == self.UNMATCHED_ID).sum())
        self._log_check(
            f"faculty_grants: {n_pairs} unique (faculty, grant) pairs | "
            f"PI rows: {n_pi} | co-PI rows: {n_copi} | "
            f"source: ri-only={n_only_ri}, copi-only={n_only_copi}, both={n_both} | "
            f"faculty_id=00000 (unresolved): {n_unmatched}"
        )
        return agg

    def _annotate_at_neu(
        self,
        faculty_grants: pd.DataFrame,
        faculty: pd.DataFrame,
        grants: pd.DataFrame,
    ) -> pd.DataFrame:
        """Add hire-date context to each faculty-grant row.

        Adds three columns:
          hire_date       - faculty hire date (NaT for supplement rows or when
                             faculty_id == '00000')
          grant_startdate - grant start date
          neu_status      - categorical:
                              'earned_at_neu'      grant started on/after hire
                              'prior_institution'  grant started strictly before
                                                    hire (does not count as
                                                    NEU work)
                              'unknown'            hire or start date missing
        """
        out = (
            faculty_grants
            .merge(faculty[["faculty_id", "hire_date"]], on="faculty_id", how="left")
            .merge(grants[["grant_id", "startdate"]].rename(columns={"startdate": "grant_startdate"}),
                   on="grant_id", how="left")
        )

        known = out["hire_date"].notna() & out["grant_startdate"].notna()
        status = pd.Series("unknown", index=out.index, dtype="object")
        status.loc[known & (out["grant_startdate"] >= out["hire_date"])] = "earned_at_neu"
        status.loc[known & (out["grant_startdate"] <  out["hire_date"])] = "prior_institution"
        out["neu_status"] = pd.Categorical(
            status, categories=["earned_at_neu", "prior_institution", "unknown"]
        )

        counts    = status.value_counts()
        n_earned  = int(counts.get("earned_at_neu", 0))
        n_prior   = int(counts.get("prior_institution", 0))
        n_unknown = int(counts.get("unknown", 0))
        pct_prior = n_prior / max(n_earned + n_prior, 1) * 100
        self._log_check(
            f"faculty_grants.neu_status: earned_at_neu={n_earned} | "
            f"prior_institution={n_prior} ({pct_prior:.1f}% of dated rows) | "
            f"unknown={n_unknown}"
        )
        return out

    # ── Export ───────────────────────────────────────────────────────────────

    def export(self) -> None:
        log.info("Writing Parquet + CSV files...")
        for name, df in self.processed.items():
            pq_path  = self.output_dir / f"{name}.parquet"
            csv_path = self.output_dir / f"{name}.csv"
            df.to_parquet(pq_path, index=False, compression="snappy")
            # CSVs are the PI-shareable copy. Keep NaT/NaN as empty; write UTF-8
            # with a BOM so Excel opens non-ASCII names correctly.
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            log.info(f"  {pq_path.name}: {df.shape}  ({pq_path.stat().st_size / 1e6:.1f} MB pq, "
                     f"{csv_path.stat().st_size / 1e6:.1f} MB csv)")

        report_path = self.output_dir / "PIPELINE_VALIDATION.txt"
        with open(report_path, "w") as f:
            f.write("Data Pipeline Validation Report\n")
            f.write(f"Generated: {pd.Timestamp.now()}\n")
            f.write("=" * 72 + "\n\n")
            for line in self.validation_log:
                f.write(line + "\n")
            f.write("\nOutput tables:\n")
            for name, df in self.processed.items():
                f.write(f"  {name}.parquet: {df.shape[0]} rows x {df.shape[1]} cols\n")
        log.info(f"  {report_path.name}")

    # ── Orchestrate ──────────────────────────────────────────────────────────

    def run(self) -> None:
        self.load_raw()
        self.processed["faculty"]        = self.build_faculty()
        grants                            = self.build_grants()
        matched_abs, orphaned_abs         = self._split_abstracts(set(grants["grant_id"]))
        # Merge matched abstracts into grants (one row per grant_id)
        grants = grants.merge(matched_abs, on="grant_id", how="left")
        for c in ["title_from_abstract", "abstract", "funding_status",
                  "type_of_funding", "funding_source"]:
            if c in grants.columns:
                grants[c] = grants[c].fillna("")
        n_with_abs = int((grants["abstract"].fillna("") != "").sum()) if "abstract" in grants.columns else 0
        self._log_check(f"grants: {n_with_abs}/{len(grants)} rows have a non-empty abstract")
        self.processed["grants"]                     = grants
        self.processed["grant_orphaned_abstracts"]   = orphaned_abs
        self.processed["faculty_grants"]             = self.build_faculty_grants()
        self.processed["faculty_grants"]             = self._annotate_at_neu(
            self.processed["faculty_grants"],
            self.processed["faculty"],
            self.processed["grants"],
        )
        self.export()
        log.info("Pipeline complete.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", type=Path, default=Path("DataSet"))
    p.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = p.parse_args()
    try:
        DataPipeline(args.input_dir, args.output_dir).run()
    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
