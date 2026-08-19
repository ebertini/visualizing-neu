// data.js — fetches the six datasets this page needs, once, at load.
//
// Extracted from what it used to be: six `const NAME = {...};` blobs sitting
// inline in what_we_can_see.html (one of them, FACETS, alone was 5.3 MB on a
// single line). This page is served over http(s) only — never opened as a
// local file — so fetch() from an ES module is safe to rely on; see
// docs/TOPIC_MODEL_REFIT_CHECKLIST.md for why and how that's verified.
//
// Top-level await lets every importer keep using these datasets as plain
// module-scope bindings, exactly as when they were inline consts — no
// function anywhere had to become async because of this move.
//
// DATASETS is also the single declared list of what this page fetches;
// scripts/_check_topicviz.py regexes it out of this file to confirm every
// name here exists in data/ and parses, and that build_viz_aggregates.py
// emits nothing this page silently fails to read.
export const DATASETS = {
  VIZ_META: "data/viz_meta.json",
  COVERAGE: "data/coverage.json",
  FACETS: "data/facets.json",
  FACETS_PI: "data/facets_pi.json",
  MISSINGNESS: "data/missingness.json",
  FUNNEL: "data/funnel.json",
};

async function loadAll() {
  const entries = Object.entries(DATASETS);
  const responses = await Promise.all(entries.map(([, path]) => fetch(path)));
  const bad = responses.find(r => !r.ok);
  if (bad) throw new Error(`${bad.status} ${bad.statusText} loading ${bad.url}`);
  const bodies = await Promise.all(responses.map(r => r.json()));
  const out = {};
  entries.forEach(([name], i) => { out[name] = bodies[i]; });
  return out;
}

// A missing/unreachable dataset used to be impossible (the data was baked
// into the page itself); now it's the one new failure mode this move
// introduces. Fail visibly, in plain language, rather than leaving a blank
// or half-built page — and rather than naming any file/column here (house
// convention: audience-facing copy stays plain-language only).
let loaded;
try {
  loaded = await loadAll();
} catch (err) {
  document.body.innerHTML =
    '<div style="max-width:640px;margin:96px auto;padding:0 24px;' +
    'font-family:system-ui,-apple-system,sans-serif;color:#333;line-height:1.5">' +
    "<h1 style=\"font-size:16px\">This page couldn't load its data.</h1>" +
    "<p>It needs to be served from a web address, not opened directly as a file on " +
    "disk, and its data needs to be sitting alongside it. Try the published version " +
    "of this page, or serve this folder locally and reload.</p></div>";
  throw err;
}

export const VIZ_META = loaded.VIZ_META;
export const COVERAGE = loaded.COVERAGE;
export const FACETS = loaded.FACETS;
export const FACETS_PI = loaded.FACETS_PI;
export const MISSINGNESS = loaded.MISSINGNESS;
export const FUNNEL = loaded.FUNNEL;
