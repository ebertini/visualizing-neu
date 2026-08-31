// detail.js — per-mark tooltip/detail builders for the two grids, passed
// into grid.js's createGrid() as buildTooltip/buildDetail callbacks. Split
// out of what_we_can_see.html's single inline script; behavior is
// unchanged, only the module boundary is new.
import { FACETS, FACETS_PI, VIZ_META } from "./data.js";

const E = window.ENRICO;

export function grantTooltip(i) {
  const title = FACETS.titles[i];
  const agency = VIZ_META.agencies[FACETS.cols.ag[i]];
  const yr = FACETS.cols.yr[i];
  const college = FACETS.levels.col[FACETS.cols.col[i]];
  const hasAbs = FACETS.cols.ab[i] === 1;
  const parent = VIZ_META.parents.find(p => p.id === FACETS.cols.tp[i]);
  // PI feedback: "grant number is inconsequential to audience" (dropped, was
  // "Grant {gid} · amount") — "add PI information in grant tooltip" (added
  // below, in its place). piNames[i] is "" when no PI matched this grant.
  const piName = FACETS.piNames && FACETS.piNames[i];
  // PI feedback: "for each grant how many different colleges does it
  // involve?" — only shown when it's actually more than one, so the common
  // single-college case doesn't grow the tooltip for no reason.
  const nColleges = FACETS.nColleges ? FACETS.nColleges[i] : 0;
  const collegesNote = nColleges > 1 ? ` (${nColleges} colleges involved)` : "";
  // Team size — only shown when there's an actual additional collaborator
  // on record (nTeam > 1), same "don't clutter the common case" rule as
  // collegesNote above. Counts distinct PEOPLE, not is_copi-flagged rows —
  // see facets.js's "team" facet def for why that distinction matters.
  const nTeam = FACETS.nTeam ? FACETS.nTeam[i] : 1;
  const teamNote = nTeam > 1 ? ` | team of ${nTeam}` : "";
  // What the grant actually IS leads the tooltip (PI feedback: "grant what
  // is it should show when you hover") — the id/amount/agency/etc. that
  // used to lead it are still there, just demoted to supporting .meta lines.
  const secondary = FACETS.hasSecondaryTheme[i]
    ? `<div class="meta">Also relevant to: ${E.esc(FACETS.secondaryParentLabel[i])} / ` +
      `${E.esc(FACETS.secondaryLeafLabel[i])} (${(FACETS.secondaryMargin[i] * 100).toFixed(0)}% margin)</div>`
    : "";
  // How this grant's topic was actually decided (build_viz_data.py's
  // assignmentSource) — the ONLY case still called out here is genuine
  // Unassigned (a real content gap, worth disclosing). "keyword_classifier_
  // low_confidence" and "llm_adjudication" are both deliberately NOT called
  // out (product decision, not an oversight: either one read as an internal
  // QA/confidence signal that invited more scrutiny than it was worth
  // surfacing per-grant) — folded into the same "no note" treatment as a
  // confident keyword match. The underlying data is unaffected; this is a
  // display-only choice.
  const srcIdx = FACETS.cols.src ? FACETS.cols.src[i] : 0;
  const srcName = FACETS.levels.src ? FACETS.levels.src[srcIdx] : "keyword_classifier";
  const srcNote = srcName === "unassigned"
    ? `<div class="meta">⚠ Unassigned: no confident topic</div>`
    : "";
  // PI-link provenance — only disclosed when the PI came from an external
  // backfill, not the original dataset (same "only flag genuine gaps, not
  // the common case" rule srcNote above already follows). FACETS.cols.piSrc
  // is a levels-enum column ("none"/"internal"/"backfill") built by
  // load_augmented_faculty_grants(); see that function's own docstring for
  // the NIH RePORTER / NSF Award Search merge this represents.
  const piSrcIdx = FACETS.cols.piSrc ? FACETS.cols.piSrc[i] : 1;
  const piSrcName = FACETS.levels.piSrc ? FACETS.levels.piSrc[piSrcIdx] : "internal";
  const piSrcNote = piSrcName === "backfill"
    ? `<div class="meta">PI recovered from NIH RePORTER / NSF Award Search records, not the original dataset</div>`
    : "";
  return `<div class="t">${E.esc(title || "(no title on record)")}</div>` +
    `<div class="meta">${E.esc(piName || "PI not on record")} | ${E.fmtAmt(FACETS.cols.amt_raw[i])}</div>` +
    `<div class="meta">${E.esc(agency.key)} | ${yr === -1 ? "year unknown" : yr}</div>` +
    `<div class="meta">${E.esc(college)}${collegesNote}${teamNote}</div>` +
    `<div class="meta">${hasAbs ? "Has abstract" : "Title only"} | ${E.esc(parent ? parent.name : "Unassigned")}</div>` +
    srcNote +
    piSrcNote +
    secondary;
}

// Honest three-way "no abstract" message rather than one vague fallback: a
// title-only grant (no abstract ever existed for it, per FACETS.cols.ab)
// reads differently from "this build just doesn't have the text" (the
// grants.parquet-not-built degraded path, FACETS.provenance.abstract_text
// === "derived") — collapsing those into one message would misrepresent
// which case actually applies.
// Topic-keyword "fingerprint": highlights, within the grant's OWN abstract
// text, the curated terms the classifier itself recorded as having matched
// (FACETS.matchedTerms[i] — from topic_keyword_assignments.parquet's own
// matched_terms column, not a client-side re-score). Deliberately a plain
// case-insensitive SUBSTRING highlight, not a reimplementation of
// keyword_match.py's exact/collapsed/stem tiers — a term matched here via
// its stem (e.g. "neuron" matching "neurons") still highlights via substring
// overlap in the common case, but this is a display approximation of the
// classifier's decision, not a faithful second scorer; if it ever visibly
// disagrees with the classifier, trust the classifier's matched-term LIST,
// not this highlighting.
function highlightMatches(text, terms) {
  const escaped = E.esc(text);
  if (!terms || !terms.length) return escaped;
  // ONE combined regex, ONE replace pass — not one .replace() call per term.
  // A per-term sequential loop (tried first, caught by a standalone test
  // before this ever reached a real page) re-scans the growing HTML output
  // on each iteration, so a later, SHORTER term (e.g. "learning") matches
  // again INSIDE a mark a longer term (e.g. "machine learning") already
  // produced, nesting <mark><mark>...</mark></mark> — invalid and visually
  // wrong. A single alternation, longest-term-first (so "machine learning"
  // still wins the same overlapping span "learning" would also match),
  // consumes each character at most once, which a single pass over the
  // ORIGINAL text structurally guarantees.
  const sorted = terms.slice().sort((a, b) => b.length - a.length);
  const escapedTerms = sorted.map(t => E.esc(t).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const combined = new RegExp(escapedTerms.join("|"), "gi");
  return escaped.replace(combined, m => `<mark>${m}</mark>`);
}

// Co-PI names, below the tooltip's own "| team of X" line (grantTooltip's
// output is prepended to this in the Selected-grant overlay — see grid.js's
// renderSelectedCard: `buildTooltip(selected) + buildDetail(selected)`).
// Gated on nTeam > 1, same "don't clutter the common case" rule as teamNote
// above — is_pi/is_copi are mutually exclusive per row, so "everyone but the
// PI" IS "everyone flagged co-PI" (see load_copi_names_per_grant's own
// docstring); a solo grant (nTeam === 1) never reaches this line, so a
// solo-labeled-"co-PI" record never shows a self-referential name here.
// Deliberately only on the overlay's detail body, not the shared hover
// tooltip — a variable-length name list doesn't belong on a small per-mark
// tooltip.
function copiNote(i) {
  const nTeam = FACETS.nTeam ? FACETS.nTeam[i] : 1;
  const coPis = FACETS.coPiNames ? FACETS.coPiNames[i] : [];
  if (nTeam <= 1 || !coPis || !coPis.length) return "";
  return `<div class="meta">Co-PIs: ${coPis.map(n => E.esc(n)).join(", ")}</div>`;
}

// Other investigators the NIH RePORTER / NSF Award Search backfill records
// on this award who never resolved to any NEU faculty record — deliberately
// disclosed HERE, on the specific grant they're mentioned on, and NEVER
// added to the Every PI roster: most of this population project-wide is
// genuinely external collaborators at other institutions, not missing
// Northeastern people (see load_unmatched_investigators_per_grant's own
// docstring for why). Framed as "per official award records," not as a
// claim about anyone's institution.
function unmatchedNote(i) {
  const names = FACETS.unmatchedInvestigators ? FACETS.unmatchedInvestigators[i] : [];
  if (!names || !names.length) return "";
  return `<div class="meta">Co-PIs per official award records, not matched to an ` +
    `NEU faculty record: ${names.map(n => E.esc(n)).join(", ")}</div>`;
}

export function grantDetail(i) {
  const note = copiNote(i) + unmatchedNote(i);
  const text = FACETS.abstracts[i];
  if (text) {
    const terms = FACETS.matchedTerms ? FACETS.matchedTerms[i] : [];
    const fingerprint = (terms && terms.length)
      ? `<div class="meta fingerprint-note">Highlighted: the curated topic terms the classifier ` +
        `found in this text (${terms.length} of them). <span class="fingerprint-terms">` +
        `${terms.map(t => E.esc(t)).join(", ")}</span></div>`
      : "";
    return `${note}<div class="abstract">${highlightMatches(text, terms)}</div>${fingerprint}`;
  }
  const reason = FACETS.cols.ab[i] === 0
    ? "this grant is title-only in the source data"
    : FACETS.provenance.abstract_text === "derived"
      ? "abstract text wasn't available when this page was built"
      : "no abstract text on record for this grant";
  return `${note}<div class="abstract abstract-empty">No abstract available: ${reason}.</div>`;
}

export function piTooltip(i) {
  const name = FACETS_PI.names[i];
  const college = FACETS_PI.levels.col[FACETS_PI.cols.col[i]];
  const dept = FACETS_PI.levels.dept[FACETS_PI.cols.dept[i]];
  const rank = FACETS_PI.levels.rank[FACETS_PI.cols.rank[i]];
  const hasGrants = FACETS_PI.cols.hasgrants[i] === 1;
  return `<div class="t">${E.esc(name || "(no name on record)")}</div>` +
    `<div class="meta">${E.esc(college)}</div>` +
    `<div class="meta">${E.esc(dept)} | ${E.esc(rank)}</div>` +
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
