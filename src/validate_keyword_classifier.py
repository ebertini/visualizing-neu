"""
validate_keyword_classifier.py — Step 3 (Validation) automated checks: the
subset of the redo plan's validation section computable WITHOUT a human-
labeled gold set. Light deps only (pandas/numpy/stdlib; the embedding-
centroid check loads the cached SPECTER2 .npy via numpy, never torch).

What this DOES compute, from already-existing artifacts:
  - Title-only normalization check (the plan's own "most important automatic
    test"): unassigned rate / conf_tier mix / mean margin_rel split by
    `modelTitleOnly` (the same field build_viz_data.py already defines —
    "did the topic model see usable abstract text", via
    clean_text.usable_abstract — recomputed here from grants.parquet rather
    than imported from build_viz_data.py, which this validation work does
    not touch).
  - Parent-level BERTopic agreement: a majority-vote crosswalk PER OLD
    BERTOPIC TOPIC (not a hand-authored old-parent-name <-> new-parent-name
    mapping, which doesn't exist and would be a subjective judgment call) —
    for each BERTopic topic_id, the majority `kw_parent_id` among docs that
    topic_id's own docs got assigned; a doc "agrees" if its own kw_parent_id
    matches that majority. This is the same majority-vote methodology
    classify_by_keywords.py's `_attach_bertopic_columns` already uses at LEAF
    granularity — this redoes it at PARENT granularity (7 classes, not 31),
    which is the actual "parent-level" comparison the plan asks for.
  - Embedding-centroid independent signal: runs
    `classify_by_keywords.classify(..., tiebreak="embedding")` fresh (does
    NOT read the canonical on-disk topic_keyword_assignments.parquet, whose
    centroid columns are null — that file was written with the default
    tiebreak="none") and reports where BERTopic's noise/artifact-but-has-text
    docs land and whether their centroid margins look like real signal or
    like noise, per the plan's own two named failure signatures.

What this does NOT compute — and says so, rather than skipping silently:
  - Accuracy by conf_tier (the plan's actual calibration test) needs the
    human-labeled gold set (data/gold/topic_gold_set.csv), which has NOT
    been labeled yet (see src/build_gold_sample.py). `gold_set_report()`
    below reads that file and reports "0 labeled rows" honestly if so,
    rather than fabricating a number.

Run:
    python3 -m src.validate_keyword_classifier
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.classify_by_keywords import (
        ARTIFACT_TOPIC_ID, TOPIC_LABELS_PATH, classify, load_curated_taxonomy,
    )
    from src.clean_text import usable_abstract
except ImportError:  # run from within src/
    from classify_by_keywords import ARTIFACT_TOPIC_ID, TOPIC_LABELS_PATH, classify, load_curated_taxonomy
    from clean_text import usable_abstract

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
GOLD_PATH = REPO_ROOT / "data" / "gold" / "topic_gold_set.csv"

# Bands from the plan's own Validation section — written down before
# looking at the number, not fitted to it afterward.
AGREEMENT_BAND_LOW = 0.55   # below: lists don't describe this corpus, re-curate
AGREEMENT_BAND_HIGH = 0.90  # 0.70-0.90 healthy; above 0.97 no new information
AGREEMENT_BAND_CEILING = 0.97


def _load_grants_with_model_title_only() -> pd.DataFrame:
    gr = pd.read_parquet(PROC / "grants.parquet")
    gr["grant_id"] = gr["grant_id"].astype(str)
    src = gr["abstract_source"].fillna("").astype(str) if "abstract_source" in gr.columns \
        else pd.Series([""] * len(gr), index=gr.index)
    # Same definition build_viz_data.py uses for modelTitleOnly: did the
    # topic model see any usable abstract text (masks LOW_TRUST_ABSTRACT_SOURCES).
    gr["modelTitleOnly"] = [
        usable_abstract(a, s) == "" for a, s in zip(gr["abstract"].fillna(""), src)
    ]
    return gr[["grant_id", "modelTitleOnly", "totaldollars"]]


def title_only_normalization_report(kw_df: pd.DataFrame) -> dict:
    grants = _load_grants_with_model_title_only()
    df = kw_df[~kw_df["is_extra"]].merge(grants, left_on="doc_id", right_on="grant_id", how="inner")

    out = {}
    for label, sub in df.groupby("modelTitleOnly"):
        key = "title_only" if label else "abstract_bearing"
        n = len(sub)
        n_unassigned = int((sub["kw_leaf_id"] == -1).sum())
        assigned = sub[sub["kw_leaf_id"] != -1]
        out[key] = {
            "n": n,
            "unassigned_rate": n_unassigned / n if n else float("nan"),
            "low_or_none_rate": float((sub["conf_tier"].isin(["low", "none"])).mean()) if n else float("nan"),
            "conf_tier_mix": sub["conf_tier"].value_counts(normalize=True).round(3).to_dict(),
            "mean_margin_rel_assigned": float(assigned["margin_rel"].mean()) if len(assigned) else float("nan"),
        }

    lo_pp = abs(out["title_only"]["low_or_none_rate"] - out["abstract_bearing"]["low_or_none_rate"]) * 100
    margin_higher_for_title_only = (
        out["title_only"]["mean_margin_rel_assigned"] > out["abstract_bearing"]["mean_margin_rel_assigned"]
    )
    out["_summary"] = {
        "low_or_none_rate_gap_pp": round(lo_pp, 1),
        "within_10pp": bool(lo_pp <= 10.0),
        "mean_margin_higher_for_title_only": bool(margin_higher_for_title_only),
        "title_weight_overboost_suspected": bool(margin_higher_for_title_only),
    }
    return out


def _old_topic_to_parent() -> dict[int, str]:
    labels = json.loads(TOPIC_LABELS_PATH.read_text())
    crosswalk = {}
    for pid, p in labels["parents"].items():
        for tid in p.get("topic_ids", []):
            crosswalk[int(tid)] = p["label"]
    return crosswalk


def parent_level_bertopic_agreement(kw_df: pd.DataFrame) -> dict:
    ta = pd.read_parquet(PROC / "topic_assignments.parquet")[["doc_id", "topic_id"]].copy()
    ta["doc_id"] = ta["doc_id"].astype(str)
    df = kw_df.merge(ta, on="doc_id", how="left")

    noise_like = {-1, ARTIFACT_TOPIC_ID}
    old_parent_of = _old_topic_to_parent()
    comparable = df[~df["topic_id"].isin(noise_like) & df["topic_id"].notna() & (df["kw_leaf_id"] != -1)].copy()
    comparable["old_parent"] = comparable["topic_id"].map(old_parent_of)

    # Majority-vote crosswalk PER OLD TOPIC (not per old-parent-label) — see
    # module docstring for why: this needs no hand-authored semantic mapping
    # between the two taxonomies' differently-named parents.
    majority_by_topic = (comparable.groupby("topic_id")["kw_parent_id"]
                          .agg(lambda s: s.value_counts().idxmax()))
    comparable["majority_kw_parent_for_topic"] = comparable["topic_id"].map(majority_by_topic)
    comparable["agrees"] = comparable["kw_parent_id"] == comparable["majority_kw_parent_for_topic"]

    n_docs = len(comparable)
    n_grants = int((~comparable["is_extra"]).sum())
    overall_rate = float(comparable["agrees"].mean()) if n_docs else float("nan")

    if overall_rate < AGREEMENT_BAND_LOW:
        band = "BELOW 0.55 — the keyword lists don't describe this corpus at the topic-cluster level; consider re-curating"
    elif overall_rate > AGREEMENT_BAND_CEILING:
        band = "ABOVE 0.97 — the scorer has essentially re-derived BERTopic's own clustering; inspectability gained, little new information"
    elif overall_rate >= 0.70:
        band = "0.70-0.90 (or above, below the 0.97 ceiling) — healthy"
    else:
        band = "between 0.55 and 0.70 — below the 'healthy' band but above the re-curate threshold; a borderline result, not a failure"

    by_old_parent = (comparable.groupby("old_parent")["agrees"]
                      .agg(["mean", "count"]).rename(columns={"mean": "agreement_rate", "count": "n"})
                      .sort_values("n", ascending=False))

    return {
        "grain": f"{n_docs} comparable docs, of which {n_grants} are real grants "
                 f"(is_extra==False) and {n_docs - n_grants} are orphan pseudo-docs",
        "n_comparable_docs": n_docs,
        "overall_agreement_rate": overall_rate,
        "band_interpretation": band,
        "by_old_parent": by_old_parent,
    }


def embedding_centroid_report(leaves: dict, parents: dict) -> dict:
    df = classify(leaves, parents, tiebreak="embedding")
    ta = pd.read_parquet(PROC / "topic_assignments.parquet")[["doc_id", "topic_id"]].copy()
    ta["doc_id"] = ta["doc_id"].astype(str)
    df["doc_id"] = df["doc_id"].astype(str)
    df = df.merge(ta, on="doc_id", how="left")

    grants = _load_grants_with_model_title_only()
    df = df.merge(grants, left_on="doc_id", right_on="grant_id", how="left")

    noise_like = df["topic_id"].isin([-1, ARTIFACT_TOPIC_ID]) | df["topic_id"].isna()
    formerly_noise_with_text = df[noise_like & (df["modelTitleOnly"] == False) &  # noqa: E712
                                   (df["kw_leaf_id"] != -1) & df["centroid_margin"].notna()]
    confident = df[df["conf_tier"].isin(["high", "medium"]) & df["centroid_margin"].notna()]

    return {
        "n_formerly_noise_with_text_now_assigned": len(formerly_noise_with_text),
        "mean_centroid_margin_formerly_noise": float(formerly_noise_with_text["centroid_margin"].mean())
            if len(formerly_noise_with_text) else float("nan"),
        "mean_centroid_margin_confident": float(confident["centroid_margin"].mean()) if len(confident) else float("nan"),
        "plan_reference_margins": {"noise_docs_reference": 0.008, "bertopic_assigned_reference": 0.025,
                                    "note": "the upstream plan's own cited numbers, for context only — "
                                            "not something this run needs to reproduce exactly"},
        "formerly_noise_parent_distribution": (
            formerly_noise_with_text["kw_parent_label"].value_counts(normalize=True).round(3).to_dict()
        ),
        "concentration_flag": (
            "CONCENTRATED in <=3 parents (possible coverage hole just relabeled)"
            if len(formerly_noise_with_text) and
            formerly_noise_with_text["kw_parent_label"].value_counts(normalize=True).iloc[:3].sum() > 0.75
            else "spread across parents (not concentrated)"
        ),
        "margin_indistinguishable_flag": (
            "margins look indistinguishable from confident docs (possible decorative confidence signal)"
            if len(formerly_noise_with_text) and len(confident) and
            abs(formerly_noise_with_text["centroid_margin"].mean() - confident["centroid_margin"].mean()) < 0.005
            else "margins are measurably lower than confident docs (expected pattern)"
        ),
    }


def gold_set_report() -> dict:
    if not GOLD_PATH.exists():
        return {"status": "NOT BUILT — run `python3 -m src.build_gold_sample` first"}
    gold = pd.read_csv(GOLD_PATH, dtype=str).fillna("")
    n_labeled = int((gold["human_parent_label"].str.strip() != "").sum())
    if n_labeled == 0:
        return {
            "status": f"scaffold exists ({len(gold)} rows) but 0 ROWS ARE LABELED — "
                      "human_parent_label is empty for every row. No accuracy or "
                      "calibration number exists yet; see src/build_gold_sample.py's "
                      "docstring for how to label it.",
            "n_rows": len(gold), "n_labeled": 0,
        }
    return {"status": f"{n_labeled}/{len(gold)} rows labeled — scoring not yet implemented "
                       "here (accuracy-by-conf_tier is future work once labeling is complete)",
            "n_rows": len(gold), "n_labeled": n_labeled}


def main() -> None:
    leaves, parents = load_curated_taxonomy()
    kw_df = pd.read_parquet(PROC / "topic_keyword_assignments.parquet")
    kw_df["doc_id"] = kw_df["doc_id"].astype(str)

    print("=" * 70)
    print("1. TITLE-ONLY NORMALIZATION CHECK")
    print("=" * 70)
    tno = title_only_normalization_report(kw_df)
    for key in ("abstract_bearing", "title_only"):
        r = tno[key]
        print(f"  {key}: n={r['n']}  unassigned_rate={r['unassigned_rate']:.1%}  "
              f"low_or_none_rate={r['low_or_none_rate']:.1%}  "
              f"mean_margin_rel(assigned)={r['mean_margin_rel_assigned']:.3f}")
    print(f"  gap (low+none rate, pp): {tno['_summary']['low_or_none_rate_gap_pp']}  "
          f"(within ~10pp: {tno['_summary']['within_10pp']})")
    print(f"  mean margin higher for title-only (would mean W_TITLE over-boosts): "
          f"{tno['_summary']['mean_margin_higher_for_title_only']}")

    print("\n" + "=" * 70)
    print("2. PARENT-LEVEL BERTOPIC AGREEMENT")
    print("=" * 70)
    agree = parent_level_bertopic_agreement(kw_df)
    print(f"  grain: {agree['grain']}")
    print(f"  overall agreement rate: {agree['overall_agreement_rate']:.1%}")
    print(f"  band: {agree['band_interpretation']}")
    print(agree["by_old_parent"].to_string())

    print("\n" + "=" * 70)
    print("3. EMBEDDING-CENTROID INDEPENDENT SIGNAL (this re-runs the classifier "
          "with --tiebreak embedding, ~1 min)")
    print("=" * 70)
    centroid = embedding_centroid_report(leaves, parents)
    print(f"  formerly-noise-with-text docs now assigned: {centroid['n_formerly_noise_with_text_now_assigned']}")
    print(f"  mean centroid margin (formerly noise): {centroid['mean_centroid_margin_formerly_noise']:.4f}")
    print(f"  mean centroid margin (confident docs):  {centroid['mean_centroid_margin_confident']:.4f}")
    print(f"  plan's own reference margins (noise vs. BERTopic-assigned): "
          f"{centroid['plan_reference_margins']['noise_docs_reference']} vs. "
          f"{centroid['plan_reference_margins']['bertopic_assigned_reference']}  (context only)")
    print(f"  concentration check: {centroid['concentration_flag']}")
    print(f"  margin check: {centroid['margin_indistinguishable_flag']}")
    print(f"  parent distribution of formerly-noise docs: {centroid['formerly_noise_parent_distribution']}")

    print("\n" + "=" * 70)
    print("4. GOLD SET (accuracy-by-conf_tier — the actual calibration test)")
    print("=" * 70)
    gold = gold_set_report()
    print(f"  {gold['status']}")


if __name__ == "__main__":
    main()
