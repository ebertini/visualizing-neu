"""
build_viz_data.py — M4 of docs/TOPIC_WORK_FORWARD_PLAN.md.

Emit the JSON the EnricoVis HTML apps fetch() at load, so the apps stop inlining
a ~1 MB `const DATA` blob and render the real SPECTER2 + BERTopic output instead
of the TF-IDF/t-SNE preview.

Reads (all produced upstream, local-only):
  data/processed/specter2_umap_2d.npy   2-D UMAP of the SPECTER2 embeddings
  data/processed/specter2_ids.txt       parallel doc_id list (grant_id / orphan-<id>)
  data/processed/grants.parquet         grant metadata
  data/processed/topic_assignments.parquet   doc_id -> topic_id / is_noise / is_extra
  outputs/topic_labels.json             25 curated labels + top_terms + parents

Writes docs/EnricoVis/data/:
  grants_umap.json   {meta, colors, order, points:[{id,title,agency,agencyLabel,
                      amount,year,titleOnly,modelTitleOnly,x,y,projection,
                      t[25],dom,isNoise}]}
                      `titleOnly` = data availability (NEU has no abstract on
                      record). `modelTitleOnly` = modeling eligibility (the
                      topic-model fit saw no abstract text) — differs from
                      `titleOnly` only for grants tagged with a
                      src.clean_text.LOW_TRUST_ABSTRACT_SOURCES value. Most
                      consumers (coverage charts, missingness, the PI's
                      EnricoVis "title only" badge) want `titleOnly`; anything
                      asking "did the model actually see text" wants
                      `modelTitleOnly`.
  topics.json        [{id,name,terms,parent}] for the 25 topics + a noise entry
  hier_topics.json   {parents:[{id,label,topic_ids}]} (parent grouping for the hierarchy app)

The point schema matches the apps' existing `const DATA` shape (a 25-long one-hot
`t` + dominant `dom`), so the canvas/highlight code is unchanged — only the data
source flips from inline to fetch.

Run (after build_specter2_embeddings + topics_bertopic + a 2-D UMAP):
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
    ta = pd.read_parquet(PROC / "topic_assignments.parquet")
    ta["doc_id"] = ta["doc_id"].astype(str)
    topic_of = dict(zip(ta["doc_id"], ta["topic_id"]))

    labels = json.load(open(OUTPUTS / "topic_labels.json", encoding="utf-8"))
    topics_meta = labels["topics"]
    n_topics = labels["_meta"]["n_topics"]  # 25 (excludes noise)

    title_col = "title_from_abstract" if "title_from_abstract" in grants.columns else "grantname"
    points = []
    for r in grants.itertuples(index=False):
        gid = r.grant_id
        if gid not in id2xy:
            continue  # grant not encoded (no title/abstract) — skip
        tid = int(topic_of.get(gid, -1))
        title = getattr(r, title_col, "") or r.grantname
        t = [0.0] * n_topics
        if 0 <= tid < n_topics:
            t[tid] = 1.0                      # one-hot: hard BERTopic assignment
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
            "dom": tid,               # -1 for noise / unassigned
            "isNoise": tid == -1,
        })

    # topics.json — 25 topics (+ a noise entry the legend can grey out).
    # `share` = fraction of placed points in the topic; `max` = max one-hot weight
    # (1.0) — both fields the apps' TOPICS entries carry.
    n_pts = max(len(points), 1)
    counts = {tid: 0 for tid in range(n_topics)}
    for p in points:
        if 0 <= p["dom"] < n_topics:
            counts[p["dom"]] += 1
    topics = []
    for tid in range(n_topics):
        m = topics_meta[str(tid)]
        topics.append({"id": tid, "name": m["label"], "terms": m["top_terms"][:10],
                       "share": round(counts[tid] / n_pts, 4), "max": 1.0,
                       "parent": m.get("parent")})
    topics.append({"id": -1, "name": topics_meta["-1"]["label"], "terms": [],
                   "share": round(sum(p["isNoise"] for p in points) / n_pts, 4),
                   "max": 1.0, "parent": None})

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
            "projection": "SPECTER2 + UMAP + HDBSCAN",
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
        p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {p.relative_to(REPO_ROOT)}  ({p.stat().st_size/1024:.0f} KB)")
    m = out["grants_umap"]["meta"]
    print(f"  {m['n_points']} points | {m['n_title_only']} title-only | {m['n_noise']} noise")


if __name__ == "__main__":
    main()
