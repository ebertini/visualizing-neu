// about.js — the "About this data" portion of the "About this data & what's
// missing" tab: the coverage headline, the two main showcase stories (money
// made through the grants, inter-college PI/co-PI collaboration), a
// supporting "what we found" summary of this session's own calibration
// work, every caveat grouped by severity, and the frozen-model summary.
//
// Split out of missing.js (2026-08-30) into its own module: missing.js
// already covered three other concerns (the missingness table, coverage
// detail, the funnel) before the about.html merge added a fourth, and now a
// fifth/sixth with the two showcases below — this keeps each module to one
// concern, matching the rest of this codebase's convention (data.js/
// constants.js/facets.js/layout.js/detail.js/grid.js/missing.js).
//
// No new data-fetching — imports the SAME already-loaded VIZ_META/COVERAGE/
// FACETS missing.js and main.js already use. The money and collaboration
// stories deliberately compute almost everything CLIENT-SIDE from FACETS
// (already in memory) rather than adding a second backend aggregation of
// the same numbers — the exact stale-number bug this file's own review
// found (four CAVEATS entries had drifted from the live data they describe)
// is what a second, independently-computed source of the same fact risks
// recreating. The one genuinely new PIECE of data, the college-pair matrix,
// has no per-grant analogue to compute from — it's backend-computed once
// (src/build_viz_aggregates.py's build_college_collab()) and shipped as
// VIZ_META.college_collab.
import { VIZ_META, COVERAGE, FACETS } from "./data.js";
import { COLLEGE_SHORT } from "./constants.js";

const E = window.ENRICO;

function renderHeadline() {
  const totalGrants = COVERAGE.agencies.reduce((s, a) => s + COVERAGE.by_agency[a].n, 0);
  const covPct = COVERAGE.provenance;
  // `total - none` is the correct complement of "have only a title" — see
  // this function's git history for the self-contradicting version a
  // real-browser check caught (summing only internal+orphan_recovered
  // silently excluded the 459 API-backfilled abstracts from "have an
  // abstract" while still counting them out of the title-only total).
  const haveAbs = totalGrants - covPct.none;
  document.getElementById("aboutHeadline").innerHTML =
    `<b>${totalGrants.toLocaleString()}</b> grants in this corpus. ` +
    `<b>${E.fmtPct(haveAbs / totalGrants, 1)}</b> have an abstract — ` +
    `<b>${covPct.none.toLocaleString()}</b> have only a title. ` +
    `<b>${COVERAGE.unassigned.n.toLocaleString()}</b> (${E.fmtPct(COVERAGE.unassigned.share_n)}) carry no confident topic — ` +
    `kept as <i>Unassigned</i>, never forced into a cluster.`;

  document.getElementById("aboutHowto").textContent =
    `Every grant and Every PI each show every record in their corpus, in every arrangement — ` +
    `nobody and nothing is ever dropped, only repositioned as you change Rows, Columns, Sort, ` +
    `or Color by.`;
}

function stattile(value, label) {
  return `<div class="stattile"><div class="v">${value}</div><div class="l">${E.esc(label)}</div></div>`;
}

// A local $ formatter, not shared/enrico.js's `E.fmtAmt` — that one caps out
// at "$XXXXM" (never abbreviates to billions), which is right for a
// per-grant amount (nothing here is ever that big) but wrong for a
// corpus-wide total in the billions.
function fmtBig(v) {
  return v >= 1e9 ? `$${(v / 1e9).toFixed(2)}B` : E.fmtAmt(v);
}

function barList(containerEl, rows, {maxN} = {}) {
  // rows: [{label, n, color}], already sorted by whoever built the list.
  const top = maxN ? rows.slice(0, maxN) : rows;
  const max = Math.max(1, ...top.map(r => r.n));
  containerEl.innerHTML = top.map(r => `
    <div class="barrow">
      <span class="lbl" title="${E.esc(r.label)}">${E.esc(r.label)}</span>
      <span class="track"><span class="fill" style="width:${(100 * r.n / max).toFixed(1)}%${r.color ? `;background:${r.color}` : ""}"></span></span>
      <span class="n">${r.nLabel || r.n.toLocaleString()}</span>
    </div>`).join("");
}

// ---------- Story B: money made through the grants ----------
function renderMoney() {
  const totalDollars = VIZ_META.totals.dollars;
  const amounts = FACETS.cols.amt_raw.slice().sort((a, b) => a - b);
  const n = amounts.length;
  const median = amounts[Math.floor(n / 2)];
  const sumTopShare = (frac) => {
    const k = Math.max(1, Math.round(n * frac));
    const topSlice = amounts.slice(n - k);
    return topSlice.reduce((s, v) => s + v, 0) / totalDollars;
  };
  const sumBottomShare = (frac) => {
    const k = Math.max(1, Math.round(n * frac));
    const bottomSlice = amounts.slice(0, k);
    return bottomSlice.reduce((s, v) => s + v, 0) / totalDollars;
  };

  document.getElementById("moneyIntro").innerHTML =
    `The headline figure is not money Northeastern raised — see the "not money NEU raised" ` +
    `caveat below for how pre-hire attribution works. Grant size is also heavily concentrated: `;

  document.getElementById("moneyStats").innerHTML = [
    stattile(fmtBig(totalDollars), `total across ${n.toLocaleString()} grants`),
    stattile(E.fmtAmt(median), "median grant"),
    stattile(E.fmtPct(sumTopShare(0.10), 0), "of dollars in the top 10% of grants"),
    stattile(E.fmtPct(sumBottomShare(0.50), 0), "of dollars in the bottom half of grants"),
  ].join("");

  renderAgencyDumbbell();
}

// A dollars-only bar list hid the actual finding here: NSF has 3x NIH's
// GRANT COUNT but only 1.2x its DOLLARS — NIH awards run ~2.2x larger.
// Expressing both measures as a SHARE of their own total puts them on one
// honest axis (never a dual-axis chart with two different scales — the
// dataviz skill's #1 named anti-pattern). Computed client-side from
// FACETS.cols.ag/amt_raw (already in memory), same as the retired bar list.
function computeAgencyShares() {
  const n = FACETS.n;
  const cnt = new Map(), dol = new Map();
  for (let i = 0; i < n; i++) {
    const ai = FACETS.cols.ag[i];
    cnt.set(ai, (cnt.get(ai) || 0) + 1);
    dol.set(ai, (dol.get(ai) || 0) + FACETS.cols.amt_raw[i]);
  }
  const totalDollars = VIZ_META.totals.dollars;
  return VIZ_META.agencies
    .map((a, i) => {
      const count = cnt.get(i) || 0, dollars = dol.get(i) || 0;
      return {key: a.key, label: a.label, color: a.color, count, dollars, nShare: n ? count / n : 0, dShare: totalDollars ? dollars / totalDollars : 0};
    })
    .sort((a, b) => b.nShare - a.nShare);
}

function renderAgencyDumbbell() {
  const svg = d3.select("#agencyDumbbellChart");
  svg.selectAll("*").remove();
  if (!VIZ_META.agencies || !VIZ_META.agencies.length || !FACETS.n) return;

  const rows = computeAgencyShares();
  // Fixed logical viewBox (house convention — see missing.js's charts):
  // this section can render eagerly at import time regardless of which
  // tab is active, because it never measures its own container width.
  const W = 900, rowH = 27, left = 74, right = 150;
  const padTop = 6, axisH = 20, gapAfterAxis = 16, padBottom = 6;
  const rowsTop = padTop + axisH + gapAfterAxis;
  const H = rowsTop + rows.length * rowH + padBottom;
  svg.attr("viewBox", `0 0 ${W} ${H}`);

  const maxShare = d3.max(rows, r => Math.max(r.nShare, r.dShare)) || 0.1;
  const xMax = Math.max(0.1, Math.ceil(maxShare * 20) / 20); // headroom, nearest 5%
  const plotW = W - left - right;
  const x = d3.scaleLinear().domain([0, xMax]).range([left, left + plotW]);

  svg.append("g").attr("class", "axis").attr("transform", `translate(0,${padTop + axisH})`)
    .call(d3.axisTop(x).ticks(5).tickFormat(d3.format(".0%")));

  const tip = E.setupTooltip(document.getElementById("agencyDumbbellTip"), document.getElementById("agencyDumbbellStage"));

  rows.forEach((r, ri) => {
    const g = svg.append("g").attr("class", "missrow").attr("transform", `translate(0,${rowsTop + ri * rowH})`);
    g.append("text").attr("class", "lbl").attr("x", left - 10).attr("y", rowH / 2 + 4).attr("text-anchor", "end")
      .text(r.key);
    const x1 = x(r.nShare), x2 = x(r.dShare);
    g.append("line").attr("x1", x1).attr("x2", x2).attr("y1", rowH / 2).attr("y2", rowH / 2)
      .attr("stroke", "#c9ccd1").attr("stroke-width", 2);
    // Hollow ring = share of grants, filled disc = share of dollars — one
    // hue per agency (color follows the entity), two treatments so the
    // pair still reads as a single item.
    g.append("circle").attr("cx", x1).attr("cy", rowH / 2).attr("r", 5)
      .attr("fill", "#fff").attr("stroke", r.color).attr("stroke-width", 2.2);
    g.append("circle").attr("cx", x2).attr("cy", rowH / 2).attr("r", 5)
      .attr("fill", r.color);
    g.append("text").attr("class", "pct").attr("x", left + plotW + 10).attr("y", rowH / 2 + 4)
      .text(`${E.fmtPct(r.nShare, 1)} → ${E.fmtPct(r.dShare, 1)}`);
    if (ri === 0) {
      // Selective direct labels (dataviz skill: label the endpoint that
      // matters, not every point) — spell out hollow-vs-filled once, on
      // the most prominent row, as a backup to the static legend above.
      g.append("text").attr("class", "rowlabel").attr("x", x1).attr("y", -6).attr("text-anchor", "middle").text("grants");
      g.append("text").attr("class", "rowlabel").attr("x", x2).attr("y", -6).attr("text-anchor", "middle").text("dollars");
    }
    g.append("rect").attr("class", "misshit").attr("x", left).attr("y", 0).attr("width", plotW).attr("height", rowH)
      .on("mousemove", ev => tip.show(
        `<div class="t">${E.esc(r.label)}</div>` +
        `<div class="meta">${r.count.toLocaleString()} grants (${E.fmtPct(r.nShare, 1)} of all grants)</div>` +
        `<div class="meta">${E.fmtAmt(r.dollars)} (${E.fmtPct(r.dShare, 1)} of all dollars)</div>`,
        ev.clientX, ev.clientY))
      .on("mouseleave", () => tip.hide());
  });
}

// ---------- Story A: inter-college PI/co-PI collaboration ----------
function renderCollaboration() {
  const cc = VIZ_META.college_collab;
  const teamCounts = {1: 0, 2: 0, 3: 0, 4: 0};
  for (const t of FACETS.nTeam) teamCounts[Math.min(t, 4)] = (teamCounts[Math.min(t, 4)] || 0) + 1;
  const multiPerson = FACETS.n - teamCounts[1];

  document.getElementById("collabIntro").innerHTML =
    `Team size counts distinct PEOPLE linked to a grant, any role — not a count of ` +
    `"co-PI"-flagged rows, which turned out to be an unreliable signal (many single-person ` +
    `grants have their sole person recorded as "co-PI" with no separate PI row at all). ` +
    `Colleges involved counts distinct roster colleges among that same group.` +
    collabGrowthPhrase(cc.by_year);

  document.getElementById("collabStats").innerHTML = [
    stattile(cc.n_cross_college.toLocaleString(), "grants cross a college line"),
    stattile(E.fmtPct(cc.n_cross_college / FACETS.n, 1), "of all grants"),
    stattile(E.fmtPct(cc.n_cross_college / multiPerson, 0), "of grants with more than one person"),
    stattile(fmtBig(cc.dollars), "on cross-college grants"),
  ].join("");

  renderCollabMatrix(cc);
}

// Computed, not typed — VIZ_META.college_collab.by_year (2005-2025) was
// previously rendered nowhere; a hand-typed version of this sentence is
// exactly the stale-number failure mode this file's own history is made
// of (see the module comment above), so it's derived fresh at render time
// from the same field the matrix below reads.
function collabGrowthPhrase(byYear) {
  if (!byYear || byYear.length < 4) return "";
  const avg = (arr) => arr.length ? arr.reduce((s, d) => s + d.n, 0) / arr.length : 0;
  const earlyAvg = avg(byYear.filter(d => d.year < 2015));
  const lateAvg = avg(byYear.filter(d => d.year >= 2015));
  if (!earlyAvg || !lateAvg) return "";
  return ` Cross-college grants have also grown steadily — from an average of ${earlyAvg.toFixed(1)}/year ` +
    `before 2015 to ${lateAvg.toFixed(1)}/year since.`;
}

// ---------- Inter-college collaboration matrix ----------
// Replaces a pair-list bar chart (two full college names concatenated into
// a 230px ellipsized label) with the form notebooks/05_collaboration_network
// already established for this exact data: a college x college heatmap
// (cell 17, w7_cross_college_matrix.png). FULL square, not a lower
// triangle — a stair-step triangle made it hard to tell which row a given
// cell belonged to once its own column ran out of cells to its right; a
// complete n x n grid (every college is both a row AND a column, each pair
// mirrored across the diagonal — same value shown twice, matching the
// source notebook's own `M + M.T` symmetrization) removes that ambiguity
// entirely, at the cost of showing every real number twice.
function renderCollabMatrix(cc) {
  const svg = d3.select("#collabMatrixChart");
  svg.selectAll("*").remove();
  const captionEl = document.getElementById("collabMatrixCaption");
  if (!cc || !cc.pairs || !cc.pairs.length || !cc.by_college || cc.by_college.length < 2) {
    if (captionEl) captionEl.textContent = "College-pair data isn't available in this build.";
    return;
  }

  // Row/column order = participation count descending (already server-
  // sorted) — puts the densest corner top-left, so "College of Engineering
  // is the hub" reads directly from the matrix's own shape.
  const order = cc.by_college.map(c => c.college);
  const n = order.length;
  const shortName = (name) => COLLEGE_SHORT[name] || name;
  const pairMap = new Map();
  for (const p of cc.pairs) pairMap.set([p.a, p.b].sort().join("||"), p);

  // Cell size picked so the matrix is at least as wide as this section's
  // own 720px reading measure (.aboutarticle p/.lede/.aboutnote) — a chart
  // narrower than the text sitting above it read as a shrunken afterthought.
  const READING_WIDTH = 720;
  const left = 74, top = 34, right = 14, bottom = 14;
  const cell = Math.max(40, Math.ceil((READING_WIDTH - left - right) / n));
  const W = left + n * cell + right;
  const H = top + n * cell + bottom;
  svg.attr("viewBox", `0 0 ${W} ${H}`);
  // .aboutstage svg{width:100%} (shared with the agency dumbbell above,
  // which SHOULD stretch full-width) would otherwise stretch this matrix to
  // fill the ~1150px content column regardless of its own viewBox size —
  // capped here, from the same computed W, rather than a separate guessed
  // CSS pixel value that could drift from it.
  document.getElementById("collabMatrixStage").style.maxWidth = `${W}px`;

  // sqrt, not linear — counts range 1..41; linear would render every
  // single-digit cell nearly indistinguishable from surface. The exact
  // value is always printed in the cell too, so the ramp only needs to
  // convey rank/magnitude at a glance, not carry the precise number.
  const maxN = d3.max(cc.pairs, p => p.n);
  const t = d3.scaleSqrt().domain([0, maxN]).range([0, 1]).clamp(true);

  order.forEach((name, ci) => {
    svg.append("text").attr("class", "rowlabel").attr("text-anchor", "middle")
      .attr("x", left + ci * cell + cell / 2).attr("y", top - 10)
      .text(shortName(name));
  });
  order.forEach((name, ri) => {
    svg.append("text").attr("class", "rowlabel").attr("text-anchor", "end")
      .attr("x", left - 10).attr("y", top + ri * cell + cell / 2 + 4)
      .text(shortName(name));
  });

  // Full row/column grid FIRST, underneath everything — every (row, col)
  // combination gets a boundary, including the diagonal and every
  // never-co-occurring pair, so a reader can trace any row all the way
  // across and any column all the way down regardless of where the colored
  // data itself stops. Reuses grid.js's own .cellgrid rule (a faint 1px
  // boundary already used for exactly this purpose on the facet grids)
  // rather than inventing a second "empty cell" convention.
  for (let ri = 0; ri < n; ri++) {
    for (let ci = 0; ci < n; ci++) {
      svg.append("rect").attr("class", "cellgrid")
        .attr("x", left + ci * cell).attr("y", top + ri * cell)
        .attr("width", cell).attr("height", cell);
    }
  }

  const tip = E.setupTooltip(document.getElementById("collabMatrixTip"), document.getElementById("collabMatrixStage"));

  for (let ri = 0; ri < n; ri++) {
    for (let ci = 0; ci < n; ci++) {
      const x0 = left + ci * cell, y0 = top + ri * cell;
      if (ri === ci) {
        // Diagonal = within-college collaboration — genuinely not computed
        // by build_college_collab() (cross-college grants only), not a
        // zero, so it gets its own neutral fill rather than either color.
        svg.append("rect").attr("x", x0 + 1).attr("y", y0 + 1).attr("width", cell - 2).attr("height", cell - 2)
          .attr("rx", 2).attr("fill", "#eef0f2");
        svg.append("rect").attr("class", "misshit")
          .attr("x", x0).attr("y", y0).attr("width", cell).attr("height", cell)
          .on("mousemove", ev => tip.show(
            `<div class="t">${E.esc(shortName(order[ri]))}</div><div class="meta">Within-college collaboration isn't computed here.</div>`,
            ev.clientX, ev.clientY))
          .on("mouseleave", () => tip.hide());
        continue;
      }
      const p = pairMap.get([order[ri], order[ci]].sort().join("||"));
      if (!p) continue; // grid-only — absence reads as an empty grid square, not zero
      const frac = t(p.n);
      const g = svg.append("g").attr("class", "matrixcell");
      g.append("rect")
        .attr("x", x0 + 1).attr("y", y0 + 1).attr("width", cell - 2).attr("height", cell - 2)
        .attr("rx", 2).attr("fill", E.seqColor(frac));
      g.append("text").attr("x", x0 + cell / 2).attr("y", y0 + cell / 2 + 3.5)
        .attr("fill", frac > 0.55 ? "#fff" : "var(--ink)")
        .text(p.n);
      g.append("rect").attr("class", "misshit")
        .attr("x", x0).attr("y", y0).attr("width", cell).attr("height", cell)
        .on("mousemove", ev => tip.show(
          `<div class="t">${E.esc(shortName(p.a))} + ${E.esc(shortName(p.b))}</div>` +
          `<div class="meta">${p.n.toLocaleString()} shared grants · ${E.fmtAmt(p.dollars)}</div>`,
          ev.clientX, ev.clientY))
        .on("mouseleave", () => tip.hide());
    }
  }

  const possiblePairs = (n * (n - 1)) / 2;
  if (captionEl) {
    captionEl.textContent =
      `${cc.n_cross_college.toLocaleString()} grants cross a college line, across ${cc.pairs.length} of ` +
      `${possiblePairs} possible college pairs — each shown twice, mirrored across the grey diagonal, so ` +
      `every row lines up with its own column. The diagonal itself (within-college collaboration) isn't ` +
      `computed by this pipeline. A blank cell means that pair has never co-occurred in this corpus, not ` +
      `that it was measured at zero — and the smallest colleges here have too few grants to read much ` +
      `into on their own.`;
  }
}

// ---------- Supporting "what we found" summary ----------
// The strongest, cheapest-to-verify findings from this session's own
// calibration work — deliberately a short list, not everything the review
// turned up (see the plan this was built from). The BERTopic baseline
// (697/$582.7M/26.7%) is a frozen historical fact about a RETIRED model
// that can never be recomputed — the one legitimate literal constant here,
// everything else is read from VIZ_META/FACETS at render time.
function renderFindings() {
  const cal = VIZ_META.calibration;
  const items = [];

  items.push(
    `Unassigned collapsed from BERTopic's frozen 697 grants ($582.7M, 26.7% of dollars) to ` +
    `${VIZ_META.totals.unassigned_n} grants (${E.fmtAmt(VIZ_META.totals.unassigned_dollars)}, ` +
    `${E.fmtPct(VIZ_META.totals.unassigned_share_d, 1)} of dollars) under the curated keyword classifier.`
  );

  if (cal.sweep_n_runs != null) {
    items.push(
      `A ${cal.sweep_n_runs}-configuration sweep of the classifier's own tuning constants found ` +
      `${cal.sweep_n_beat_baseline === 0 ? "none" : cal.sweep_n_beat_baseline} that beat the baseline — ` +
      `the fix for the classifier's title-only confidence gap turned out to be curation coverage, ` +
      `not constant-tuning.`
    );
  }
  if (cal.llm_n_reviewed != null) {
    items.push(
      `An optional LLM review layer, given only the classifier's own uncertain tail (${cal.llm_n_reviewed.toLocaleString()} grants), ` +
      `abstained on ${cal.llm_n_abstained.toLocaleString()} (${E.fmtPct(cal.llm_n_abstained / cal.llm_n_reviewed, 0)}) rather than force an answer, ` +
      `and changed the topic on ${cal.llm_n_changed_leaf.toLocaleString()} of the rest.`
    );
  }

  // Computing vs. Biomedical over time — computed client-side from
  // FACETS.cols.yr/tp/amt_raw (all already loaded), comparing 2005-2014 to
  // 2016-2025 dollar shares. Parent names looked up by string match against
  // VIZ_META.parents rather than an assumed index, so this can't silently
  // break if the parent order ever changes.
  const computingId = VIZ_META.parents.find(p => p.name.startsWith("Computing"))?.id;
  const biomedId = VIZ_META.parents.find(p => p.name === "Biomedical Sciences")?.id;
  if (computingId != null && biomedId != null) {
    const windowShare = (lo, hi, pid) => {
      let win = 0, tot = 0;
      for (let i = 0; i < FACETS.n; i++) {
        const yr = FACETS.cols.yr[i];
        if (yr == null || yr < lo || yr > hi) continue;
        tot += FACETS.cols.amt_raw[i];
        if (FACETS.cols.tp[i] === pid) win += FACETS.cols.amt_raw[i];
      }
      return tot ? win / tot : null;
    };
    const compEarly = windowShare(2005, 2014, computingId), compLate = windowShare(2016, 2025, computingId);
    const bioEarly = windowShare(2005, 2014, biomedId), bioLate = windowShare(2016, 2025, biomedId);
    if (compEarly != null && compLate != null && bioEarly != null && bioLate != null) {
      items.push(
        `Computing, Networking & Robotic Systems grew from ${E.fmtPct(compEarly, 0)} to ${E.fmtPct(compLate, 0)} ` +
        `of dollars (2005-2014 vs. 2016-2025), overtaking Biomedical Sciences (${E.fmtPct(bioEarly, 0)} → ${E.fmtPct(bioLate, 0)}) ` +
        `as the largest funded theme in the last decade.`
      );
    }
  }

  document.getElementById("findingsList").innerHTML = items.map(t => `<li>${t}</li>`).join("");
}

// Grouped by severity, most severe first — a readable list, not the flat
// chart-footer chip row shared/enrico.js's renderCaveats builds (that
// component takes a mandatory id filter and is meant for a single line
// under a chart, not a stand-alone section — see the coverage section's OWN
// renderCaveats call in missing.js, which IS whitelisted, for that narrower
// case). This one deliberately shows EVERY caveat, not a curated subset —
// the comprehensive reference the former about.html page existed to be.
function renderCaveats() {
  const SEV_ORDER = ["high", "med", "low"];
  const SEV_LABEL = {high: "High severity", med: "Medium severity", low: "Low severity"};
  const cavEl = document.getElementById("aboutCaveats");
  cavEl.innerHTML = SEV_ORDER.map(sev => {
    const rows = VIZ_META.caveats.filter(c => c.severity === sev);
    if (!rows.length) return "";
    const items = rows.map(c => `<li>${E.esc(c.text)}</li>`).join("");
    return `<div class="cavgroup sev-${sev}"><h4>${SEV_LABEL[sev]}</h4><ul class="cavlist">${items}</ul></div>`;
  }).join("");

  const fi = VIZ_META.frozen_inputs;
  document.getElementById("modelgrid").innerHTML =
    `<dt>Pipeline</dt><dd>${E.esc(fi.projection)}</dd>` +
    `<dt>Grants embedded</dt><dd>${fi.n_points.toLocaleString()}</dd>` +
    `<dt>Topics</dt><dd>${fi.n_topics} + an explicit "Unassigned" noise cluster</dd>`;
}

export function initAboutSection() {
  renderHeadline();
  renderMoney();
  renderCollaboration();
  renderFindings();
  renderCaveats();
}
