"""
Data Pipeline: load raw .xlsx files, clean them, and export 4 canonical Parquet
tables to `data/processed/`.

Outputs
-------
1. faculty.parquet
       Faculty roster from the HR Snowflake export (supersedes
       faculty-list-2025). Adds hire date, terminal degree, and
       termination info so downstream analyses can apply hire-date filters.

2. grants.parquet
       One row per grant from ri_matches_grants_2026, enriched with the
       AAD federal-grant-coverage columns
       (DB Coverage, PI Names Available, Co-PI Available) joined on agency.

3. grant_abstracts.parquet
       One row per grant abstract from grants-with-abstract
       (titles + abstract text, plus sponsor / dollar / date metadata).

4. faculty_grants.parquet
       Faculty -> grants lookup. Union of (faculty, grant) pairs from BOTH
       ri_matches_grants_2026 and grants-with-coPI, deduplicated on
       (clientfacultyid, grantid). Includes the is_copi flag so analyses
       can choose PI-only vs. full-credit accounting.

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

    # ── Build: grant_abstracts ───────────────────────────────────────────────

    def build_grant_abstracts(self) -> pd.DataFrame:
        log.info("Building grant_abstracts.parquet...")
        df = _lower_cols(self.raw["grants_abs"])

        # Drop columns that are essentially empty or not useful for analysis
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

        coverage = (df["abstract"] != "").mean() * 100 if "abstract" in df.columns else 0
        self._log_check(f"grant_abstracts: {len(df)} rows | abstract coverage: {coverage:.1f}%")
        return df.reset_index(drop=True)

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
            d["clientfacultyid"] = d["clientfacultyid"].astype(str)
            d["personname"] = d["personname"].fillna("").str.strip()
            d["iscopi"] = d["iscopi"].fillna(False).astype(bool)

        ri_sub["source"] = "ri_matches"
        copi_sub["source"] = "grants_with_copi"

        combined = pd.concat([ri_sub, copi_sub], ignore_index=True)

        # If the same (faculty, grant) appears in both, keep one row but
        # mark its source as "both" and OR the iscopi flag.
        agg = (
            combined.groupby(["clientfacultyid", "grantid"], as_index=False)
            .agg(
                personname=("personname", lambda s: s.dropna().iloc[0] if s.dropna().size else ""),
                iscopi=("iscopi", "max"),
                source=("source", lambda s: "both" if s.nunique() > 1 else s.iloc[0]),
            )
        )
        agg = agg.rename(columns={"clientfacultyid": "faculty_id", "grantid": "grant_id",
                                  "personname": "faculty_name", "iscopi": "is_copi"})
        agg = agg[["faculty_id", "faculty_name", "grant_id", "is_copi", "source"]]

        # Quick stats
        n_pairs = len(agg)
        n_pi    = (~agg["is_copi"]).sum()
        n_copi  = agg["is_copi"].sum()
        n_only_copi = (agg["source"] == "grants_with_copi").sum()
        n_only_ri   = (agg["source"] == "ri_matches").sum()
        n_both      = (agg["source"] == "both").sum()
        self._log_check(
            f"faculty_grants: {n_pairs} unique (faculty, grant) pairs | "
            f"PI rows: {n_pi} | co-PI rows: {n_copi} | "
            f"source: ri-only={n_only_ri}, copi-only={n_only_copi}, both={n_both}"
        )
        return agg

    # ── Export ───────────────────────────────────────────────────────────────

    def export(self) -> None:
        log.info("Writing Parquet files...")
        for name, df in self.processed.items():
            path = self.output_dir / f"{name}.parquet"
            df.to_parquet(path, index=False, compression="snappy")
            log.info(f"  {path.name}: {df.shape}")

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
        self.processed["faculty"]          = self.build_faculty()
        self.processed["grants"]           = self.build_grants()
        self.processed["grant_abstracts"]  = self.build_grant_abstracts()
        self.processed["faculty_grants"]   = self.build_faculty_grants()
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
