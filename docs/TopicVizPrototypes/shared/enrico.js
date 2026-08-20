/* ============================================================
   docs/TopicVizPrototypes shared kit — palettes + reusable D3 helpers.
   This is the user's own prototype work (kept separate from
   docs/EnricoVis/, a parallel visualization effort by the PI).
   Load AFTER the d3 CDN script and BEFORE the page's own inline
   data/logic. Everything lives on the global `ENRICO` namespace so
   it never collides with a page's own top-level consts.

   Palettes here were copied verbatim from docs/EnricoVis/grant_atlas.html
   (agency), topic_islands.html (25-topic), topic_hierarchy.html (8-parent)
   at extraction time, to keep colors reading consistently across both the
   PI's apps and these prototypes. If the PI's palettes change upstream,
   this copy will silently drift — re-sync by hand if that matters.
   ============================================================ */
(function (global) {
  "use strict";

  // ---- Agency palette (Okabe-Ito derived, colorblind-safe, red-free) ----
  const COLORS = {
    NSF: "#0072B2", NIH: "#E69F00", "NIH-SUB": "#56B4E9", Navy: "#009E73",
    NASA: "#9467BD", Army: "#E7298A", DOE: "#66A61E", AFRO: "#A6761D", Other: "#B0B4BB",
  };
  const ORDER = ["NSF", "NIH", "NIH-SUB", "Navy", "NASA", "Army", "DOE", "AFRO", "Other"];

  // ---- 25-topic palette (Tableau-20 extended), + 7 SPARE colors (indices
  // 25-31) — pre-allocated headroom so a refit that produces more than 25
  // leaf topics gets a real, distinct color immediately (topicColor already
  // wraps via % TOPIC_COLORS.length, so this is a pure size increase, not a
  // behavior change for the current 25). The 7 spares continue the same
  // ColorBrewer-Dark2-adjacent family the last 4 original entries came from.
  const TOPIC_COLORS = [
    "#4E79A7", "#A0CBE8", "#F28E2B", "#FFBE7D", "#59A14F", "#8CD17D", "#B6992D", "#F1CE63",
    "#499894", "#86BCB6", "#E15759", "#FF9D9A", "#79706E", "#BAB0AC", "#D37295", "#FABFD2",
    "#B07AA1", "#D4A6C8", "#9D7660", "#D7B5A6", "#6B4C9A", "#1B9E77", "#D95F02", "#7570B3", "#E7298A",
    "#66A61E", "#E6AB02", "#A6761D", "#8DA0CB", "#66C2A5", "#FC8D62", "#E78AC3",
  ];

  // ---- 8-parent-theme palette, + 4 SPARE colors (indices 8-11) — same
  // pre-allocated-headroom idea as TOPIC_COLORS above, for whenever a human
  // curates a 9th+ parent theme (see docs/TOPIC_MODEL_REFIT_CHECKLIST.md —
  // parent themes are always a manual grouping step, never produced directly
  // by a refit). Must stay byte-identical to src/build_viz_aggregates.py's
  // own PARENT_COLORS copy. Red-free/grey-free, matching this palette's
  // existing convention (grey is reserved for NOISE_GREY).
  const PARENT_COLORS = [
    "#4E79A7", "#F28E2B", "#59A14F", "#B07AA1", "#76B7B2", "#EDC948", "#9C755F", "#D37295",
    "#6B4C9A", "#1B9E77", "#B6992D", "#7570B3",
  ];
  const PARENT_NAMES = [
    "Life Sciences & Biomedicine", "Physical Sciences & Engineering", "Environment, Ocean & Climate",
    "Computing & Cybersecurity", "Networks, Signals & Control", "AI, Robotics & Cognition",
    "Society, Health & Mobility", "Education & Learning",
  ];

  // Hard convention: HDBSCAN "Unassigned" / no-data is ALWAYS this grey,
  // system-wide — never repurpose it for anything else.
  const NOISE_GREY = "#c7ccd3";

  const topicColor = (i) => (i == null || i < 0 ? NOISE_GREY : TOPIC_COLORS[i % TOPIC_COLORS.length]);
  const parentColor = (i) => (i == null || i < 0 ? NOISE_GREY : PARENT_COLORS[i % PARENT_COLORS.length]);
  const parentName = (i) => (i == null || i < 0 ? "Unassigned" : PARENT_NAMES[i] || `P${i}`);

  // ---- formatting ----
  const fmtAmt = (v) =>
    v >= 1e6 ? "$" + (v / 1e6).toFixed(v >= 1e7 ? 0 : 1) + "M" : v >= 1e3 ? "$" + Math.round(v / 1e3) + "K" : "$" + Math.round(v || 0);
  const fmtPct = (v, digits) => (v * 100).toFixed(digits == null ? 0 : digits) + "%";
  const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---- collapsible controls dock (Escape-to-fold, focus management) ----
  // opts: {dock, fold, opener} — the three elements from the .dock/.fold/.opener markup
  function setupDock(opts) {
    const { dock, fold, opener } = opts;
    function setDock(open) {
      dock.classList.toggle("collapsed", !open);
      opener.classList.toggle("show", !open);
      fold.setAttribute("aria-expanded", open);
      opener.setAttribute("aria-expanded", open);
      (open ? fold : opener).focus();
    }
    fold.addEventListener("click", () => setDock(false));
    opener.addEventListener("click", () => setDock(true));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !dock.classList.contains("collapsed") && document.activeElement.tagName !== "INPUT") setDock(false);
    });
    return { setDock };
  }

  // ---- shared tooltip: works on tap AND hover, since it's just positioned
  // absolutely and shown/hidden — never a CSS :hover trigger. ----
  function setupTooltip(tipEl, stageEl) {
    function show(html, clientX, clientY) {
      const rect = stageEl.getBoundingClientRect();
      const mx = clientX - rect.left, my = clientY - rect.top;
      tipEl.innerHTML = html;
      tipEl.classList.add("show");
      const tw = tipEl.offsetWidth, th = tipEl.offsetHeight;
      let lx = mx + 14, ly = my + 14;
      if (lx + tw > rect.width - 8) lx = mx - tw - 14;
      if (ly + th > rect.height - 8) ly = my - th - 14;
      tipEl.style.left = lx + "px";
      tipEl.style.top = ly + "px";
    }
    function hide() {
      tipEl.classList.remove("show");
    }
    return { show, hide };
  }

  // ---- segmented control (peer options, not on/off) ----
  // opts: {container, options:[{key,label}], value, onChange(key)}
  function setupSegmented(opts) {
    const { container, options, onChange } = opts;
    let value = opts.value;
    container.innerHTML = "";
    container.classList.add("segmented");
    const btns = {};
    options.forEach((o) => {
      const b = document.createElement("button");
      b.textContent = o.label;
      b.className = o.key === value ? "active" : "";
      b.setAttribute("aria-pressed", o.key === value);
      b.onclick = () => {
        if (o.key === value) return;
        value = o.key;
        Object.entries(btns).forEach(([k, el]) => {
          el.classList.toggle("active", k === value);
          el.setAttribute("aria-pressed", k === value);
        });
        onChange(value);
      };
      btns[o.key] = b;
      container.appendChild(b);
    });
    return { get value() { return value; } };
  }

  // ---- ARIA dual-thumb year-range slider ----
  // opts: {slider, sband, thLo, thHi, yLoOut, yHiOut, yearMin, yearMax, yLo, yHi, onChange(lo,hi)}
  function setupYearSlider(opts) {
    const { slider, sband, thLo, thHi, yLoOut, yHiOut, yearMin, yearMax, onChange } = opts;
    let yLo = opts.yLo, yHi = opts.yHi;
    const span = yearMax - yearMin || 1;
    const pct = (yr) => (yr - yearMin) / span;
    function yearAt(clientX) {
      const r = slider.getBoundingClientRect();
      const t = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
      return Math.round(yearMin + t * span);
    }
    function render() {
      thLo.style.left = pct(yLo) * 100 + "%";
      thHi.style.left = pct(yHi) * 100 + "%";
      sband.style.left = pct(yLo) * 100 + "%";
      sband.style.width = (pct(yHi) - pct(yLo)) * 100 + "%";
      if (yLoOut) yLoOut.textContent = yLo;
      if (yHiOut) yHiOut.textContent = yHi;
      thLo.setAttribute("aria-valuenow", yLo);
      thHi.setAttribute("aria-valuenow", yHi);
    }
    [thLo, thHi].forEach((t) => {
      t.setAttribute("aria-valuemin", yearMin);
      t.setAttribute("aria-valuemax", yearMax);
    });
    let drag = null, refLo = 0, refHi = 0, refYear = 0;
    function applyDrag(yr) {
      if (drag === "lo") yLo = Math.min(yr, yHi);
      else if (drag === "hi") yHi = Math.max(yr, yLo);
      else if (drag === "band") {
        const w = refHi - refLo;
        let nlo = refLo + (yr - refYear);
        nlo = Math.max(yearMin, Math.min(nlo, yearMax - w));
        yLo = nlo; yHi = nlo + w;
      }
      render();
      onChange(yLo, yHi);
    }
    slider.addEventListener("pointerdown", (e) => {
      const yr = yearAt(e.clientX);
      if (e.target === thLo) drag = "lo";
      else if (e.target === thHi) drag = "hi";
      else if (e.target === sband) { drag = "band"; refLo = yLo; refHi = yHi; refYear = yr; }
      else { drag = Math.abs(yr - yLo) <= Math.abs(yr - yHi) ? "lo" : "hi"; applyDrag(yr); }
      slider.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    slider.addEventListener("pointermove", (e) => { if (drag) applyDrag(yearAt(e.clientX)); });
    slider.addEventListener("pointerup", () => { drag = null; });
    slider.addEventListener("pointercancel", () => { drag = null; });
    function keyThumb(e, which) {
      let dd = 0;
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") dd = -1;
      else if (e.key === "ArrowRight" || e.key === "ArrowUp") dd = 1;
      else return;
      e.preventDefault();
      if (which === "lo") yLo = Math.max(yearMin, Math.min(yLo + dd, yHi));
      else yHi = Math.min(yearMax, Math.max(yHi + dd, yLo));
      render();
      onChange(yLo, yHi);
    }
    thLo.addEventListener("keydown", (e) => keyThumb(e, "lo"));
    thHi.addEventListener("keydown", (e) => keyThumb(e, "hi"));
    render();
    return { render, get yLo() { return yLo; }, get yHi() { return yHi; } };
  }

  // ---- coverage ramp (house grey->blue), t in [0,1] = coverage FRACTION.
  // Deliberately anchored at NOISE_GREY: 0% coverage is meant to visually
  // read as kin to "Unassigned" (thin evidence looks like the same grey as
  // no-confident-topic), which is the point of this specific encoding. Only
  // use this for a genuine coverage/fraction value — see seqColor below for
  // ordinal facets where the low end is real data, not an absence.
  const coverageRamp = d3.interpolateRgb(NOISE_GREY, "#0072B2");

  // ---- sequential ramp for ORDINAL facets (a start year, a dollar band)
  // that want "later/more reads as more saturated" without a categorical
  // palette's implication of unordered peers. Anchored at a light BLUE, not
  // NOISE_GREY — unlike coverageRamp above, the low end here is real data
  // (the earliest year, the smallest dollar band), and #c7ccd3 is reserved
  // for Unassigned/no-data system-wide; reusing coverageRamp here would make
  // "earliest year" visually indistinguishable from "no data".
  // seqColor(t) takes t in [0,1]; callers normalize their own domain first.
  const sequentialRamp = d3.interpolateRgb("#bcd9ec", "#0072B2");
  const seqColor = (t) => sequentialRamp(Math.max(0, Math.min(1, t)));

  // ---- coverage evidence strip: a thin per-year ribbon, fill = coverage
  // fraction on the house grey->blue ramp. Shared by topic_flow.html
  // (under the x-axis) and what_we_can_see.html (as its hero encoding),
  // so "thin evidence" reads identically wherever it appears.
  // sel: a d3 selection of a <g> already translated into place.
  // years: array of year numbers (dense, including zero-coverage years).
  // coverageByYear: Map/object year -> fraction in [0,1] or null/undefined
  //   for "no grants that year" (rendered as a hairline, not a hole).
  function drawCoverageStrip(sel, { x, width, height, years, coverageByYear }) {
    const cellW = Math.max(1, width);
    sel.selectAll("rect.cov-cell")
      .data(years)
      .join("rect")
      .attr("class", "cov-cell")
      .attr("x", (yr) => x(yr) - cellW / 2)
      .attr("y", 0)
      .attr("width", cellW)
      .attr("height", height)
      .attr("fill", (yr) => {
        const c = coverageByYear[yr];
        return c == null ? "#f0f1f3" : coverageRamp(c);
      })
      .attr("rx", 1);
  }

  // ---- accessible tab strip: role=tablist/tab/tabpanel, arrow-key nav
  // (Left/Right/Home/End), and a #hash sync so a tab is linkable and
  // survives reload. Built for pages with several stacked sections that
  // used to rely on scrolling (see what_we_can_see.html).
  //
  // Render-on-first-activation is the CALLER's job, not this helper's: a
  // hidden (display:none) panel measures clientWidth as 0, so any render
  // function that lays out from its container's width must never run
  // against a panel that isn't actually visible yet. onActivate(key,
  // firstTime) tells the caller exactly when to do that first render.
  //
  // opts: {tablist: Element, tabs: [{key, label, panel: Element}],
  //        initial?: key, onActivate(key, firstTime)}
  function setupTabs(opts) {
    const { tablist, tabs, onActivate } = opts;
    const activated = new Set();
    let current = null;
    const btns = {};

    tablist.innerHTML = "";
    tablist.setAttribute("role", "tablist");

    tabs.forEach((t) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = t.label;
      b.className = "tab";
      b.id = `tab-${t.key}`;
      b.setAttribute("role", "tab");
      b.setAttribute("aria-controls", t.panel.id);
      b.tabIndex = -1;
      t.panel.setAttribute("role", "tabpanel");
      t.panel.setAttribute("aria-labelledby", b.id);
      b.addEventListener("click", () => activate(t.key));
      b.addEventListener("keydown", (e) => {
        const idx = tabs.findIndex((x) => x.key === t.key);
        let ni = null;
        if (e.key === "ArrowRight") ni = (idx + 1) % tabs.length;
        else if (e.key === "ArrowLeft") ni = (idx - 1 + tabs.length) % tabs.length;
        else if (e.key === "Home") ni = 0;
        else if (e.key === "End") ni = tabs.length - 1;
        if (ni != null) {
          e.preventDefault();
          activate(tabs[ni].key);
          btns[tabs[ni].key].focus();
        }
      });
      btns[t.key] = b;
      tablist.appendChild(b);
    });

    function activate(key) {
      if (key === current) return;
      current = key;
      tabs.forEach((t) => {
        const active = t.key === key;
        btns[t.key].classList.toggle("active", active);
        btns[t.key].setAttribute("aria-selected", String(active));
        btns[t.key].tabIndex = active ? 0 : -1;
        t.panel.hidden = !active;
      });
      if (location.hash.slice(1) !== key) history.replaceState(null, "", `#${key}`);
      const firstTime = !activated.has(key);
      activated.add(key);
      onActivate(key, firstTime);
    }

    const fromHash = tabs.find((t) => t.key === location.hash.slice(1));
    const startKey = (fromHash || tabs.find((t) => t.key === opts.initial) || tabs[0]).key;
    activate(startKey);
    window.addEventListener("hashchange", () => {
      const t = tabs.find((x) => x.key === location.hash.slice(1));
      if (t) activate(t.key);
    });

    return { activate, get current() { return current; } };
  }

  // ---- caveat footer: renders viz_meta.caveats[] filtered to the ids a
  // given view touches, so disclosure text lives in exactly one place. ----
  function renderCaveats(containerEl, caveats, ids) {
    const rows = caveats.filter((c) => ids.includes(c.id));
    containerEl.innerHTML = rows
      .map((c) => `<span class="${c.severity === "high" ? "sev-high" : ""}">${esc(c.text)}</span>`)
      .join("");
  }

  global.ENRICO = {
    COLORS, ORDER, TOPIC_COLORS, PARENT_COLORS, PARENT_NAMES, NOISE_GREY,
    topicColor, parentColor, parentName, seqColor,
    fmtAmt, fmtPct, esc,
    setupDock, setupTooltip, setupSegmented, setupYearSlider, setupTabs,
    drawCoverageStrip, renderCaveats,
  };
})(window);
