#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Top-K similarity search with pgvector (cosine)
"""
import os
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

# ===== 설정 =====
QUERY = "우리은행 예금상품이 뭐야?"
MODEL = "text-embedding-3-small"
TOP_K = 5
# ===============

def get_embedding(text, model=MODEL):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.embeddings.create(model=model, input=text, encoding_format="float")
    return resp.data[0].embedding  # list[float], dim=1536

def fetch_top_k(conn, query_emb, k=TOP_K):
    """
    pgvector: cosine 거리 연산자 `<=>`
    - 더 작을수록 가깝다 → ORDER BY embedding <=> query ASC
    - 유사도 값은 1 - 거리 로 계산해 함께 반환
    """
    with conn.cursor() as cur:
        sql = f"""
        SELECT
          chunk_id, doc_id, bank_name, product_type, product_name,
          clause_no, clause_name, text,
          1 - (embedding <=> %s::vector) AS cosine_sim
        FROM bank_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT {k};
        """
        cur.execute(sql, (list(query_emb), list(query_emb)))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]

def main():
    load_dotenv()  # .env의 DB/OPENAI 키 로드
    emb = get_embedding(QUERY)

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "bank_rag_db"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )

    results = fetch_top_k(conn, emb, TOP_K)

    print(f"\n🔍 Query: {QUERY}\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r['bank_name']} / {r['product_name']} / {r.get('clause_name')}  (sim={r['cosine_sim']:.3f})")
        preview = r["text"].replace("\n", " ")
        print("    ", (preview[:180] + "…") if len(preview) > 180 else preview)
        print()

    conn.close()

if __name__ == "__main__":
    main()
