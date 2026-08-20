"""Compute SPECTER2 embeddings for every grant that has abstract text.

Run once. Re-run (and BUST the existing cache) whenever grants.parquet OR
src/clean_text.py changes — the text fed to SPECTER2 now passes through the
shared cleaner, so a cleaner change invalidates cached vectors.

Cannot run in CI / any sandbox without HuggingFace network access; this is a
local-machine step (see docs/TOPIC_WORK_FORWARD_PLAN.md §5.11).

Outputs:
  data/processed/specter2_embeddings.npy      – (N, 768) float32 array
  data/processed/specter2_ids.txt             – parallel list of `grant_id`s
  data/processed/specter2_doc_manifest.parquet – row-aligned with the ids above:
      doc_id, title_chars, abstract_chars, abstract_source — a cheap record
      of exactly what reached the tokenizer, so a light-deps test can verify
      grants with abstract_source in clean_text.LOW_TRUST_ABSTRACT_SOURCES
      (e.g. nih_reporter_parent) were actually embedded title-only.
"""
from __future__ import annotations
import time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

# Import the shared cleaner whether run as a script (`python src/build_..._.py`)
# or as a module (`python -m src.build_specter2_embeddings`).
try:
    from src.clean_text import clean_abstract, clean_title, usable_abstract
except ImportError:  # run as a script: src/ is already on sys.path[0]
    from clean_text import clean_abstract, clean_title, usable_abstract

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
OUT_VEC = PROC / "specter2_embeddings.npy"
OUT_IDS = PROC / "specter2_ids.txt"
OUT_MANIFEST = PROC / "specter2_doc_manifest.parquet"
BATCH = 8
MAX_LEN = 512

def main() -> None:
    print("loading model...")
    tok = AutoTokenizer.from_pretrained("allenai/specter2_base")
    model = AutoAdapterModel.from_pretrained("allenai/specter2_base")
    model.load_adapter("allenai/specter2", source="hf", load_as="proximity", set_active=True)
    model.set_active_adapters("proximity")
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    print(f"model loaded, device={device}")

    gr = pd.read_parquet(PROC / "grants.parquet")
    gr["grant_id"] = gr["grant_id"].astype(str)
    # Prefer the (typically longer) abstract-side title if present
    if "title_from_abstract" in gr.columns:
        gr["_title"] = gr["title_from_abstract"].where(
            gr["title_from_abstract"].astype(str).str.len() > 0, gr["grantname"])
    else:
        gr["_title"] = gr["grantname"]
    gr["abstract"] = gr["abstract"].fillna("").astype(str)
    gr["_title"]   = gr["_title"].fillna("").astype(str)
    # Mask out LOW_TRUST_ABSTRACT_SOURCES text (e.g. nih_reporter_parent — a
    # subaward's borrowed parent-center abstract) BEFORE the length filter
    # below, so those grants fall through to title-only encoding exactly as
    # if the abstract were never recovered. The real text stays in
    # grants.parquet for display; only this modeling copy is masked.
    if "abstract_source" in gr.columns:
        src = gr["abstract_source"].fillna("").astype(str)
        gr["abstract"] = [usable_abstract(a, s) for a, s in zip(gr["abstract"], src)]
    # Encode any grant with either a title or a substantive abstract
    gr = gr[(gr["_title"].str.len() > 0) | (gr["abstract"].str.len() >= 50)]

    # doc_id is the canonical key: grant_id for grants, 'orphan-<id>' for the M2
    # extra_neu_abstracts pseudo-docs (recovered orphan abstracts with a resolved
    # faculty but no matching NEU grant). BERTopic (M3) sees the union.
    gr_source = gr["abstract_source"].fillna("").astype(str) if "abstract_source" in gr.columns \
        else pd.Series([""] * len(gr), index=gr.index)
    corpus = pd.DataFrame({
        "doc_id": gr["grant_id"], "_title": gr["_title"], "abstract": gr["abstract"],
        "abstract_source": gr_source,
    })
    extra_path = PROC / "extra_neu_abstracts.parquet"
    if extra_path.exists():
        ex = pd.read_parquet(extra_path)
        ex_source = ex["abstract_source"].fillna("").astype(str) if "abstract_source" in ex.columns \
            else pd.Series([""] * len(ex), index=ex.index)
        ex_abstract = [usable_abstract(a, s) for a, s in
                       zip(ex["abstract"].fillna("").astype(str), ex_source)]
        ex_corpus = pd.DataFrame({
            "doc_id": ex["doc_id"].astype(str),
            "_title": ex["title"].fillna("").astype(str),
            "abstract": ex_abstract,
            "abstract_source": ex_source,
        })
        corpus = pd.concat([corpus, ex_corpus], ignore_index=True)
        print(f"corpus = {len(gr)} grants + {len(ex_corpus)} orphan pseudo-docs = {len(corpus)}")
    else:
        print(f"corpus = {len(gr)} grants (no extra_neu_abstracts.parquet found)")
    corpus = corpus.reset_index(drop=True)

    # Clean once, up front, with the shared cleaner. Funding-mechanism boilerplate
    # and mangled markup are out-of-distribution noise for SPECTER2 (trained on
    # published-paper prose), so we strip them BEFORE encoding — not just for LDA.
    corpus["_title_clean"] = corpus["_title"].map(clean_title)
    corpus["_abstract_clean"] = corpus["abstract"].map(clean_abstract)
    print(f"encoding {len(corpus)} documents (cleaned via src/clean_text.py)...")

    ids: list[str] = []
    vecs: list[np.ndarray] = []
    sep = tok.sep_token
    t0 = time.time()
    for start in range(0, len(corpus), BATCH):
        chunk = corpus.iloc[start : start + BATCH]
        texts = [f"{t}{sep}{a}" for t, a in zip(chunk["_title_clean"], chunk["_abstract_clean"])]
        inputs = tok(texts, padding=True, truncation=True, return_tensors="pt",
                     return_token_type_ids=False, max_length=MAX_LEN).to(device)
        with torch.no_grad():
            out = model(**inputs)
        emb = out.last_hidden_state[:, 0, :].detach().cpu().numpy().astype(np.float32)
        vecs.append(emb)
        ids.extend(chunk["doc_id"].astype(str).tolist())
        if start % (BATCH * 20) == 0:
            elapsed = time.time() - t0
            rate = (start + BATCH) / max(elapsed, 0.1)
            eta = (len(corpus) - start) / max(rate, 0.1)
            print(f"  {start + len(chunk):5d}/{len(corpus)}  "
                  f"({rate:.1f} docs/s, ETA {eta / 60:.1f} min)")

    X = np.vstack(vecs)
    print(f"final shape: {X.shape}  ({time.time() - t0:.1f}s total)")
    np.save(OUT_VEC, X)
    OUT_IDS.write_text("\n".join(ids))

    # Cheap, row-aligned record of exactly what reached the tokenizer — lets
    # a light-deps test (tests/test_low_trust_exclusion.py) confirm
    # LOW_TRUST_ABSTRACT_SOURCES grants were actually embedded title-only,
    # without needing torch/HF to re-derive it.
    manifest = pd.DataFrame({
        "doc_id": corpus["doc_id"].astype(str),
        "title_chars": corpus["_title_clean"].str.len(),
        "abstract_chars": corpus["_abstract_clean"].str.len(),
        "abstract_source": corpus["abstract_source"],
    })
    manifest.to_parquet(OUT_MANIFEST, index=False)
    print(f"wrote {OUT_MANIFEST}")
    print(f"wrote {OUT_VEC}  ({OUT_VEC.stat().st_size / 1e6:.1f} MB)")
    print(f"wrote {OUT_IDS}")


if __name__ == "__main__":
    main()
