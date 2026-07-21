"""
topics_bertopic.py — CANONICAL topic model: BERTopic over precomputed SPECTER2
embeddings (SPECTER2 -> UMAP -> HDBSCAN -> c-TF-IDF).

M1 of docs/TOPIC_WORK_FORWARD_PLAN.md. Uses the *offline embedding path*: we
pass the cached SPECTER2 vectors (data/processed/specter2_embeddings.npy) to
`BERTopic.fit_transform(docs, embeddings=X)`, so no HuggingFace / torch call
happens at fit time. Clustering is driven by the embeddings; the doc text is
used only for c-TF-IDF topic keywords.

CANNOT run in CI / any sandbox — depends on the cached .npy which is produced
by src/build_specter2_embeddings.py on a local machine (see plan §5.11). Fitting
BERTopic itself (umap-learn / hdbscan) is local-only too.

Run:
    python -m src.build_specter2_embeddings     # once, to produce the cache
    python -m src.topics_bertopic                # fits + writes model/diagnostics

Writes:
    data/processed/bertopic_model/         (BERTopic.save, pickle)
    data/processed/topic_assignments.parquet   grant_id -> topic_id, is_noise
    outputs/bertopic_diagnostics.json      cluster sizes, %-noise, intra-cosine, seed
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

# Heavy, local-only deps — imported lazily-ish at module top so a plain import
# fails loudly in an environment that hasn't installed them (that's intended).
from bertopic import BERTopic
from hdbscan import HDBSCAN
from umap import UMAP

try:
    from src.clean_text import DOMAIN_STOPS, clean_abstract, clean_title
except ImportError:  # run from within src/
    from clean_text import DOMAIN_STOPS, clean_abstract, clean_title

SEED = 42
MIN_CLUSTER_SIZE = 25
UMAP_N_COMPONENTS = 5      # 5-D UMAP feeds HDBSCAN (2-D is only for the viz)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
OUTPUTS = REPO_ROOT / "outputs"


def default_vectorizer() -> CountVectorizer:
    """c-TF-IDF vectorizer: English + DOMAIN_STOPS, unigrams+bigrams.

    Keeps topic keywords consistent with the LDA track's vocabulary controls.
    """
    stops = list(ENGLISH_STOP_WORDS | set(DOMAIN_STOPS))
    return CountVectorizer(stop_words=stops, ngram_range=(1, 2), min_df=5)


def _diagnostics(topics: list[int], embeddings: np.ndarray,
                 min_cluster_size: int, seed: int) -> dict:
    """Cluster sizes, %-noise, and mean intra-cluster cosine similarity."""
    t = np.asarray(topics)
    n = len(t)
    n_noise = int((t == -1).sum())
    sizes = {int(k): int((t == k).sum()) for k in sorted(set(t.tolist()))}

    # Mean intra-cluster cosine: for each non-noise cluster, average cosine of
    # each member to the (unit-normalized) cluster centroid, then average across
    # clusters (size-weighted).
    norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9)
    per_cluster, weights = [], []
    for k in sizes:
        if k == -1:
            continue
        members = norm[t == k]
        if len(members) < 2:
            continue
        centroid = members.mean(axis=0)
        centroid /= np.linalg.norm(centroid) + 1e-9
        per_cluster.append(float((members @ centroid).mean()))
        weights.append(len(members))
    mean_intra = (
        float(np.average(per_cluster, weights=weights)) if per_cluster else float("nan")
    )

    return {
        "seed": seed,
        "min_cluster_size": min_cluster_size,
        "n_docs": n,
        "n_topics": len([k for k in sizes if k != -1]),
        "n_noise": n_noise,
        "pct_noise": round(100 * n_noise / max(n, 1), 2),
        "largest_topic_size": max((v for k, v in sizes.items() if k != -1), default=0),
        "mean_intra_cluster_cosine": round(mean_intra, 4),
        "cluster_sizes": sizes,
    }


def fit(docs, embeddings, seed: int = SEED, min_cluster_size: int = MIN_CLUSTER_SIZE,
        vectorizer_model: CountVectorizer | None = None) -> tuple[BERTopic, dict]:
    """Fit BERTopic on precomputed `embeddings` (offline path).

    Parameters
    ----------
    docs : list[str]            cleaned documents, aligned 1:1 with `embeddings`
    embeddings : np.ndarray     (N, D) precomputed SPECTER2 vectors
    seed : int                  UMAP random_state (determinism)
    min_cluster_size : int      HDBSCAN min_cluster_size (the key granularity knob)

    Returns (fitted BERTopic, diagnostics dict).
    """
    umap_model = UMAP(
        n_components=UMAP_N_COMPONENTS, n_neighbors=15, min_dist=0.0,
        metric="cosine", random_state=seed,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=min_cluster_size, metric="euclidean",
        cluster_selection_method="eom", prediction_data=True,
    )
    topic_model = BERTopic(
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model or default_vectorizer(),
        calculate_probabilities=False,
        verbose=True,
    )
    topics, _ = topic_model.fit_transform(docs, embeddings=np.asarray(embeddings))
    return topic_model, _diagnostics(topics, np.asarray(embeddings), min_cluster_size, seed)


def _load_docs_aligned_to_cache() -> tuple[list[str], list[str], np.ndarray]:
    """Load cached embeddings + build cleaned docs in the SAME order as the cache."""
    vec_path, ids_path = PROC / "specter2_embeddings.npy", PROC / "specter2_ids.txt"
    if not vec_path.exists() or not ids_path.exists():
        raise FileNotFoundError(
            f"Missing SPECTER2 cache ({vec_path.name} / {ids_path.name}). "
            "Run `python -m src.build_specter2_embeddings` locally first."
        )
    embeddings = np.load(vec_path)
    ids = ids_path.read_text().splitlines()

    gr = pd.read_parquet(PROC / "grants.parquet")
    gr["grant_id"] = gr["grant_id"].astype(str)
    title_col = "title_from_abstract" if "title_from_abstract" in gr.columns else "grantname"
    gr["_title"] = gr[title_col].where(gr[title_col].astype(str).str.len() > 0, gr["grantname"])
    gr["abstract"] = gr["abstract"].fillna("").astype(str)
    by_id = gr.set_index("grant_id")

    docs: list[str] = []
    for gid in ids:
        if gid in by_id.index:
            row = by_id.loc[gid]
            ct, ca = clean_title(row["_title"]), clean_abstract(row["abstract"])
            docs.append(f"{ct}. {ca}".strip())
        else:
            docs.append("")  # keep alignment; should not happen if cache is fresh
    if len(docs) != len(embeddings):
        raise ValueError(f"docs ({len(docs)}) and embeddings ({len(embeddings)}) misaligned")
    return docs, ids, embeddings


def main() -> None:
    docs, ids, embeddings = _load_docs_aligned_to_cache()
    print(f"fitting BERTopic on {len(docs)} docs / {embeddings.shape} embeddings...")
    topic_model, diagnostics = fit(docs, embeddings)

    OUTPUTS.mkdir(exist_ok=True)
    model_dir = PROC / "bertopic_model"
    topic_model.save(str(model_dir), serialization="pickle")
    print(f"wrote {model_dir}/")

    topics = topic_model.topics_
    assignments = pd.DataFrame({
        "grant_id": ids,
        "topic_id": topics,
        "is_noise": [t == -1 for t in topics],
    })
    assignments.to_parquet(PROC / "topic_assignments.parquet", index=False)
    print(f"wrote {PROC / 'topic_assignments.parquet'}  ({len(assignments)} rows)")

    (OUTPUTS / "bertopic_diagnostics.json").write_text(json.dumps(diagnostics, indent=2))
    print(f"wrote {OUTPUTS / 'bertopic_diagnostics.json'}")
    print(f"  topics={diagnostics['n_topics']}  noise={diagnostics['pct_noise']}%  "
          f"intra-cosine={diagnostics['mean_intra_cluster_cosine']}")


if __name__ == "__main__":
    main()
