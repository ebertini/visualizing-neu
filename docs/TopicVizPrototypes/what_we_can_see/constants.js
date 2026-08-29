// constants.js — small shared lookups used across the grant/PI facet grids
// and the "What's missing" tab. Split out of what_we_can_see.html's single
// inline script for readability; behavior is unchanged, only the module
// boundary is new (see docs/TOPIC_MODEL_REFIT_CHECKLIST.md).
import { COVERAGE } from "./data.js";

const E = window.ENRICO;

export const AGENCIES = COVERAGE.agencies;                 // ORDER, 9
export const YEARS = COVERAGE.years;                        // full 1995-2026

// Shared by the cliff chart and the by-agency/by-year coverage bars on the
// "What's missing" tab (the old agency x year heatmap this used to feed is
// gone, but per-year and per-agency lookups are still useful on their own).
export const cellByKey = {};
COVERAGE.cells.forEach(c=> cellByKey[c.agency+"|"+c.year] = c);

export const NOISE = E.NOISE_GREY;
export const ST_LABEL = {earned_at_neu: "Earned at NEU", prior_institution: "Prior institution", unknown: "Unknown dates"};
export const STATUS_COLOR = {earned_at_neu: "#0072B2", prior_institution: "#F28E2B", unknown: "#9AA0A6"};

// Local parent-theme palette for THIS panel only — deliberately NOT
// E.PARENT_COLORS (shared/enrico.js), which is copied verbatim from the
// PI's own docs/EnricoVis/topic_hierarchy.html so his apps stay visually
// consistent, and which topic_flow.html also reads via E.parentColor().
// Changing the shared constant would silently recolor both of those too.
// This facet grid's marks are much smaller (4.2px) than a scatter-plot
// point, so it gets its own set: D3/matplotlib's "tab10" categorical
// palette, well-vetted for exactly this — 8 maximally distinct hues at
// small mark sizes — with tab10's usual grey 8th color swapped for cyan so
// nothing here can be confused with NOISE_GREY (#c7ccd3), reserved for
// Unassigned/no-data.
//
// 7 in active use (curated keyword-classifier taxonomy, was 8 under BERTopic)
// + 5 SPARE colors (indices 7-11) — pre-allocated headroom, same idea as
// shared/enrico.js's TOPIC_COLORS/PARENT_COLORS: facets.js already indexes
// this with `% TP_COLORS.length`, so an 8th+ parent theme gets a real,
// distinct color the moment a human curates its name, instead of silently
// reusing color 0. The spares continue the same full-saturation "tab10
// family" this palette is built from, not an arbitrary pick.
export const TP_COLORS = [
  "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#17becf",
  "#bcbd22", "#66A61E", "#E6AB02", "#8DA0CB",
];

// Hand-curated short forms for the 7 parent themes (curated keyword-classifier
// taxonomy, promoted 2026-08-29 — replaces the prior 8-parent BERTopic-era
// set) — most of the full names (from build_viz_aggregates.py's PARENT_NAMES)
// run past what fits a row/column label or a legend chip without truncating
// mid-word. Only used for row/column headers and the color legend; the
// per-grant hover tooltip reads the full name straight from VIZ_META.parents
// independently of this, so it's unaffected.
export const PARENT_SHORT = {
  0: "Biomedical Sciences", 1: "Public & Behav. Health", 2: "Environment & Ecology",
  3: "Soc. Sci & Workforce Dev", 4: "Materials & Civil Eng",
  5: "Math & Fundamental Physics", 6: "Computing & Robotics",
};

// Same idea, for college names — "College of Social Sciences and
// Humanities" is 42 characters, wider than the whole row-label lane. Applied
// to any level list built from a raw college string: GRANT_FACET_DEFS.col,
// PI_FACET_DEFS.col, and PI_FACET_DEFS.dept (department strings include the
// same college names verbatim wherever a faculty's home unit IS the
// college). Display-only — the underlying data and every hover tooltip that
// reads FACETS.levels.col / FACETS_PI.levels.col directly (not through this
// map) keep the full name; row/column labels carry a `full` field alongside
// the shortened `label` so their own hover still shows it in full.
export const COLLEGE_SHORT = {
  "College of Engineering": "COE",
  "College of Science": "COS",
  "Khoury College of Computer Sciences": "Khoury",
  "Bouvé College of Health Sciences": "Bouvé",
  "College of Social Sciences and Humanities": "CSSH",
  "College of Social Sciences & Humanities": "CSSH",
  "D'Amore-McKim School of Business": "DMSB",
  "College of Professional Studies": "CPS",
  "College of Arts, Media and Design": "CAMD",
  "School of Law": "Law",
  "Northeastern University London": "NU London",
  "Mills College at Northeastern": "Mills",
  "Network science institute": "NetSI",
  "PI not on 2025 roster": "Not on roster",
};
