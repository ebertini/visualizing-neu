// facets.js — the facet-definition tables driving both unit-visualization
// grids, plus the small helpers that read a facetDefs table generically.
// Split out of what_we_can_see.html's single inline script; behavior is
// unchanged, only the module boundary is new.
import { FACETS, FACETS_PI, VIZ_META } from "./data.js";
import { NOISE, ST_LABEL, STATUS_COLOR, TP_COLORS, PARENT_SHORT, COLLEGE_SHORT, RANK_COLOR } from "./constants.js";

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
// distinct-per-level palette instead. (Abstract source and PI-matched were
// removed as facet options entirely — see the "no longer a facet" note
// further down; markTooltip still surfaces abstract presence per-grant.
// Abstract presence itself ("ab") was reinstated as a facet below.)
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
  // Abstract source ("asrc") and PI matched ("pi") are still not facet
  // options — removed per feedback that they cluttered the controls.
  // FACETS.cols.asrc/pi still exist in the data (unused by this table) but
  // aren't offered as Rows/Columns/Color choices.
  ab: {
    label: "Has abstract", ordinal: false, legend: "chips",
    values: () => FACETS.cols.ab,
    levels: () => [
      {key: 0, label: "Title only", color: NOISE},
      {key: 1, label: "Has abstract", color: "#0072B2"},
    ],
  },
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
  // How many distinct roster colleges a grant involves (PI + co-PIs) — a new
  // facet (PI feedback: "for each grant how many different colleges does it
  // involve?"). Banded small (0/1/2/3+) since 4+ is a rarity; ordinal since
  // "more colleges" is a real order, not an arbitrary category.
  ncol: {
    label: "Colleges involved", ordinal: true, legend: "chips",
    values: () => FACETS.cols.ncol,
    levels: () => FACETS.levels.ncol.map((name, i, arr) =>
      ({key: i, label: name, color: i === 0 ? NOISE : E.seqColor((i - 1) / Math.max(arr.length - 2, 1))})),
  },
  // Team size — count of DISTINCT people linked to a grant, any role.
  // Deliberately NOT a count of co-PI-flagged rows: verified against the
  // real corpus that a grant's `is_copi` flag is a per-row ROLE LABEL, not a
  // team-size signal — 291 of 602 "has a co-PI" grants actually have only
  // ONE person on record total (that person's role is recorded as "co-PI"
  // with no separate PI row present at all). Counting distinct people
  // instead gives the honest team size; every grant has >=1, so bands start
  // at "1" (solo) with no miss bin needed, unlike "Colleges involved" above.
  // Pairs with "PI's college" (Rows/Columns) + this (Color) to see team-size
  // distribution by college — the closest single-mark-per-grant view can
  // get to "how many co-PIs are from which colleges" (a true cross-college
  // pairing breakdown would need a different chart type, e.g. a matrix).
  team: {
    label: "Team size", ordinal: true, legend: "chips",
    values: () => FACETS.cols.team,
    levels: () => FACETS.levels.team.map((name, i, arr) =>
      ({key: i, label: name === "1" ? "1 (solo)" : name, color: E.seqColor(i / Math.max(arr.length - 1, 1))})),
  },
  // Both "Confidence" (the keyword classifier's own BM25F tier) and "How
  // this topic was decided" (keyword vs. LLM-adjudicated vs. low-confidence
  // vs. unassigned) were REMOVED as arrange/color/sort options here by
  // product decision — surfacing per-grant confidence/QA signal invited more
  // scrutiny ("why not all grants," "why is this one lower confidence")
  // than it was worth. The underlying data (FACETS.cols.conf/src,
  // FACETS.levels.conf/src) is untouched and still fully inspectable
  // directly in facets.json/the parquet — this removal is UI-surface only.
  // The one exception still shown per-grant is genuine Unassigned (a real
  // content gap), via a tooltip note in detail.js, not a facet here.
};
export const GRANT_ARRANGE_FACETS = ["ag", "yr", "col", "st", "ab", "tp", "tid", "amt", "ncol", "team"];

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
    // PI feedback: rank is nested — Teaching Professor and its two seniority
    // variants are one family, Professor and its two are a second family —
    // the row/column LABELING already groups these correctly (it's just an
    // ordinal string list), but coloring by bare level index broke that
    // grouping visually. RANK_COLOR (constants.js) fixes this: one hue per
    // family, darker = more senior, so a legend reader sees the ladder.
    label: "Academic rank", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.rank,
    levels: () => FACETS_PI.levels.rank.map((name, i) => ({key: i, label: name, color: RANK_COLOR[name] || NOISE})),
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
  // "Was this person ever a PI, ever a co-PI, or both, across their
  // different grants?" — is_pi/is_copi are mutually exclusive PER GRANT
  // ROW (verified: 2,368 PI rows / 776 co-PI rows, zero overlap), so
  // "co-PI" is only ever a per-grant label; this rolls it up to the one
  // per-faculty question that's actually answerable. Categorical, not a
  // ramp — these are four distinct identities (no grants / PI only /
  // co-PI only / both), not a magnitude scale. See the "pi_copi_role"
  // caveat for the "Co-PI only" bucket's known ~17% suspect rate.
  role: {
    label: "PI / co-PI role", ordinal: false, legend: "chips",
    values: () => FACETS_PI.cols.role,
    levels: () => FACETS_PI.levels.role.map((name, i) =>
      ({key: i, label: name, color: [NOISE, "#0072B2", "#F28E2B", "#2ca02c"][i] || NOISE})),
  },
  amt: {
    label: "Dollars as PI", ordinal: true, legend: "chips",
    values: () => FACETS_PI.cols.amt,
    levels: () => FACETS_PI.levels.amt.map((name, i, arr) =>
      ({key: i, label: name, color: i === 0 ? NOISE : E.seqColor((i - 1) / (arr.length - 2))})),
  },
  // "Dollars earned from grants a PI earned AT Northeastern" (PI feedback) —
  // the same PI-only credit model as "amt" above, further filtered to
  // neu_status == "earned_at_neu" per the funding-credit-model caveat. A
  // separate facet, not a redefinition of "amt".
  amt_neu: {
    label: "Dollars earned at NEU (as PI)", ordinal: true, legend: "chips",
    values: () => FACETS_PI.cols.amt_neu,
    levels: () => FACETS_PI.levels.amt_neu.map((name, i, arr) =>
      ({key: i, label: name, color: i === 0 ? NOISE : E.seqColor((i - 1) / Math.max(arr.length - 2, 1))})),
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
export const PI_ARRANGE_FACETS = ["col", "dept", "rank", "track", "tenure", "hire_yr", "status", "hasgrants", "ngrants", "role", "amt", "amt_neu", "tp"];

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

// PI feedback: "sort by... size of dollar and size of what — need
// clarification" — "Size" was ambiguous between grant COUNT and dollar
// amount; both options now spell out which.
// "Need a suggestion?" (PI feedback: entry-point questions that configure
// Rows/Columns/Color/Sort for you) — each preset is handed to
// grid.js's applyPreset(). Deliberately a small, curated set of genuinely
// common questions, not exhaustive — the controls dock still covers
// everything else. Keys must exist in the matching facetDefs table.
//
// Every preset here sets Rows AND Columns (a real 2D cross-tab, not just one
// axis with Color doing all the work) plus a Color and Sort that both add
// something — feedback on an earlier, simpler round of presets that mostly
// left Columns empty. One rule followed throughout: `sort` is ONE shared
// mode applied independently to both axes' own marginal totals (grid.js),
// so pairing an ordinal axis (year, dollar band, team size, hire year...)
// with "dollars"/"size" sort would reorder it by magnitude instead of its
// natural sequence — every preset below uses "natural" whenever an ordinal
// axis is in play (chronological "Start year"/"Hire year" in particular
// would otherwise scramble), and "dollars"/"size" only when BOTH axes are
// plain categories with no inherent order to protect.
export const GRANT_SUGGESTIONS = [
  {label: "Which agencies fund which research themes?", arrange: "ag", split: "tp", color: "amt", sort: "dollars"},
  {label: "How has each research theme's funding changed over time?", arrange: "tp", split: "yr", color: "amt", sort: "natural"},
  {label: "Do bigger teams cluster at certain colleges, and in which themes?", arrange: "col", split: "team", color: "tp", sort: "dollars"},
  {label: "How does pre-hire vs. at-NEU attribution vary by college?", arrange: "col", split: "st", color: "amt", sort: "dollars"},
  {label: "What's still unassigned, and in which agencies?", arrange: "tid", split: "ag", color: "ab", sort: "size"},
];
export const PI_SUGGESTIONS = [
  {label: "How does funding differ by rank across colleges?", arrange: "col", split: "rank", color: "amt", sort: "dollars"},
  {label: "Who hasn't been funded, by college?", arrange: "col", split: "hasgrants", color: "tp", sort: "size"},
  {label: "How does tenure status vary by appointment track?", arrange: "track", split: "tenure", color: "amt", sort: "dollars"},
  {label: "Which colleges' PIs work in which research themes?", arrange: "col", split: "tp", color: "amt", sort: "dollars"},
  {label: "How has hiring changed over time, by college?", arrange: "col", split: "hire_yr", color: "status", sort: "natural"},
];

export const SORT_OPTIONS = [
  ["natural", "Natural order"],
  ["size", "Bin size (grant count)"],
  ["dollars", "Bin size (total dollars)"],
];

// (fitWidthToText — a canvas-measured auto-width helper for the search input
// and suggestion select — was removed once both became fixed-width in CSS
// (see .gridtoolbar-fields in style.css). Its finding still stands if this
// need ever comes back: CSS field-sizing:content and width:fit-content do
// NOT reliably size a native <input>/<select> to its own text across
// browsers (confirmed in a real-browser check: both stayed clipped/oversized
// regardless), because neither element has "content" in the
// CSS-intrinsic-sizing sense a div full of text does — measure real glyphs
// on a canvas instead, using the element's own computed font.)
