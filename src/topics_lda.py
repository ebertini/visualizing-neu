"""
topics_lda.py — LEGACY LDA topic model (k=8), extracted from
notebooks/06_research_topics.ipynb.

Kept only so the report notebook can regenerate the compendium's k=8 numbers
for continuity after BERTopic (src/topics_bertopic.py) becomes canonical — see
docs/TOPIC_WORK_FORWARD_PLAN.md (M1 / M5b / M5f). NOT used by EnricoVis.

Faithful to nb06:
  - cleaning:   src.clean_text.clean_for_lda + length filter (>=200 chars, >=40 tokens)
  - vectorizer: CountVectorizer(max_df=0.6, min_df=15, stop_words='english',
                ngram_range=(1,2), token_pattern=r'(?u)\\b[a-z]{3,}\\b')
                then drop any token whose parts are all in DOMAIN_STOPS
  - model:      LatentDirichletAllocation(k=8, learning_method='batch',
                max_iter=50, random_state=42)

Typical use:
    import pandas as pd
    from src import topics_lda
    grants = pd.read_parquet("data/processed/grants.parquet")
    res = topics_lda.run(grants)          # dict with model, docs, top_words, ...
    res["docs"][["grant_id", "topic", "topic_label", "topic_prob"]]

WARNING — LDA topic ids are assigned arbitrarily and reshuffle on any change to
the corpus, seed, or preprocessing. `TOPIC_LABELS` below is hand-curated for the
current grants.parquet fit; re-inspect `top_words(...)` and rewrite the labels
after any re-fit. (This drift is exactly why the plan moves to BERTopic.)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

try:
    from src.clean_text import DOMAIN_STOPS, clean_for_lda, passes_length_filter
except ImportError:  # run as a script from within src/
    from clean_text import DOMAIN_STOPS, clean_for_lda, passes_length_filter

K_DEFAULT = 8
SEED = 42
MAX_ITER = 50

# Hand-curated labels for the current grants.parquet fit (nb06 cell 13).
# Re-inspect top_words() and rewrite these after any re-fit.
TOPIC_LABELS = {
    0: "Mathematics & theoretical physics",
    1: "Biomedical (drug/disease/cancer)",
    2: "Software, data & ML systems",
    3: "Cell & molecular biology",
    4: "Environmental & public health",
    5: "Hardware, energy & wireless systems",
    6: "HCI, learning & applied research",
    7: "STEM education & outreach",
}


def preprocess(grants: pd.DataFrame) -> pd.DataFrame:
    """Select model-worthy grants and add a `clean` column.

    Mirrors nb06: keep grants whose raw abstract is >200 chars, clean them, then
    keep only those with >=40 cleaned tokens. Returns a copy of the surviving
    grant rows (all original columns preserved) plus `clean`.
    """
    df = grants.copy()
    df["abstract"] = df["abstract"].fillna("").astype(str)
    df = df[df["abstract"].str.len() > 200].copy()
    df["clean"] = df["abstract"].map(clean_for_lda)
    df = df[df["clean"].str.split().str.len() >= 40].reset_index(drop=True)
    return df


def build_dtm(clean_texts) -> tuple[np.ndarray, np.ndarray, CountVectorizer]:
    """Vectorize cleaned abstracts and drop DOMAIN_STOPS-only tokens.

    Returns (X, vocab, vectorizer). X is the DOMAIN_STOPS-filtered doc-term
    matrix; vocab is the parallel term array.
    """
    vec = CountVectorizer(
        max_df=0.6, min_df=15, stop_words="english",
        ngram_range=(1, 2), token_pattern=r"(?u)\b[a-z]{3,}\b",
    )
    X = vec.fit_transform(clean_texts)
    vocab = np.array(vec.get_feature_names_out())
    # Drop any token whose parts are ALL in DOMAIN_STOPS
    keep = np.array([not all(w in DOMAIN_STOPS for w in v.split()) for v in vocab])
    return X[:, keep], vocab[keep], vec


def fit(X, k: int = K_DEFAULT, seed: int = SEED, max_iter: int = MAX_ITER) -> LatentDirichletAllocation:
    lda = LatentDirichletAllocation(
        n_components=k, learning_method="batch", max_iter=max_iter, random_state=seed,
    )
    lda.fit(X)
    return lda


def top_words(lda: LatentDirichletAllocation, vocab: np.ndarray, n: int = 12) -> list[list[str]]:
    """Top-n terms per topic, highest weight first."""
    return [[vocab[i] for i in np.argsort(row)[::-1][:n]] for row in lda.components_]


def umass_coherence(lda: LatentDirichletAllocation, X, n_top: int = 10, eps: float = 1.0) -> np.ndarray:
    """UMass coherence per topic (sklearn-only; no gensim). Less negative = better."""
    binary = (X > 0).astype(np.int8)
    doc_count = np.asarray(binary.sum(axis=0)).ravel()
    scores = []
    for row in lda.components_:
        top = np.argsort(row)[::-1][:n_top]
        s, count = 0.0, 0
        for i in range(1, len(top)):
            for j in range(i):
                co = binary[:, top[i]].multiply(binary[:, top[j]]).sum()
                s += np.log((co + eps) / doc_count[top[j]])
                count += 1
        scores.append(s / max(count, 1))
    return np.array(scores)


def assign(lda: LatentDirichletAllocation, X, docs: pd.DataFrame,
           labels: dict[int, str] | None = None) -> pd.DataFrame:
    """Add topic / topic_prob / topic_label columns to `docs` (in place, returns it)."""
    labels = labels if labels is not None else TOPIC_LABELS
    doc_topic = lda.transform(X)
    docs["topic"] = doc_topic.argmax(axis=1)
    docs["topic_prob"] = doc_topic.max(axis=1)
    docs["topic_label"] = docs["topic"].map(labels)
    return docs


def run(grants: pd.DataFrame, k: int = K_DEFAULT, seed: int = SEED) -> dict:
    """End-to-end convenience: preprocess -> DTM -> fit -> assign.

    Returns a dict with keys: docs, model, X, vocab, vectorizer, top_words,
    coherence. `docs` carries the topic assignment columns.
    """
    docs = preprocess(grants)
    X, vocab, vec = build_dtm(docs["clean"])
    lda = fit(X, k=k, seed=seed)
    docs = assign(lda, X, docs)
    return {
        "docs": docs,
        "model": lda,
        "X": X,
        "vocab": vocab,
        "vectorizer": vec,
        "top_words": top_words(lda, vocab),
        "coherence": umass_coherence(lda, X),
    }
