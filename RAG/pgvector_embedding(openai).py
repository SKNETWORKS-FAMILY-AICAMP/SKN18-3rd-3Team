import os
import csv
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.pgvector import PGVector
from langchain.docstore.document import Document
from langchain.llms import OpenAI as LangChainOpenAI
from langchain.chains import RetrievalQA

# 1️⃣ 환경 변수 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 2️⃣ DB 연결 정보
conn_info = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT"),
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}

# 3️⃣ psycopg2로 DB 접속 및 테이블 생성
conn = psycopg2.connect(**conn_info)
cur = conn.cursor()

cur.execute("""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(1536)  -- text-embedding-3-small의 차원
);
""")
conn.commit()

# 4️⃣ CSV 로드
csv_path = "우리예금약관_정제_임베딩용.csv"
docs = []
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    for row in reader:
        if row:  # 빈 줄 제외
            docs.append(row[0])

# 5️⃣ OpenAI 임베딩 생성
embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=OPENAI_API_KEY)

# 6️⃣ 문서 임베딩 후 DB 삽입
for text in docs:
    vector = embeddings.embed_query(text)
    cur.execute(
        "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
        (text, vector)
    )
conn.commit()

print(f"{len(docs)}개의 문서를 DB에 임베딩 완료했습니다.")

# 7️⃣ LangChain PGVector로 VectorStore 구성
connection_string = (
    f"postgresql+psycopg2://{conn_info['user']}:{conn_info['password']}@"
    f"{conn_info['host']}:{conn_info['port']}/{conn_info['dbname']}"
)

vector_store = PGVector(
    connection_string=connection_string,
    embedding_function=embeddings,
    collection_name="documents"
)

# 8️⃣ LLM + Retriever QA 구성
llm = LangChainOpenAI(temperature=0, openai_api_key=OPENAI_API_KEY)
retriever = vector_store.as_retriever(search_kwargs={"k": 3})
qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)

# 9️⃣ 테스트 질의
# query = "예금 해지 시 이자는 어떻게 계산됩니까?"

while 1:
    input_query = input("은행에 대한 약관에 대해 궁금한점 입력(종료: 'q'입력): ")
    if input_query == 'q':
        break
    answer = qa_chain.run(input_query)

    print("질문:", input_query)
    print("답변:", answer)
    print("\n")
    print("=" * 50)