#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""No-KSS semantic chunking pipeline (regex splitter)"""
import os, re, math, json, argparse
from dataclasses import dataclass
from typing import List, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
from tqdm import tqdm

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[OK] Loaded environment variables from {env_path}")
    else:
        print(f"[INFO] No .env file found at {env_path}")
except ImportError:
    print("[INFO] python-dotenv not installed")
except Exception as e:
    print(f"[WARNING] Error loading .env: {e}")

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

TOKEN_PER_CHAR = 3.8
HDR_KEYS = ["은행명:", "상품종류:", "상품이름:", "조항:", "조항이름:"]

def est_tokens_from_chars(chars: int, ratio: float = TOKEN_PER_CHAR) -> int:
    return int(math.ceil(chars / ratio))

def split_header_and_body(text: str) -> Tuple[str, str]:
    if not isinstance(text, str): return "", ""
    lines = text.splitlines()
    header_lines, i = [], 0
    for line in lines[:6]:
        if any(line.startswith(k) for k in HDR_KEYS):
            header_lines.append(line); i += 1
        else: break
    while i < len(lines) and lines[i].strip() == "": i += 1
    header = "\n".join(header_lines).strip()
    body = "\n".join(lines[i:]).strip() if i < len(lines) else ""
    return header, body

_SENT_PAT = re.compile(r"""
(?:
    (?<=[\.!\?:;])\s+   # end punctuation + ws
  | \n+                   # newlines
  | (?=^[\s]*[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳\-\u2022]|^[\s]*\(?\d+\)|^\s*\d+\.)  # bullets
)
""", re.VERBOSE | re.MULTILINE)

def sentence_split(text: str) -> List[str]:
    if not text: return []
    parts = [p for p in _SENT_PAT.split(text) if p and p.strip()]
    return [p.strip() for p in parts]

@dataclass
class EmbedResult:
    texts: List[str]
    vectors: np.ndarray

def get_embeddings(texts: List[str], model: str = "text-embedding-3-small", batch_size: int = 128, show_progress: bool = False) -> EmbedResult:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key: raise RuntimeError("OPENAI_API_KEY is not set")
    if OpenAI is None: raise RuntimeError("openai package missing. pip install openai>=1.0.0")
    client = OpenAI(api_key=api_key)
    vecs = []
    total_batches = (len(texts) + batch_size - 1) // batch_size
    iterator = range(0, len(texts), batch_size)
    if show_progress:
        iterator = tqdm(iterator, total=total_batches, desc="Embedding batches", unit="batch")
    for i in iterator:
        batch = texts[i:i+batch_size]
        resp = client.embeddings.create(model=model, input=batch, encoding_format="float")
        vecs.extend([d.embedding for d in resp.data])
    return EmbedResult(texts=texts, vectors=np.array(vecs, dtype=np.float32))

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0: return 0.0
    return float(np.dot(a, b) / (na * nb))

def build_semantic_chunks(sentences: List[str], vectors: np.ndarray, header: str,
                          cos_threshold: float = 0.80, max_tokens: int = 600,
                          target_tokens: int = 480) -> List[str]:
    chunks = []
    if not sentences: return chunks
    cur_sentences = [sentences[0]]
    cur_tokens = est_tokens_from_chars(len(sentences[0]))
    for i in range(1, len(sentences)):
        sim = cosine(vectors[i-1], vectors[i])
        next_tokens = est_tokens_from_chars(len(sentences[i]))
        trial_tokens = cur_tokens + next_tokens + 1
        if sim >= cos_threshold and trial_tokens <= max_tokens:
            cur_sentences.append(sentences[i]); cur_tokens = trial_tokens
        else:
            body = " ".join(cur_sentences).strip()
            chunk_text = (header + "\n" + body).strip() if header else body
            chunks.append(chunk_text)
            cur_sentences = [sentences[i]]; cur_tokens = next_tokens
    body = " ".join(cur_sentences).strip()
    chunk_text = (header + "\n" + body).strip() if header else body
    chunks.append(chunk_text)
    return chunks

def run_pipeline(input_csv: str, out_chunks: str, out_sents: str,
                 cos_threshold: float = 0.80, max_tokens: int = 600,
                 target_tokens: int = 480, batch_size: int = 128,
                 model: str = "text-embedding-3-small") -> None:
    print(f"[LOADING] Reading data from {input_csv}...")
    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    required = ["chunk_id","doc_id","은행명","상품종류","상품이름","조항","조항이름","text"]
    missing = [c for c in required if c not in df.columns]
    if missing: raise ValueError(f"Missing required columns: {missing}")
    print(f"[OK] Loaded {len(df)} rows\n")
    
    sent_rows, chunk_rows, boundary_samples = [], [], []
    print(f"[PROCESSING] Processing {len(df)} documents...\n")
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Processing docs", unit="doc"):
        header, body = split_header_and_body(row["text"])
        sentences = sentence_split(body)
        if not sentences:
            chunk_rows.append({**row.to_dict(), "text": (header + "\n").strip() if header else ""})
            continue
        emb = get_embeddings(sentences, model=model, batch_size=batch_size, show_progress=False)
        for i, s in enumerate(sentences):
            sent_rows.append({
                "doc_id": row["doc_id"], "chunk_id": row["chunk_id"],
                "은행명": row["은행명"], "상품이름": row["상품이름"],
                "조항": row["조항"], "조항이름": row["조항이름"],
                "sent_idx": i, "sentence": s
            })
        chunks = build_semantic_chunks(sentences, emb.vectors, header,
                                       cos_threshold=cos_threshold, max_tokens=max_tokens,
                                       target_tokens=target_tokens)
        for i in range(len(sentences)-1):
            sim = cosine(emb.vectors[i], emb.vectors[i+1])
            boundary_samples.append({
                "doc_id": row["doc_id"], "orig_chunk_id": row["chunk_id"],
                "i": i, "cosine": sim, "decision": "merge" if sim >= cos_threshold else "split"
            })
        base = ":".join(str(row["chunk_id"]).split(":")[:-1]) or f"{row['doc_id']}:{row['조항']}"
        for idx, ch_text in enumerate(chunks):
            new_row = row.to_dict()
            new_row["chunk_id"] = f"{base}:{idx}"
            new_row["text"] = ch_text
            chunk_rows.append(new_row)
    print("\n[SAVING] Saving results...")
    sents_df = pd.DataFrame(sent_rows)
    chunks_df = pd.DataFrame(chunk_rows)
    boundary_df = pd.DataFrame(boundary_samples)
    
    print(f"  [OK] Saving chunks to {out_chunks}")
    chunks_df.to_csv(out_chunks, index=False, encoding="utf-8-sig")
    
    print(f"  [OK] Saving sentences to {out_sents}")
    sents_df.to_csv(out_sents, index=False, encoding="utf-8-sig")
    
    boundary_path = out_chunks.replace(".csv", "_boundary_similarity.csv")
    print(f"  [OK] Saving boundary similarity to {boundary_path}")
    boundary_df.to_csv(boundary_path, index=False, encoding="utf-8-sig")
    def body_tokens(t: str) -> int:
        h, b = split_header_and_body(t); return est_tokens_from_chars(len(b))
    te = chunks_df["text"].map(body_tokens) if len(chunks_df) else pd.Series([], dtype=float)
    
    print("\n" + "="*60)
    print("✨ Pipeline Complete! ✨")
    print("="*60)
    print(json.dumps({
        "chunks": int(len(chunks_df)), "sentences": int(len(sents_df)), "boundary_events": int(len(boundary_df)),
        "chunk_token_mean": float(te.mean()) if len(te) else 0.0,
        "chunk_token_p95": float(te.quantile(0.95)) if len(te) else 0.0,
        "chunk_token_max": int(te.max()) if len(te) else 0,
        "boundary_file": boundary_path
    }, ensure_ascii=False, indent=2))
    print("="*60)

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out_chunks", required=True)
    ap.add_argument("--out_sents", required=True)
    ap.add_argument("--cos_threshold", type=float, default=0.80)
    ap.add_argument("--max_tokens", type=int, default=600)
    ap.add_argument("--target_tokens", type=int, default=480)
    ap.add_argument("--batch_size", type=int, default=128)
    ap.add_argument("--model", default="text-embedding-3-small")
    return ap.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        input_csv=args.input, out_chunks=args.out_chunks, out_sents=args.out_sents,
        cos_threshold=args.cos_threshold, max_tokens=args.max_tokens,
        target_tokens=args.target_tokens, batch_size=args.batch_size, model=args.model
    )
