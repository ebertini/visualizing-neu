// main.js — entry point. Wires the two unit-visualization grids, the
// "What's missing" tab, and the tab strip together. Split out of
// what_we_can_see.html's single inline script (previously an IIFE running
// at the bottom of the page); behavior is unchanged, only the module
// boundary is new — see docs/TOPIC_MODEL_REFIT_CHECKLIST.md.
//
// This is the only module with page-level side effects, in the same order
// they ran in before the split: the two createGrid instantiations, the
// missing-tab init, then tabs + resize. Everything it needs to build that
// sequence is imported below; nothing here does its own data or DOM wiring
// beyond that sequence.
import { FACETS, FACETS_PI, VIZ_META } from "./data.js";
import { GRANT_FACET_DEFS, PI_FACET_DEFS, GRANT_ARRANGE_FACETS, PI_ARRANGE_FACETS,
         GRANT_SUGGESTIONS, PI_SUGGESTIONS } from "./facets.js";
import { createGrid } from "./grid.js";
import { grantTooltip, grantDetail, piTooltip, piDetail } from "./detail.js";
import { initMissingTab } from "./missing.js";
import { initAboutSection } from "./about.js";

const E = window.ENRICO;

const grantGrid = createGrid({
  data: FACETS, facetDefs: GRANT_FACET_DEFS, arrangeFacets: GRANT_ARRANGE_FACETS,
  defaultArrangeKey: "ag", noun: "grants",
  ids: {
    arrangeSelect: "arrangeSelect", splitSelect: "splitSelect", sortSelect: "sortSelect",
    colorSelect: "colorSelect", colorLegend: "facetColorLegend", legendToggle: "facetLegendToggle",
    chartwrap: "facetchartwrap", labelsSvg: "facetlabels", scrollDiv: "facetscroll",
    chartSvg: "facetchart", tip: "facettip", dock: "facetdock", dial: "facetDial",
    selectedPanel: "selectedGrantPanel", selectedBody: "selectedBody", selectedClose: "selectedGrantClose",
    // Optional — createGrid wires these only when both ids resolve, so a
    // grid without a search box (none currently) can just omit them.
    searchInput: "facetSearch", searchCount: "facetSearchCount",
    // Read-only, geometry only: updateLegendLayout (grid.js) needs this
    // element's right edge as the left boundary of the color legend's
    // available slot in the toolbar row. The select's own BEHAVIOR is still
    // wired entirely outside createGrid, in wireSuggestions below — this id
    // buys the grid's closure a measurement anchor, not ownership.
    suggestSelect: "facetSuggest",
  },
  buildTooltip: grantTooltip, buildDetail: grantDetail,
  // Grant search box (PI feedback's "Round 2"/next-direction item): filter
  // by title, PI name, or agency — the same three fields already shown in
  // grantTooltip, so a match always corresponds to something visible on
  // hover. Title/PI name are per-grant arrays in FACETS; agency is looked up
  // through VIZ_META.agencies the same way grantTooltip does.
  searchFields: (data, i) => [
    data.titles[i] || "",
    data.piNames ? (data.piNames[i] || "") : "",
    (VIZ_META.agencies[data.cols.ag[i]] || {}).key || "",
  ],
});

const piGrid = createGrid({
  data: FACETS_PI, facetDefs: PI_FACET_DEFS, arrangeFacets: PI_ARRANGE_FACETS,
  defaultArrangeKey: "col", noun: "faculty",
  ids: {
    arrangeSelect: "piArrangeSelect", splitSelect: "piSplitSelect", sortSelect: "piSortSelect",
    colorSelect: "piColorSelect", colorLegend: "piColorLegend", legendToggle: "piLegendToggle",
    chartwrap: "pichartwrap", labelsSvg: "pilabels", scrollDiv: "piscroll",
    chartSvg: "pichart", tip: "pitip", dock: "pidock", dial: "piDial",
    selectedPanel: "piSelectedPanel", selectedBody: "piSelectedBody", selectedClose: "piSelectedClose",
    searchInput: "piSearch", searchCount: "piSearchCount",
    suggestSelect: "piSuggest", // measurement anchor only — see grantGrid above
  },
  buildTooltip: piTooltip, buildDetail: piDetail,
  // PI search box, mirroring the grants grid's above: filter by name,
  // college, or department — the same fields piTooltip already shows, so a
  // match always corresponds to something visible on hover.
  searchFields: (data, i) => [
    data.names[i] || "",
    data.levels.col[data.cols.col[i]] || "",
    data.levels.dept[data.cols.dept[i]] || "",
  ],
});

// "Need a suggestion?" — populate each grid's own preset dropdown and wire
// it to grid.applyPreset (see grid.js). The select's own displayed value
// stays on the chosen suggestion after applying it (previously reset back
// to the "Need a suggestion?" placeholder immediately, which looked like
// nothing had happened) — so the dropdown itself shows which suggestion is
// active, the same way the Rows/Columns/Color by/Sort selects show their
// own current value. Manually changing Rows/Columns/Color/Sort afterward
// does NOT clear this back to the placeholder — a known, accepted
// simplification, not a bug: the label just describes what you picked, not
// a live-tracked "is the view still exactly this."
function wireSuggestions(selectId, grid, presets) {
  const sel = document.getElementById(selectId);
  presets.forEach((p, i) => {
    const o = document.createElement("option");
    o.value = String(i); o.textContent = p.label;
    sel.appendChild(o);
  });
  // Fixed width in CSS now, identical to the search input beside it (see
  // .gridtoolbar-fields in style.css) — no longer auto-sized to whichever
  // option is showing. Consequence, accepted by design: these labels are
  // full sentences, so a picked suggestion visually clips. A native
  // <select>'s selected-value box has no text-overflow and can't grow to
  // its content; the open dropdown list still shows every label in full.
  sel.addEventListener("change", () => {
    if (sel.value === "") return;
    grid.applyPreset(presets[Number(sel.value)]);
  });
}
wireSuggestions("facetSuggest", grantGrid, GRANT_SUGGESTIONS);
wireSuggestions("piSuggest", piGrid, PI_SUGGESTIONS);

// Every grant/Every PI carry no caveat text of their own now (PI feedback:
// clean grids, no explanatory copy) — every caveat, including roster_snapshot,
// lives on the "About this data & what's missing" tab's About section
// (formerly a standalone about.html, merged in 2026-08-30 — see missing.js),
// linked from the page header.

// grantGrid/piGrid's initial render() and the resize listener that keeps
// re-rendering it both live below, where the tabs are set up — a hidden
// panel measures clientWidth as 0, and every panel but this page's first
// tab starts hidden.

initMissingTab();
initAboutSection();

/* ---------- tabs: three sections, one visible at a time ----------
   Down from the original six to three: "Coverage" and "Does it matter? What
   we can't see" are retired as their own tabs — their content is folded
   into "What's missing & where it goes" (the by-agency/by-year coverage
   bars, the NIH-vs-NSF cliff chart, and the mosaic's one-line finding) or
   dropped ("What we cannot see" — those five points are argued elsewhere:
   the external_collaborators/roster_snapshot entries in VIZ_META.caveats,
   and the missingness view itself). "Every PI" is new.
   The formerly-standalone about.html was folded into THIS tab too
   (2026-08-30) — its own "missing" key is unchanged (about.html's own
   footer already linked to `#missing` before the merge, so no link needed
   updating beyond the ones that pointed at about.html itself), only the
   label changed to reflect the new combined scope. It's since dropped its
   own pill in the tablist entirely (`hidden: true`, below) — reachable only
   via the header's "About this data" link/hash, now that the tablist's
   freed-up row holds each grid's own toolbar instead (see TOOLBAR_BY_TAB).
   Of this tab's several render functions, only grantGrid.render and
   piGrid.render actually read live container width off their own DOM node
   — every other one (about section, coverage bars, cliff, mosaic finding,
   missingness, funnel — see missing.js) has a fixed viewBox or is plain
   HTML and already ran once, above, regardless of which tab is active. The
   two width-dependent ones instead (re)render every time their own tab is
   activated (a hidden panel measures clientWidth as 0) and again on
   resize, but ONLY while that tab is current. */
const TAB_DEFS = [
  {key: "every", label: "Every grant", panel: document.getElementById("facetsection")},
  {key: "pis", label: "Every PI", panel: document.getElementById("pisection")},
  {key: "missing", label: "About this data & what's missing", panel: document.getElementById("missingfunnelpanel"), hidden: true},
];
const WIDTH_DEPENDENT_RENDER = {every: grantGrid.render, pis: piGrid.render};
// Each grid's own dial+dock and its own search/suggestion/legend/toggle
// (what_we_can_see.html's #facetDialGroup/#facetToolbar and
// #piDialGroup/#piToolbar) live in the tablist's own row (.tabbar), pulled
// OUT of #facetsection/#pisection — split into TWO elements per grid,
// placed before and after #tabstrip respectively, so DOM/visual/focus order
// all agree (see .tabbar's own comment in style.css for why that's worth a
// second wrapper instead of one + CSS `order`). Neither is a descendant of
// the section setupTabs hides/shows, so their own visibility has to be
// driven explicitly here, alongside the width-dependent re-render below.
// Split into two maps (rather than kept as one, as originally): the dial
// group needs different treatment on a tab with no grid toolbar of its own
// ("missing") than the main toolbar does — see onActivate below.
const DIAL_GROUP_BY_GRID = {every: document.getElementById("facetDialGroup"), pis: document.getElementById("piDialGroup")};
const MAIN_TOOLBAR_BY_TAB = {every: document.getElementById("facetToolbar"), pis: document.getElementById("piToolbar")};
// The "About this data" header link/button (what_we_can_see.html's
// .aboutlink) now shares .tab/.tab.active styling with the two real tab
// pills (PI feedback: one consistent selected/unselected look, blue =
// selected) even though it isn't a rendered pill in #tabstrip itself
// (TAB_DEFS marks it `hidden: true`, above) — so its own `.active` class
// has to be driven explicitly here too, mirroring what setupTabs already
// does internally for the two real buttons.
const aboutLinkEl = document.querySelector(".aboutlink");
// Which grid's dial-group keeps reserving space on a tab with no grid
// toolbar of its own ("missing") — defaults to "every" (TAB_DEFS[0]) before
// either grid has ever been the active tab, then tracks whichever grid was
// last actually shown, so switching to "About this data" from "Every PI"
// doesn't cause an unrelated jump.
let lastGridKey = "every";
const tabsCtl = E.setupTabs({
  tablist: document.getElementById("tabstrip"),
  tabs: TAB_DEFS,
  onActivate: (key) => {
    if (key === "every" || key === "pis") lastGridKey = key;
    // PI feedback: "Every grant"/"Every PI" should sit in the same position
    // on every tab, including "About this data" — which has no dial/search/
    // legend of its own. Exactly one grid's dial-group always stays in the
    // DOM (never `hidden`) so its 52px keeps reserving #tabstrip's usual
    // spot; on "missing" specifically it's also made invisible+inert via
    // .dial-group-ghost (style.css) rather than shown for real, since its
    // dock's Rows/Columns/Color/Sort selects don't apply to this tab.
    const dialGridKey = (key === "every" || key === "pis") ? key : lastGridKey;
    Object.entries(DIAL_GROUP_BY_GRID).forEach(([k, el]) => {
      el.hidden = k !== dialGridKey;
      el.classList.toggle("dial-group-ghost", k === dialGridKey && key !== "every" && key !== "pis");
    });
    Object.entries(MAIN_TOOLBAR_BY_TAB).forEach(([k, el]) => { el.hidden = k !== key; });
    aboutLinkEl.classList.toggle("active", key === "missing");
    const fn = WIDTH_DEPENDENT_RENDER[key]; if (fn) fn();
  },
});
window.addEventListener("resize", () => {
  const fn = WIDTH_DEPENDENT_RENDER[tabsCtl.current];
  if (fn) fn();
});
