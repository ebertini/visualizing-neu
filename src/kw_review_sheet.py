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

from src.clean_text import LOW_TRUST_ABSTRACT_SOURCES
from src.kw_vocab import tokenize
from src.topic_keywords import CURATED_PATH, DRAFT_PATH

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
OUTPUTS = REPO_ROOT / "outputs"
REVIEW_PATH = OUTPUTS / "KEYWORD_REVIEW.md"
UNASSIGNED_REVIEW_PATH = OUTPUTS / "KEYWORD_REVIEW_UNASSIGNED.md"

# Curated terms + a small closed stopword class filtered out of the "content
# tokens" shown per grant below — the point is to surface words a curator
# might plausibly add as a new keyword, not every "the"/"and"/"of" in the text.
_TRIVIAL_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "with", "on", "at",
    "by", "from", "is", "are", "be", "will", "this", "that", "these", "those",
    "as", "into", "over", "our", "we", "its", "it", "their", "which", "such",
})

ARTIFACT_TOPIC_ID = 14  # kept in sync with src/build_viz_aggregates.py — a
# BERTopic-legacy concept (the ONR placeholder-title artifact cluster) with no
# meaning in the keyword taxonomy; None-safe below so retiring it elsewhere
# (Step 4 of the redo plan) doesn't break this section.


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
        # Leaves produced by recursive sub-clustering during Phase 4a curation
        # (e.g. a leaf split off another) only recorded source_leaf_id/note in
        # provenance, not n_terms — fall back to the leaf's own keyword count.
        n = leaf["provenance"].get("n_terms", len(leaf.get("keywords", [])))
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
        # Not every dropped-leaf record shares one schema — some (e.g. a leaf
        # dropped by merge/relabel rather than by term-count rule) only carry
        # id/label/reason, with no n_terms/top_terms.
        n_terms = d.get("n_terms")
        size = f"{n_terms} terms" if n_terms is not None else d.get("label", "no size recorded")
        lines.append(f"- Leaf {d['id']} ({size}): {d['reason']}")
        if d.get("top_terms"):
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

    # CANONICAL source: the keyword classifier's own output (kw_leaf_id == -1),
    # once it exists — NOT topic_assignments.parquet's BERTopic topic_id, which
    # would show a stale, now-wrong Unassigned set (BERTopic and the keyword
    # classifier disagree on ~40% of docs; a grant fixed by curation this
    # session would still show up here as "Unassigned" if this read BERTopic).
    # Falls back to the BERTopic-based reading only in a bootstrap-only
    # environment where classify_by_keywords hasn't been run yet.
    kw_path = PROC / "topic_keyword_assignments.parquet"
    if kw_path.exists():
        kw = pd.read_parquet(kw_path)
        kw["doc_id"] = kw["doc_id"].astype(str)
        unassigned_ids = set(kw.loc[kw["kw_leaf_id"] == -1, "doc_id"])
        source_note = "keyword classifier"
    else:
        ta = pd.read_parquet(PROC / "topic_assignments.parquet")
        ta["doc_id"] = ta["doc_id"].astype(str)
        mask = ta["topic_id"] == -1
        if ARTIFACT_TOPIC_ID is not None:
            mask = mask | (ta["topic_id"] == ARTIFACT_TOPIC_ID)
        unassigned_ids = set(ta.loc[mask, "doc_id"])
        source_note = "BERTopic — data/processed/topic_keyword_assignments.parquet not found"

    sub = gr[gr["grant_id"].isin(unassigned_ids)].copy()
    title_col = "title_from_abstract" if "title_from_abstract" in sub.columns else "grantname"
    sub["_title"] = sub[title_col].where(sub[title_col].astype(str).str.len() > 0, sub["grantname"])
    sub = sub.sort_values("totaldollars", ascending=False).head(20)
    lines = [f"## 8. The 20 largest currently-Unassigned grants by dollars "
             f"(of {len(unassigned_ids)} total, source: {source_note})\n",
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


def _content_tokens(title: str, abstract: str, curated_terms: set[str], limit: int = 40) -> list[str]:
    """Content-bearing tokens from a grant's own text, for a curator scanning
    for plausible new keyword candidates — deliberately NOT the full
    discovery/scoring machinery (df_corpus, precision, etc.): the point here
    is "what does this doc actually say", not a re-run of vocabulary
    discovery. Excludes tokens already in the curated vocabulary (those, by
    definition, are not why the doc scored zero — a term IS in the vocab but
    didn't match; see the docstring note in render_unassigned) and bare
    trivial stopwords/very short tokens."""
    toks = tokenize(f"{title} {abstract}")
    seen: dict[str, int] = {}
    for t in toks:
        if len(t) <= 2 or t in _TRIVIAL_STOPWORDS or t in curated_terms:
            continue
        seen[t] = seen.get(t, 0) + 1
    ranked = sorted(seen.items(), key=lambda kv: -kv[1])
    return [t for t, _ in ranked[:limit]]


def render_unassigned(reason: str) -> str:
    """Per-doc review sheet for the classifier's own Unassigned bucket —
    unlike §8 above (dollar-sorted top-20 across BOTH unassigned_reason
    values), this is uncapped and filterable by reason, with full title +
    abstract + agency + dollars + a scan of the doc's own content tokens, so
    a curator can actually read every no_keyword_evidence grant (the only
    reason a curation pass can move) rather than the handful that happen to
    be dollar-sorted top-20.

    "Near-miss terms" here means content tokens from the doc's own text that
    are NOT already in the curated vocabulary — i.e. candidate NEW terms a
    curator might add — not a re-scoring against existing terms: a
    no_keyword_evidence grant scored score1<=0 because literally zero
    curated terms matched via match_text's exact/collapsed/stem tiers, so
    there is nothing "near" to show among terms that already exist.
    """
    kw_path = PROC / "topic_keyword_assignments.parquet"
    if not kw_path.exists():
        raise FileNotFoundError(f"{kw_path} does not exist — run `python3 -m src.classify_by_keywords` first")
    kw = pd.read_parquet(kw_path)
    kw["doc_id"] = kw["doc_id"].astype(str)
    kw = kw[~kw["is_extra"]]

    sub = kw[kw["kw_leaf_id"] == -1].copy()
    if reason != "all":
        sub = sub[sub["unassigned_reason"] == reason]

    gr = pd.read_parquet(PROC / "grants.parquet")
    gr["grant_id"] = gr["grant_id"].astype(str)
    title_col = "title_from_abstract" if "title_from_abstract" in gr.columns else "grantname"
    gr["_title"] = gr[title_col].where(gr[title_col].astype(str).str.len() > 0, gr["grantname"]).fillna("")
    gr["_abstract"] = gr["abstract"].fillna("") if "abstract" in gr.columns else ""
    gr["_low_trust"] = (gr["abstract_source"].astype(str).isin(LOW_TRUST_ABSTRACT_SOURCES)
                         if "abstract_source" in gr.columns else False)
    gr_idx = gr.set_index("grant_id")

    curated = json.loads(CURATED_PATH.read_text())
    curated_terms = {kwd["term"] for leaf in curated["leaves"].values() for kwd in leaf.get("keywords", [])}

    sub = sub.merge(gr_idx[["_title", "_abstract", "_low_trust", "agencyname", "totaldollars"]],
                     left_on="doc_id", right_index=True, how="left")
    sub = sub.rename(columns={"_title": "title_", "_abstract": "abstract_", "_low_trust": "low_trust_"})
    sub = sub.sort_values("totaldollars", ascending=False, na_position="last")

    lines = [f"# Unassigned grants — reason: {reason} ({len(sub)} rows)\n"]
    lines.append(
        "Per-doc review sheet: full title + abstract + agency + dollars + a scan of the doc's "
        "own content tokens NOT already in the curated vocabulary (candidate new keyword terms, "
        "not a re-score of existing ones — see this function's docstring in kw_review_sheet.py). "
        "`placeholder_title_only` grants have no real text (titles like \"Grant\"/\"Research\") and "
        "are not fixable by curation; `no_keyword_evidence` grants are the ones worth reading.\n"
    )
    for row in sub.itertuples():
        title = str(row.title_).strip() or "(no title)"
        # A low-trust-source abstract (see clean_text.LOW_TRUST_ABSTRACT_SOURCES) is DISPLAYED
        # on the dashboard but MASKED to "" for the model/classifier — treat it as if it were
        # title-only for content-token purposes, or a curated term added from its visible text
        # will never actually fire (confirmed the hard way: grants 1089127/1250146 both looked
        # curatable from their displayed abstracts but stayed unassigned after curation, because
        # both are `abstract_source == "nih_reporter_parent"`).
        low_trust = bool(getattr(row, "low_trust_", False))
        abstract = "" if low_trust else str(row.abstract_).strip()
        tokens = _content_tokens(title, abstract, curated_terms)
        lines.append(f"## {row.doc_id} — {title}")
        lines.append(f"- reason: `{row.unassigned_reason}` · agency: {row.agencyname} · "
                      f"dollars: ${row.totaldollars:,.0f}" if pd.notna(row.totaldollars)
                      else f"- reason: `{row.unassigned_reason}` · agency: {row.agencyname} · dollars: (unknown)")
        lines.append(f"- content tokens (candidate new-term material): {', '.join(tokens) or '(none found)'}")
        if low_trust:
            lines.append("- abstract: ⚠ MODEL CANNOT SEE THIS TEXT (low-trust `abstract_source`, "
                          "e.g. a borrowed NIH-parent-center abstract) — do not curate a term from "
                          f"it; treat this grant as title-only. Raw text for reference: "
                          f"{str(row.abstract_).strip()[:300]}...")
        elif abstract:
            lines.append(f"- abstract: {abstract}")
        else:
            lines.append("- abstract: (none — title-only)")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="source", choices=["draft", "curated"], default="draft")
    ap.add_argument("--unassigned", dest="unassigned_reason",
                     choices=["no_keyword_evidence", "placeholder_title_only", "all"],
                     help="instead of the full curation sheet, write an uncapped per-doc review "
                          "of the classifier's own Unassigned bucket, filtered by unassigned_reason")
    args = ap.parse_args()
    if args.unassigned_reason:
        text = render_unassigned(args.unassigned_reason)
        UNASSIGNED_REVIEW_PATH.write_text(text)
        print(f"wrote {UNASSIGNED_REVIEW_PATH}  (reason: {args.unassigned_reason})")
        return
    text = render(args.source)
    REVIEW_PATH.write_text(text)
    print(f"wrote {REVIEW_PATH}  (source: {args.source})")


if __name__ == "__main__":
    main()
