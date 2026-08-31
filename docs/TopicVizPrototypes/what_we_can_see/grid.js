// grid.js — the generic engine behind both unit-visualization grids ("Every
// grant" over data=FACETS/facetDefs=GRANT_FACET_DEFS, "Every PI" over
// FACETS_PI/PI_FACET_DEFS) — everything below used to be specific to the
// grants grid; parameterizing it on `opts` is what lets "Every PI" reuse it
// verbatim rather than duplicating ~400 lines of layout/interaction code.
//
// Deliberately kept as ONE file, unsplit: createGrid's closure state
// (arrangeKey, splitKey, colorKey, sortMode, selected, tip) is per-instance,
// and there are two live instances (grantGrid, piGrid) in main.js that must
// never share any of it. Splitting render() out would require threading
// all of that through parameters — a rewrite, not a move.
//
// Notably, createGrid never imports FACETS/FACETS_PI/GRANT_FACET_DEFS/
// PI_FACET_DEFS directly — everything arrives through opts (see main.js's
// two createGrid({...}) calls), which is what keeps this module free of a
// data.js import and keeps the whole module graph acyclic.
import {
  computeBins, sortedOrder, matrixLayout, computeMarkPositions, reduceMotion,
  CELL_PAD, LABEL_LANE, STAGE_MARGIN, RING_PAD, LABEL_LINE_H,
} from "./layout.js";
import { populateSelect, populateOptions, defaultSortMode, SORT_OPTIONS, fitWidthToText } from "./facets.js";
import { NOISE } from "./constants.js";

const E = window.ENRICO;

// A single persistent toggle button (the "dial", next to each grid's own
// title) opening/closing its controls dropdown — simpler than shared/
// enrico.css's setupDock, which assumes two separate elements (a fold
// button inside the open dock, an opener button that appears only while
// closed) because that kit's dock/opener float in the chart's own corner
// rather than living in the header next to a title. Escape only closes
// while a text input elsewhere isn't focused, matching setupDock's guard.
export function setupDial(dial, dock, onOpen) {
  function setOpen(open) {
    dock.classList.toggle("collapsed", !open);
    dial.setAttribute("aria-expanded", String(open));
    // Only the legend toggle passes onOpen — it re-measures whether the
    // legend needs to become a floating overlay now that it's visible
    // again (see measureLegendOverlay; can't measure a display:none
    // element's height, so this can't happen while still collapsed).
    if (open && onOpen) onOpen();
  }
  dial.addEventListener("click", () => setOpen(dock.classList.contains("collapsed")));
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !dock.classList.contains("collapsed") && document.activeElement.tagName !== "INPUT") {
      setOpen(false);
      dial.focus();
    }
  });
  // PI feedback: "clicking anywhere outside the option dial should close
  // it." A click ON the dial itself is already handled above (toggles); a
  // click anywhere inside the open dock (e.g. a <select>) must NOT close
  // it, so this only fires for a target outside both.
  document.addEventListener("click", e => {
    if (dock.classList.contains("collapsed")) return;
    if (dial.contains(e.target) || dock.contains(e.target)) return;
    setOpen(false);
  });
}

export function createGrid(opts) {
  const {data, facetDefs, arrangeFacets, defaultArrangeKey, noun, ids, buildTooltip, buildDetail, searchFields} = opts;

  // Columns carries the default facet; Rows starts on "— none —" — a single
  // undifferentiated band reads better as a first view than a 90-row lane of
  // e.g. department names (PI feedback: column-first, not row-first).
  let arrangeKey = "", splitKey = defaultArrangeKey, colorKey = defaultArrangeKey,
      sortMode = defaultSortMode(facetDefs, defaultArrangeKey);
  // selected is a row index into data.* or null — set by clicking a mark or
  // a cell. Independent of arrangeKey/splitKey/colorKey/sortMode on
  // purpose: a selection survives every reconfiguration, so its mark stays
  // highlighted and its details stay visible no matter how the view changes.
  let selected = null;

  // Search — opt-in per grid via ids.searchInput/searchFields (see main.js).
  // A HIGHLIGHT, not a filter: matching marks stay full opacity, non-matching
  // marks dim, so the grid's own "every X is present" invariant holds even
  // while searching — nothing is removed from the view.
  let searchQuery = "";
  const searchInputEl = ids.searchInput && document.getElementById(ids.searchInput);
  const searchCountEl = ids.searchCount && document.getElementById(ids.searchCount);
  function matchesSearch(i) {
    if (!searchQuery) return true;
    if (!searchFields) return true;
    return searchFields(data, i).some(f => String(f || "").toLowerCase().includes(searchQuery));
  }

  const tip = E.setupTooltip(document.getElementById(ids.tip), document.getElementById(ids.chartwrap));

  // Rows and Columns each list every facet plus "— none —", in a fixed
  // order, built once (see init below) rather than rebuilt per change — the
  // two axes can't hold the same facet at once, but that's enforced by
  // transposing values (see the change handlers below), not by filtering
  // either select's option list. This just keeps both <select>s' displayed
  // value in sync with the current arrangeKey/splitKey after such a swap.
  function syncAxisSelects() {
    document.getElementById(ids.arrangeSelect).value = arrangeKey;
    document.getElementById(ids.splitSelect).value = splitKey;
  }
  function populateSortSelectLocal() {
    const sel = document.getElementById(ids.sortSelect);
    populateOptions(sel, SORT_OPTIONS, sortMode);
    sortMode = sel.value;
  }

  // A legend that fits on roughly one row (most facets — Agency is 9 chips,
  // NEU attribution is 4) can just sit in the toolbar's normal flow; one
  // that wraps to several rows (Department: 91, Topic (leaf): 26) would
  // otherwise grow the whole toolbar taller every time it's shown — the
  // exact thing that made the dial cover the chart before this toolbar
  // existed. So instead it becomes a floating overlay below the toolbar —
  // same idea as the controls dock opening off its own dial — scrolling
  // internally instead of pushing the chart down. Can't measure a
  // display:none element, so this only runs while the legend is actually
  // visible (collapsed legends re-measure on open — see setupDial's onOpen).
  const LEGEND_INLINE_MAX_H = 56;
  function measureLegendOverlay() {
    const el = document.getElementById(ids.colorLegend);
    if (el.classList.contains("collapsed")) return;
    el.classList.remove("overlay"); // measure the natural, unclamped height first
    el.classList.toggle("overlay", el.scrollHeight > LEGEND_INLINE_MAX_H);
  }

  function renderColorLegend() {
    const el = document.getElementById(ids.colorLegend);
    if (!colorKey) {
      el.innerHTML = `<span class="chiprow-label">No color</span>`;
    } else {
      const def = facetDefs[colorKey];
      const levels = def.levels();
      const head = `<span class="chiprow-label">${E.esc(def.label)}</span>`;
      const chip = lv => `<span><span class="swatch" style="background:${lv.color}"></span>${E.esc(lv.label)}</span>`;
      if (def.legend === "ramp") {
        // A flat chip row stops working past ~10-12 levels — "Start year" has
        // ~30. A gradient bar + two end labels says "ordered, low to high" in
        // one glance. Any off-ramp level (Unknown year) still gets its own
        // explicit grey chip, so a no-data bin is never folded into the scale.
        const onRamp = levels.filter(lv => lv.color !== NOISE);
        const offRamp = levels.filter(lv => lv.color === NOISE);
        el.innerHTML = head +
          `<span class="ramplegend"><span class="end">${E.esc(onRamp[0].label)}</span>` +
          `<span class="bar"></span><span class="end">${E.esc(onRamp[onRamp.length - 1].label)}</span></span>` +
          offRamp.map(chip).join("");
      } else {
        el.innerHTML = head + levels.map(chip).join("");
      }
    }
    measureLegendOverlay();
  }

  // Floating "Selected" card — the persistent readout that survives every
  // Rows/Columns/Sort/Color change. It's hidden entirely (not just empty)
  // until something's selected, and closes via its own close button or Esc.
  function renderSelectedCard() {
    const panel = document.getElementById(ids.selectedPanel);
    const body = document.getElementById(ids.selectedBody);
    panel.hidden = selected == null;
    if (selected == null) { body.innerHTML = ""; return; }
    body.innerHTML = buildTooltip(selected) + buildDetail(selected);
    // "Show N more" (detail.js's piDetail) is a native <details> — no JS
    // needed for the open/close toggle itself, but opening it can reveal
    // titles below the panel's own scroll viewport (or the .abstract box's
    // inner 260px cap) with nothing visibly moving on screen, reading as if
    // the click did nothing. Scroll the disclosure into view on open so the
    // newly revealed titles are actually seen.
    body.querySelectorAll("details.grantmore").forEach(d => {
      d.addEventListener("toggle", () => {
        if (d.open) d.scrollIntoView({behavior: reduceMotion() ? "auto" : "smooth", block: "nearest"});
      });
    });
  }
  function select(i) { selected = i; renderSelectedCard(); render(); }
  function clearSelection() {
    if (selected == null) return;
    selected = null;
    renderSelectedCard();
    render();
  }

  function render() {
    renderColorLegend();

    if (searchCountEl) {
      if (!searchQuery) {
        searchCountEl.textContent = "";
      } else {
        const n = d3.range(data.n).filter(matchesSearch).length;
        searchCountEl.textContent = `${n.toLocaleString()} of ${data.n.toLocaleString()} match`;
      }
    }

    const wrap = document.getElementById(ids.chartwrap);
    const W = wrap.clientWidth;
    // The controls dock floats OVER the chart now (see its CSS) instead of
    // reserving its own width — only the pinned row-label lane (LABEL_LANE),
    // plus its own left margin (STAGE_MARGIN) and a little right breathing
    // room, is reserved, so folding/opening the dock no longer changes the
    // layout. The lane itself collapses to 0 when Rows is "— none —" (laneW
    // below) so Columns gets the full width back.
    const laneW = arrangeKey ? LABEL_LANE : 0;
    const availW = Math.max(200, W - STAGE_MARGIN - laneW - 16);

    const {aLevels, sLevels, byCell, aMarginalN, aMarginalD, sMarginalN, sMarginalD} =
      computeBins(facetDefs, data, arrangeKey, splitKey);
    // Neither axis has a real sort to apply when it isn't active — with
    // none, that axis's levels list is the single synthetic level and
    // sorting it is a no-op anyway, so "natural" there is just the accurate
    // label (mirrors the split axis's own existing guard below).
    const aOrder = sortedOrder(aLevels.length, aMarginalN, aMarginalD, arrangeKey ? sortMode : "natural");
    const sOrder = sortedOrder(sLevels.length, sMarginalN, sMarginalD, splitKey ? sortMode : "natural");
    const layout = matrixLayout(aLevels, sLevels, byCell, aOrder, sOrder, availW);

    // colorKey === "" is the "none" option (PI feedback) — every mark falls
    // back to one flat color and there's no per-level breakdown anywhere
    // downstream (legend, cell tooltip, the by-color grouping within a cell).
    const colorDef = colorKey ? facetDefs[colorKey] : null;
    const colorLevels = colorDef ? colorDef.levels() : [];
    const colorMap = new Map(colorLevels.map(lv => [lv.key, lv.color]));
    const colorVals = colorDef ? colorDef.values() : null;
    const colorRank = new Map(colorLevels.map((lv, i) => [lv.key, i]));
    const FLAT_COLOR = "#0072B2";

    // Marks within a cell are grouped by their color level (ties broken by
    // ascending row index), so the color encoding stays readable at mark
    // size instead of a speckle, and each cell doubles as a small stacked
    // composition. Skipped entirely when there's no color facet.
    if (colorDef) {
      layout.cells.forEach(c => {
        c.members.sort((i, j) => (colorRank.get(colorVals[i]) ?? 99) - (colorRank.get(colorVals[j]) ?? 99) || i - j);
      });
    }
    const positions = computeMarkPositions(layout.cells, layout.mark, layout.gap, data.n);

    // Aggregate tooltip content (count, dollars, color breakdown) for a
    // group of members — used by the row/column axis labels below, NOT by
    // the grid itself. Grouping detail used to also show on hovering a
    // cell's own background, which meant two different tooltips could
    // appear depending on exactly where the pointer sat within a cell (its
    // gaps vs. a mark) — confusing. Now the grid only ever shows a
    // per-grant tooltip (see markSel below); the aggregate view lives
    // entirely on the axis labels, where it's unambiguous which grouping
    // it describes.
    function groupDetail(members, label) {
      let rows = "";
      if (colorDef) {
        const counts = new Map();
        members.forEach(i => { const k = colorVals[i]; counts.set(k, (counts.get(k) || 0) + 1); });
        rows = colorLevels
          .filter(lv => counts.has(lv.key))
          .map(lv => `<div class="meta">${E.esc(lv.label)}: ${counts.get(lv.key)} (${E.fmtPct(counts.get(lv.key) / members.length)})</div>`)
          .join("");
      }
      const dollars = members.reduce((s, i) => s + data.cols.amt_raw[i], 0);
      // PI feedback: "add dollar band to the column/row overview for
      // quicker reference" / "what is the label that states the dollar
      // total" — the total now has an explicit "Total:" label, and (unless
      // Color by is already "amt", which would just repeat the rows above)
      // a dollar-band BREAKDOWN of the group's own members, the same shape
      // as the color breakdown, so a row/column's dollar composition is
      // readable at a glance without switching Color by.
      let amtRows = "";
      if (colorKey !== "amt" && facetDefs.amt && data.levels.amt) {
        const amtCol = facetDefs.amt.values();
        const amtLevels = facetDefs.amt.levels();
        const counts = new Map();
        members.forEach(i => { const k = amtCol[i]; counts.set(k, (counts.get(k) || 0) + 1); });
        amtRows = amtLevels
          .filter(lv => counts.has(lv.key))
          .map(lv => `<div class="meta">${E.esc(lv.label)}: ${counts.get(lv.key)} (${E.fmtPct(counts.get(lv.key) / members.length)})</div>`)
          .join("");
      }
      return `<div class="t">${E.esc(label)}</div>` +
        `<div class="meta">${members.length.toLocaleString()} ${noun} · Total: ${E.fmtAmt(dollars)}</div>${rows}${amtRows}`;
    }

    // A fixed container size + a viewBox that grows to fit content makes
    // the browser scale the WHOLE drawing down instead of growing the page.
    // Height grows via ids.chartwrap; width grows via the scroll div
    // actually scrolling instead of the SVG being squeezed to the
    // container's width — see the CSS on #facetlabels/#facetscroll/#facetchart.
    const chartH = Math.max(480, layout.totalH + 24);
    wrap.style.flex = "0 0 auto";
    wrap.style.height = `${chartH}px`;

    const gridW = Math.max(availW, layout.contentW);
    const svgEl = d3.select("#" + ids.chartSvg);
    svgEl.style("width", `${gridW}px`).style("height", `${chartH}px`);
    svgEl.attr("viewBox", `0 0 ${gridW} ${chartH}`);
    document.getElementById(ids.scrollDiv).style.left = `${STAGE_MARGIN + laneW}px`;

    const labelsEl = document.getElementById(ids.labelsSvg);
    labelsEl.style.width = `${laneW}px`;
    const labelsSvg = d3.select("#" + ids.labelsSvg);
    // viewBox width floors at 1, not 0 — a 0-width viewBox is spec-invalid
    // and some engines drop the element entirely; the lane is already
    // width:0 + overflow:hidden when collapsed, so this is invisible either
    // way and just keeps the attribute legal.
    labelsSvg.attr("viewBox", `0 0 ${Math.max(1, laneW)} ${chartH}`);

    // Row labels + counts live in this separate, non-scrolling SVG (pinned
    // between the dock and the scrollable matrix) so a row's identity never
    // scrolls out of view while panning across columns. Keyed on r.ai alone
    // (not `aLevels[r.ai].key`): d3 recomputes the key function on STALE
    // bound data too, using whichever aLevels array is in scope for THIS
    // render — after switching Rows to a facet with fewer levels than the
    // previous one, an old row's `ai` can exceed the new aLevels' length,
    // making `aLevels[r.ai]` undefined and `.key` on that throw, silently
    // aborting the render. r.ai never indexes into anything external, so it
    // can't throw regardless of level-count direction. When Rows is
    // "— none —" there's nothing to label — pass no data so a stale row
    // from a previous arrangement is torn down via the exit() below instead
    // of rendering one bare "· 2,676" tspan into the collapsed, hidden lane.
    let rowG = labelsSvg.selectAll("g.row-label-g").data(arrangeKey ? layout.rows : [], r => r.ai);
    rowG.exit().remove();
    rowG = rowG.enter().append("g").attr("class", "row-label-g").merge(rowG)
      .attr("transform", d => `translate(0,${d.y})`);
    rowG.selectAll("text.rowlabel").data(d => [d]).join("text")
      .attr("class", "rowlabel").attr("x", 0).attr("y", 10)
      .html(d => {
        const lines = d.labelLines
          .map((line, li) => `<tspan x="0"${li > 0 ? ` dy="${LABEL_LINE_H}"` : ""}>${E.esc(line)}</tspan>`)
          .join("");
        return `${lines}<tspan class="n"> · ${d.total.toLocaleString()}</tspan>`;
      })
      .on("mousemove", (ev, d) => {
        const label = aLevels[d.ai].full || aLevels[d.ai].label;
        const members = layout.cells.filter(c => c.ai === d.ai).flatMap(c => c.members);
        tip.show(groupDetail(members, label), ev.clientX, ev.clientY);
      })
      .on("mouseleave", () => tip.hide());

    const plot = svgEl.selectAll("g.plotroot").data([null]).join("g").attr("class", "plotroot");

    // Fixed-order paint layers, created once and reused every render (no
    // transform on any of them — they're purely a z-order fence, every
    // child's own x/y/transform is unchanged). Without this, a bare
    // `plot.selectAll(...).join(...)` per section appends any NEWLY
    // ENTERING node at the end of `plot`'s existing children, not in
    // section order — harmless the first render (nothing else exists yet),
    // but on the SECOND render, cells whose key already existed (e.g. row 0,
    // when Rows starts on "— none —") get reused in place, while brand-new
    // cells (row 1+, or a newly-added column) are appended AFTER every
    // `rect.markrect`. Their `.binhit` sits on top of those rows' marks
    // (fill:transparent still hit-tests) and swallows `mousemove`, so the
    // per-mark tooltip silently stopped firing from row 2 onward while
    // `.binhit`'s own click-to-nearest-mark kept working — the tell that
    // pinned this down. Layering by section means an entering cell can only
    // ever land inside cellLayer, which is structurally always beneath
    // markLayer, so paint order no longer depends on join/enter timing.
    const layer = cls => plot.selectAll("g." + cls).data([null]).join("g").attr("class", cls);
    const hdrLayer = layer("l-hdr");
    const gridLayer = layer("l-grid");
    const cellLayer = layer("l-cell");
    const markLayer = layer("l-mark");
    const ringLayer = layer("l-ring");

    // Column headers (the split facet's levels) — only when a split is
    // active; with none, sLevels is the single unlabeled synthetic level.
    const hdrData = splitKey
      ? sOrder.map((si, idx) => ({si, lv: sLevels[si], lines: layout.colLabelLines[idx]}))
      : [];
    let hdrG = hdrLayer.selectAll("g.colhdr-g").data(hdrData, d => d.lv.key);
    hdrG.exit().remove();
    hdrG = hdrG.enter().append("g").attr("class", "colhdr-g").merge(hdrG)
      .attr("transform", d => `translate(${layout.colX.get(d.si)},0)`);
    hdrG.selectAll("text.colhdr").data(d => [d]).join("text")
      .attr("class", "colhdr").attr("x", CELL_PAD).attr("y", 11)
      .html(d => d.lines
        .map((line, li) => `<tspan x="${CELL_PAD}"${li > 0 ? ` dy="${LABEL_LINE_H}"` : ""}>${E.esc(line)}</tspan>`)
        .join(""))
      .on("mousemove", (ev, d) => {
        const label = d.lv.full || d.lv.label;
        const members = layout.cells.filter(c => c.si === d.si).flatMap(c => c.members);
        tip.show(groupDetail(members, label), ev.clientX, ev.clientY);
      })
      .on("mouseleave", () => tip.hide());

    // Faint cell-boundary gridline, for EVERY cell (empty or not) — PI
    // feedback asked for two things together: "add a very faint grid line
    // for every grant/PI tab" and "remove the default grey line that goes
    // in empty cells" (the old fixed 2px horizontal bar this replaced). One
    // change satisfies both: a stroked, unfilled rect around every cell's
    // own boundary means an empty bin still reads as "this bin exists, it's
    // just empty" (the old bar's whole purpose) without a separate
    // special-cased marker — see .cellgrid in style.css for the faint color.
    gridLayer.selectAll("rect.cellgrid").data(layout.cells, c => c.ai + "|" + c.si).join("rect")
      .attr("class", "cellgrid")
      .attr("x", c => c.x).attr("y", c => c.y).attr("width", c => c.w).attr("height", c => c.h);

    // Cell groups: a hit-rect (this cell's own color-level breakdown on
    // hover) — marks stay on top for their own hover target (see the
    // hdrLayer/cellLayer/markLayer/ringLayer fence above; this is now
    // enforced structurally, not by draw-order-within-plot statement order)
    // and the hit-rect only "shows through" in the gaps.
    let cellG = cellLayer.selectAll("g.cell-g").data(layout.cells.filter(c => c.members.length > 0), c => c.ai + "|" + c.si);
    cellG.exit().remove();
    cellG = cellG.enter().append("g").attr("class", "cell-g").merge(cellG)
      .attr("transform", c => `translate(${c.x},${c.y})`);

    // Purely a click target now (resolving an imprecise click to the
    // nearest mark slot, below) — no hover tooltip of its own. That detail
    // moved to the row/column axis labels (see groupDetail above), so the
    // grid itself only ever shows one kind of tooltip: a mark's own,
    // individual-grant detail.
    cellG.selectAll("rect.binhit").data(c => [c]).join("rect")
      .attr("class", "binhit")
      .attr("width", c => c.w).attr("height", c => c.h)
      .on("click", (ev, c) => {
        // Marks are as small as 4.8px — reliably clicking one exactly isn't
        // a reasonable ask, and this hit-rect covers the WHOLE cell, so most
        // clicks land here rather than on a specific mark. Resolve the click
        // to whichever row's packed grid slot it falls nearest to, using the
        // same row-major layout computeMarkPositions used to place them.
        const [lx, ly] = d3.pointer(ev, ev.currentTarget);
        const lc = Math.min(c.cellCols - 1, Math.max(0, Math.floor((lx - CELL_PAD) / (layout.mark + layout.gap))));
        const lr = Math.max(0, Math.floor((ly - CELL_PAD) / (layout.mark + layout.gap)));
        const idx = Math.min(c.members.length - 1, lr * c.cellCols + lc);
        select(c.members[idx]);
      });

    const t = d3.transition().duration(reduceMotion() ? 0 : 420).ease(d3.easeCubicInOut);
    const idxArr = d3.range(data.n);

    // Search dimming: 1 for a match (or no search active), a faint 0.12 for
    // a non-match — dim, not removed, so the mark stays in its normal grid
    // position and "every grant is present" still holds while searching.
    const markOpacity = i => (searchQuery && !matchesSearch(i)) ? 0.12 : 1;

    const markSel = markLayer.selectAll("rect.markrect")
      .data(idxArr, i => data.ids[i])
      .join(
        enter => enter.append("rect")
          .attr("class", "markrect")
          .attr("width", layout.mark).attr("height", layout.mark).attr("rx", 0.8)
          .attr("x", i => positions[i].x).attr("y", i => positions[i].y)
          .attr("fill", i => colorDef ? (colorMap.get(colorVals[i]) || NOISE) : FLAT_COLOR)
          .attr("opacity", 0)
          .call(e => e.transition(t).attr("opacity", markOpacity)),
        update => update.call(u => u.transition(t)
          .attr("width", layout.mark).attr("height", layout.mark)
          .attr("x", i => positions[i].x).attr("y", i => positions[i].y)
          .attr("fill", i => colorDef ? (colorMap.get(colorVals[i]) || NOISE) : FLAT_COLOR)
          .attr("opacity", markOpacity)),
        exit => exit.remove()
      )
      .on("mousemove", (ev, i) => tip.show(buildTooltip(i), ev.clientX, ev.clientY))
      .on("mouseleave", () => tip.hide())
      .on("click", (ev, i) => select(i));

    // Selection highlight: a dedicated ring drawn AROUND the selected mark
    // with a visible gap, rather than a stroke ON the mark itself — a border
    // on a 4.8px square competes for the same few pixels as its own fill and
    // is easy to miss. ringLayer is the last layer, so it always paints on
    // top of every cell/mark regardless of join/enter order.
    const ringSel = ringLayer.selectAll("rect.selectring")
      .data(selected != null && positions[selected] ? [selected] : []);
    ringSel.exit().remove();
    ringSel.enter().append("rect").attr("class", "selectring")
      .merge(ringSel)
      .attr("x", i => positions[i].x - RING_PAD)
      .attr("y", i => positions[i].y - RING_PAD)
      .attr("width", layout.mark + RING_PAD * 2)
      .attr("height", layout.mark + RING_PAD * 2);

    if (selected != null) markSel.filter(i => i === selected).raise();
  }

  // Rows and Columns both list every facet plus "— none —", in the SAME
  // fixed order, built once here rather than rebuilt on every change (see
  // syncAxisSelects above) — mutual exclusion is enforced in the change
  // handlers below by transposing, not by filtering either list.
  populateSelect(document.getElementById(ids.arrangeSelect), facetDefs, arrangeFacets, true, arrangeKey);
  populateSelect(document.getElementById(ids.splitSelect), facetDefs, arrangeFacets, true, splitKey);
  populateSelect(document.getElementById(ids.colorSelect), facetDefs, arrangeFacets, true, colorKey);
  populateSortSelectLocal();

  // Sort follows whichever axis is doing the primary reading: Rows when a
  // Rows facet is set (the dominant, pinned-label axis), else Columns, else
  // neither (both none — sortMode is inert on a 1x1 matrix).
  function primarySortKey() { return arrangeKey || splitKey; }

  document.getElementById(ids.arrangeSelect).addEventListener("change", e => {
    const prevArrangeKey = arrangeKey;
    arrangeKey = e.target.value;
    // The two axes can't hold the same facet — picking one Rows already
    // holds via Columns (or vice versa, in the other handler) TRANSPOSES:
    // the other axis inherits whatever this axis just gave up. Visible
    // immediately (the other <select> changes in front of you) and always
    // reversible by repeating the action — never a silent, invisible swap.
    if (arrangeKey && splitKey === arrangeKey) splitKey = prevArrangeKey;
    syncAxisSelects();
    sortMode = defaultSortMode(facetDefs, primarySortKey()); // per-facet smart default
    populateSortSelectLocal();
    render();
  });
  document.getElementById(ids.splitSelect).addEventListener("change", e => {
    const prevSplitKey = splitKey;
    splitKey = e.target.value;
    if (splitKey && arrangeKey === splitKey) arrangeKey = prevSplitKey;
    syncAxisSelects();
    sortMode = defaultSortMode(facetDefs, primarySortKey());
    populateSortSelectLocal();
    render();
  });
  document.getElementById(ids.sortSelect).addEventListener("change", e => { sortMode = e.target.value; render(); });
  document.getElementById(ids.colorSelect).addEventListener("change", e => { colorKey = e.target.value; render(); });

  if (searchInputEl) {
    // Sized to fit its OWN text (placeholder when empty, typed value once
    // something's typed) — see fitWidthToText's own comment for why this is
    // JS-measured rather than CSS-only. Runs once up front (for the
    // placeholder) and again on every keystroke.
    fitWidthToText(searchInputEl, searchInputEl.value || searchInputEl.placeholder);
    searchInputEl.addEventListener("input", e => {
      searchQuery = e.target.value.trim().toLowerCase();
      fitWidthToText(searchInputEl, e.target.value || searchInputEl.placeholder);
      render();
    });
  }

  setupDial(document.getElementById(ids.dial), document.getElementById(ids.dock));
  // Same toggle pattern as the controls dial, reused for the legend — the
  // legend panel starts WITHOUT a .collapsed class in the markup (defaults
  // open, where the controls dock defaults closed), and re-measures
  // whether it needs to become a floating overlay each time it's opened
  // (see measureLegendOverlay).
  setupDial(document.getElementById(ids.legendToggle), document.getElementById(ids.colorLegend), measureLegendOverlay);
  document.getElementById(ids.selectedClose).addEventListener("click", clearSelection);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && selected != null && document.activeElement.tagName !== "INPUT") clearSelection();
  });

  // "Need a suggestion?" presets (PI feedback: entry-point questions that
  // configure Rows/Columns/Color/Sort for you) — a preset only ever names
  // facet KEYS already in facetDefs, so an invalid key here is a bug in the
  // preset table, not user input; left unguarded deliberately; any of
  // arrange/split/color/sort may be omitted to leave that axis unchanged.
  function applyPreset({arrange, split, color, sort}) {
    if (arrange !== undefined) arrangeKey = arrange;
    if (split !== undefined) splitKey = split;
    if (color !== undefined) colorKey = color;
    syncAxisSelects();
    document.getElementById(ids.colorSelect).value = colorKey;
    sortMode = sort !== undefined ? sort : defaultSortMode(facetDefs, primarySortKey());
    populateSortSelectLocal();
    render();
  }

  renderSelectedCard();
  return {render, applyPreset};
}
