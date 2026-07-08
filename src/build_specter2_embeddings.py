"""Compute SPECTER2 embeddings for every grant that has abstract text.

Run once. Re-run only when grants.parquet changes.

Outputs:
  data/processed/specter2_embeddings.npy   – (N, 768) float32 array
  data/processed/specter2_ids.txt          – parallel list of `grant_id`s
"""
from __future__ import annotations
import time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
OUT_VEC = PROC / "specter2_embeddings.npy"
OUT_IDS = PROC / "specter2_ids.txt"
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

    # Encode any grant with either a title or a substantive abstract
    gr = gr[(gr["_title"].str.len() > 0) | (gr["abstract"].str.len() >= 50)].reset_index(drop=True)
    print(f"encoding {len(gr)} grants...")

    ids: list[str] = []
    vecs: list[np.ndarray] = []
    sep = tok.sep_token
    t0 = time.time()
    for start in range(0, len(gr), BATCH):
        chunk = gr.iloc[start : start + BATCH]
        texts = [f"{t}{sep}{a}" for t, a in zip(chunk["_title"], chunk["abstract"])]
        inputs = tok(texts, padding=True, truncation=True, return_tensors="pt",
                     return_token_type_ids=False, max_length=MAX_LEN).to(device)
        with torch.no_grad():
            out = model(**inputs)
        emb = out.last_hidden_state[:, 0, :].detach().cpu().numpy().astype(np.float32)
        vecs.append(emb)
        ids.extend(chunk["grant_id"].astype(str).tolist())
        if start % (BATCH * 20) == 0:
            elapsed = time.time() - t0
            rate = (start + BATCH) / max(elapsed, 0.1)
            eta = (len(gr) - start) / max(rate, 0.1)
            print(f"  {start + len(chunk):5d}/{len(gr)}  "
                  f"({rate:.1f} docs/s, ETA {eta / 60:.1f} min)")

    X = np.vstack(vecs)
    print(f"final shape: {X.shape}  ({time.time() - t0:.1f}s total)")
    np.save(OUT_VEC, X)
    OUT_IDS.write_text("\n".join(ids))
    print(f"wrote {OUT_VEC}  ({OUT_VEC.stat().st_size / 1e6:.1f} MB)")
    print(f"wrote {OUT_IDS}")


if __name__ == "__main__":
    main()
