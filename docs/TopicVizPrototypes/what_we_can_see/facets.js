// facets.js — the facet-definition tables driving both unit-visualization
// grids, plus the small helpers that read a facetDefs table generically.
// Split out of what_we_can_see.html's single inline script; behavior is
// unchanged, only the module boundary is new.
import { FACETS, FACETS_PI, VIZ_META } from "./data.js";
import { NOISE, ST_LABEL, STATUS_COLOR, TP_COLORS, PARENT_SHORT, COLLEGE_SHORT } from "./constants.js";

const E = window.ENRICO;

/* ============================================================
   "Every grant, arranged" — the unit visualization.
   One <rect class="markrect"> per grant (FACETS.n = 2676), always. Every
   facet below has an explicit bin for missing/unmatched values (the two
   college miss bins, the "none" abstract source, etc.) so a mark is never
   silently dropped when you switch "Arrange by" / "Split by" — only ever
   repositioned. Marks are keyed on grant id (FACETS.ids[i]) in the d3 join
   below (see grid.js), which is what makes switching facets *transition*
   marks to their new bin rather than redraw the whole chart from scratch.
   ============================================================ */

// Every facet declares:
//   ordinal   — has an intrinsic order that size-sorting would destroy
//               (start year, dollar band). Drives the sort control's
//               per-facet default (see defaultSortMode below).
//   legend    — "ramp" (a gradient bar, for a facet with too many ordered
//               levels to show as chips — just "yr" today, at ~30 levels)
//               or "chips" (the flat swatch-per-level row, everything else).
// PI feedback ("Is there a reason why you can't map certain categories to
// color?") — there wasn't a principled one. yr/amt/col used to have no real
// palette (every level rendered the same flat blue) and were hidden from
// "Color by" rather than fixed. Every facet below now has a real,
// distinct-per-level palette instead. (Abstract presence/source and PI-matched
// were removed as facet options entirely — see the "no longer a facet" note
// further down; markTooltip still surfaces abstract presence per-grant.)
export const GRANT_FACET_DEFS = {
  ag: {
    label: "Agency", ordinal: false, legend: "chips",
    values: () => FACETS.cols.ag,
    levels: () => VIZ_META.agencies.map((a, i) => ({key: i, label: a.key, color: a.color})),
  },
  yr: {
    label: "Start year", ordinal: true, legend: "ramp",
    values: () => FACETS.cols.yr,
    levels: () => {
      const uniq = Array.from(new Set(FACETS.cols.yr)).sort((a, b) => a - b);
      const real = uniq.filter(y => y !== -1);
      const span = (real[real.length - 1] - real[0]) || 1;
      const out = real.map(y => ({key: y, label: String(y), color: E.seqColor((y - real[0]) / span)}));
      return uniq.includes(-1) ? [{key: -1, label: "Unknown year", color: NOISE}, ...out] : out;
    },
  },
  col: {
    // Indices 0/1 are the two miss bins (see build_viz_aggregates.py's
    // NO_PI_LABEL / PI_OFF_ROSTER_LABEL) and stay NOISE — #c7ccd3 is reserved
    // for genuine no-data. Real colleges (index 2+) get a distinct color
    // each from the 25-topic palette, reused here as a general-purpose
    // strong categorical set rather than inventing a second one.
    label: "PI's college", ordinal: false, legend: "chips",
    values: () => FACETS.cols.col,
    levels: () => FACETS.levels.col.map((name, i) =>
      ({key: i, label: COLLEGE_SHORT[name] || name, full: name, color: i < 2 ? NOISE : E.topicColor(i - 2)})),
  },
  st: {
    label: "NEU attribution", ordinal: false, legend: "chips",
    values: () => FACETS.cols.st,
    levels: () => FACETS.levels.st.map((name, i) =>
      ({key: i, label: ST_LABEL[name] || name, color: STATUS_COLOR[name] || NOISE})),
  },
  // Abstract presence ("ab"), abstract source ("asrc"), and PI matched
  // ("pi") are no longer facet options — removed per feedback that they
  // cluttered the controls. FACETS.cols.ab/asrc/pi still exist in the data
  // (markTooltip reads FACETS.cols.ab directly, not through this table, so
  // per-grant "Has abstract"/"Title only" context in the hover tooltip is
  // unaffected) — only the Rows/Columns/Color *options* are gone.
  tp: {
    label: "Parent theme", ordinal: false, legend: "chips",
    values: () => FACETS.cols.tp,
    levels: () => VIZ_META.parents.slice().sort((a, b) => a.id - b.id)
      .map(p => ({key: p.id, label: p.id < 0 ? p.name : (PARENT_SHORT[p.id] || p.name),
        color: p.id < 0 ? NOISE : TP_COLORS[p.id % TP_COLORS.length]})),
  },
  tid: {
    // The leaf-topic facet the BERTopic model actually produces (25 topics +
    // noise) — not exposed as an "Arrange by" option before this rework.
    // VIZ_META.topics carries a "noise" flag on its id:-1 entry; filter it
    // out here so -1 isn't emitted twice (once explicitly, once from the list).
    label: "Topic (leaf)", ordinal: false, legend: "chips",
    values: () => FACETS.cols.tid,
    levels: () => [{key: -1, label: "Unassigned", color: NOISE}].concat(
      VIZ_META.topics.filter(t => !t.noise).sort((a, b) => a.id - b.id)
        .map(t => ({key: t.id, label: t.name, color: E.topicColor(t.id)}))),
  },
  amt: {
    label: "Dollar band", ordinal: true, legend: "chips",
    values: () => FACETS.cols.amt,
    levels: () => FACETS.levels.amt.map((name, i, arr) =>
      ({key: i, label: name, color: E.seqColor(arr.length > 1 ? i / (arr.length - 1) : 1)})),
  },
};
export const GRANT_ARRANGE_FACETS = ["ag", "yr", "col", "st", "tp", "tid", "amt"];

// Mirrors GRANT_FACET_DEFS above, over facets_pi.json (all 2,247 roster
// faculty) instead of facets.json (2,676 grants) — the "every PI" tab's own
// table. Every categorical field here already carries its own "gap" bin as
// index 0 (build_viz_aggregates.py's PI_NOT_RECORDED, or "No grants as PI"
// for the funding/theme facets) except "col" (college is ~100% known on the
// roster) — colored NOISE below wherever that bin is present, same
// reserved-grey convention as the grants table.
export const PI_FACET_DEFS = {
  col: {
    label: "College", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.col,
    levels: () => FACETS_PI.levels.col.map((name, i) =>
      ({key: i, label: COLLEGE_SHORT[name] || name, full: name, color: E.topicColor(i)})),
  },
  dept: {
    label: "Department", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.dept,
    levels: () => FACETS_PI.levels.dept.map((name, i) =>
      ({key: i, label: COLLEGE_SHORT[name] || name, full: name, color: i === 0 ? NOISE : E.topicColor(i - 1)})),
  },
  rank: {
    label: "Academic rank", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.rank,
    levels: () => FACETS_PI.levels.rank.map((name, i) => ({key: i, label: name, color: i === 0 ? NOISE : E.topicColor(i - 1)})),
  },
  track: {
    label: "Appointment track", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.track,
    levels: () => FACETS_PI.levels.track.map((name, i) => ({key: i, label: name, color: i === 0 ? NOISE : E.topicColor(i - 1)})),
  },
  tenure: {
    label: "Tenure status", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.tenure,
    levels: () => FACETS_PI.levels.tenure.map((name, i) =>
      ({key: i, label: name, color: name === "Not recorded" ? NOISE : ["#0072B2", "#F28E2B", "#2ca02c"][i % 3]})),
  },
  hire_yr: {
    label: "Hire year", ordinal: true, legend: "ramp",
    values: () => FACETS_PI.cols.hire_yr,
    levels: () => {
      const uniq = Array.from(new Set(FACETS_PI.cols.hire_yr)).sort((a, b) => a - b);
      const real = uniq.filter(y => y !== -1);
      const span = (real[real.length - 1] - real[0]) || 1;
      const out = real.map(y => ({key: y, label: String(y), color: E.seqColor((y - real[0]) / span)}));
      return uniq.includes(-1) ? [{key: -1, label: "Unknown hire year", color: NOISE}, ...out] : out;
    },
  },
  status: {
    label: "Employment status", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.status,
    levels: () => FACETS_PI.levels.status.map((name, i) => ({key: i, label: name, color: i === 0 ? "#0072B2" : "#9AA0A6"})),
  },
  hasgrants: {
    label: "Has grants in this corpus", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.hasgrants,
    levels: () => FACETS_PI.levels.hasgrants.map((name, i) => ({key: i, label: name, color: i === 0 ? NOISE : "#0072B2"})),
  },
  ngrants: {
    label: "Number of grants", ordinal: true, legend: "chips",
    values: () => FACETS_PI.cols.ngrants,
    levels: () => FACETS_PI.levels.ngrants.map((name, i, arr) =>
      ({key: i, label: name, color: E.seqColor(arr.length > 1 ? i / (arr.length - 1) : 1)})),
  },
  amt: {
    label: "Dollars as PI", ordinal: true, legend: "chips",
    values: () => FACETS_PI.cols.amt,
    levels: () => FACETS_PI.levels.amt.map((name, i, arr) =>
      ({key: i, label: name, color: i === 0 ? NOISE : E.seqColor((i - 1) / (arr.length - 2))})),
  },
  tp: {
    label: "Parent theme (as PI)", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.tp,
    // Indices 0 and 1 are two DIFFERENT no-data cases — "No grants as PI"
    // (never a PI at all) vs. "Unassigned" (was a PI, but no confident
    // topic) — so they shouldn't share one grey. "Unassigned" gets a
    // darker grey (#9AA0A6, already used elsewhere in this file as a
    // secondary/darker grey, e.g. the status facet's "Departed") rather
    // than NOISE (#c7ccd3) — still clearly "no real data," just visually
    // distinct from the "no grants" bin.
    levels: () => FACETS_PI.levels.tp.map((name, i) => ({key: i, label: i < 2 ? name : (PARENT_SHORT[i - 2] || name),
      color: i === 0 ? NOISE : i === 1 ? "#9AA0A6" : TP_COLORS[(i - 2) % TP_COLORS.length]})),
  },
};
export const PI_ARRANGE_FACETS = ["col", "dept", "rank", "track", "tenure", "hire_yr", "status", "hasgrants", "ngrants", "amt", "tp"];

// Every function below is shared by both unit-visualization grids ("Every
// grant" over facetDefs=GRANT_FACET_DEFS/data=FACETS, "Every PI" over
// PI_FACET_DEFS/FACETS_PI) — each takes facetDefs/data explicitly rather
// than closing over a single global table, which is what makes createGrid()
// (grid.js) able to instantiate the same grid logic twice.
export function populateSelect(sel, facetDefs, keys, withNone, current) {
  sel.innerHTML = "";
  if (withNone) {
    const o = document.createElement("option");
    o.value = ""; o.textContent = "— none —";
    sel.appendChild(o);
  }
  keys.forEach(k => {
    const o = document.createElement("option");
    o.value = k; o.textContent = facetDefs[k].label;
    sel.appendChild(o);
  });
  sel.value = current != null && (keys.includes(current) || current === "") ? current : (withNone ? "" : keys[0]);
}

// Per-facet smart default (PI feedback: "sort by size by default" — but an
// ordinal facet like start year or dollar band has a real intrinsic order
// that size-sorting would destroy, so those default to "natural" instead).
export function defaultSortMode(facetDefs, key) { return key && facetDefs[key].ordinal ? "natural" : "size"; }

export function populateOptions(sel, opts, current) {
  sel.innerHTML = "";
  opts.forEach(([value, label]) => {
    const o = document.createElement("option");
    o.value = value; o.textContent = label;
    sel.appendChild(o);
  });
  sel.value = opts.some(([v]) => v === current) ? current : opts[0][0];
}

export const SORT_OPTIONS = [["natural", "Natural order"], ["size", "Size"], ["dollars", "Size ($)"]];
