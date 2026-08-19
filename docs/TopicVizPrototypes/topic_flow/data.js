// data.js — fetches the two datasets topic_flow.html needs, once, at load.
// Replaces the two `const NAME = {...};` blobs that used to be inlined
// directly in the page (see docs/TOPIC_MODEL_REFIT_CHECKLIST.md). Served
// over http(s) only — never opened as a local file.
//
// DATASETS is also the single declared list of what this page fetches;
// scripts/_check_topicviz.py regexes it out of this file.
export const DATASETS = {
  VIZ_META: "data/viz_meta.json",
  TOPIC_TIME: "data/topic_time.json",
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

let loaded;
try {
  loaded = await loadAll();
} catch (err) {
  document.body.innerHTML =
    '<div style="max-width:640px;margin:96px auto;padding:0 24px;' +
    'font-family:system-ui,-apple-system,sans-serif;color:#333;line-height:1.5">' +
    "<h1 style=\"font-size:16px\">This page couldn't load its data.</h1>" +
    "<p>It needs to be served from a web address, not opened directly as a " +
    "file on disk, and its data needs to be sitting alongside it. Try the " +
    "published version of this page, or serve this folder locally and " +
    "reload.</p></div>";
  throw err;
}

export const VIZ_META = loaded.VIZ_META;
export const TOPIC_TIME = loaded.TOPIC_TIME;
