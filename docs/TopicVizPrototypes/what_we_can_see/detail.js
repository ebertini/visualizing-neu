// detail.js — per-mark tooltip/detail builders for the two grids, passed
// into grid.js's createGrid() as buildTooltip/buildDetail callbacks. Split
// out of what_we_can_see.html's single inline script; behavior is
// unchanged, only the module boundary is new.
import { FACETS, FACETS_PI, VIZ_META } from "./data.js";

const E = window.ENRICO;

export function grantTooltip(i) {
  const gid = FACETS.ids[i];
  const title = FACETS.titles[i];
  const agency = VIZ_META.agencies[FACETS.cols.ag[i]];
  const yr = FACETS.cols.yr[i];
  const college = FACETS.levels.col[FACETS.cols.col[i]];
  const hasAbs = FACETS.cols.ab[i] === 1;
  const parent = VIZ_META.parents.find(p => p.id === FACETS.cols.tp[i]);
  // What the grant actually IS leads the tooltip (PI feedback: "grant what
  // is it should show when you hover") — the id/amount/agency/etc. that
  // used to lead it are still there, just demoted to supporting .meta lines.
  return `<div class="t">${E.esc(title || "(no title on record)")}</div>` +
    `<div class="meta">Grant ${E.esc(gid)} · ${E.fmtAmt(FACETS.cols.amt_raw[i])}</div>` +
    `<div class="meta">${E.esc(agency.key)} · ${yr === -1 ? "year unknown" : yr}</div>` +
    `<div class="meta">${E.esc(college)}</div>` +
    `<div class="meta">${hasAbs ? "Has abstract" : "Title only"} · ${E.esc(parent ? parent.name : "Unassigned")}</div>`;
}

// Honest three-way "no abstract" message rather than one vague fallback: a
// title-only grant (no abstract ever existed for it, per FACETS.cols.ab)
// reads differently from "this build just doesn't have the text" (the
// grants.parquet-not-built degraded path, FACETS.provenance.abstract_text
// === "derived") — collapsing those into one message would misrepresent
// which case actually applies.
export function grantDetail(i) {
  const text = FACETS.abstracts[i];
  if (text) return `<div class="abstract">${E.esc(text)}</div>`;
  const reason = FACETS.cols.ab[i] === 0
    ? "this grant is title-only in the source data"
    : FACETS.provenance.abstract_text === "derived"
      ? "abstract text wasn't available when this page was built"
      : "no abstract text on record for this grant";
  return `<div class="abstract abstract-empty">No abstract available — ${reason}.</div>`;
}

export function piTooltip(i) {
  const name = FACETS_PI.names[i];
  const college = FACETS_PI.levels.col[FACETS_PI.cols.col[i]];
  const dept = FACETS_PI.levels.dept[FACETS_PI.cols.dept[i]];
  const rank = FACETS_PI.levels.rank[FACETS_PI.cols.rank[i]];
  const hasGrants = FACETS_PI.cols.hasgrants[i] === 1;
  return `<div class="t">${E.esc(name || "(no name on record)")}</div>` +
    `<div class="meta">${E.esc(college)}</div>` +
    `<div class="meta">${E.esc(dept)} · ${E.esc(rank)}</div>` +
    `<div class="meta">${hasGrants ? E.fmtAmt(FACETS_PI.cols.amt_raw[i]) + " as PI" : "No grants in this corpus"}</div>`;
}

// Mirrors grantDetail's honesty above: most of the roster (1,690 of 2,247)
// genuinely has no grant in this corpus at all — that's the whole point of
// this tab existing — so that's said plainly rather than shown as an empty
// panel that reads like a loading state.
// Only the first VISIBLE titles show up front; the rest sit behind a native
// <details> disclosure (same no-JS toggle pattern as the "How this is
// computed" .drawer elsewhere on this page) — VISIBLE < 8 (the aggregator's
// own per-PI cap, see grant_titles in build_viz_aggregates.py) means most
// multi-grant PIs get a collapsed remainder rather than a long list up front.
const PI_GRANTS_VISIBLE = 5;

export function piDetail(i) {
  const titles = FACETS_PI.grant_titles[i] || [];
  if (!titles.length) {
    return `<div class="abstract abstract-empty">No grants for this person in this corpus.</div>`;
  }
  const item = t => `<li>${E.esc(t || "(no title on record)")}</li>`;
  const shown = titles.slice(0, PI_GRANTS_VISIBLE).map(item).join("");
  const rest = titles.slice(PI_GRANTS_VISIBLE);
  const more = rest.length
    ? `<details class="grantmore"><summary>Show ${rest.length} more</summary>` +
      `<ul class="grantlist">${rest.map(item).join("")}</ul></details>`
    : "";
  const bandLabel = FACETS_PI.levels.ngrants[FACETS_PI.cols.ngrants[i]];
  const note = titles.length >= 8
    ? `<div class="meta">Showing the first ${titles.length} of ${E.esc(bandLabel)} grants.</div>` : "";
  return `<div class="abstract"><ul class="grantlist">${shown}</ul>${more}${note}</div>`;
}
