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
         GRANT_SUGGESTIONS, PI_SUGGESTIONS, fitWidthToText } from "./facets.js";
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
  // Sized to fit whichever option is CURRENTLY SHOWING (the "Need a
  // suggestion?" placeholder at first, then whatever was picked) — see
  // fitWidthToText's own comment for why this is JS-measured rather than
  // CSS-only (a native <select> doesn't reliably size to just its selected
  // option's text via CSS alone across browsers).
  fitWidthToText(sel, sel.options[sel.selectedIndex].text);
  sel.addEventListener("change", () => {
    fitWidthToText(sel, sel.options[sel.selectedIndex].text);
    if (sel.value === "") return;
    grid.applyPreset(presets[Number(sel.value)]);
  });
}
wireSuggestions("facetSuggest", grantGrid, GRANT_SUGGESTIONS);
wireSuggestions("piSuggest", piGrid, PI_SUGGESTIONS);

// Every grant/Every PI carry no caveat text of their own now (PI feedback:
// clean grids, no explanatory copy) — every caveat, including neu_status
// (the $2.18B headline) and roster_snapshot, lives on the "About this data
// & what's missing" tab's About section (formerly a standalone about.html,
// merged in 2026-08-30 — see missing.js), linked from the page header.

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
   the neu_status/external_collaborators/roster_snapshot entries in
   VIZ_META.caveats, and the missingness view itself). "Every PI" is new.
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
// Each grid's own toolbar (Rows/Columns/Color/Sort dial, search, legend)
// now lives in the tablist's own row (what_we_can_see.html's .tabbar),
// pulled OUT of #facetsection/#pisection so it can sit inline with the tab
// buttons instead of stacked below them — saves the vertical space a
// second row used to cost. Since it's no longer a descendant of the
// section setupTabs hides/shows, its own visibility has to be driven
// explicitly here, alongside the width-dependent re-render above.
const TOOLBAR_BY_TAB = {every: document.getElementById("facetToolbar"), pis: document.getElementById("piToolbar")};
const tabsCtl = E.setupTabs({
  tablist: document.getElementById("tabstrip"),
  tabs: TAB_DEFS,
  onActivate: (key) => {
    Object.entries(TOOLBAR_BY_TAB).forEach(([k, el]) => { el.hidden = k !== key; });
    const fn = WIDTH_DEPENDENT_RENDER[key]; if (fn) fn();
  },
});
window.addEventListener("resize", () => {
  const fn = WIDTH_DEPENDENT_RENDER[tabsCtl.current];
  if (fn) fn();
});
