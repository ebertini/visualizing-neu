"""
build_viz_aggregates.py — Round 1 of the topic-model visualization prototypes
(see docs/TopicVizPrototypes/`topic_flow.html` and `what_we_can_see.html`).

These prototypes are the user's own analysis work, kept separate from
docs/EnricoVis/ (a parallel visualization effort by the PI). They DO read
EnricoVis's canonical BERTopic/SPECTER2 output as an upstream input — that
model is the PI's, reused here rather than re-fit — but every derived file
this script writes goes to docs/TopicVizPrototypes/, never into EnricoVis/.

Unlike src/build_viz_data.py, this script does NOT need specter2_umap_2d.npy /
topic_assignments.parquet / outputs/topic_labels.json — those inputs are
absent locally and not regenerable without a HuggingFace SPECTER2 download.
Topic assignments and UMAP coords are effectively frozen; the real BERTopic
output already lives in the two committed files this script reads FROM:

Reads (frozen, read-only, owned by docs/EnricoVis/ — never write here):
  docs/EnricoVis/data/grants_umap.json   2,676 grant points: id/agency/amount/
                                          year/titleOnly/dom(topic)/isNoise
  docs/EnricoVis/data/topics.json        26 entries: 25 topics + noise, each
                                          with a "parent" ("P0".."P7" or null)

Reads (locally built, optional — enriches provenance if present):
  data/processed/grants.parquet          grant_id -> abstract_source
                                          ("internal"/"orphan_recovered"/"")

Writes (docs/TopicVizPrototypes/data/, committed, inlined into the
prototypes at build time — CI does not publish source data/ directories,
see docs/TOPIC_WORK_EXECUTION_REPORT.md):
  viz_meta.json     shared dimensions (agencies, parents, topics, year axis,
                     totals) + the single canonical caveats[] array
  topic_time.json   topic & parent share/dollars per year, dense 2005-2025
                     + a pre-2005 "prelude" summary (too sparse to stack)
  coverage.json     abstract coverage by agency x year, the NIH cliff, and
                     the Unassigned/artifact breakdown

Run:
    .venv/bin/python -m src.build_viz_aggregates [--check-only]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
ENRICOVIS_DATA = REPO_ROOT / "docs" / "EnricoVis" / "data"     # read-only upstream (PI's work)
OUT_DIR = REPO_ROOT / "docs" / "TopicVizPrototypes" / "data"   # writable (this script's own output)

# Guard against ever writing into the PI's frozen EnricoVis output — this
# script's OUT_DIR is a different directory already, but keep the stem
# check too as a belt-and-suspenders safety net.
FROZEN_STEMS = {"grants_umap", "topics", "grants_hier"}

# 8-parent-theme names/colors — copied verbatim from docs/EnricoVis/topic_hierarchy.html
# (PARENT_COLORS, the PI's file) and docs/TopicVizPrototypes/shared/enrico.js
# (PARENT_NAMES, this project's own copy), which must in turn stay in sync
# with this list. Do not hand-edit one without the other two.
PARENT_NAMES = [
    "Life Sciences & Biomedicine", "Physical Sciences & Engineering", "Environment, Ocean & Climate",
    "Computing & Cybersecurity", "Networks, Signals & Control", "AI, Robotics & Cognition",
    "Society, Health & Mobility", "Education & Learning",
]
PARENT_COLORS = ["#4E79A7", "#F28E2B", "#59A14F", "#B07AA1", "#76B7B2", "#EDC948", "#9C755F", "#D37295"]

# Topic 11 is a documented artifact bucket (docs/TOPIC_WORK_EXECUTION_REPORT.md):
# 28 of 62 docs are placeholder "Grant" title-only ONR/NIH-sub records. It has
# no parent theme and is folded into "Unassigned" everywhere in the hierarchy
# app — we do the same here for the parent-level series.
ARTIFACT_TOPIC_ID = 11

DENSE_FROM, DENSE_TO = 2005, 2025

CAVEATS = [
    {
        "id": "neu_status",
        "severity": "high",
        "text": (
            "The $2.18B headline is not money Northeastern raised — grants are "
            "attributed to a faculty member even if the award predates their NEU hire."
        ),
    },
    {
        "id": "nih_cliff",
        "severity": "high",
        "text": (
            "NIH abstract coverage collapses from 64% (2019) to 0% from 2021 onward. "
            "This is a data-collection artifact, not a funding decline — NIH grant "
            "counts hold steady while the evidence behind each topic label thins out."
        ),
    },
    {
        "id": "unassigned",
        "severity": "med",
        "text": (
            "808 grants (27.8% of dollars) carry no confident topic — 746 HDBSCAN "
            "noise + 62 in a flagged artifact bucket (topic 11). Shown as a grey "
            "‘Unassigned’ band, never dropped."
        ),
    },
    {
        "id": "t11_artifact",
        "severity": "med",
        "text": (
            "Topic 11 (“Mixed / low-coherence”) is a flagged artifact: 28 of its "
            "62 grants carry the placeholder title “Grant”. It has no parent theme."
        ),
    },
    {
        "id": "sparse_prelude",
        "severity": "low",
        "text": (
            "1995–2004 (118 grants total) is too sparse to stack reliably and is "
            "shown separately from the 2005–2025 series."
        ),
    },
    {
        "id": "partial_recent",
        "severity": "low",
        "text": "2025 is a partial year; 2026 has essentially no data yet.",
    },
    {
        "id": "agency_skew",
        "severity": "low",
        "text": "~88% of dollars are NSF/NIH. Internal, foundation, and industry funding are largely invisible.",
    },
]


def _guard_output_path(path: Path) -> None:
    if path.stem in FROZEN_STEMS:
        raise RuntimeError(
            f"refusing to write {path} — {path.stem} is a frozen input "
            "(the real BERTopic/SPECTER2 output); see module docstring."
        )


def _parent_index(parent_key: str | None) -> int:
    """'P0'..'P7' -> 0..7; None (incl. the artifact topic) -> -1 (Unassigned)."""
    if parent_key is None:
        return -1
    m = re.match(r"P(\d+)$", parent_key)
    return int(m.group(1)) if m else -1


def load_frozen() -> tuple[list[dict], list[dict]]:
    grants_umap = json.loads((ENRICOVIS_DATA / "grants_umap.json").read_text(encoding="utf-8"))
    topics = json.loads((ENRICOVIS_DATA / "topics.json").read_text(encoding="utf-8"))
    return grants_umap["points"], topics


def load_abstract_source(points: list[dict]) -> tuple[dict[str, str], str]:
    """Best-effort grant_id -> abstract_source ('internal'/'orphan_recovered'/'none').
    Falls back to deriving it from `titleOnly` (exactly equivalent when the
    real value is absent, since titleOnly IS `abstract == ""` at the source —
    see src/build_viz_data.py) if grants.parquet hasn't been built locally.
    """
    parquet_path = PROC / "grants.parquet"
    if parquet_path.exists():
        import pandas as pd  # local import: keep this script runnable with json alone

        g = pd.read_parquet(parquet_path, columns=["grant_id", "abstract_source"])
        g["grant_id"] = g["grant_id"].astype(str).str.strip()
        src = dict(zip(g["grant_id"], g["abstract_source"]))
        by_id = {}
        for p in points:
            v = src.get(str(p["id"]).strip(), "")
            by_id[p["id"]] = v if v else "none"
        return by_id, "parquet"
    # Degraded fallback — never silently fabricate provenance detail we don't have.
    return {p["id"]: ("none" if p["titleOnly"] else "internal") for p in points}, "derived"


def build_viz_meta(points: list[dict], topics: list[dict]) -> dict:
    from src.build_viz_data import COLORS, ORDER  # reuse verbatim, palettes can't drift

    agencies = []
    for key in ORDER:
        label = next((p["agencyLabel"] for p in points if p["agency"] == key), key)
        agencies.append({"key": key, "label": label, "color": COLORS[key]})

    parents = [
        {"id": i, "name": name, "color": PARENT_COLORS[i]}
        for i, name in enumerate(PARENT_NAMES)
    ] + [{"id": -1, "name": "Unassigned", "color": "#c7ccd3"}]

    topics_out = []
    for t in topics:
        tid = t["id"]
        topics_out.append({
            "id": tid,
            "name": t["name"],
            "parent": _parent_index(t.get("parent")),
            "terms": t.get("terms", []),
            "share": t.get("share", 0.0),
            "artifact": tid == ARTIFACT_TOPIC_ID,
            "noise": tid == -1,
        })

    years_present = sorted({p["year"] for p in points if p["year"] is not None})
    prelude_years = [y for y in years_present if y < DENSE_FROM]
    prelude_n = sum(1 for p in points if p["year"] is not None and p["year"] < DENSE_FROM)

    total_dollars = sum(p["amount"] for p in points)
    unassigned_n = sum(1 for p in points if p["dom"] == -1 or p["dom"] == ARTIFACT_TOPIC_ID)
    unassigned_dollars = sum(
        p["amount"] for p in points if p["dom"] == -1 or p["dom"] == ARTIFACT_TOPIC_ID
    )

    return {
        "frozen_inputs": {
            "projection": "SPECTER2 + UMAP + HDBSCAN",
            "n_points": len(points),
            "n_topics": 25,
        },
        "agencies": agencies,
        "parents": parents,
        "topics": topics_out,
        "years": {
            "min": years_present[0],
            "max": years_present[-1],
            "dense_from": DENSE_FROM,
            "dense_to": DENSE_TO,
            "prelude_years": prelude_years,
            "prelude_n": prelude_n,
            "complete_through": 2024,
        },
        "totals": {
            "n_grants": len(points),
            "dollars": total_dollars,
            "unassigned_n": unassigned_n,
            "unassigned_dollars": unassigned_dollars,
            "unassigned_share": round(unassigned_dollars / total_dollars, 4),
        },
        "caveats": CAVEATS,
    }


def build_topic_time(points: list[dict], topics: list[dict]) -> dict:
    parent_of_topic = {t["id"]: _parent_index(t.get("parent")) for t in topics}
    years = list(range(DENSE_FROM, DENSE_TO + 1))
    y_index = {y: i for i, y in enumerate(years)}

    def blank():
        return {"n": [0] * len(years), "d": [0.0] * len(years)}

    topic_series = {str(t["id"]): blank() for t in topics}          # "-1".."24"
    parent_series = {str(i): blank() for i in range(-1, 8)}
    topic_title_only = {str(t["id"]): [0] * len(years) for t in topics}
    parent_title_only = {str(i): [0] * len(years) for i in range(-1, 8)}
    totals = blank()

    prelude_n, prelude_d = 0, 0.0
    prelude_by_parent = {str(i): 0 for i in range(-1, 8)}

    for p in points:
        yr = p["year"]
        tid = p["dom"]
        pid = parent_of_topic.get(tid, -1)
        amt = p["amount"]
        if yr is None or yr < DENSE_FROM or yr > DENSE_TO:
            if yr is not None and yr < DENSE_FROM:
                prelude_n += 1
                prelude_d += amt
                prelude_by_parent[str(pid)] += 1
            continue
        i = y_index[yr]
        topic_series[str(tid)]["n"][i] += 1
        topic_series[str(tid)]["d"][i] += amt
        parent_series[str(pid)]["n"][i] += 1
        parent_series[str(pid)]["d"][i] += amt
        totals["n"][i] += 1
        totals["d"][i] += amt
        if p["titleOnly"]:
            topic_title_only[str(tid)][i] += 1
            parent_title_only[str(pid)][i] += 1

    return {
        "years": years,
        "prelude": {"n": prelude_n, "d": prelude_d, "by_parent": prelude_by_parent},
        "series": {"topic": topic_series, "parent": parent_series},
        "title_only": {"topic": topic_title_only, "parent": parent_title_only},
        "totals_by_year": totals,
    }


def build_coverage(points: list[dict]) -> dict:
    from src.build_viz_data import COLORS, ORDER

    abs_src, src_path = load_abstract_source(points)

    years = list(range(min(p["year"] for p in points if p["year"]), max(p["year"] for p in points if p["year"]) + 1))
    cells = []
    by_year_n: dict[int, int] = {y: 0 for y in years}
    by_year_abs: dict[int, int] = {y: 0 for y in years}
    by_agency: dict[str, list[int]] = {a: [0, 0] for a in ORDER}

    per_cell: dict[tuple[str, int], list[int]] = {}
    for p in points:
        yr = p["year"]
        if yr is None:
            continue
        has_abs = not p["titleOnly"]
        by_year_n[yr] += 1
        by_year_abs[yr] += 1 if has_abs else 0
        by_agency[p["agency"]][0] += 1
        by_agency[p["agency"]][1] += 1 if has_abs else 0
        key = (p["agency"], yr)
        cell = per_cell.setdefault(key, [0, 0, 0, 0])  # n, abs, noise, title_only
        cell[0] += 1
        cell[1] += 1 if has_abs else 0
        cell[2] += 1 if p["dom"] == -1 else 0
        cell[3] += 1 if p["titleOnly"] else 0

    for (agency, yr), (n, a, noise, title_only) in sorted(per_cell.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        cells.append({
            "agency": agency, "year": yr, "n": n, "abs": a,
            "noise": noise, "title_only": title_only, "cov": round(a / n, 4) if n else None,
        })

    provenance = {"internal": 0, "orphan_recovered": 0, "none": 0}
    for v in abs_src.values():
        provenance[v] = provenance.get(v, 0) + 1
    provenance["source"] = src_path

    unassigned_n = sum(1 for p in points if p["dom"] == -1)
    t11_n = sum(1 for p in points if p["dom"] == ARTIFACT_TOPIC_ID)

    # abstract-presence x assignment crosstab — the reassuring finding this
    # view should lead with: losing the abstract barely moves the unassigned
    # rate (titles carry most of the signal for BERTopic's HDBSCAN step).
    crosstab = {
        "abs_assigned": sum(1 for p in points if not p["titleOnly"] and p["dom"] != -1),
        "abs_unassigned": sum(1 for p in points if not p["titleOnly"] and p["dom"] == -1),
        "title_assigned": sum(1 for p in points if p["titleOnly"] and p["dom"] != -1),
        "title_unassigned": sum(1 for p in points if p["titleOnly"] and p["dom"] == -1),
    }

    # The one cliff this round documents — verified: NIH+NIH-SUB coverage
    # falls from 64% (2019) to 3% (2020) to 0% (2021-2025).
    cliffs = [{
        "agency": "NIH",
        "last_good_year": 2019,
        "first_zero_year": 2021,
        "text": (
            "NIH abstract coverage falls from 64% (2019) to 3% (2020) to 0% "
            "(2021-2025). Data-collection artifact; only NIH RePORTER backfill "
            "can repair it."
        ),
    }]

    return {
        "years": years,
        "agencies": ORDER,
        "colors": COLORS,
        "cells": cells,
        "by_year": {
            "n": [by_year_n[y] for y in years],
            "abs": [by_year_abs[y] for y in years],
            "cov": [round(by_year_abs[y] / by_year_n[y], 4) if by_year_n[y] else None for y in years],
        },
        "by_agency": {
            a: {"n": n, "abs": ab, "cov": round(ab / n, 4) if n else 0.0}
            for a, (n, ab) in by_agency.items()
        },
        "provenance": provenance,
        "unassigned": {
            "n": unassigned_n + t11_n,
            "noise_n": unassigned_n,
            "t11_n": t11_n,
            "share": round((unassigned_n + t11_n) / len(points), 4),
        },
        "crosstab": crosstab,
        "cliffs": cliffs,
    }


def validate(points: list[dict], viz_meta: dict, topic_time: dict, coverage: dict) -> list[str]:
    lines = []
    n = len(points)
    total_dollars = sum(p["amount"] for p in points)
    lines.append(f"n_points = {n} (expect 2676)")
    assert n == 2676, "point count drifted from the frozen grants_umap.json"

    lines.append(f"total dollars = {total_dollars:,.0f} (expect 2,183,457,207)")
    assert abs(total_dollars - 2_183_457_207) < 1.0, "dollar total drifted"

    # topic_time reconciliation: dense-window totals + prelude must equal the corpus.
    dense_n = sum(topic_time["totals_by_year"]["n"])
    dense_d = sum(topic_time["totals_by_year"]["d"])
    prelude_n = topic_time["prelude"]["n"]
    prelude_d = topic_time["prelude"]["d"]
    post_2025_n = sum(1 for p in points if p["year"] is not None and p["year"] > DENSE_TO)
    post_2025_d = sum(p["amount"] for p in points if p["year"] is not None and p["year"] > DENSE_TO)
    reconciled_n = dense_n + prelude_n + post_2025_n
    reconciled_d = dense_d + prelude_d + post_2025_d
    lines.append(f"topic_time reconciled n = {reconciled_n} (expect {n})")
    assert reconciled_n == n, "topic_time year buckets don't cover every point"
    assert abs(reconciled_d - total_dollars) < 1.0, "topic_time dollar buckets don't reconcile"

    prelude_by_parent_sum = sum(topic_time["prelude"]["by_parent"].values())
    assert prelude_by_parent_sum == prelude_n, "prelude by_parent doesn't sum to prelude n"

    # per-year parent series must sum to totals_by_year at every index.
    for i in range(len(topic_time["years"])):
        s = sum(topic_time["series"]["parent"][str(k)]["n"][i] for k in range(-1, 8))
        assert s == topic_time["totals_by_year"]["n"][i], f"parent series don't sum to totals at year index {i}"
    lines.append("parent series sum to totals_by_year at every year ✓")

    # zero-coverage agencies — a genuine, verified invariant in this corpus.
    for a in ("NIH-SUB", "Navy", "AFRO"):
        cov = coverage["by_agency"][a]["cov"]
        lines.append(f"{a} coverage = {cov} (expect 0.0)")
        assert cov == 0.0, f"{a} coverage is no longer 0 — update the assumption or the corpus changed"

    # Unassigned block — must match across viz_meta and coverage.
    assert viz_meta["totals"]["unassigned_n"] == coverage["unassigned"]["n"] == 808, "Unassigned count drifted from 808"
    lines.append(f"Unassigned = {coverage['unassigned']['n']} grants, "
                 f"${viz_meta['totals']['unassigned_dollars']:,.0f} "
                 f"({viz_meta['totals']['unassigned_share']:.1%})")

    lines.append(f"abstract_source provenance path = {coverage['provenance']['source']}")

    ct = coverage["crosstab"]
    assert sum(ct.values()) == n, "crosstab doesn't cover every point"
    abs_rate = ct["abs_unassigned"] / (ct["abs_assigned"] + ct["abs_unassigned"])
    title_rate = ct["title_unassigned"] / (ct["title_assigned"] + ct["title_unassigned"])
    lines.append(f"unassigned rate: has-abstract {abs_rate:.1%}, title-only {title_rate:.1%} (should be close)")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="run validation, print it, write nothing")
    args = ap.parse_args()

    points, topics = load_frozen()
    viz_meta = build_viz_meta(points, topics)
    topic_time = build_topic_time(points, topics)
    coverage = build_coverage(points)

    report = validate(points, viz_meta, topic_time, coverage)
    viz_meta["validation"] = report
    print("\n".join(report))

    if args.check_only:
        print("\n--check-only: nothing written.")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, obj in [("viz_meta", viz_meta), ("topic_time", topic_time), ("coverage", coverage)]:
        p = OUT_DIR / f"{name}.json"
        _guard_output_path(p)
        p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {p.relative_to(REPO_ROOT)}  ({p.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
