#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV의 text 컬럼을 OpenAI 임베딩(text-embedding-3-small)으로 변환 후
pgvector 테이블(bank_chunks)에 UPSERT
"""
import os
import argparse
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from tqdm import tqdm
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "ragdb"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )

def embed_texts(texts, model="text-embedding-3-small", batch_size=100):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    vectors = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding"):
        batch = texts[i:i+batch_size]
        resp = client.embeddings.create(model=model, input=batch, encoding_format="float")
        vectors.extend([r.embedding for r in resp.data])
    return vectors

def upsert_rows(rows):
    sql = """
    INSERT INTO bank_chunks
    (chunk_id, doc_id, bank_name, product_type, product_name, clause_no, clause_name, text, embedding)
    VALUES %s
    ON CONFLICT (chunk_id) DO UPDATE SET
      doc_id = EXCLUDED.doc_id,
      bank_name = EXCLUDED.bank_name,
      product_type = EXCLUDED.product_type,
      product_name = EXCLUDED.product_name,
      clause_no = EXCLUDED.clause_no,
      clause_name = EXCLUDED.clause_name,
      text = EXCLUDED.text,
      embedding = EXCLUDED.embedding;
    """
    with get_conn() as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=200)
        conn.commit()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="CSV 파일 경로 (청킹 완료본)")
    ap.add_argument("--batch_size", type=int, default=100)
    args = ap.parse_args()

    df = pd.read_csv(args.csv, encoding="utf-8-sig")
    required = ["chunk_id","doc_id","은행명","상품종류","상품이름","조항","조항이름","text"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"필수 컬럼 누락: {c}")

    texts = df["text"].astype(str).tolist()
    embs = embed_texts(texts, batch_size=args.batch_size)

    rows = [
        (
            df.loc[i,"chunk_id"],
            df.loc[i,"doc_id"],
            df.loc[i,"은행명"],
            df.loc[i,"상품종류"],
            df.loc[i,"상품이름"],
            str(df.loc[i,"조항"]),
            df.loc[i,"조항이름"],
            df.loc[i,"text"],
            embs[i]
        )
        for i in range(len(df))
    ]
    upsert_rows(rows)
    print(f"✅ {len(rows)}개의 청크가 DB에 업서트 완료되었습니다.")

if __name__ == "__main__":
    main()
