"""
build_gold_sample.py — Step 3 (Validation) scaffold: draws a stratified n=180
gold-set SAMPLE for human labeling. Light deps only (pandas/stdlib).

*** THIS SCRIPT DOES NOT LABEL ANYTHING. *** It writes `data/gold/topic_gold_set.csv`
with an EMPTY `human_parent_label` column. No accuracy/calibration number
exists anywhere in this repo until a human fills that column in by hand,
BLIND (without seeing model predictions) — see "How to actually label" below.

Stratification (per the topic-model-redo plan's Validation section): agency
bucket x text-availability x BERTopic-status, deliberately oversampling
"noise-with-text" (BERTopic left it as noise/artifact, but it has real
abstract text) since that is exactly the population this redesign targets.
Labeling is done at PARENT level only (7 curated parents is human-labelable;
31 leaves is not).

Population: grants (doc_id == grant_id, `is_extra == False`) present in both
`data/processed/topic_keyword_assignments.parquet` (Phase 4b's own output)
and `data/processed/grants.parquet`. Orphan pseudo-docs (`orphan-<id>`) are
excluded — they have no grant_id/agency to stratify by.

How to actually label (do this before trusting any accuracy number):
    1. Open data/gold/topic_gold_set.csv in a spreadsheet.
    2. For each row, read title + abstract_preview and pick ONE of the 7
       curated parent labels (printed by this script, also in
       outputs/topic_keywords.json's parents{}) into human_parent_label.
    3. Do NOT open data/gold/topic_gold_set_predictions.csv while labeling —
       it holds the keyword classifier's own prediction plus the old
       BERTopic parent for the same rows, kept in a SEPARATE file
       specifically so a human labeler is never shown a prediction before
       forming their own judgment (blind labeling). Only join the two files
       back together, by grant_id, after every row is labeled.
    4. Re-run `python3 -m src.validate_keyword_classifier` — it reads
       human_parent_label and computes real accuracy/calibration once rows
       are non-empty; it already prints "0 labeled rows" honestly if not.

Run:
    python3 -m src.build_gold_sample
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

try:
    from src.classify_by_keywords import ARTIFACT_TOPIC_ID, CURATED_PATH
except ImportError:  # run from within src/
    from classify_by_keywords import ARTIFACT_TOPIC_ID, CURATED_PATH

import json

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
GOLD_DIR = REPO_ROOT / "data" / "gold"
GOLD_PATH = GOLD_DIR / "topic_gold_set.csv"
PREDICTIONS_PATH = GOLD_DIR / "topic_gold_set_predictions.csv"

N_TOTAL = 180
NOISE_WITH_TEXT_SHARE = 1 / 3  # deliberate oversample, per the plan
SEED = 42

# Collapse the long tail of agencies into a small number of strata buckets —
# 180 rows split across 15+ raw agency values x 2 x 2 would leave most cells
# with 0-1 rows, defeating "by stratum" reporting entirely.
AGENCY_BUCKETS = {
    "National Science Foundation": "NSF",
    "National Institutes of Health": "NIH",
    "National Institutes of Health - SubAward": "NIH",
    "Office of Naval Research": "ONR",
    "Army Research Office": "ARO",
    "Air Force Research Office": "AFRO",
}


def _agency_bucket(name: str) -> str:
    return AGENCY_BUCKETS.get(name, "Other")


def _abstract_preview(abstract: str, n: int = 400) -> str:
    a = str(abstract or "").strip()
    return (a[:n] + "…") if len(a) > n else a


def build_population() -> pd.DataFrame:
    kw = pd.read_parquet(PROC / "topic_keyword_assignments.parquet")
    kw = kw[~kw["is_extra"]].copy()
    kw["doc_id"] = kw["doc_id"].astype(str)

    ta = pd.read_parquet(PROC / "topic_assignments.parquet")
    ta["doc_id"] = ta["doc_id"].astype(str)
    ta = ta[["doc_id", "topic_id", "is_noise"]].rename(columns={"topic_id": "bertopic_topic_id_gold"})

    gr = pd.read_parquet(PROC / "grants.parquet")
    gr["grant_id"] = gr["grant_id"].astype(str)
    title_col = "title_from_abstract" if "title_from_abstract" in gr.columns else "grantname"
    gr["_title"] = gr[title_col].where(gr[title_col].astype(str).str.len() > 0, gr["grantname"]).fillna("").astype(str)

    df = kw.merge(gr, left_on="doc_id", right_on="grant_id", how="inner")
    df = df.merge(ta, on="doc_id", how="left")

    df["text_availability"] = df["abstract"].fillna("").astype(str).str.len().gt(0).map(
        {True: "abstract", False: "title_only"})
    noise_like = df["bertopic_topic_id_gold"].isna() | df["bertopic_topic_id_gold"].isin([-1, ARTIFACT_TOPIC_ID])
    df["bertopic_status"] = noise_like.map({True: "noise", False: "assigned"})
    df["agency_bucket"] = df["agencyname"].map(_agency_bucket)
    df["stratum"] = (df["agency_bucket"] + "|" + df["text_availability"] + "|" + df["bertopic_status"])
    return df


def sample_gold_set(df: pd.DataFrame, n_total: int = N_TOTAL, seed: int = SEED) -> pd.DataFrame:
    rng = random.Random(seed)

    noise_with_text = df[(df["bertopic_status"] == "noise") & (df["text_availability"] == "abstract")]
    n_noise_with_text = min(len(noise_with_text), round(n_total * NOISE_WITH_TEXT_SHARE))
    picked_idx = set(rng.sample(list(noise_with_text.index), n_noise_with_text)) if n_noise_with_text else set()

    remaining_pool = df.drop(index=picked_idx)
    n_remaining = n_total - len(picked_idx)
    strata_sizes = remaining_pool.groupby("stratum").size()
    total_remaining_pool = len(remaining_pool)

    for stratum, group in remaining_pool.groupby("stratum"):
        # Proportional allocation to population share, floor'd, at least 1
        # if the stratum has anything at all — every real stratum should be
        # represented, per "reports ... by stratum".
        share = strata_sizes[stratum] / total_remaining_pool if total_remaining_pool else 0
        quota = max(1, round(n_remaining * share)) if len(group) else 0
        quota = min(quota, len(group))
        picked_idx |= set(rng.sample(list(group.index), quota))

    picked_idx = list(picked_idx)
    # Trim/pad to exactly n_total where the pool allows (rounding above can
    # over/undershoot by a few rows).
    if len(picked_idx) > n_total:
        picked_idx = rng.sample(picked_idx, n_total)
    elif len(picked_idx) < n_total:
        leftover = list(set(df.index) - set(picked_idx))
        picked_idx += rng.sample(leftover, min(n_total - len(picked_idx), len(leftover)))

    return df.loc[picked_idx].copy()


def main() -> None:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    df = build_population()
    sample = sample_gold_set(df)

    curated = json.loads(CURATED_PATH.read_text())
    parent_labels = sorted(p["label"] for p in curated["parents"].values())

    gold = pd.DataFrame({
        "grant_id": sample["grant_id"],
        "title": sample["_title"],
        "abstract_preview": sample["abstract"].map(_abstract_preview),
        "agency": sample["agencyname"],
        "stratum": sample["stratum"],
        "human_parent_label": "",  # <-- fill by hand, blind, one of parent_labels below
    }).sort_values("grant_id")
    gold.to_csv(GOLD_PATH, index=False)

    predictions = pd.DataFrame({
        "grant_id": sample["grant_id"],
        "kw_parent_label": sample["kw_parent_label"],
        "kw_leaf_label": sample["kw_leaf_label"],
        "conf_tier": sample["conf_tier"],
        "bertopic_topic_id": sample["bertopic_topic_id_gold"],
    }).sort_values("grant_id")
    predictions.to_csv(PREDICTIONS_PATH, index=False)

    print(f"wrote {GOLD_PATH} ({len(gold)} rows) — human_parent_label is EMPTY, not yet labeled")
    print(f"wrote {PREDICTIONS_PATH} ({len(predictions)} rows) — DO NOT open while labeling (see docstring)")
    print(f"\nvalid human_parent_label values (the 7 curated parents):")
    for label in parent_labels:
        print(f"  - {label}")
    print(f"\nstratum counts in the drawn sample:")
    print(sample["stratum"].value_counts().to_string())


if __name__ == "__main__":
    main()
