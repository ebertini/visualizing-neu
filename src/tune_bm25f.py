"""
tune_bm25f.py — bounded sweep of the keyword classifier's BM25F constants
(K1/B/ALPHA/W_TITLE) and conf_tier thresholds (HIGH_MARGIN_REL/HIGH_MIN_TERMS/
MEDIUM_MARGIN_REL/MEDIUM_MIN_TERMS) against the 180-row gold set — the
"NEXT CONCRETE STEP" named in CLAUDE.md, done AFTER (not instead of) the
curation pass that closed the title-only unassigned gap (see
outputs/topic_keywords.json's 2026-08-30 curation notes and
src/kw_review_sheet.py --unassigned).

Modelled on src/tune_bertopic.py (module-level grid, JSON to outputs/).

Match-once/rescore-many: matching (src.classify_by_keywords.match_corpus) is
the expensive step (~30s) and is INVARIANT to every constant swept here — it
depends only on the taxonomy's term list and the corpus text. Scoring
(score_corpus) is cheap (~0.5s) and depends on the module-level K1/B/ALPHA/
W_TITLE/threshold globals, monkeypatched here between grid points (same
pattern tests/test_classify_by_keywords.py already uses). This makes a
several-dozen-point sweep take ~1 minute instead of ~1 hour.

Guardrails against overfitting a 4-constant sweep to an n=180 gold set
(±7pp CI, ~13 title-only rows): only report/adopt a candidate whose gold
accuracy beats baseline by MORE than the baseline's own CI half-width, and
tune the title-only gap (a full-corpus, label-free metric, n=291) as the
PRIMARY signal for W_TITLE — gold accuracy is a non-regression guard on top,
not the objective itself. Keeping the literature defaults is a valid,
reportable outcome if nothing clears the bar.

Run:
    python3 -m src.tune_bm25f

Writes:
    outputs/bm25f_sweep.json
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import src.classify_by_keywords as cbk
from src.validate_keyword_classifier import gold_set_report, parent_level_bertopic_agreement

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = REPO_ROOT / "outputs"

# Baseline (module defaults) — literature-standard Okapi placeholders per
# classify_by_keywords.py's own docstring, never tuned against this corpus
# before this sweep.
BASELINE = dict(K1=cbk.K1, B=cbk.B, ALPHA=cbk.ALPHA, W_TITLE=cbk.W_TITLE,
                HIGH_MARGIN_REL=cbk.HIGH_MARGIN_REL, HIGH_MIN_TERMS=cbk.HIGH_MIN_TERMS,
                MEDIUM_MARGIN_REL=cbk.MEDIUM_MARGIN_REL, MEDIUM_MIN_TERMS=cbk.MEDIUM_MIN_TERMS)

# A bounded grid, not an exhaustive one — chosen around the literature
# defaults plus the specific failure mode found in practice (title-only docs
# structurally capped below "high" by HIGH_MIN_TERMS=3; see CLAUDE.md and
# notebooks/09's Section 2 rewrite). K1/B/ALPHA rarely move accuracy much in
# BM25 literature; W_TITLE and HIGH_MIN_TERMS are the two knobs the redo plan
# and this session's investigation both flagged as the live suspects.
GRID = {
    "K1": [1.2, 1.5, 2.0],
    "B": [0.5, 0.75, 0.9],
    "ALPHA": [0.5],  # only ever appears as a leaf-score normalization exponent;
    # varying it rescales every leaf's score by the same monotonic transform
    # relative to its OWN keyword-weight total, so it does not change which
    # leaf wins (ranking is invariant) — swept at one value only, not because
    # it can't matter, but because BM25 literature and this corpus's own
    # structure give no reason to expect it moves accuracy independently of
    # K1/B/W_TITLE; left in the grid dict (not hardcoded) so a future pass
    # can widen this without touching the harness.
    "W_TITLE": [1.0, 1.5, 2.0, 3.0],
    "HIGH_MIN_TERMS": [1, 2, 3],
}
# Threshold margins held fixed at baseline in this pass — the investigation
# found the title-only gap's structural cause was HIGH_MIN_TERMS (a term-COUNT
# gate), not the margin thresholds; sweeping margins too would double the grid
# size for a dimension with no identified problem to fix.


@dataclass(frozen=True)
class Candidate:
    K1: float
    B: float
    ALPHA: float
    W_TITLE: float
    HIGH_MARGIN_REL: float = cbk.HIGH_MARGIN_REL
    HIGH_MIN_TERMS: int = cbk.HIGH_MIN_TERMS
    MEDIUM_MARGIN_REL: float = cbk.MEDIUM_MARGIN_REL
    MEDIUM_MIN_TERMS: int = cbk.MEDIUM_MIN_TERMS


def _apply(module, cand: Candidate) -> None:
    for field in ("K1", "B", "ALPHA", "W_TITLE", "HIGH_MARGIN_REL", "HIGH_MIN_TERMS",
                  "MEDIUM_MARGIN_REL", "MEDIUM_MIN_TERMS"):
        setattr(module, field, getattr(cand, field))


def evaluate(cand: Candidate, leaves: dict, parents: dict, match_results: list[dict],
             match_results_full: list[dict], n_docs_full: int) -> dict:
    _apply(cbk, cand)
    df = cbk.score_corpus(match_results, leaves, parents, n_docs_full,
                           match_results_full=match_results_full)
    df["doc_id"] = df["doc_id"].astype(str)

    gold = gold_set_report(df)
    agree = parent_level_bertopic_agreement(df)

    n = len(df)
    unassigned = df[df["kw_leaf_id"] == -1]
    tiers = df["conf_tier"].value_counts().to_dict()

    # Title-only gap, computed inline (not via title_only_normalization_report,
    # which needs grants.parquet's modelTitleOnly join) using the same
    # has-abstract-tokens signal score_corpus already computed per doc.
    # Reload once outside the loop would be cheaper, but this is a cheap
    # groupby, not a re-match — negligible next to the ~0.5s score_corpus call.
    return {
        "params": cand.__dict__,
        "n_unassigned": int(len(unassigned)),
        "pct_unassigned": round(100 * len(unassigned) / n, 2),
        "conf_tier_mix": tiers,
        "gold_accuracy": gold.get("keyword_classifier_accuracy"),
        "gold_ci95": gold.get("keyword_classifier_ci95"),
        "gold_accuracy_by_tier": {k: v["accuracy"] for k, v in gold.get("accuracy_by_conf_tier", {}).items()},
        "gold_calibration_check": gold.get("calibration_check"),
        "bertopic_agreement": agree.get("overall_agreement_rate"),
        "bertopic_agreement_band": agree.get("band_interpretation"),
    }


def _title_only_gap(df, ids, titles, abstracts) -> dict:
    """Full-corpus (label-free, n=291 title-only) low/none-rate gap — the
    PRIMARY signal for W_TITLE, per this module's guardrail note above."""
    from src.kw_vocab import tokenize
    title_only_ids = {i for i, a in zip(ids, abstracts) if not tokenize(a)}
    d = df.copy()
    d["doc_id"] = d["doc_id"].astype(str)
    d["title_only"] = d["doc_id"].isin(title_only_ids)
    out = {}
    for key, sub in d.groupby("title_only"):
        out["title_only" if key else "abstract_bearing"] = {
            "n": len(sub),
            "low_or_none_rate": round(100 * sub["conf_tier"].isin(["low", "none"]).mean(), 2),
        }
    to = out.get("title_only", {}).get("low_or_none_rate", 0.0)
    ab = out.get("abstract_bearing", {}).get("low_or_none_rate", 0.0)
    out["gap_pp"] = round(to - ab, 2)
    return out


def main() -> None:
    print("loading taxonomy + corpus, matching once (this is the expensive step, ~30s)...")
    t0 = time.time()
    leaves, parents = cbk.load_curated_taxonomy()
    ids, titles, abstracts = cbk.load_doc_fields()
    n_docs_full = len(ids)
    match_results_full = cbk.match_corpus(leaves, ids, titles, abstracts)
    print(f"  done in {time.time() - t0:.1f}s\n")

    baseline_cand = Candidate(**BASELINE)
    baseline_result = evaluate(baseline_cand, leaves, parents, match_results_full,
                                match_results_full, n_docs_full)
    _apply(cbk, baseline_cand)
    baseline_gap = _title_only_gap(
        cbk.score_corpus(match_results_full, leaves, parents, n_docs_full), ids, titles, abstracts)
    baseline_result["title_only_gap"] = baseline_gap
    print(f"BASELINE: gold_accuracy={baseline_result['gold_accuracy']:.3f} "
          f"CI={baseline_result['gold_ci95']}  title_only_gap={baseline_gap['gap_pp']}pp  "
          f"unassigned={baseline_result['n_unassigned']}")

    ci_lo, ci_hi = baseline_result["gold_ci95"]
    ci_half_width = (ci_hi - ci_lo) / 2
    adopt_threshold = baseline_result["gold_accuracy"] + ci_half_width
    print(f"adopt threshold (baseline + CI half-width, {ci_half_width:.3f}): "
          f"{adopt_threshold:.3f} — a candidate must clear THIS to be considered better\n")

    runs = []
    for k1 in GRID["K1"]:
        for b in GRID["B"]:
            for alpha in GRID["ALPHA"]:
                for w_title in GRID["W_TITLE"]:
                    for hmt in GRID["HIGH_MIN_TERMS"]:
                        cand = Candidate(K1=k1, B=b, ALPHA=alpha, W_TITLE=w_title, HIGH_MIN_TERMS=hmt)
                        result = evaluate(cand, leaves, parents, match_results_full,
                                           match_results_full, n_docs_full)
                        _apply(cbk, cand)
                        gap = _title_only_gap(
                            cbk.score_corpus(match_results_full, leaves, parents, n_docs_full),
                            ids, titles, abstracts)
                        result["title_only_gap"] = gap
                        runs.append(result)

    _apply(cbk, baseline_cand)  # restore module state for anything running after this script

    beats_baseline = [r for r in runs if r["gold_accuracy"] is not None
                      and r["gold_accuracy"] > adopt_threshold]
    beats_baseline.sort(key=lambda r: -r["gold_accuracy"])

    print(f"\nswept {len(runs)} configurations")
    print(f"configurations clearing the adopt threshold: {len(beats_baseline)}")
    for r in beats_baseline[:10]:
        print(f"  {r['params']}: gold_acc={r['gold_accuracy']:.3f} "
              f"title_only_gap={r['title_only_gap']['gap_pp']}pp "
              f"bertopic_agree={r['bertopic_agreement']:.3f}")

    if not beats_baseline:
        print("\nNO candidate cleared the adopt threshold — keeping literature defaults is "
              "the recommended, documentable outcome of this sweep (see module docstring's "
              "overfitting guardrail: n=180 gold set, ±{:.1f}pp CI half-width).".format(
                  100 * ci_half_width))

    OUTPUTS.mkdir(exist_ok=True)
    (OUTPUTS / "bm25f_sweep.json").write_text(json.dumps({
        "baseline": baseline_result,
        "adopt_threshold": adopt_threshold,
        "grid": GRID,
        "n_runs": len(runs),
        "runs": runs,
        "beats_baseline": beats_baseline,
        "recommendation": ("keep literature defaults" if not beats_baseline
                            else f"adopt {beats_baseline[0]['params']}"),
    }, indent=2))
    print(f"\nwrote {OUTPUTS / 'bm25f_sweep.json'}")


if __name__ == "__main__":
    main()
