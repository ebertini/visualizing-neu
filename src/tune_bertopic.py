"""
tune_bertopic.py — M3 of docs/TOPIC_WORK_FORWARD_PLAN.md.

Sweep HDBSCAN `min_cluster_size` over several values x 3 seeds on the unified
corpus (grants + M2 orphan pseudo-docs), reporting per configuration:
  - number of topics (excl. the -1 noise cluster)
  - %-noise (size of -1 / N)
  - largest topic size
  - mean intra-cluster cosine similarity

Reads the cached SPECTER2 embeddings (regenerate them AFTER M2 with
`python -m src.build_specter2_embeddings`). Local-only (no HF network needed at
sweep time — embeddings are precomputed).

Run:
    python -m src.tune_bertopic

Writes:
    outputs/bertopic_sweep.json    (per-run + per-size aggregates)
"""
from __future__ import annotations

import json
import statistics as st

from src.topics_bertopic import OUTPUTS, _load_docs_aligned_to_cache, fit

SIZES = [15, 20, 25, 30, 40]
SEEDS = [42, 7, 123]
METRICS = ["n_topics", "pct_noise", "largest_topic_size", "mean_intra_cluster_cosine"]


def main() -> None:
    docs, ids, emb = _load_docs_aligned_to_cache()
    print(f"sweep on {len(docs)} docs / embeddings {emb.shape}\n")

    runs = []
    for mcs in SIZES:
        for seed in SEEDS:
            _, d = fit(docs, emb, seed=seed, min_cluster_size=mcs)
            runs.append({"min_cluster_size": mcs, "seed": seed, **{k: d[k] for k in METRICS}})
            print(f"  mcs={mcs:>2} seed={seed:>3}: topics={d['n_topics']:>2}  "
                  f"noise={d['pct_noise']:>5}%  largest={d['largest_topic_size']:>4}  "
                  f"intra={d['mean_intra_cluster_cosine']}")

    by_size = {}
    for mcs in SIZES:
        sub = [r for r in runs if r["min_cluster_size"] == mcs]
        by_size[mcs] = {
            "n_topics_mean": round(st.mean(r["n_topics"] for r in sub), 1),
            "n_topics_std": round(st.pstdev([r["n_topics"] for r in sub]), 1),
            "pct_noise_mean": round(st.mean(r["pct_noise"] for r in sub), 1),
            "largest_mean": round(st.mean(r["largest_topic_size"] for r in sub)),
            "intra_mean": round(st.mean(r["mean_intra_cluster_cosine"] for r in sub), 4),
        }

    OUTPUTS.mkdir(exist_ok=True)
    (OUTPUTS / "bertopic_sweep.json").write_text(
        json.dumps({"n_docs": len(docs), "seeds": SEEDS, "runs": runs, "by_size": by_size}, indent=2))

    print("\n=== SWEEP SUMMARY (mean across 3 seeds) ===")
    print(f"{'mcs':>4} | {'topics':>10} | {'noise%':>6} | {'largest':>7} | {'intra':>6}")
    print("-" * 48)
    for mcs in SIZES:
        a = by_size[mcs]
        topics = f"{a['n_topics_mean']}±{a['n_topics_std']}"
        print(f"{mcs:>4} | {topics:>10} | {a['pct_noise_mean']:>6} | {a['largest_mean']:>7} | {a['intra_mean']:>6}")
    print("\nwrote outputs/bertopic_sweep.json")


if __name__ == "__main__":
    main()
