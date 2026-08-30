// main.js — entry point. Wires the two unit-visualization grids, the
// "What's missing" tab, and the tab strip together. Split out of
// what_we_can_see.html's single inline script (previously an IIFE running
// at the bottom of the page); behavior is unchanged, only the module
// boundary is new — see docs/TOPIC_MODEL_REFIT_CHECKLIST.md.
//
// This is the only module with page-level side effects, in the same order
// they ran in before the split: #count, the two createGrid instantiations,
// the missing-tab init, then tabs + resize. Everything it needs to build
// that sequence is imported below; nothing here does its own data or DOM
// wiring beyond that sequence.
import { FACETS, FACETS_PI, COVERAGE, VIZ_META } from "./data.js";
import { AGENCIES } from "./constants.js";
import { GRANT_FACET_DEFS, PI_FACET_DEFS, GRANT_ARRANGE_FACETS, PI_ARRANGE_FACETS,
         GRANT_SUGGESTIONS, PI_SUGGESTIONS } from "./facets.js";
import { createGrid } from "./grid.js";
import { grantTooltip, grantDetail, piTooltip, piDetail } from "./detail.js";
import { initMissingTab } from "./missing.js";

const E = window.ENRICO;

const totalGrants = d3.sum(AGENCIES, a => COVERAGE.by_agency[a].n);
document.getElementById("count").textContent = totalGrants.toLocaleString();
// The coverage headline that used to live here ("72.3% of grants have an
// abstract…") moved to about.html, linked from the header — see the
// analogous block there, built from the same COVERAGE fields.

const grantGrid = createGrid({
  data: FACETS, facetDefs: GRANT_FACET_DEFS, arrangeFacets: GRANT_ARRANGE_FACETS,
  defaultArrangeKey: "ag", noun: "grants",
  ids: {
    arrangeSelect: "arrangeSelect", splitSelect: "splitSelect", sortSelect: "sortSelect",
    colorSelect: "colorSelect", colorLegend: "facetColorLegend", legendToggle: "facetLegendToggle",
    chartwrap: "facetchartwrap", labelsSvg: "facetlabels", scrollDiv: "facetscroll",
    chartSvg: "facetchart", tip: "facettip", dock: "facetdock", dial: "facetDial",
    selectedPanel: "selectedGrantPanel", selectedBody: "selectedBody", selectedClose: "selectedGrantClose",
    // Optional — only the grants grid has a search box; createGrid wires
    // these only when both ids resolve, so omitting them (as piGrid does
    // below) cleanly opts a grid out of search entirely.
    searchInput: "facetSearch", searchCount: "facetSearchCount",
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
  },
  buildTooltip: piTooltip, buildDetail: piDetail,
});

// "Need a suggestion?" — populate each grid's own preset dropdown and wire
// it to grid.applyPreset (see grid.js). Reset back to the placeholder
// option after applying, so picking the SAME suggestion twice in a row
// still fires a change event.
function wireSuggestions(selectId, grid, presets) {
  const sel = document.getElementById(selectId);
  presets.forEach((p, i) => {
    const o = document.createElement("option");
    o.value = String(i); o.textContent = p.label;
    sel.appendChild(o);
  });
  sel.addEventListener("change", () => {
    if (sel.value === "") return;
    grid.applyPreset(presets[Number(sel.value)]);
    sel.value = "";
  });
}
wireSuggestions("facetSuggest", grantGrid, GRANT_SUGGESTIONS);
wireSuggestions("piSuggest", piGrid, PI_SUGGESTIONS);

// Every grant/Every PI carry no caveat text of their own now (PI feedback:
// clean grids, no explanatory copy) — every caveat, including neu_status
// (the $2.18B headline) and roster_snapshot, lives on about.html, linked
// from the page header.

// grantGrid/piGrid's initial render() and the resize listener that keeps
// re-rendering it both live below, where the tabs are set up — a hidden
// panel measures clientWidth as 0, and every panel but this page's first
// tab starts hidden.

initMissingTab();

/* ---------- tabs: three sections, one visible at a time ----------
   Down from the original six to three: "Coverage" and "Does it matter? What
   we can't see" are retired as their own tabs — their content is folded
   into "What's missing & where it goes" (the by-agency/by-year coverage
   bars, the NIH-vs-NSF cliff chart, and the mosaic's one-line finding) or
   dropped ("What we cannot see" — those five points are argued elsewhere:
   the neu_status/external_collaborators/roster_snapshot entries in
   VIZ_META.caveats, and the missingness view itself). "Every PI" is new.
   Of this tab's several render functions, only grantGrid.render and
   piGrid.render actually read live container width off their own DOM node
   — every other one (coverage bars, cliff, mosaic finding, missingness,
   funnel — see missing.js) has a fixed viewBox and already ran once, above,
   regardless of which tab is active. The two width-dependent ones instead
   (re)render every time their own tab is activated (a hidden panel
   measures clientWidth as 0) and again on resize, but ONLY while that tab
   is current. */
const TAB_DEFS = [
  {key: "every", label: "Every grant", panel: document.getElementById("facetsection")},
  {key: "pis", label: "Every PI", panel: document.getElementById("pisection")},
  {key: "missing", label: "What's missing & where it goes", panel: document.getElementById("missingfunnelpanel")},
];
const WIDTH_DEPENDENT_RENDER = {every: grantGrid.render, pis: piGrid.render};
const tabsCtl = E.setupTabs({
  tablist: document.getElementById("tabstrip"),
  tabs: TAB_DEFS,
  onActivate: (key) => { const fn = WIDTH_DEPENDENT_RENDER[key]; if (fn) fn(); },
});
window.addEventListener("resize", () => {
  const fn = WIDTH_DEPENDENT_RENDER[tabsCtl.current];
  if (fn) fn();
});
