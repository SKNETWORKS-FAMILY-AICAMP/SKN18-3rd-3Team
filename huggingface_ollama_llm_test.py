import psycopg2
import requests
from psycopg2.extras import RealDictCursor

# =============== 1. PostgreSQL 연결 ===============
conn = psycopg2.connect(
    host="localhost",
    dbname="vectordb",
    user="admin",
    password="admin123",
    port="5432"
)
cur = conn.cursor(cursor_factory=RealDictCursor)

# =============== 2. 임베딩 함수 정의 ===============
from huggingface_embedding import get_embedding_hf


# =============== 3. LLM 응답 생성 함수 ===============
def generate_response_ollama(prompt: str, context: str):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "gemma3:4b",  # 원하는 모델명 사용
        "prompt": f"""다음 정보를 참고하여 질문에 답해주세요:\n\n{context}\n\n,
        질문이 들어오면 은행명,상품종류,상품이름,조항,조항이름
        부분을 위주로 질문 키워드를 추출하고, 질문에 맞게 답해주세요.

        - 우리은행, KB_bank 키워드를 입력받으면 은행명에서 정확히 키워드를 추출하세요.
        - '제O조', 'O조' 형식으로 입력받은 경우 조항에서 정확히 추출하세요. 단, O는 완전히 일치해야 합니다.
        - '<명사> 제O조', '<명사> O조' 인 키워드를 입력받으면, 공백을 무시했을때, <명사>키워드가 상품이름 문자열을 완전히 포함해야 합니다.
        - 위에서 제시한 키워드 패턴이 없는 명사형 키워드는 상품이름에서 추출하고, 그 뒤에 명사형 키워드를 입력받은 경우 조항이름에서 추출하세요.
        - 정확한 조항이 없으면 '해당 조항을 찾을 수 없습니다.'라고 답변해주세요.
        ,질문: {prompt}""",
        "stream": False
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"Ollama 생성 오류: {response.text}")
    return response.json()["response"]

# =============== 4. 유사한 문서 검색 함수 ===============
def search_similar_texts(query_embedding, top_k=10):
    cur.execute("""
        SELECT text, embedding <#> %s::vector AS distance
        FROM terms
        ORDER BY embedding <#> %s::vector
        LIMIT %s;
    """, (query_embedding, query_embedding, top_k))
    results = cur.fetchall()
    return results


# =============== 5. 테스트 실행 ===============
def run_test():
    user_query = input("📝 질문을 입력하세요: ")
    query_embedding = get_embedding_hf(user_query)
    
    print("🔍 유사 문서 검색 중...")
    similar_docs = search_similar_texts(query_embedding)

    context = "\n\n".join([doc["text"] for doc in similar_docs])
    print("\n📚 유사한 문서 Context:")
    print(context)

    print("\n🤖 Ollama LLM 응답 생성 중...")
    answer = generate_response_ollama(user_query, context)
    
    print("\n✅ LLM 응답:")
    print(answer)

# 실행
if __name__ == "__main__":
    run_test()

    cur.close()
    conn.close()
