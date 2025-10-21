import psycopg2
import pandas as pd
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

# ==========================
# 1. 설정: 모델 이름과 DB 정보
# ==========================
HF_EMBED_MODEL = "jhgan/ko-sbert-nli"  # <-- Hugging Face 모델 이름
DB_CONFIG = {
    "host": "localhost",
    "dbname": "vectordb",
    "user": "admin",
    "password": "admin123",
    "port": "5432"
}

# ==========================
# 2. 모델 로드 및 임베딩 함수 정의
# ==========================
import os
os.environ['TRANSFORMERS_CACHE'] = './huggingface_embedding'

print("🔄 Hugging Face 임베딩 모델 로드 중...")
hf_model = SentenceTransformer(HF_EMBED_MODEL)
embedding_dim = hf_model.get_sentence_embedding_dimension()
print(f"✅ 모델 로드 완료 (임베딩 차원: {embedding_dim})")

def get_embedding_hf(text: str) -> list:
    return hf_model.encode(text, convert_to_numpy=True).tolist()

# ==========================
# 3. PostgreSQL 연결 및 테이블 생성
# ==========================
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
cur.execute(f"""
    CREATE TABLE IF NOT EXISTS terms (
        id SERIAL PRIMARY KEY,
        text TEXT,
        embedding VECTOR({embedding_dim})
    );
""")
conn.commit()

# ==========================
# 4. CSV 로드
# ==========================
df = pd.read_csv("우리예금약관_정제_임베딩용.csv")

if 'text' not in df.columns:
    raise ValueError(f"CSV에 'text' 컬럼이 없습니다. 실제 컬럼명: {list(df.columns)}")

# ==========================
# 5. 임베딩 및 DB 삽입
# ==========================
if __name__ == "__main__":
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Embedding & Inserting"):
        try:
            text_value = str(row["text"])
            embedding = get_embedding_hf(text_value)
        except:
            try:
                text_value = str(row["text"])[:1000]
                embedding = get_embedding_hf(text_value)
                print("⚠️ 모델 입력 제한: 1000자 이하로 자름")
            except:
                text_value = str(row["text"])[:500]
                embedding = get_embedding_hf(text_value)
                print("⚠️ 모델 입력 제한: 500자 이하로 자름")
        
        cur.execute(
            "INSERT INTO terms (text, embedding) VALUES (%s, %s)",
            (text_value, embedding)
        )
    conn.commit()
    print("✅ 모든 CSV 데이터가 임베딩되어 DB에 저장되었습니다.")

    cur.close()
    conn.close()
