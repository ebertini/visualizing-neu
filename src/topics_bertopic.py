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
    data/processed/specter2_umap_2d.npy    2-D UMAP of the same embeddings, for the
                                            viz only (n_components=5 above feeds
                                            HDBSCAN; this is a separate fit, same
                                            seed) — closes a gap where this file
                                            previously had no producing script
                                            (src/build_viz_data.py:72 reads it)
    outputs/bertopic_diagnostics.json      cluster sizes, %-noise, intra-cosine, seed
    outputs/topic_labels.json              SEED ONLY, written if absent: every topic's
                                            label defaults to its c-TF-IDF top-3 terms,
                                            parent defaults to null (Unassigned) — see
                                            docs/TOPIC_MODEL_REFIT_CHECKLIST.md. Never
                                            overwrites an existing (possibly hand-
                                            curated) file.
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
    from src.clean_text import DOMAIN_STOPS, model_doc_halves
except ImportError:  # run from within src/
    from clean_text import DOMAIN_STOPS, model_doc_halves

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
    # min_df=2 on the per-topic c-TF-IDF documents: light singleton/typo filtering
    # while keeping terms distinctive to a few topics. Higher values (e.g. 5) crash
    # on coarse configs where the topic count drops below the threshold.
    return CountVectorizer(stop_words=stops, ngram_range=(1, 2), min_df=2)


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
    # A null title_from_abstract passes the .where() condition above (NaN's
    # str() is "nan", which has length 3), so it needs its own fillna rather
    # than relying on the .where() alone — found while auditing this file
    # against build_specter2_embeddings.py's matching logic, which already
    # had this fillna. 0 nulls in the current corpus, but cheap to close.
    gr["_title"] = gr["_title"].fillna("").astype(str)
    gr["abstract"] = gr["abstract"].fillna("").astype(str)
    # Mask LOW_TRUST_ABSTRACT_SOURCES text (e.g. nih_reporter_parent) so the
    # doc-text BERTopic sees for c-TF-IDF keyword extraction matches what
    # build_specter2_embeddings.py already embedded — a grant tagged
    # low-trust reads as title-only in both places, not just one.
    # by_id stores RAW (title, abstract, abstract_source) — model_doc_halves
    # does the masking + cleaning in one place at doc-build time below, so
    # this and build_specter2_embeddings.py can't drift on how they treat
    # LOW_TRUST_ABSTRACT_SOURCES or NaN titles.
    src = gr["abstract_source"].fillna("").astype(str) if "abstract_source" in gr.columns \
        else pd.Series([""] * len(gr), index=gr.index)
    by_id = {gid: (t, a, s) for gid, t, a, s in zip(gr["grant_id"], gr["_title"], gr["abstract"], src)}

    # M2 orphan pseudo-docs ('orphan-<id>') live in extra_neu_abstracts, not grants.
    extra_path = PROC / "extra_neu_abstracts.parquet"
    if extra_path.exists():
        ex = pd.read_parquet(extra_path)
        ex_src = ex["abstract_source"].fillna("").astype(str) if "abstract_source" in ex.columns \
            else pd.Series([""] * len(ex), index=ex.index)
        for did, t, a, s in zip(ex["doc_id"], ex["title"], ex["abstract"], ex_src):
            by_id[str(did)] = (t, a, s)

    docs, missing = [], 0
    for did in ids:
        if did in by_id:
            t, a, s = by_id[did]
            title, abstract = model_doc_halves(t, a, s)
            docs.append(f"{title}. {abstract}".strip())
        else:
            docs.append("")  # keep alignment; should not happen if cache is fresh
            missing += 1
    if missing:
        print(f"WARNING: {missing} cache ids not found in grants/extras (cache stale?)")
    if len(docs) != len(embeddings):
        raise ValueError(f"docs ({len(docs)}) and embeddings ({len(embeddings)}) misaligned")
    return docs, ids, embeddings


def _save_umap_2d(embeddings: np.ndarray, seed: int = SEED) -> None:
    """Fit + persist a SEPARATE 2-D UMAP of the same embeddings, for the viz only.

    Distinct from the n_components=5 UMAP `fit()` uses to feed HDBSCAN (that one
    is never persisted — it's an internal step of the BERTopic pipeline). This is
    plotting-only, unconditionally overwritten on every run (same pattern as
    src/build_specter2_embeddings.py's cache), and is what src/build_viz_data.py
    reads to place points on the grant_atlas / topic_islands scatterplots.
    """
    umap_2d = UMAP(
        n_components=2, n_neighbors=15, min_dist=0.0,
        metric="cosine", random_state=seed,
    ).fit_transform(embeddings)
    out = PROC / "specter2_umap_2d.npy"
    np.save(out, umap_2d)
    print(f"wrote {out}  {umap_2d.shape}")


def _seed_topic_labels(topic_model: BERTopic) -> dict:
    """Build a SEED outputs/topic_labels.json — every topic's c-TF-IDF top terms
    as its label, no parent grouping. Schema matches what src/build_viz_data.py
    reads (labels["_meta"]["n_topics"], labels["topics"][str(id)]["label"/"top_terms"/
    "parent"], labels["parents"][pid]["label"/"topic_ids"]).

    This is a bootstrap, not a substitute for curation: parent-theme grouping and
    nicer labels are a deliberate, optional human pass on top (see
    docs/TOPIC_MODEL_REFIT_CHECKLIST.md) — this just guarantees the file is always
    valid and buildable immediately after a fit, with zero manual steps required.
    """
    all_topics = topic_model.get_topics()  # {topic_id: [(word, score), ...]}
    topic_ids = sorted(tid for tid in all_topics if tid != -1)
    topics_meta = {}
    for tid in topic_ids:
        words = [w for w, _score in all_topics[tid]]
        label = ", ".join(words[:3]) if words else f"Topic {tid}"
        topics_meta[str(tid)] = {"label": label, "top_terms": words[:10], "parent": None}
    topics_meta["-1"] = {"label": "Unassigned / noise", "top_terms": [], "parent": None}
    return {"_meta": {"n_topics": len(topic_ids)}, "topics": topics_meta, "parents": {}}


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
        "doc_id": ids,                               # grant_id, or 'orphan-<id>' for extras
        "topic_id": topics,
        "is_noise": [t == -1 for t in topics],
        "is_extra": [str(i).startswith("orphan-") for i in ids],
    })
    assignments.to_parquet(PROC / "topic_assignments.parquet", index=False)
    print(f"wrote {PROC / 'topic_assignments.parquet'}  ({len(assignments)} rows)")

    (OUTPUTS / "bertopic_diagnostics.json").write_text(json.dumps(diagnostics, indent=2))
    print(f"wrote {OUTPUTS / 'bertopic_diagnostics.json'}")
    print(f"  topics={diagnostics['n_topics']}  noise={diagnostics['pct_noise']}%  "
          f"intra-cosine={diagnostics['mean_intra_cluster_cosine']}")

    _save_umap_2d(embeddings)

    labels_path = OUTPUTS / "topic_labels.json"
    if labels_path.exists():
        print(f"{labels_path} already exists — leaving it alone (may be hand-curated). "
              "Delete it first if you want a fresh auto-generated seed.")
    else:
        labels_path.write_text(json.dumps(_seed_topic_labels(topic_model), indent=2))
        print(f"wrote {labels_path}  (seed: c-TF-IDF labels, no parent grouping yet — "
              "see docs/TOPIC_MODEL_REFIT_CHECKLIST.md)")


if __name__ == "__main__":
    main()
