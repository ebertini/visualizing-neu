"""
kw_review_sheet.py — Phase 4a: render outputs/KEYWORD_REVIEW.md, the
human-readable curation sheet, from either the draft or the curated JSON
(`--from draft|curated`, default draft) — so the same renderer lets a curator
proofread their own edits after promoting the draft.

Light deps only (pandas for the grants table + dollar figures; no
torch/bertopic/umap/hdbscan). Sections follow the topic-redo plan's Phase 4a
spec:
  0. exact commands + time estimate
  1. coverage numbers FIRST — does this even work?
  2. candidate parent groups
  3. ambiguous terms needing disambiguation (the most valuable page)
  4. dropped-as-generic / small-cluster-flagged leaves
  5. leaf keyword lists
  6. the k-sweep (silhouette by k)
  7. downstream files to edit if the parent count changes
  8. the 20 largest currently-Unassigned grants by dollars

Run:
    python3 -m src.kw_review_sheet                 # from the draft
    python3 -m src.kw_review_sheet --from curated   # proofread your own edits
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.topic_keywords import CURATED_PATH, DRAFT_PATH

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
OUTPUTS = REPO_ROOT / "outputs"
REVIEW_PATH = OUTPUTS / "KEYWORD_REVIEW.md"

ARTIFACT_TOPIC_ID = 14  # kept in sync with src/build_viz_aggregates.py


def _section0() -> str:
    return """## 0. Commands + time estimate

```bash
cp outputs/keyword_topics.draft.json outputs/topic_keywords.json
$EDITOR outputs/topic_keywords.json        # ~60-90 min required tier, see below
python3 -m src.kw_curation --check         # exit 1 until genuinely curated
python3 -m src.kw_review_sheet --from curated   # proofread your own edits
```

**Required tier (~60-90 min):** parent labels + accept/reject (~10 min), leaf
labels + accept/reject (~40 min), and only the terms flagged in §3 below
(expect ~15-20% of all terms) — sorted flagged-first with a
`— trust below this line —` separator once you're inside a leaf's keyword
list. If the flagged fraction feels like it's ballooned past ~35%, that's a
signal to tighten the discovery parameters and regenerate rather than review
harder.
"""


def _section1(vc: dict, tg: dict) -> str:
    cov = vc["coverage_pruned"]
    return f"""## 1. Does this even work? (coverage — read this first)

- Full harvested vocabulary: **{vc['_meta']['full_vocab_size']} terms**, of which
  **{vc['coverage_full_vocab']['docs_matching_0_terms']} grants** have zero matching
  candidate terms at all (the irreducible floor — genuinely text-less docs).
- Pruned to **{cov['pruned_vocab_size']} terms** ({vc['_meta']['prune_target']} by rank +
  {cov['n_backfilled']} backfilled): **{cov['docs_matching_0_of_pruned_set']} grants**
  still match zero terms — equal to the floor above, by construction (verified by
  an assert in kw_vocab_discover.py).
- Parent clustering: k={tg['_meta']['chosen_k_parent']}
  (silhouette={tg['_meta']['chosen_k_parent_silhouette']}); leaf clustering:
  k={tg['_meta']['chosen_k_leaf']} (silhouette={tg['_meta']['chosen_k_leaf_silhouette']}).
- Nesting check: **{tg['_meta']['n_leaf_clusters_spanning_gt1_parent']} leaf clusters
  span more than one parent** (should be 0 — Plan B guarantees this by construction).
- ARI (doc-centroid grouping vs. full c-TF-IDF-loading grouping):
  **{tg['_meta']['ari_doc_centroid_vs_full_ctfidf_loading']}** — low means the semantic
  grouping is adding real information beyond simple topic co-occurrence, which is
  what you want to see.
"""


def _section2(tg: dict) -> str:
    lines = ["## 2. Candidate parent groups\n"]
    groups = sorted(tg["parent_groups"].items(), key=lambda kv: -kv[1]["n_terms"])
    total = sum(g["n_terms"] for _, g in groups)
    for gid, g in groups:
        share = 100 * g["n_terms"] / total if total else 0
        legacy = ", ".join(f"topic {c['topic_id']} (concentration={c['concentration_score']}, "
                            f"n={c['raw_n_docs']})"
                            for c in g.get("contributing_legacy_topics", [])[:3])
        lines.append(f"### {gid} — {g['n_terms']} terms ({share:.1f}%)")
        lines.append(f"- Top terms: {', '.join(g['top_terms'][:12])}")
        lines.append(f"- Contributing legacy topics: {legacy or '(none)'}")
        lines.append("")
    return "\n".join(lines)


LARGE_LEAF_FLOOR = 50  # a term flagged inside a leaf this size or bigger is
# almost certainly headed for acceptance, so a bad term there matters far
# more than the same term sitting in a leaf you're about to reject entirely.


def _section3(vc: dict, draft: dict) -> str:
    # Map term -> the leaves it currently lives in, so a flagged term can be
    # prioritized by whether it's actually inside a large/likely-accepted
    # leaf, not just shown in arbitrary vocabulary order (a real gap found in
    # practice: "whether", df=206, precision=0.19, sat inside a 300-term
    # leaf and was flagged by both criteria but got cut by a naive [:150]
    # slice in an earlier version of this function).
    term_to_leaves: dict[str, list[tuple[str, int]]] = {}
    for lid, leaf in draft["leaves"].items():
        n = leaf["provenance"]["n_terms"]
        for kw in leaf["keywords"]:
            term_to_leaves.setdefault(kw["term"], []).append((lid, n))

    flagged = []
    for t in vc["terms"]:
        reasons = []
        if t.get("max_topic_precision", 1) < 0.35:
            reasons.append(f"low precision ({t['max_topic_precision']})")
        if t.get("df_corpus", 0) > 150:
            reasons.append(f"high df ({t['df_corpus']})")
        if reasons:
            leaves_here = term_to_leaves.get(t["term"], [])
            max_leaf_size = max((n for _, n in leaves_here), default=0)
            flagged.append((t["term"], reasons, leaves_here, max_leaf_size, t.get("df_corpus", 0)))

    # Sort so a bad term sitting inside a large (likely-accepted) leaf shows
    # up first — that's the case that actually costs you something if missed.
    flagged.sort(key=lambda f: (f[3] >= LARGE_LEAF_FLOOR, f[4]), reverse=True)

    lines = [f"## 3. Flagged terms needing disambiguation ({len(flagged)}/{len(vc['terms'])} "
             f"= {100*len(flagged)/max(len(vc['terms']),1):.1f}%) — the most valuable page\n"]
    lines.append(f"Sorted so terms sitting inside a large (>={LARGE_LEAF_FLOOR}-term, likely-accepted) "
                  "leaf come first — those are the ones actually worth your time.\n")
    lines.append("— review these; everything else can be skimmed —\n")
    for term, reasons, leaves_here, max_leaf_size, _ in flagged[:300]:
        where = ", ".join(f"leaf {lid} ({n} terms)" for lid, n in leaves_here) or "(not in any accepted-length leaf)"
        lines.append(f"- `{term}` — {'; '.join(reasons)} — in: {where}")
    if len(flagged) > 300:
        lines.append(f"\n... and {len(flagged) - 300} more, all in smaller/less-consequential leaves "
                      "(see outputs/kw_vocab_candidates.json for the full list).")
    lines.append("\n— trust below this line —\n")
    return "\n".join(lines)


def _section4(draft: dict) -> str:
    lines = ["## 4. Dropped-as-generic / small-cluster drop candidates\n"]
    lines.append("Nothing vanishes silently — every candidate for dropping is listed here "
                  "with its reason and its terms, so you can override the auto-flag.\n")
    for d in draft["dropped_leaves"]:
        lines.append(f"- Leaf {d['id']} ({d['n_terms']} terms): {d['reason']}")
        lines.append(f"  - terms: {', '.join(d['top_terms'])}")
    if not draft["dropped_leaves"]:
        lines.append("(none flagged)")
    return "\n".join(lines)


def _section5(draft: dict) -> str:
    lines = ["## 5. Leaf keyword lists\n"]
    for lid, leaf in sorted(draft["leaves"].items(), key=lambda kv: int(kv[0])):
        terms = ", ".join(k["term"] for k in leaf["keywords"])
        lines.append(f"### Leaf {lid} — {leaf['label']}  (parent: {leaf['parent']})")
        lines.append(f"- keywords: {terms}")
        if leaf["notes"]:
            lines.append(f"- ⚠ {leaf['notes']}")
        lines.append("")
    return "\n".join(lines)


def _section6(tg: dict) -> str:
    lines = ["## 6. k-sweep (silhouette by k)\n", "| k | silhouette |", "|---|---|"]
    for k, s in sorted(tg["silhouette_by_k"].items(), key=lambda kv: int(kv[0])):
        marker = ""
        if int(k) == tg["_meta"]["chosen_k_parent"]:
            marker = " ← chosen k_parent"
        if int(k) == tg["_meta"]["chosen_k_leaf"]:
            marker += " ← chosen k_leaf"
        lines.append(f"| {k} | {s}{marker} |")
    return "\n".join(lines)


def _section7() -> str:
    return """## 7. Downstream files to edit if the parent count changes

If curation changes the accepted parent count away from 8, these need manual sync
(per docs/TOPIC_MODEL_REFIT_CHECKLIST.md's existing checklist for this):
- `src/build_viz_aggregates.py` — `PARENT_NAMES` / `PARENT_COLORS`
- `docs/TopicVizPrototypes/shared/enrico.js` — `PARENT_COLORS`, `parentName()`/`parentColor()`
- `docs/TopicVizPrototypes/what_we_can_see/constants.js` — `TP_COLORS` (parent-indexed)
- `CLAUDE.md`'s "Topic modeling — state of play" section (parent count is stated there)
"""


def _section8() -> str:
    gr = pd.read_parquet(PROC / "grants.parquet")
    gr["grant_id"] = gr["grant_id"].astype(str)
    ta = pd.read_parquet(PROC / "topic_assignments.parquet")
    ta["doc_id"] = ta["doc_id"].astype(str)
    unassigned_ids = set(ta.loc[(ta["topic_id"] == -1) | (ta["topic_id"] == ARTIFACT_TOPIC_ID), "doc_id"])
    sub = gr[gr["grant_id"].isin(unassigned_ids)].copy()
    title_col = "title_from_abstract" if "title_from_abstract" in sub.columns else "grantname"
    sub["_title"] = sub[title_col].where(sub[title_col].astype(str).str.len() > 0, sub["grantname"])
    sub = sub.sort_values("totaldollars", ascending=False).head(20)
    lines = [f"## 8. The 20 largest currently-Unassigned grants by dollars "
             f"(of {len(unassigned_ids)} total, giving the $ headline faces)\n",
             "| grant_id | title | dollars |", "|---|---|---|"]
    for _, row in sub.iterrows():
        title = str(row["_title"])[:80]
        lines.append(f"| {row['grant_id']} | {title} | ${row['totaldollars']:,.0f} |")
    return "\n".join(lines)


def render(source: str) -> str:
    path = CURATED_PATH if source == "curated" else DRAFT_PATH
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist — run `python3 -m src.topic_keywords` first"
                                 if source == "draft" else
                                 f"{path} does not exist — promote the draft first (see §0)")
    draft = json.loads(path.read_text())
    vc = json.loads((OUTPUTS / "kw_vocab_candidates.json").read_text())
    tg = json.loads((OUTPUTS / "kw_term_groups_planB.json").read_text())

    parts = [
        f"# Keyword-Topic Review Sheet (source: {source})\n",
        _section0(), _section1(vc, tg), _section2(tg), _section3(vc, draft),
        _section4(draft), _section5(draft), _section6(tg), _section7(), _section8(),
    ]
    return "\n\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="source", choices=["draft", "curated"], default="draft")
    args = ap.parse_args()
    text = render(args.source)
    REVIEW_PATH.write_text(text)
    print(f"wrote {REVIEW_PATH}  (source: {args.source})")


if __name__ == "__main__":
    main()
