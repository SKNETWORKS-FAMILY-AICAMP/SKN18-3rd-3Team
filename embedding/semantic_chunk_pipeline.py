#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semantic Chunking Pipeline (KSS + OpenAI text-embedding-3-small + cosine merge)

Inputs
------
- merged CSV file with columns:
["chunk_id","doc_id","은행명","상품종류","상품이름","조항","조항이름","text"]
where text begins with 0~5 header lines like:
    은행명: ...
    상품종류: ...
    상품이름: ...
    조항: ...
    조항이름: ...
    <blank line>
    본문...

What it does
------------
1) Sentence-split each row's 본문 using KSS (if installed) or a regex fallback.
2) Get OpenAI embeddings (text-embedding-3-small) per sentence.
3) Greedily merge adjacent sentences into a chunk while:
    - cosine(sent_i, sent_{i+1}) >= COS_THRESHOLD  (semantic continuity)
    - and estimated tokens <= MAX_TOKENS (safety)
When either fails, start a new chunk.
Also softly aim for TARGET_TOKENS per chunk.
4) Save two files:
- semantic-chunked CSV with same schema, updated chunk_id ...:0, :1, ...
- sentence-level embeddings CSV (per sentence) to help debugging
- boundary similarity CSV: similarity at split points vs kept points

Usage
-----
export OPENAI_API_KEY=...
python semantic_chunk_pipeline.py \
  --input "우리+국민_약관_병합본_v2.csv" \
  --out_chunks "우리+국민_약관_semantic_chunks.csv" \
  --out_sents "우리+국민_약관_sentences.csv" \
  --cos_threshold 0.80 \
  --max_tokens 600 \
  --target_tokens 480 \
  --batch_size 128

Notes
-----
* Requires: openai>=1.0.0
* KSS optional (pip install kss). If not installed, uses regex-based splitter.
"""

import os
import re
import math
import json
import argparse
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path

import pandas as pd

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded environment variables from {env_path}")
    else:
        print(f"ℹ No .env file found at {env_path}")
except ImportError:
    print("ℹ python-dotenv not installed. Install with: pip install python-dotenv")
    pass
import numpy as np

# --- Optional import of KSS ---
try:
    import kss  # type: ignore
    HAS_KSS = True
except Exception:
    HAS_KSS = False

# --- OpenAI ---
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # will check at runtime

# ---------------- Config defaults ----------------
TOKEN_PER_CHAR = 3.8  # heuristic for Korean

# ---------------- Utilities ----------------
def est_tokens_from_chars(chars: int, ratio: float = TOKEN_PER_CHAR) -> int:
    return int(math.ceil(chars / ratio))

HDR_KEYS = ["은행명:", "상품종류:", "상품이름:", "조항:", "조항이름:"]

def split_header_and_body(text: str) -> Tuple[str, str]:
    if not isinstance(text, str):
        return "", ""
    lines = text.splitlines()
    header_lines = []
    i = 0
    # collect header lines
    for line in lines[:6]:
        if any(line.startswith(k) for k in HDR_KEYS):
            header_lines.append(line)
            i += 1
        else:
            break
    # skip blank line
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    header = "\n".join(header_lines).strip()
    body = "\n".join(lines[i:]).strip() if i < len(lines) else ""
    return header, body

def sentence_split(text: str) -> List[str]:
    """KSS if available; else regex fallback."""
    if not text:
        return []
    if HAS_KSS:
        # kss returns a generator; cast to list
        return [s.strip() for s in kss.split_sentences(text) if s.strip()]
    # regex fallback: split on .?! followed by space/newline + also split newlines
    parts = re.split(r'(?<=[\.\?\!])\s+|\n+', text)
    return [s.strip() for s in parts if s and s.strip()]

# ---------------- Embedding ----------------
@dataclass
class EmbedResult:
    texts: List[str]
    vectors: np.ndarray  # shape: (N, D)

def get_embeddings(texts: List[str], model: str = "text-embedding-3-small", batch_size: int = 128) -> EmbedResult:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in environment.")
    if OpenAI is None:
        raise RuntimeError("openai python package not available. Install `pip install openai>=1.0.0`.")
    client = OpenAI(api_key=api_key)
    vecs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        resp = client.embeddings.create(model=model, input=batch, encoding_format="float")
        # resp.data is list with 'embedding'
        for item in resp.data:
            vecs.append(item.embedding)
    return EmbedResult(texts=texts, vectors=np.array(vecs, dtype=np.float32))

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

# ---------------- Semantic Chunking ----------------
def build_semantic_chunks(sentences: List[str],
                        vectors: np.ndarray,
                        header: str,
                        cos_threshold: float = 0.80,
                        max_tokens: int = 600,
                        target_tokens: int = 480) -> List[str]:
    """
    Greedy merge: keep adding next sentence if
    - cosine(last, next) >= cos_threshold
    - est_tokens(current + next) <= max_tokens
    Otherwise, finalize current chunk and start new.
    Aim for target_tokens softly.
    """
    chunks = []
    if not sentences:
        return chunks

    cur_sentences = [sentences[0]]
    cur_tokens = est_tokens_from_chars(len(sentences[0]))

    for i in range(1, len(sentences)):
        last_vec = vectors[i-1]
        next_vec = vectors[i]
        sim = cosine(last_vec, next_vec)

        next_tokens = est_tokens_from_chars(len(sentences[i]))
        trial_tokens = cur_tokens + next_tokens + 1  # + space

        if sim >= cos_threshold and trial_tokens <= max_tokens:
            cur_sentences.append(sentences[i])
            cur_tokens = trial_tokens
        else:
            # finalize current
            body = " ".join(cur_sentences).strip()
            chunk_text = (header + "\n" + body).strip() if header else body
            chunks.append(chunk_text)

            # start new
            cur_sentences = [sentences[i]]
            cur_tokens = next_tokens

    # flush last
    body = " ".join(cur_sentences).strip()
    chunk_text = (header + "\n" + body).strip() if header else body
    chunks.append(chunk_text)
    return chunks

# ---------------- Main pipeline ----------------
def run_pipeline(input_csv: str,
                out_chunks: str,
                out_sents: str,
                cos_threshold: float = 0.80,
                max_tokens: int = 600,
                target_tokens: int = 480,
                batch_size: int = 128,
                model: str = "text-embedding-3-small") -> None:
    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    required = ["chunk_id","doc_id","은행명","상품종류","상품이름","조항","조항이름","text"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    sent_rows = []   # for sentence-level export
    chunk_rows = []  # for final chunk export
    boundary_samples = []  # [(doc_id, idx, sim, decision)]

    # Process per original row
    for _, row in df.iterrows():
        header, body = split_header_and_body(row["text"])
        sentences = sentence_split(body)

        if not sentences:
            # preserve empty as one chunk with header only
            chunk_rows.append({
                **row.to_dict(),
                "text": (header + "\n").strip() if header else ""
            })
            continue

        # Embedding for sentences
        emb = get_embeddings(sentences, model=model, batch_size=batch_size)

        # Save sentence-level rows
        for i, s in enumerate(sentences):
            sent_rows.append({
                "doc_id": row["doc_id"],
                "chunk_id": row["chunk_id"],
                "은행명": row["은행명"],
                "상품이름": row["상품이름"],
                "조항": row["조항"],
                "조항이름": row["조항이름"],
                "sent_idx": i,
                "sentence": s
            })

        # Semantic chunks
        chunks = build_semantic_chunks(
            sentences, emb.vectors, header,
            cos_threshold=cos_threshold, max_tokens=max_tokens, target_tokens=target_tokens
        )

        # Record boundary sims for diagnostics
        for i in range(len(sentences)-1):
            sim = cosine(emb.vectors[i], emb.vectors[i+1])
            decision = "merge" if sim >= cos_threshold else "split"
            boundary_samples.append({
                "doc_id": row["doc_id"],
                "orig_chunk_id": row["chunk_id"],
                "i": i,
                "cosine": sim,
                "decision": decision
            })

        # Emit chunks with resequenced suffix :0..
        base = ":".join(str(row["chunk_id"]).split(":")[:-1]) or f"{row['doc_id']}:{row['조항']}"
        for idx, ch_text in enumerate(chunks):
            new_row = row.to_dict()
            new_row["chunk_id"] = f"{base}:{idx}"
            new_row["text"] = ch_text
            chunk_rows.append(new_row)

    # Build DataFrames
    sents_df = pd.DataFrame(sent_rows)
    chunks_df = pd.DataFrame(chunk_rows)
    boundary_df = pd.DataFrame(boundary_samples)

    # Save
    chunks_df.to_csv(out_chunks, index=False, encoding="utf-8-sig")
    sents_df.to_csv(out_sents, index=False, encoding="utf-8-sig")
    boundary_path = out_chunks.replace(".csv", "_boundary_similarity.csv")
    boundary_df.to_csv(boundary_path, index=False, encoding="utf-8-sig")

    # Simple report
    # Estimate tokens for chunks (body only)
    def body_tokens(t: str) -> int:
        h, b = split_header_and_body(t)
        return est_tokens_from_chars(len(b))

    te = chunks_df["text"].map(body_tokens)
    report = {
        "chunks": len(chunks_df),
        "sentences": len(sents_df),
        "boundary_events": len(boundary_df),
        "chunk_token_mean": float(te.mean() if len(te) else 0),
        "chunk_token_p95": float(te.quantile(0.95) if len(te) else 0),
        "chunk_token_max": int(te.max() if len(te) else 0),
        "boundary_file": boundary_path
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input merged CSV (우리+국민_약관_병합본_v2.csv)")
    ap.add_argument("--out_chunks", required=True, help="Output CSV with semantic chunks")
    ap.add_argument("--out_sents", required=True, help="Output CSV with sentence-level rows")
    ap.add_argument("--cos_threshold", type=float, default=0.80)
    ap.add_argument("--max_tokens", type=int, default=600)
    ap.add_argument("--target_tokens", type=int, default=480)
    ap.add_argument("--batch_size", type=int, default=128)
    ap.add_argument("--model", default="text-embedding-3-small")
    return ap.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        input_csv=args.input,
        out_chunks=args.out_chunks,
        out_sents=args.out_sents,
        cos_threshold=args.cos_threshold,
        max_tokens=args.max_tokens,
        target_tokens=args.target_tokens,
        batch_size=args.batch_size,
        model=args.model,
    )
