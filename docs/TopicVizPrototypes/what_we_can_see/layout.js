// layout.js — pure geometry/binning helpers behind both unit-visualization
// grids. No DOM writes, no page state, no data import — everything here
// takes facetDefs/data/layout numbers as parameters. Split out of
// what_we_can_see.html's single inline script; behavior is unchanged, only
// the module boundary is new.

// Partitions every row into an (arrange level x split level) cell and
// returns each axis's FULL level list — including levels with zero
// members — plus per-level marginal totals (count and dollars). The sort
// control orders levels by these MARGINALS, never by an individual cell:
// the matrix layout requires a single global row order and a single global
// column order, so if each row could reorder its own cells independently,
// "every split category holds the same column in every row" (PI feedback)
// would stop being true.
//
// When no "Rows" or "Columns" facet is chosen, that axis's levels list is a
// single synthetic unlabeled level (key 0, every row's ai/si is 0) so the
// matrix layout can treat "no rows"/"no split" as a plain 1-row or
// 1-column matrix instead of a separate path.
export function computeBins(facetDefs, data, arrKey, spKey) {
  const aDef = arrKey ? facetDefs[arrKey] : null;
  const aVals = aDef ? aDef.values() : null;
  const aLevels = aDef ? aDef.levels() : [{key: 0, label: "", color: null}];
  const aIndex = new Map(aLevels.map((lv, i) => [lv.key, i]));
  const sDef = spKey ? facetDefs[spKey] : null;
  const sVals = sDef ? sDef.values() : null;
  const sLevels = sDef ? sDef.levels() : [{key: 0, label: "", color: null}];
  const sIndex = new Map(sLevels.map((lv, i) => [lv.key, i]));

  const byCell = new Map();
  const aMarginalN = new Map(), aMarginalD = new Map(), sMarginalN = new Map(), sMarginalD = new Map();
  for (let i = 0; i < data.n; i++) {
    const ai = arrKey ? aIndex.get(aVals[i]) : 0;
    const si = spKey ? sIndex.get(sVals[i]) : 0;
    if (ai == null || si == null) continue; // defensive: shouldn't occur, every value has a level
    const key = ai + "|" + si;
    let cell = byCell.get(key);
    if (!cell) { cell = {ai, si, members: []}; byCell.set(key, cell); }
    cell.members.push(i);
    const amt = data.cols.amt_raw[i];
    aMarginalN.set(ai, (aMarginalN.get(ai) || 0) + 1);
    aMarginalD.set(ai, (aMarginalD.get(ai) || 0) + amt);
    sMarginalN.set(si, (sMarginalN.get(si) || 0) + 1);
    sMarginalD.set(si, (sMarginalD.get(si) || 0) + amt);
  }
  return {aLevels, sLevels, byCell, aMarginalN, aMarginalD, sMarginalN, sMarginalD};
}

// Orders one axis's levels by that axis's OWN marginal total (see the
// computeBins comment above for why never by an individual cell). Returns
// a permutation of 0..nLevels-1 — "natural" is the identity permutation,
// i.e. the facet's own declared level order.
export function sortedOrder(nLevels, marginalN, marginalD, mode) {
  const idx = Array.from({length: nLevels}, (_, i) => i);
  if (mode === "natural") return idx;
  const key = mode === "dollars" ? marginalD : marginalN;
  return idx.sort((a, b) => (key.get(b) || 0) - (key.get(a) || 0) || a - b);
}

// ONE fixed mark size for every arrangement — a bin's box no longer changes
// size when Rows/Columns/Sort changes (PI feedback: it used to, distractingly,
// since the old geometry picked the largest of five tiers that fit both the
// available width AND height for that particular arrangement). Overflow is
// handled elsewhere, not by shrinking the mark: #facetchartwrap's height
// grows to content (see its CSS) and #facetscroll scrolls horizontally if a
// row of columns is wider than the viewport — nothing is ever scaled down
// or a level dropped to force a fit.
export const MARK = 7.8, GAP = 1.3;
export const MIN_CELL_COLS = 3, CELL_PAD = 4, COL_GUT = 10, ROW_GUT = 14, HDR_H = 24, LABEL_LANE = 285;
// Breathing room between the chart's own container edge and the row-label
// lane — the grid is otherwise full-bleed (no section padding of its own),
// so without this the row labels sit flush against the browser edge.
// Mirrored in this page's CSS (page.css's #facetlabels/#pilabels' `left`).
export const STAGE_MARGIN = 24;
// Gap between a selected mark's own edge and its highlight ring — see
// grid.js's rect.selectring.
export const RING_PAD = 3;

// Row/column labels ("College of Engineering · 1,234") were previously
// truncated to a fixed character count while the bin box was sized purely
// from its mark grid — a bin with only a few marks (a small grid) but a
// long label spilled text into its neighbor. Measuring the actual rendered
// text width and sizing to fit it (up to a cap) fixes that at the source
// instead of guessing a character count. LABEL_MAX_W leaves room for the
// pinned row-label SVG's own left/right padding.
export const LABEL_MAX_W = LABEL_LANE - 40;
const measureCtx = document.createElement("canvas").getContext("2d");
// Kept in lockstep with .rowlabel/.colhdr's actual rendered font-size
// (style.css) — this measures the SAME text at the SAME size D3 will
// paint it at, so wrapLabel/fitLabel's width budget matches reality. A
// mismatch here (e.g. bumping the CSS font-size without updating this)
// silently overflows a label past its lane or column instead of wrapping.
measureCtx.font = "15.75px ui-monospace, 'SF Mono', Menlo, 'Cascadia Mono', Consolas, monospace";
export function measureText(s) { return measureCtx.measureText(s).width; }
export function fitLabel(s, maxW) {
  if (measureText(s) <= maxW) return s;
  let lo = 0, hi = s.length;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (measureText(s.slice(0, mid) + "…") <= maxW) lo = mid; else hi = mid - 1;
  }
  // Prefer breaking at a word boundary over mid-word ("Life Sciences &…"
  // rather than "Life Sciences & Bi…") — but only when the nearest space
  // doesn't throw away more than half of what character-fitting allowed;
  // for a short maxW with no good nearby break, mid-word is still better
  // than truncating a label down to almost nothing.
  const spaceIdx = s.lastIndexOf(" ", lo);
  const cut = spaceIdx > lo / 2 ? spaceIdx : lo;
  return s.slice(0, cut) + "…";
}

// Row and column labels used to always cut off after one line, even when
// there was clearly more than one line's worth of room (a tall row band,
// a wide-enough header) — this wraps instead, up to MAX_LABEL_LINES lines,
// greedily packing whole words per line. Any words left over after the
// line budget runs out (or a single word that's wider than maxW on its
// own) get folded through fitLabel's existing character-level ellipsis,
// so a label that's genuinely too long to show in full still ends in "…"
// rather than being silently cut mid-word.
export const LABEL_LINE_H = 18, MAX_LABEL_LINES = 2;
export function wrapLabel(text, maxW, maxLines) {
  const words = text.split(/\s+/).filter(Boolean);
  const lines = [];
  let i = 0;
  while (i < words.length && lines.length < maxLines) {
    let line = words[i++];
    while (i < words.length) {
      const trial = `${line} ${words[i]}`;
      if (measureText(trial) > maxW) break;
      line = trial;
      i++;
    }
    lines.push(line);
  }
  if (i < words.length) lines[lines.length - 1] += " " + words.slice(i).join(" ");
  return lines.map(line => (measureText(line) > maxW ? fitLabel(line, maxW) : line));
}

// Picks ONE shared cell width (in mark-columns) for the WHOLE matrix — every
// cell must be the same width for split categories to line up into columns
// (PI feedback: "each split category should be aligned in the same
// column"). `want` caps how many columns a cell gets even when there's tons
// of horizontal room, so a cell doesn't become one absurdly wide row just
// because the screen is big — capped to roughly what a square-ish packing
// of its own largest cell would need. If even MIN_CELL_COLS doesn't fit the
// available width, cellCols is still floored there and the matrix is
// allowed to exceed availW — #facetscroll (see CSS) then scrolls
// horizontally rather than any level being dropped to force a fit.
export function pickCellGeometry(nCols, maxCellN, availW) {
  const want = Math.max(MIN_CELL_COLS, Math.ceil(Math.sqrt(maxCellN * 1.4)));
  const perCol = (availW - (nCols - 1) * COL_GUT) / nCols - 2 * CELL_PAD;
  const fit = Math.floor((perCol + GAP) / (MARK + GAP));
  const cellCols = Math.max(MIN_CELL_COLS, Math.min(fit, want));
  return {mark: MARK, gap: GAP, cellCols};
}

// Lays every (arrange x split) cell into a matrix: aOrder/sOrder are the
// axes' already-sorted level orders (permutations from sortedOrder above).
// Every cell in a given row shares that row's y/height; every cell in a
// given column shares that column's x/width — the alignment PI feedback #2
// asked for. A cell with zero members still gets a slot (the caller draws
// a thin "no grants here" placeholder there) rather than being omitted —
// see the aggregator's own "no grant ever dropped from a facet" invariant.
export function matrixLayout(aLevels, sLevels, byCell, aOrder, sOrder, availW) {
  const nCols = sOrder.length;
  let maxCellN = 0;
  byCell.forEach(c => { maxCellN = Math.max(maxCellN, c.members.length); });

  // Each row's own tallest cell (by member count) — used to lay out that
  // row's actual band height in the loop below.
  const rowMaxCounts = aOrder.map(ai => {
    let m = 0;
    sOrder.forEach(si => { m = Math.max(m, (byCell.get(ai + "|" + si) || {members: []}).members.length); });
    return m;
  });

  const {mark, gap, cellCols} = pickCellGeometry(nCols, maxCellN, availW);
  const cellW = cellCols * (mark + gap) - gap + 2 * CELL_PAD;
  const hasSplit = sLevels.length > 1 || sLevels[0].label !== "";
  const hasRows = aLevels.length > 1 || aLevels[0].label !== "";

  // Column headers wrap up to MAX_LABEL_LINES, same as row labels below —
  // hdrH grows to fit whichever header needs the most lines, since every
  // column shares one header band (see grid.js's render() for how these
  // lines actually get drawn as separate tspans).
  const colLabelLines = hasSplit
    ? sOrder.map(si => wrapLabel(sLevels[si].label, cellW - CELL_PAD, MAX_LABEL_LINES))
    : [];
  const hdrH = hasSplit
    ? Math.max(HDR_H, Math.max(1, ...colLabelLines.map(ls => ls.length)) * LABEL_LINE_H + CELL_PAD)
    : 0;

  const colX = new Map(sOrder.map((si, pos) => [si, pos * (cellW + COL_GUT)]));
  const contentW = nCols * cellW + (nCols - 1) * COL_GUT;

  const cells = [];
  let y = hdrH;
  const rows = aOrder.map((ai, rowIdx) => {
    const rowMax = rowMaxCounts[rowIdx];
    const markRows = Math.max(1, Math.ceil(rowMax / cellCols));
    const markGridH = markRows * (mark + gap) - gap + 2 * CELL_PAD;
    // A wrapped row label (up to MAX_LABEL_LINES lines) can need more
    // vertical room than the mark grid itself does — a small cell (few
    // members) paired with a long level name is the common case — so the
    // row grows to fit whichever is taller, rather than letting the label
    // overflow into the next row.
    const labelLines = hasRows ? wrapLabel(aLevels[ai].label, LABEL_MAX_W, MAX_LABEL_LINES) : [];
    const bandH = hasRows ? Math.max(markGridH, labelLines.length * LABEL_LINE_H + CELL_PAD) : markGridH;
    const row = {ai, y, bandH, total: 0, labelLines};
    sOrder.forEach(si => {
      const src = byCell.get(ai + "|" + si);
      const members = src ? src.members : [];
      row.total += members.length;
      cells.push({
        ai, si, members, x: colX.get(si), y, w: cellW, h: bandH,
        markX0: colX.get(si) + CELL_PAD, markY0: y + CELL_PAD, cellCols,
      });
    });
    y += bandH + ROW_GUT;
    return row;
  });
  return {cells, rows, colX, colLabelLines, mark, gap, cellCols, cellW, contentW, hdrH, totalH: y - ROW_GUT};
}

export function computeMarkPositions(cells, mark, gap, n) {
  const pos = new Array(n);
  cells.forEach(c => {
    c.members.forEach((i, i0) => {
      const lc = i0 % c.cellCols, lr = Math.floor(i0 / c.cellCols);
      pos[i] = {x: c.markX0 + lc * (mark + gap), y: c.markY0 + lr * (mark + gap), cell: c};
    });
  });
  return pos;
}

export function reduceMotion() { return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
