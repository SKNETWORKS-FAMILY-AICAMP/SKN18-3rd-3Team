import psycopg2
import pandas as pd
import requests
from tqdm import tqdm

# ==========================
# 1. 설정: 모델 이름과 DB 정보
# ==========================
# 모델 변경하고 사용하려면 DB docker container를 삭제하고 docker container를 다시 build해야함
# 현재 directory의 database, init.sql폴더를 삭제 후 명령어 "docker-compose up -d"실행
OLLAMA_EMBED_MODEL = "qwen3-embedding:0.6b"  # <- 여기만 바꾸면 다른 모델 사용 가능
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"

DB_CONFIG = {
    "host": "localhost",
    "dbname": "vectordb",
    "user": "admin",
    "password": "admin123",
    "port": "5432"
}

# ==========================
# 2. PostgreSQL 연결
# ==========================
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# ==========================
# 3. 임베딩 차원 추출 함수
# ==========================
def get_embedding_dimension(model_name: str) -> int:
    dummy_text = "임베딩 차원 테스트용"
    payload = {"model": model_name, "prompt": dummy_text}
    response = requests.post(OLLAMA_API_URL, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"Ollama 응답 오류 (차원 확인): {response.text}")
    embedding = response.json()["embedding"]
    return len(embedding)

# ==========================
# 4. 테이블 생성
# ==========================
embedding_dim = get_embedding_dimension(OLLAMA_EMBED_MODEL)

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
# 5. CSV 로드
# ==========================
df = pd.read_csv("우리예금약관_정제_임베딩용.csv")

if 'text' not in df.columns:
    raise ValueError(f"CSV에 'text' 컬럼이 없습니다. 실제 컬럼명: {list(df.columns)}")

# ==========================
# 6. 임베딩 생성 함수
# ==========================
def get_embedding_ollama(text: str) -> list:
    payload = {"model": OLLAMA_EMBED_MODEL, "prompt": text}
    response = requests.post(OLLAMA_API_URL, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"Ollama 응답 오류: {response.text}")
    return response.json()["embedding"]

# ==========================
# 7. 데이터 삽입
# ==========================
if __name__ == "__main__":
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Embedding & Inserting"):
        try:
            text_value = str(row["text"])
            embedding = get_embedding_ollama(text_value)
        except:
            try:
                text_value = str(row["text"])[:1000]
                embedding = get_embedding_ollama(text_value)
                print("이 모델은 문자 수 제한이 1000자 이하 입니다.")
            except:
                text_value = str(row["text"])[:500]
                embedding = get_embedding_ollama(text_value)
                print("이 모델은 문자 수 제한이 500자 이하 입니다.")
        cur.execute(
            "INSERT INTO terms (text, embedding) VALUES (%s, %s)",
            (text_value, embedding)
        )
    conn.commit()
    print("✅ 모든 CSV 데이터가 임베딩되어 DB에 저장되었습니다.")

    cur.close()
    conn.close()
