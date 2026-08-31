// missing.js — the "What's missing" portion of the "About this data &
// what's missing" tab: the by-agency/by-year coverage bars, the NIH-vs-NSF
// cliff chart, the mosaic finding, the sortable missing-fields table (three
// grains), and the funnel. Split out of what_we_can_see.html's single
// inline script; behavior is unchanged, only the module boundary is new.
// The "About this data" portion (coverage headline, the money/collaboration
// showcases, caveats, model summary) briefly lived here after the
// about.html merge (2026-08-30) but was moved out to its own about.js the
// same day — this file had already grown to cover three concerns before
// that merge, and the showcases added a fourth/fifth; see about.js's own
// module comment.
//
// initMissingTab() bundles this tab's eager-init sequence (previously a
// flat block near the bottom of the inline script) into one exported
// function, called once from main.js (alongside, not inside, about.js's
// own initAboutSection()). This keeps `missGrain` — mutated by the
// Grants/PIs/Abstract-records segmented control below — a module-private
// `let` instead of an imported binding: assigning to an imported name is a
// TypeError (imported bindings are read-only), so the control's onChange
// handler has to live in the same module as the state it mutates.
import { VIZ_META, COVERAGE, MISSINGNESS, FUNNEL } from "./data.js";
import { AGENCIES, YEARS, cellByKey } from "./constants.js";

const E = window.ENRICO;

function renderCoverageByAgency(){
  const svgA = d3.select("#covagencychart");
  svgA.selectAll("*").remove();
  const W = 900, rowH = 30, left = 190, right = 70, top = 8;
  const H = top * 2 + AGENCIES.length * rowH;
  svgA.attr("viewBox", `0 0 ${W} ${H}`);
  const plotW = W - left - right;
  const covTip = E.setupTooltip(document.getElementById("covagencytip"), document.getElementById("covagencystage"));

  AGENCIES.forEach((agencyKey, ri) => {
    const meta = VIZ_META.agencies.find(a => a.key === agencyKey) || {label: agencyKey, color: "#0072B2"};
    const stats = COVERAGE.by_agency[agencyKey];
    const g = svgA.append("g").attr("class", "missrow").attr("transform", `translate(0,${top + ri * rowH})`);
    g.append("text").attr("class", "lbl").attr("x", left - 10).attr("y", rowH / 2 + 4).attr("text-anchor", "end")
      .text(agencyKey);
    g.append("rect").attr("x", left).attr("y", rowH / 2 - 9).attr("width", plotW).attr("height", 18)
      .attr("rx", 2).attr("fill", "#eef0f2");
    g.append("rect").attr("x", left).attr("y", rowH / 2 - 9).attr("width", plotW * (stats.cov || 0)).attr("height", 18)
      .attr("rx", 2).attr("fill", meta.color);
    g.append("text").attr("class", "pct").attr("x", left + plotW + 8).attr("y", rowH / 2 + 4)
      .text(`${stats.n.toLocaleString()} · ${E.fmtPct(stats.cov)}`);
    g.append("rect").attr("class", "misshit").attr("x", left).attr("y", rowH / 2 - 9).attr("width", plotW).attr("height", 18)
      .on("mousemove", ev => covTip.show(
        `<div class="t">${E.esc(meta.label)}</div><div class="meta">${stats.n.toLocaleString()} grants · ${stats.abs.toLocaleString()} with an abstract (${E.fmtPct(stats.cov)})</div>`,
        ev.clientX, ev.clientY))
      .on("mouseleave", () => covTip.hide());
  });
}

function renderCoverageByYear(){
  const svgY = d3.select("#covyearchart");
  svgY.selectAll("*").remove();
  const W = 900, H = 100, margin = {top: 8, right: 16, bottom: 20, left: 16};
  svgY.attr("viewBox", `0 0 ${W} ${H}`);
  const x = d3.scalePoint().domain(YEARS).range([margin.left, W - margin.right]);
  const cellW = (x(YEARS[1]) - x(YEARS[0])) * 0.82;
  const covByYear = {};
  YEARS.forEach((y, i) => { covByYear[y] = COVERAGE.by_year.cov[i]; });

  const g = svgY.append("g").attr("transform", `translate(0,${margin.top})`);
  E.drawCoverageStrip(g, {x, width: cellW, height: H - margin.top - margin.bottom, years: YEARS, coverageByYear: covByYear});

  YEARS.forEach(y => {
    if (y % 5 !== 0) return;
    svgY.append("text").attr("class", "rowlabel").attr("x", x(y)).attr("y", H - 4).attr("text-anchor", "middle").text(y);
  });
}

// The mosaic panel that used to hold this finding as a two-column stacked
// chart is gone — the finding itself survives as one line. Reads the
// classifier's own confidence_by_text block (not the old crosstab, which
// only ever asked "assigned vs not" — the classifier assigns nearly
// everything, so that question stopped being the interesting one). States
// whatever the numbers actually show — under the curated keyword classifier
// this is NOT the same reassuring "titles carry most of the signal" claim
// BERTopic supported; a real gap here is a genuine, currently-uncalibrated
// limitation (see the "low_confidence" / "keyword_classifier" caveats), not
// something to soften.
function mosaicFindingText(){
  const cb = COVERAGE.confidence_by_text;
  if (!cb) return "Confidence-by-text breakdown unavailable.";
  const lowNoneRate = (blk) => blk && blk.n ? (blk.low + blk.none) / blk.n : null;
  const absRate = lowNoneRate(cb.abs);
  const titleRate = lowNoneRate(cb.title);
  if (absRate === null || titleRate === null) return "Confidence-by-text breakdown unavailable.";
  const gapPp = Math.abs(titleRate - absRate) * 100;
  const verdict = gapPp <= 10
    ? "close enough that text availability isn't driving confidence"
    : "a real gap — text availability still moves classifier confidence more than it should";
  return `Low/no-confidence rate: ${E.fmtPct(absRate)} with an abstract vs ${E.fmtPct(titleRate)} title-only (${verdict}).`;
}

/* ---------- NIH vs NSF coverage line, 2005-2025 (kept from the
   deprecated "Does it matter?" tab — the evidence behind the single
   loudest caveat on the page) ---------- */
function renderCliff(){
  const svg3 = d3.select("#cliffchart");
  svg3.selectAll("*").remove();
  const W=480,H=260, margin={top:10,right:16,bottom:26,left:34};
  const yrs = YEARS.filter(y=>y>=2005 && y<=2025);
  const x = d3.scaleLinear().domain([2005,2025]).range([margin.left,W-margin.right]);
  const y = d3.scaleLinear().domain([0,1]).range([H-margin.bottom,margin.top]);

  svg3.append("g").attr("transform",`translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(5).tickFormat(d3.format(".0%")).tickSize(-(W-margin.left-margin.right)))
    .call(g=>g.selectAll(".tick line").attr("stroke",'var(--hair)'))
    .call(g=>g.select(".domain").remove());
  svg3.append("g").attr("transform",`translate(0,${H-margin.bottom})`)
    .call(d3.axisBottom(x).ticks(6).tickFormat(d3.format("d")));

  function series(agency){
    return yrs.map(yr=>{
      const c = cellByKey[agency+"|"+yr];
      return {yr, cov: c ? c.cov : null};
    });
  }
  const line = d3.line().defined(d=>d.cov!=null).x(d=>x(d.yr)).y(d=>y(d.cov)).curve(d3.curveLinear);

  [["NSF","#0072B2"],["NIH","#E69F00"]].forEach(([agency,color])=>{
    const data = series(agency);
    svg3.append("path").attr("d",line(data)).attr("fill","none").attr("stroke",color).attr("stroke-width",2);
    svg3.selectAll(`.dot-${agency}`).data(data.filter(d=>d.cov!=null)).join("circle")
      .attr("cx",d=>x(d.yr)).attr("cy",d=>y(d.cov)).attr("r",2.4).attr("fill",color);
    const last = [...data].reverse().find(d=>d.cov!=null);
    if(last) svg3.append("text").attr("x",x(last.yr)+5).attr("y",y(last.cov)+3)
      .attr("class","rowlabel").attr("fill",color).text(agency);
  });
  // cliff marker position comes from COVERAGE.cliffs[0] (server-computed,
  // shared with topic_flow.html via the same viz_meta.json/coverage.json
  // source) rather than a hardcoded year — previously both files hardcoded
  // 2019.5 independently.
  const cliff = COVERAGE.cliffs[0];
  const cliffX = x(cliff.last_good_year + 0.5);
  svg3.append("line").attr("x1",cliffX).attr("x2",cliffX)
    .attr("y1",margin.top).attr("y2",H-margin.bottom)
    .attr("stroke","#8a4b00").attr("stroke-dasharray","4 3").attr("stroke-width",1.2);
}

/* ---------- "What's missing, field by field" ---------- */
// Three grains, one at a time (PI feedback: split by grants vs. PIs rather
// than one flat list) — each scored against its OWN population (2,676
// grants / 2,247 roster faculty / 8,075 raw abstract-upload records), never
// against a shared 2,676. A field with a "recoverable" count (currently
// only "Abstract text", from scripts/_check_new_abstracts.py) gets a third
// bar segment — recoverable grants are a SUBSET of "missing", not additional.
let missGrain = "grants";
const MISS_GRAIN_LABELS = {grants: "grants", pis: "faculty on the current roster", abstract_records: "raw abstract-upload records"};

function updateMissingSub(){
  const grain = MISSINGNESS.grains[missGrain];
  document.getElementById("missingSub").textContent =
    `${grain.n.toLocaleString()} ${MISS_GRAIN_LABELS[missGrain]}, sorted by the field with the most gaps first.`;
}

function renderMissingness(){
  const svg4 = d3.select("#missingchart");
  svg4.selectAll("*").remove();
  const W = 900, rowH = 34, top = 10, left = 190, right = 60;
  const grain = MISSINGNESS.grains[missGrain];
  const fields = grain.fields; // server-sorted by missing count, descending
  const barW = W - left - right;
  svg4.attr("viewBox", `0 0 ${W} ${Math.max(1, top * 2 + fields.length * rowH)}`);

  const missTip = E.setupTooltip(document.getElementById("missingtip"), document.getElementById("missingstage"));

  fields.forEach((f, i) => {
    const n = grain.n || 1;
    const recoverable = Math.min(f.recoverable || 0, f.missing);
    const stillMissing = f.missing - recoverable;
    const wKnown = barW * (f.known / n), wRec = barW * (recoverable / n),
          wMiss = barW * (stillMissing / n), wNA = barW * (f.na / n);
    const g = svg4.append("g").attr("class", "missrow").attr("transform", `translate(0,${top + i * rowH})`);

    g.append("text").attr("class", "lbl").attr("x", 0).attr("y", rowH / 2 + 4).text(f.label);

    let x = left;
    g.append("rect").attr("x", x).attr("y", rowH / 2 - 9).attr("width", wKnown).attr("height", 18)
      .attr("rx", 2).attr("fill", "#0072B2").attr("opacity", .85);
    x += wKnown;
    if (wRec > 0) {
      g.append("rect").attr("x", x).attr("y", rowH / 2 - 9).attr("width", wRec).attr("height", 18)
        .attr("rx", 2).attr("fill", "#56B4E9");
      x += wRec;
    }
    g.append("rect").attr("x", x).attr("y", rowH / 2 - 9).attr("width", wMiss).attr("height", 18)
      .attr("rx", 2).attr("fill", E.NOISE_GREY);
    x += wMiss;
    if (wNA > 0) {
      g.append("rect").attr("x", x).attr("y", rowH / 2 - 9).attr("width", wNA).attr("height", 18)
        .attr("rx", 2).attr("fill", "#e6e8ec");
    }
    g.append("text").attr("class", "pct").attr("x", left + barW + 8).attr("y", rowH / 2 + 4)
      .text(E.fmtPct(f.known / n));

    g.append("rect").attr("class", "misshit").attr("x", left).attr("y", rowH / 2 - 9).attr("width", barW).attr("height", 18)
      .on("mousemove", ev => {
        missTip.show(
          `<div class="t">${E.esc(f.label)}</div>` +
          `<div class="meta">${f.known.toLocaleString()} known (${E.fmtPct(f.known / n)})</div>` +
          (recoverable > 0 ? `<div class="meta">${recoverable.toLocaleString()} recoverable from a newer data export</div>` : "") +
          `<div class="meta">${f.missing.toLocaleString()} missing (${E.fmtPct(f.missing / n)})</div>` +
          (f.na > 0 ? `<div class="meta">${f.na.toLocaleString()} not applicable</div>` : ""),
          ev.clientX, ev.clientY);
      })
      .on("mouseleave", () => missTip.hide());
  });

  renderMissingTable(grain);
}

// Sortable field table — a plain-reading companion to the bars above, with
// the "where the gap comes from" column the bars alone can't carry.
const MISS_TABLE_COLS = [
  {key: "label", label: "Field", num: false},
  {key: "known", label: "Known", num: true},
  {key: "missing", label: "Missing", num: true},
  {key: "pct", label: "% missing", num: true},
  {key: "recoverable", label: "Recoverable", num: true},
  {key: "where", label: "Where the gap comes from", num: false},
];
function renderMissingTable(grain){
  const el = document.getElementById("missingtablewrap");
  let sortKey = "missing", sortDir = -1;

  function draw(){
    const rows = grain.fields
      .map(f => ({...f, pct: grain.n ? f.missing / grain.n : 0, recoverable: f.recoverable || 0}))
      .sort((a, b) => (a[sortKey] > b[sortKey] ? 1 : a[sortKey] < b[sortKey] ? -1 : 0) * sortDir);
    el.innerHTML = `<table class="misstable"><thead><tr>` +
      MISS_TABLE_COLS.map(c => `<th data-key="${c.key}" class="${c.num ? "num" : ""}${c.key === sortKey ? " sorted" : ""}">` +
        `${E.esc(c.label)}${c.key === sortKey ? (sortDir === 1 ? " ▲" : " ▼") : ""}</th>`).join("") +
      `</tr></thead><tbody>` +
      rows.map(f => `<tr>` +
        `<td>${E.esc(f.label)}</td>` +
        `<td class="num">${f.known.toLocaleString()}</td>` +
        `<td class="num">${f.missing.toLocaleString()}</td>` +
        `<td class="num">${E.fmtPct(f.pct)}</td>` +
        `<td class="num">${f.recoverable ? f.recoverable.toLocaleString() : "—"}</td>` +
        `<td>${E.esc(f.where || "")}</td>` +
        `</tr>`).join("") +
      `</tbody></table>`;
    el.querySelectorAll("th").forEach(th => th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (key === sortKey) sortDir = -sortDir;
      else { sortKey = key; sortDir = (key === "label" || key === "where") ? 1 : -1; }
      draw();
    }));
  }
  draw();
}

/* ---------- "Where the records go" — main trunk + orphan branch ---------- */
// Hand-written per-transition context — these three losses are each a
// different KIND of loss (no match at all / re-upload dedup / matched but
// empty), and funnel.json's trunk only carries counts, not the "why", so
// the reasons live here rather than being invented generically from n's.
const FUNNEL_LOSS_NOTES = [
  "didn't match an NEU grant directly — the orphan pool below",
  "duplicate re-uploads of the same grant (kept most recent)",
  "matched, but the abstract field was empty",
];

function renderFunnel(){
  const svg5 = d3.select("#funnelchart");
  svg5.selectAll("*").remove();
  if (!FUNNEL.trunk || !FUNNEL.trunk.length) return; // degraded provenance: nothing built locally

  const W = 900, left = 300, right = 40;
  const barW = W - left - right, rowH = 28, gapH = 44, top = 12;
  const trunk = FUNNEL.trunk, maxN = trunk[0].n;
  const funnelTip = E.setupTooltip(document.getElementById("funneltip"), document.getElementById("funnelstage"));

  trunk.forEach((s, i) => {
    const y = top + i * (rowH + gapH);
    const w = barW * (s.n / maxN);
    const g = svg5.append("g").attr("class", "funnelbar").attr("transform", `translate(0,${y})`);
    g.append("text").attr("class", "lbl").attr("x", left - 10).attr("y", rowH / 2 + 4).attr("text-anchor", "end")
      .text(s.label);
    g.append("rect").attr("x", left).attr("y", 0).attr("width", w).attr("height", rowH).attr("rx", 3)
      .attr("fill", "#0072B2").attr("opacity", .85);
    g.append("text").attr("class", "n").attr("x", left + w + 8).attr("y", rowH / 2 + 4)
      .text(s.n.toLocaleString());
    g.append("rect").attr("class", "funnelhit").attr("x", 0).attr("y", -6).attr("width", W).attr("height", rowH + 12)
      .on("mousemove", ev => funnelTip.show(
        `<div class="t">${E.esc(s.label)}</div><div class="meta">${s.n.toLocaleString()} records</div>`,
        ev.clientX, ev.clientY))
      .on("mouseleave", () => funnelTip.hide());

    if (i < trunk.length - 1) {
      const loss = s.n - trunk[i + 1].n;
      svg5.append("text").attr("class", "funnelloss")
        .attr("x", left).attr("y", y + rowH + gapH / 2 + 4)
        .text(`↓ −${loss.toLocaleString()} ${FUNNEL_LOSS_NOTES[i]}`);
    }
  });

  const branch = FUNNEL.branch;
  if (!branch) return; // M2 outputs not built locally — trunk only, honestly

  const byId = Object.fromEntries(branch.steps.map(s => [s.id, s.n]));
  const notAttempted = branch.n - byId.usable;
  const segments = [
    {label: "Title-only orphan (never attempted)", n: notAttempted, color: "#e6e8ec"},
    {label: "No faculty resolved", n: byId.unattributed, color: E.NOISE_GREY},
    {label: "Duplicate re-upload (dropped)", n: byId.duplicate, color: "#9AA0A6"},
    {label: "Backfilled onto an existing grant", n: byId.update, color: "#0072B2"},
    {label: "Added as a new record for the topic model", n: byId.extra, color: "#F28E2B"},
  ];

  const branchY = top + trunk.length * (rowH + gapH) + 14;
  svg5.append("text").attr("class", "branchlabel").attr("x", 0).attr("y", branchY - 10)
    .text(`What happened to the ${branch.n.toLocaleString()} that never matched a grant`);

  let x = 0;
  const bh = 30;
  segments.forEach(seg => {
    const w = W * (seg.n / branch.n);
    const g = svg5.append("g").attr("transform", `translate(${x},${branchY})`);
    g.append("rect").attr("width", w).attr("height", bh).attr("fill", seg.color);
    if (w > 46) {
      g.append("text").attr("class", "segseglabel").attr("x", 6).attr("y", bh / 2 + 3.5)
        .text(seg.n.toLocaleString());
    }
    g.append("rect").attr("class", "funnelhit").attr("width", w).attr("height", bh)
      .on("mousemove", ev => funnelTip.show(
        `<div class="t">${E.esc(seg.label)}</div><div class="meta">${seg.n.toLocaleString()} of ${branch.n.toLocaleString()} orphans (${E.fmtPct(seg.n / branch.n)})</div>`,
        ev.clientX, ev.clientY))
      .on("mouseleave", () => funnelTip.hide());
    x += w;
  });

  const totals = FUNNEL.totals;
  if (totals && totals.corpus_for_bertopic) {
    svg5.append("text").attr("class", "funnelloss").attr("x", 0).attr("y", branchY + bh + 20)
      .text(`Net effect: ${totals.has_text_final.toLocaleString()} grants end up carrying text; `+
            `the topic model's corpus grows to ${totals.corpus_for_bertopic.toLocaleString()} documents `+
            `(${totals.grants_total.toLocaleString()} grants + ${byId.extra} recovered extras).`);
  }
}

// The whole tab's eager-init sequence, called once from main.js. Bundled
// into one function (rather than left as a flat script-bottom block, as it
// was inline) specifically so the segmented control's onChange handler —
// which mutates missGrain — stays in the same module as that state; see
// the module comment above.
export function initMissingTab(){
  document.getElementById("mosaicFinding").textContent = mosaicFindingText();
  E.renderCaveats(document.getElementById("coverageCaveats"), VIZ_META.caveats, ["nih_cliff", "unassigned", "placeholder_titles", "keyword_classifier", "low_confidence"]);

  updateMissingSub();
  E.setupSegmented({
    container: document.getElementById("missGrainSwitch"),
    options: [{key: "grants", label: "Grants"}, {key: "pis", label: "PIs"}, {key: "abstract_records", label: "Abstract records"}],
    value: missGrain,
    onChange: (key) => { missGrain = key; updateMissingSub(); renderMissingness(); },
  });

  document.getElementById("funnelSub").textContent = (FUNNEL.trunk && FUNNEL.trunk.length)
    ? `${FUNNEL.trunk[0].n.toLocaleString()} raw records in, ${FUNNEL.trunk[FUNNEL.trunk.length - 1].n.toLocaleString()} grants with usable text out.`
    : "Local build outputs not found — run src/build_dataset.py to see this section.";

  renderCoverageByAgency();
  renderCoverageByYear();
  renderCliff();
  renderMissingness();
  renderFunnel();
}
