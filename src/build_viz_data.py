"""
build_viz_data.py — M4 of docs/TOPIC_WORK_FORWARD_PLAN.md.

Emit the JSON the EnricoVis HTML apps fetch() at load, so the apps stop inlining
a ~1 MB `const DATA` blob and render the real SPECTER2 + curated-keyword-classifier
output instead of the TF-IDF/t-SNE preview.

**Canonical topic source is now the keyword classifier (Phase 4b of the
topic-model redo), not BERTopic directly.** `outputs/topic_labels.json` is no
longer BERTopic's own seed file — it's now `src.classify_by_keywords
--write-topic-labels`'s conversion of the curated `outputs/topic_keywords.json`
taxonomy (31 leaves / 8 parents) into this file's schema, so the code below
that reads `labels["topics"]`/`labels["parents"]` is unchanged; only what
populates that file changed. BERTopic's own assignment is kept as an explicit
`bertopicDom`/`bertopicNoise` COMPARISON pair per point — never dropped, since
`topic_assignments.parquet` stays byte-untouched and is still worth showing
against the new labels.

Reads (all produced upstream, local-only):
  data/processed/specter2_umap_2d.npy   2-D UMAP of the SPECTER2 embeddings
  data/processed/specter2_ids.txt       parallel doc_id list (grant_id / orphan-<id>)
  data/processed/grants.parquet         grant metadata
  data/processed/topic_keyword_assignments.parquet   doc_id -> kw_leaf_id / conf_tier /
                                         margin_rel / n_terms_matched / unassigned_reason
                                         (CANONICAL — src.classify_by_keywords)
  data/processed/topic_assignments.parquet   doc_id -> topic_id / is_noise (BERTopic,
                                         kept as a comparison column, never canonical)
  outputs/topic_labels.json             31 curated leaf labels + top_terms + parents
                                         (converted from outputs/topic_keywords.json)

Writes docs/EnricoVis/data/:
  grants_umap.json   {meta, colors, order, points:[{id,title,agency,agencyLabel,
                      amount,year,titleOnly,modelTitleOnly,x,y,projection,
                      t[31],dom,isNoise,bertopicDom,bertopicNoise,conf,confTier,
                      nTerms,matchedTerms,unassignedReason,assignmentSource,
                      secondaryLeaf,secondaryParent,secondaryMargin,hasSecondaryTheme}]}
                      secondaryLeaf/secondaryParent/secondaryMargin surface the
                      classifier's own already-computed runner-up leaf (never
                      exposed before); hasSecondaryTheme flags when that runner-up
                      is genuinely close (margin < 0.15, verified against real
                      grants — see the computation site) rather than a distant
                      also-ran, so the frontend can show an "also relevant to"
                      hint for the ~8.9% of grants that genuinely sit between
                      two parents (e.g. HCI-flavored grants).
                      `titleOnly` = data availability (NEU has no abstract on
                      record). `modelTitleOnly` = modeling eligibility (the
                      topic-model fit saw no abstract text) — differs from
                      `titleOnly` only for grants tagged with a
                      src.clean_text.LOW_TRUST_ABSTRACT_SOURCES value. Most
                      consumers (coverage charts, missingness, the PI's
                      EnricoVis "title only" badge) want `titleOnly`; anything
                      asking "did the model actually see text" wants
                      `modelTitleOnly`.
  topics.json        [{id,name,terms,parent,share,max,conf_mean}] for the 31 leaves
                      + a noise entry
  hier_topics.json   {parents:[{id,label,topic_ids}]} (parent grouping for the hierarchy app)

The point schema matches the apps' existing `const DATA` shape (a one-hot `t` +
dominant `dom`), so the canvas/highlight code is unchanged — only the data
source flips from inline to fetch, and `t`'s length now matches the curated
leaf count (31) rather than BERTopic's (32).

Run (after build_specter2_embeddings + a 2-D UMAP + src.classify_by_keywords):
    python -m src.build_viz_data
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.viz_constants import COLORS, ORDER
    from src.clean_text import usable_abstract
except ImportError:  # run from within src/
    from viz_constants import COLORS, ORDER
    from clean_text import usable_abstract

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
OUTPUTS = REPO_ROOT / "outputs"
VIZ_DIR = REPO_ROOT / "docs" / "EnricoVis" / "data"

# See the secondary-theme comment at its use site below for why this value.
SECONDARY_THEME_MARGIN_THRESHOLD = 0.15


def agency_bucket(name: str) -> str:
    n = str(name or "").lower()
    if "subaward" in n and "health" in n:
        return "NIH-SUB"
    if "national science foundation" in n or n.strip() == "nsf":
        return "NSF"
    if "national institutes of health" in n or "nih" in n:
        return "NIH"
    if "naval" in n or "navy" in n or "office of naval research" in n:
        return "Navy"
    if "nasa" in n or "aeronautics and space" in n:
        return "NASA"
    if "army" in n:
        return "Army"
    if "energy" in n and "department" in n:
        return "DOE"
    if "air force" in n:
        return "AFRO"
    return "Other"


def build() -> dict:
    umap = np.load(PROC / "specter2_umap_2d.npy")
    ids = (PROC / "specter2_ids.txt").read_text().splitlines()
    id2xy = {sid: (float(umap[i, 0]), float(umap[i, 1])) for i, sid in enumerate(ids)}

    grants = pd.read_parquet(PROC / "grants.parquet")
    grants["grant_id"] = grants["grant_id"].astype(str)

    # CANONICAL topic source: the curated keyword classifier.
    kw = pd.read_parquet(PROC / "topic_keyword_assignments.parquet")
    kw["doc_id"] = kw["doc_id"].astype(str)
    kw_by_id = {row.doc_id: row for row in kw.itertuples(index=False)}

    # BERTopic's own assignment — kept as a comparison column only.
    # topic_assignments.parquet stays byte-untouched; not every environment
    # will have it (it's gitignored, local-only), so degrade to None rather
    # than fail if it's absent.
    bertopic_path = PROC / "topic_assignments.parquet"
    bertopic_by_id: dict[str, tuple[int, bool]] = {}
    if bertopic_path.exists():
        ta = pd.read_parquet(bertopic_path)
        ta["doc_id"] = ta["doc_id"].astype(str)
        bertopic_by_id = {did: (int(tid), bool(noise))
                           for did, tid, noise in zip(ta["doc_id"], ta["topic_id"], ta["is_noise"])}

    labels = json.load(open(OUTPUTS / "topic_labels.json", encoding="utf-8"))
    topics_meta = labels["topics"]
    n_topics = labels["_meta"]["n_topics"]  # 31 (excludes the "-1" Unassigned entry)

    # The one-hot `t` vector below indexes t[tid] for tid in range(n_topics) —
    # this only holds if the curated leaf-id space is dense (kw_curation.py's
    # own gate already guarantees this for outputs/topic_keywords.json, but
    # assert it again here since this script consumes topic_labels.json
    # independently and shouldn't silently trust an intermediate file).
    real_topic_ids = sorted(int(k) for k in topics_meta if k != "-1")
    if real_topic_ids != list(range(n_topics)):
        raise ValueError(
            f"outputs/topic_labels.json's topic ids are not a dense range(0,{n_topics}) "
            f"— got {real_topic_ids[:10]}{'...' if len(real_topic_ids) > 10 else ''}. "
            "Re-run `python -m src.classify_by_keywords --write-topic-labels` against "
            "a curated taxonomy that passes `kw_curation.py --check`."
        )

    title_col = "title_from_abstract" if "title_from_abstract" in grants.columns else "grantname"
    points = []
    missing_kw = 0
    for r in grants.itertuples(index=False):
        gid = r.grant_id
        if gid not in id2xy:
            continue  # grant not encoded (no title/abstract) — skip
        kw_row = kw_by_id.get(gid)
        secondary_leaf = secondary_parent = secondary_margin = None
        has_secondary_theme = False
        if kw_row is None:
            missing_kw += 1
            tid, conf, conf_tier, n_terms, unassigned_reason = -1, 0.0, "none", 0, "no_usable_text"
            assignment_source = "unassigned"
        else:
            kw_tid = int(kw_row.kw_leaf_id)  # the keyword classifier's OWN pick — used below
            # only for the secondary-theme computation, which is a property of
            # its own scoring, independent of any later LLM adjudication.
            conf, conf_tier, n_terms = float(kw_row.margin_rel), kw_row.conf_tier, int(kw_row.n_terms_matched)
            # `pd.DataFrame(list_of_dicts)` (in classify_by_keywords.py's
            # score_corpus) silently coerces a real Python `None` among
            # otherwise-string values in this column to float `NaN` on
            # read-back (confirmed pandas behavior — see the same issue
            # fixed in tests/test_classify_by_keywords.py) — passing that nan
            # straight into this dict makes `json.dump()` write the literal,
            # SPEC-INVALID token `NaN` (not `null`) for every assigned grant.
            # Not previously caught because nothing browser-side fetches this
            # file directly (see standing "no browser" limitation) — Python's
            # own json module reads its own NaN output back permissively, so
            # this stayed invisible until something spec-compliant (a real
            # browser's JSON.parse, `jq`, etc.) ever touched the file.
            unassigned_reason = None if pd.isna(kw_row.unassigned_reason) else kw_row.unassigned_reason

            # `final_leaf_id`/`final_source` exist only after
            # `python -m src.adjudicate_low_confidence --merge` has been run
            # at least once (see that module) — degrade gracefully to the
            # keyword classifier's own pick when they're absent, so this
            # script works identically whether or not adjudication has ever
            # happened. When present, the LLM's resolution (or a low-
            # confidence keyword pick kept visible-but-flagged) is what the
            # dashboard should actually show as the topic — not a redefinition
            # of kw_leaf_id/conf/confTier (which keep describing the keyword
            # classifier's own BM25F result unchanged), but a NEW field
            # (assignmentSource) plus using the resolved leaf for dom/t/isNoise.
            has_final = hasattr(kw_row, "final_leaf_id") and pd.notna(kw_row.final_leaf_id)
            if has_final:
                tid = int(kw_row.final_leaf_id)
                assignment_source = kw_row.final_source
            else:
                tid = kw_tid
                assignment_source = (
                    "unassigned" if kw_tid == -1
                    else "keyword_classifier" if conf_tier in ("high", "medium")
                    else "keyword_classifier_low_confidence"
                )

            # Secondary-theme signal: the classifier already computes a
            # runner-up leaf/score per doc (kw_leaf2_id/margin_rel) but never
            # exposed it before — surfaces the genuinely-close, sits-between-
            # PARENTS population (interdisciplinary grants like HCI) without
            # any new scoring. hasSecondaryTheme is deliberately scoped to
            # cross-parent runner-ups only (not same-parent-different-leaf,
            # which is "which flavor of X" ambiguity, not the interdisciplinary
            # case this was built for) — 0.15 is not an arbitrary pick:
            # verified against the real corpus that this threshold isolates
            # 238/2675 (8.9%) assigned grants whose runner-up leaf sits in a
            # DIFFERENT parent from the winner — a real, sizeable population.
            if kw_tid >= 0 and kw_row.kw_leaf2_id is not None and int(kw_row.kw_leaf2_id) != kw_tid:
                secondary_leaf = int(kw_row.kw_leaf2_id)
                secondary_parent = topics_meta.get(str(secondary_leaf), {}).get("parent")
                secondary_margin = round(float(kw_row.margin_rel), 4)
                primary_parent = topics_meta.get(str(kw_tid), {}).get("parent")
                has_secondary_theme = (
                    secondary_margin < SECONDARY_THEME_MARGIN_THRESHOLD
                    and secondary_parent != primary_parent
                )
        bt_tid, bt_noise = bertopic_by_id.get(gid, (None, None))
        title = getattr(r, title_col, "") or r.grantname
        t = [0.0] * n_topics
        if 0 <= tid < n_topics:
            t[tid] = 1.0                      # one-hot: hard keyword-classifier assignment
        x, y = id2xy[gid]
        points.append({
            "id": gid,
            "title": str(title)[:300],
            "agency": agency_bucket(r.agencyname),
            "agencyLabel": str(r.agencyname or "Unknown"),
            "amount": float(r.totaldollars or 0),
            "year": int(r.startdateyear) if pd.notna(r.startdateyear) else None,
            # DATA availability (does NEU have abstract text on record) — what
            # every existing consumer (missingness table, coverage-by-year/
            # agency charts, topic_flow.html, the PI's read-only EnricoVis
            # apps' "title only" badge) means by "title only". Do NOT redefine
            # this to modeling eligibility — see modelTitleOnly below for that.
            "titleOnly": bool(str(r.abstract or "") == ""),
            # MODELING eligibility (did the topic-model fit actually see
            # abstract text) — differs from titleOnly only for grants tagged
            # with a src.clean_text.LOW_TRUST_ABSTRACT_SOURCES value (e.g.
            # nih_reporter_parent: real text is on record, but excluded from
            # the fit). Use this, not titleOnly, for anything that means
            # "did the model see real text for this doc" (e.g. a per-topic
            # abstract-vs-title-only confidence breakdown).
            "modelTitleOnly": bool(usable_abstract(r.abstract, getattr(r, "abstract_source", "")) == ""),
            "x": round(x, 3),
            "y": round(y, 3),
            "projection": "specter2-umap",
            "t": t,
            "dom": tid,               # -1 for the classifier's own Unassigned — CANONICAL
            "isNoise": tid == -1,
            # BERTopic's assignment, kept as a comparison column only — never
            # read by anything that means "the current topic label" (that's
            # dom/isNoise above). None when topic_assignments.parquet isn't
            # available locally (it's gitignored).
            "bertopicDom": bt_tid,
            "bertopicNoise": bt_noise,
            "conf": round(conf, 4),
            "confTier": conf_tier,
            "nTerms": n_terms,
            # The classifier's OWN recorded matched terms for the winning leaf
            # (topic_keyword_assignments.parquet's matched_terms column) — was
            # computed all along but never shipped past the aggregate nTerms
            # count. Powers the topic-keyword "fingerprint" view (highlighting
            # which curated terms actually fired in this grant's own text,
            # from the classifier's own recorded matches — NOT a client-side
            # re-implementation of keyword_match.py's tiers, which could
            # silently disagree with the classifier it's meant to explain).
            "matchedTerms": (list(kw_row.matched_terms) if kw_row is not None
                              and kw_row.matched_terms is not None else []),
            "unassignedReason": unassigned_reason,
            # How this grant's CURRENT topic (dom, above) was actually
            # decided — see the has_final branch above. One of
            # "keyword_classifier" / "keyword_classifier_low_confidence" /
            # "llm_adjudication" / "unassigned". Always populated (falls back
            # to a conf_tier-derived equivalent pre-adjudication) so the
            # frontend never needs its own null-handling for this field.
            # NOTE: kept in the data for anyone inspecting it directly, but
            # deliberately NOT surfaced as its own visible category anywhere
            # in what_we_can_see/ — facets.js's "src" facet folds
            # "llm_adjudication" into "keyword_classifier" for display (a
            # product decision: calling out "reviewed by an LLM" per grant
            # invited "why not all grants," not an oversight).
            "assignmentSource": assignment_source,
            # Secondary-theme signal — see the comment where these are
            # computed above. secondaryLeaf/secondaryParent/secondaryMargin
            # are always the runner-up leaf's own data when one exists (even
            # for a large margin); hasSecondaryTheme is the one flag the
            # frontend should actually branch on ("worth showing as a hint"),
            # so a page doesn't need to duplicate the threshold logic.
            "secondaryLeaf": secondary_leaf,
            "secondaryParent": secondary_parent,
            "secondaryMargin": secondary_margin,
            "hasSecondaryTheme": has_secondary_theme,
        })
    if missing_kw:
        print(f"WARNING: {missing_kw} grants had no row in topic_keyword_assignments.parquet "
              f"(stale/partial classifier run?) — treated as Unassigned.")

    # topics.json — 31 leaves (+ a noise entry the legend can grey out).
    # `share` = fraction of placed points in the topic; `max` = max one-hot weight
    # (1.0) — both fields the apps' TOPICS entries carry. `conf_mean` = mean
    # classifier margin_rel across points landing in this leaf (0.0 for -1,
    # which by definition has no positive margin).
    n_pts = max(len(points), 1)
    counts = {tid: 0 for tid in range(n_topics)}
    conf_sum = {tid: 0.0 for tid in range(n_topics)}
    for p in points:
        if 0 <= p["dom"] < n_topics:
            counts[p["dom"]] += 1
            conf_sum[p["dom"]] += p["conf"]
    topics = []
    for tid in range(n_topics):
        m = topics_meta[str(tid)]
        n_here = counts[tid]
        topics.append({"id": tid, "name": m["label"], "terms": m["top_terms"][:10],
                       "share": round(n_here / n_pts, 4), "max": 1.0,
                       "parent": m.get("parent"),
                       "conf_mean": round(conf_sum[tid] / n_here, 4) if n_here else 0.0})
    topics.append({"id": -1, "name": topics_meta["-1"]["label"], "terms": [],
                   "share": round(sum(p["isNoise"] for p in points) / n_pts, 4),
                   "max": 1.0, "parent": None, "conf_mean": 0.0})

    # ── hierarchy data for topic_hierarchy.html ──────────────────────────────
    # Integer parent indices 0..7 (+ -1 for the "Unassigned" group: t11 artifact
    # and the noise cluster). The app groups leaves->parents by the `parent`
    # field, so non-contiguous topic->parent mappings are fine.
    parents = labels.get("parents", {})
    pid_order = list(parents.keys())                       # P0..P7 (insertion order)
    topic2parent = {tid: i for i, pid in enumerate(pid_order)
                    for tid in parents[pid]["topic_ids"]}
    hier_parents = ([{"id": i, "name": parents[pid]["label"]} for i, pid in enumerate(pid_order)]
                    + [{"id": -1, "name": "Unassigned"}])
    hier_leaves = ([{"id": tid, "name": topics_meta[str(tid)]["label"],
                     "parent": topic2parent.get(tid, -1)} for tid in range(n_topics)]
                   + [{"id": -1, "name": "Unassigned", "parent": -1}])
    hier_points = [{"id": p["id"], "x": p["x"], "y": p["y"], "title": p["title"],
                    "agency": p["agency"], "agencyLabel": p["agencyLabel"],
                    "amount": p["amount"], "year": p["year"], "titleOnly": p["titleOnly"],
                    "parent": topic2parent.get(p["dom"], -1) if p["dom"] >= 0 else -1,
                    "leaf": p["dom"]}
                   for p in points]
    grants_hier = {"points": hier_points, "parents": hier_parents, "leaves": hier_leaves}

    grants_umap = {
        "meta": {
            # Coordinates are still SPECTER2 + UMAP; HDBSCAN no longer drives
            # the topic LABEL (dom) — that's the curated keyword classifier
            # (BM25F) now. Stating only one half would misrepresent the method.
            "projection": "SPECTER2 + UMAP (layout) + curated keyword classifier (labels)",
            "n_points": len(points),
            "n_topics": n_topics,
            "n_title_only": int(sum(p["titleOnly"] for p in points)),
            "n_noise": int(sum(p["isNoise"] for p in points)),
        },
        "colors": COLORS, "order": ORDER, "points": points,
    }
    return {"grants_umap": grants_umap, "topics": topics, "grants_hier": grants_hier}


def main() -> None:
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    out = build()
    for name, obj in [("grants_umap", out["grants_umap"]), ("topics", out["topics"]),
                      ("grants_hier", out["grants_hier"])]:
        p = VIZ_DIR / f"{name}.json"
        # allow_nan=False: fail loudly (ValueError) on any stray float NaN
        # rather than silently writing the invalid `NaN` token — Python's
        # own json module reads its own NaN output back permissively, which
        # is exactly how the `unassigned_reason` bug above stayed invisible
        # until something spec-compliant (a real browser) touched the file.
        p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
        print(f"wrote {p.relative_to(REPO_ROOT)}  ({p.stat().st_size/1024:.0f} KB)")
    m = out["grants_umap"]["meta"]
    print(f"  {m['n_points']} points | {m['n_title_only']} title-only | {m['n_noise']} noise")


if __name__ == "__main__":
    main()
