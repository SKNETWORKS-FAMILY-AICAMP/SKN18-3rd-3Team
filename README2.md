# 📚 프로젝트 구조 및 아키텍처 상세 가이드

> 우리은행 + 국민은행 대출/예적금 Q&A RAG 시스템 - 심층 분석

---

## 📖 목차

1. [전체 아키텍처 개요](#전체-아키텍처-개요)
2. [폴더별 상세 설명](#폴더별-상세-설명)
3. [핵심 개념 이해](#핵심-개념-이해)
4. [데이터 흐름](#데이터-흐름)
5. [Docker 구성 요소](#docker-구성-요소)
6. [FAQ](#faq)

---

## 🏗️ 전체 아키텍처 개요

### 시스템 구성도

```
┌─────────────────────────────────────────────────────────────┐
│                    사용자 (웹 브라우저)                      │
│                   http://localhost:8501                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Streamlit UI (app.py)                       │
│              - 질문 입력 인터페이스                          │
│              - 필터 옵션 (은행/상품)                         │
│              - 답변 및 참고 문서 표시                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  RAG Engine (rag/engine.py)                  │
│              - 전체 파이프라인 오케스트레이션                │
│              - 컴포넌트 초기화 및 관리                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              LangGraph Pipeline (rag/graph/)                 │
│                                                               │
│  1. Normalize → 쿼리 정규화                                  │
│  2. Route     → 메타데이터 추출 (은행/상품)                 │
│  3. Search    → 벡터 유사도 검색                             │
│  4. Rewrite   → 쿼리 재작성 (필요시)                         │
│  5. Generate  → LLM 답변 생성                                │
│  6. Format    → 응답 포맷팅                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ↓                               ↓
┌─────────────────────────┐   ┌─────────────────────────┐
│  PostgreSQL + pgvector  │   │   OpenAI API            │
│  - 벡터 검색            │   │   - Embeddings          │
│  - 문서 저장            │   │   - GPT (답변 생성)     │
└─────────────────────────┘   └─────────────────────────┘
```

---

## 📂 폴더별 상세 설명

### 📁 루트 디렉토리

```
SKN18-3rd-3Team/
├── app.py                    # Streamlit 웹 애플리케이션
├── compose.yml               # Docker Compose 설정
├── requirements.txt          # Python 패키지 의존성
├── README.md                 # 기본 프로젝트 문서
├── README2.md                # 상세 아키텍처 가이드 (본 문서)
├── multiagent_ver2.ipynb     # 멀티 에이전트 개발 노트북
├── data/                     # 데이터 파일
├── docker/                   # Docker 설정
├── rag/                      # RAG 시스템 핵심 모듈
├── LangGraph/                # 대체 LangGraph 구현
├── MultiAgent/               # 멀티 에이전트 시스템
├── scripts/                  # 유틸리티 스크립트
├── front/                    # 프론트엔드
├── test/                     # 테스트
└── db_ingest/                # 데이터베이스 수집
```

---

### 🎯 `rag/` - RAG 시스템 핵심 모듈

RAG 시스템의 모든 핵심 기능을 담당하는 메인 디렉토리입니다.

#### 📦 `rag/core/` - 핵심 유틸리티

**역할**: 시스템 전반에서 사용되는 기본 기능 제공

```
rag/core/
├── __init__.py
├── config.py          # 환경 변수 및 설정 관리
├── logger.py          # 로깅 시스템
└── singleton.py       # 싱글톤 패턴 구현
```

**주요 기능**:
- **`config.py`**: 
  - 환경 변수 로드 (`.env` 파일)
  - OpenAI API 키, DB URL, 모델 설정 등
  - 설정값 검증 및 기본값 제공

- **`logger.py`**: 
  - 통합 로깅 시스템
  - 파일 + 콘솔 출력
  - 로그 레벨 관리 (DEBUG, INFO, ERROR)

- **`singleton.py`**: 
  - 싱글톤 패턴 구현
  - 리소스 중복 생성 방지

---

#### 🗄️ `rag/db/` - 데이터베이스 레이어

**역할**: PostgreSQL 연결 및 데이터 CRUD 작업

```
rag/db/
├── __init__.py
├── connection.py      # PostgreSQL 연결 관리
└── repo.py            # DocumentRepository (CRUD)
```

**주요 기능**:
- **`connection.py`**: 
  - PostgreSQL 연결 풀 관리
  - 헬스 체크
  - 트랜잭션 관리

- **`repo.py`**: 
  - 문서 CRUD 작업
  - 테이블 생성
  - 문서 개수 조회
  - 벡터 인덱스 생성

**사용 예시**:
```python
from rag.db.connection import DatabaseConnection
from rag.db.repo import DocumentRepository

db = DatabaseConnection(db_url)
repo = DocumentRepository(db)

# 문서 개수 확인
count = repo.get_document_count()
print(f"총 {count}개 문서 인덱싱됨")
```

---

#### 🔤 `rag/embeddings/` - 임베딩 생성

**역할**: 텍스트를 벡터로 변환하는 순수 기능

```
rag/embeddings/
├── __init__.py
├── provider.py        # 임베딩 프로바이더 인터페이스
└── openai_embed.py    # OpenAI 임베딩 구현
```

**핵심 개념**:
- **임베딩(Embedding)**: 텍스트를 숫자 벡터로 변환
- **벡터**: 의미를 수치로 표현 (예: 3072차원)
- **유사도**: 벡터 간 거리로 의미 유사성 측정

**주요 기능**:
- **`embed_texts()`**: 여러 텍스트를 한 번에 벡터화 (배치 처리)
- **`embed_query()`**: 단일 쿼리를 벡터화 (검색 시 사용)
- **재시도 로직**: API 실패 시 자동 재시도 (3회)

**사용 시점**:
1. **인덱싱 시**: 문서를 벡터로 변환하여 DB 저장
2. **검색 시**: 사용자 질문을 벡터로 변환하여 유사 문서 검색

**예시**:
```python
from rag.embeddings.openai_embed import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large",
    api_key="sk-..."
)

# 인덱싱 시
docs = ["대출 조건", "예금 금리"]
vectors = embeddings.embed_texts(docs)
# → [[0.123, -0.456, ...], [0.789, 0.234, ...]]

# 검색 시
query = "국민은행 대출 금리는?"
query_vector = embeddings.embed_query(query)
# → [0.456, -0.123, ...]
```

---

#### 🤖 `rag/llm/` - LLM 모델

**역할**: 대화형 AI 모델을 통한 답변 생성

```
rag/llm/
├── __init__.py
├── llm.py             # LLM 인터페이스
└── openai_chat.py     # OpenAI GPT 구현
```

**주요 기능**:
- **`generate()`**: 시스템 프롬프트 + 사용자 쿼리 → 답변 생성
- **`generate_with_messages()`**: 대화 히스토리 기반 답변
- **재시도 로직**: API 실패 시 자동 재시도

**embeddings vs llm 차이**:
| 항목 | embeddings | llm |
|------|-----------|-----|
| **입력** | 텍스트 | 프롬프트 + 컨텍스트 |
| **출력** | 벡터 (숫자 배열) | 텍스트 (자연어) |
| **용도** | 검색, 유사도 계산 | 답변 생성, 요약 |
| **모델** | text-embedding-3-large | gpt-5-nano |

---

#### 📥 `rag/ingestion/` - 데이터 수집 및 인덱싱

**역할**: CSV 데이터를 벡터 DB에 저장하는 전체 파이프라인

```
rag/ingestion/
├── __init__.py
├── load_csv.py        # CSV → Document 변환
├── chunking.py        # 텍스트 분할 (옵션)
└── indexer.py         # 벡터화 + DB 저장
```

**왜 필요한가?**
RAG는 "검색 → 생성" 시스템입니다. 검색하려면 먼저 데이터를 벡터 DB에 넣어야 합니다!

**전체 흐름**:
```
CSV 파일 (data/final_data.csv)
      ↓
load_csv.py → Document 객체로 변환
      ↓
chunking.py → 텍스트 분할 (필요시)
      ↓
indexer.py → 임베딩 생성 + DB 저장
      ↓
PostgreSQL + pgvector (벡터 DB)
```

**각 파일의 역할**:

1. **`load_csv.py`** - CSV 로더
   ```python
   # CSV 파일
   은행명,상품종류,조항내용
   국민은행,대출,"만 19세 이상..."
   
   ↓ load_bank_data()
   
   # LangChain Document
   Document(
       page_content="만 19세 이상...",
       metadata={"은행명": "국민은행", "상품종류": "대출"}
   )
   ```
   - CSV 읽기 (pandas)
   - 빈 데이터 필터링
   - 메타데이터 추출
   - Document 객체 생성

2. **`chunking.py`** - 텍스트 분할
   - 긴 텍스트를 작은 청크로 분할
   - 현재는 CSV에서 이미 분할되어 있어 사용 안 함

3. **`indexer.py`** - 인덱서
   ```python
   Document 객체
        ↓
   embeddings.embed_texts() → 벡터 생성
        ↓
   vectorstore.add_documents() → DB 저장
        ↓
   진행 상황 로깅 + 에러 처리
   ```
   - 배치 처리 (50개씩)
   - 진행 상황 로깅
   - 에러 처리
   - 통계 제공

**embeddings vs ingestion 차이**:
| 항목 | embeddings | ingestion |
|------|-----------|-----------|
| **역할** | 🔧 도구 (변환기) | 🏭 프로세스 (파이프라인) |
| **책임** | 텍스트 → 벡터 | CSV → DB 전체 과정 |
| **사용 시점** | 인덱싱 + 검색 | 인덱싱만 |
| **재사용성** | 시스템 전체 | 데이터 준비 단계만 |

**비유**:
- `embeddings/` = 용접기 (도구)
- `ingestion/` = 자동차 공장 (전체 생산 라인)

---

#### 🗂️ `rag/vectorstore/` - 벡터 스토어

**역할**: pgvector 기반 벡터 검색 구현

```
rag/vectorstore/
├── __init__.py
├── pgvector_store.py  # pgvector 래퍼
├── sql.py             # SQL 쿼리 정의
└── types.py           # 타입 정의
```

**주요 기능**:
- 벡터 유사도 검색 (코사인 유사도)
- 메타데이터 필터링 (은행명, 상품종류)
- 배치 삽입
- 인덱스 생성 (IVFFLAT/HNSW)

---

#### 🔍 `rag/retriever.py` - 검색기

**역할**: 벡터 검색 및 문서 검색 로직

**주요 기능**:
- 쿼리 벡터화
- 유사 문서 검색
- 메타데이터 필터링
- Top-K 문서 반환

---

#### 📝 `rag/prompts/` - 프롬프트 템플릿

**역할**: Jinja2 기반 프롬프트 템플릿 관리

```
rag/prompts/
├── answer.j2          # 답변 생성용 템플릿
└── citations.j2       # 인용 포맷팅 템플릿
```

**예시**:
```jinja2
# answer.j2
당신은 은행 상품 전문가입니다.

질문: {{ query }}

참고 문서:
{% for doc in documents %}
- {{ doc.content }}
{% endfor %}

위 문서를 바탕으로 정확하게 답변하세요.
```

---

#### ⚙️ `rag/engine.py` - RAG 엔진 (핵심!)

**역할**: RAG 파이프라인 전체 오케스트레이션

**주요 기능**:
1. 모든 컴포넌트 초기화
   - DB 연결
   - 임베딩 모델
   - LLM 모델
   - 벡터 스토어
   - LangGraph 파이프라인

2. 쿼리 처리
   - 사용자 질문 입력
   - LangGraph 실행
   - 답변 + 참고 문서 반환

3. 헬스 체크
   - DB 상태 확인
   - 문서 개수 확인

**초기화 과정**:
```
RAG Engine 초기화 시작
  ↓
1. Config 로드 (환경 변수)
  ↓
2. DB 연결 설정
  ↓
3. Repository 초기화
  ↓
4. Embeddings 초기화 (text-embedding-3-large)
  ↓
5. Vector Store 초기화
  ↓
6. Retriever 초기화
  ↓
7. LLM 초기화 (gpt-5-nano)
  ↓
8. Jinja2 템플릿 로드
  ↓
9. LangGraph 빌드 및 컴파일
  ↓
초기화 완료! (약 5-10초)
```

---

### 🕸️ `rag/graph/` - LangGraph 워크플로우

**역할**: RAG 파이프라인을 그래프 형태로 구성

```
rag/graph/
├── __init__.py
├── State.py           # 그래프 상태 정의
├── build.py           # 그래프 빌드 및 컴파일
├── README.md          # 그래프 설명
├── nodes/             # 그래프 노드들
├── multiAgent/        # 멀티 에이전트
└── route/             # 라우팅 로직
```

#### 📊 `rag/graph/build.py` - 그래프 빌더

**워크플로우**:
```
사용자 질문
    ↓
┌─────────────────┐
│  1. Normalize   │ ← 쿼리 정규화 (공백 제거, 소문자 변환)
└────────┬────────┘
         ↓
┌─────────────────┐
│  2. Route       │ ← 메타데이터 추출 (은행명, 상품종류)
└────────┬────────┘
         ↓
┌─────────────────┐
│  3. Search      │ ← 벡터 유사도 검색
└────────┬────────┘
         ↓
    검색 결과 충분?
    /          \
  YES           NO
   ↓             ↓
Generate    ┌─────────────────┐
            │  4. Rewrite     │ ← LLM으로 쿼리 재작성
            └────────┬────────┘
                     ↓
                  다시 Search
                     ↓
┌─────────────────┐
│  5. Generate    │ ← LLM 답변 생성
└────────┬────────┘
         ↓
┌─────────────────┐
│  6. Format      │ ← 응답 포맷팅
└────────┬────────┘
         ↓
    최종 답변
```

#### 🎯 `rag/graph/nodes/` - 그래프 노드

각 노드는 RAG 파이프라인의 단계를 담당합니다.

**노드 목록**:

1. **`normalize_query_node.py`** - 쿼리 정규화
   - 공백 제거
   - 특수문자 처리
   - 소문자 변환

2. **`route_metadata_node.py`** - 메타데이터 라우팅
   - 쿼리에서 은행명 추출 (우리은행, 국민은행)
   - 상품종류 추출 (대출, 예적금)
   - 필터 설정

3. **`vector_search_node.py`** - 벡터 검색
   - 쿼리 벡터화
   - 유사 문서 검색 (Top-K)
   - 메타데이터 필터링 적용

4. **`rewrite_query_node.py`** - 쿼리 재작성
   - 검색 결과가 부족할 때 실행
   - LLM으로 쿼리 개선
   - 다시 검색

5. **`generate_answer_node.py`** - 답변 생성
   - 검색된 문서 + 질문 → 프롬프트 생성
   - LLM 호출
   - 자연어 답변 생성

6. **`format_response_node.py`** - 응답 포맷팅
   - 답변 정리
   - 참고 문서 정보 추가
   - 최종 응답 구성

**추가 노드** (확장 기능):
- `classify_node.py` - 쿼리 분류
- `eval_node.py` - 답변 품질 평가
- `search_sql_node.py` - SQL 기반 검색
- `search_web_node.py` - 웹 검색

#### 🤖 `rag/graph/multiAgent/` - 멀티 에이전트

**역할**: 특화된 작업을 수행하는 에이전트들

```
multiAgent/
├── classify_agent.py  # 분류 에이전트
├── sql_agent.py       # SQL 쿼리 에이전트
├── gen_agent.py       # 생성 에이전트
└── eval_agent.py      # 평가 에이전트
```

---

### 🛠️ `scripts/` - 유틸리티 스크립트

#### 📥 `scripts/index_data.py` - 데이터 인덱싱

**역할**: CSV 데이터를 벡터 DB에 인덱싱

**실행 방법**:
```bash
# Docker 환경
docker-compose exec app python scripts/index_data.py

# 로컬 환경
python scripts/index_data.py
```

**실행 과정**:
```
1. 설정 로드
2. DB 연결
3. 임베딩 모델 초기화
4. CSV 파일 로드 (data/final_data.csv)
5. Document 객체 변환
6. 배치 처리 (50개씩)
   - 임베딩 생성
   - DB 저장
   - 진행 상황 로깅
7. 통계 출력
   - 성공: 495개
   - 실패: 5개
   - 총 시간: 2분 30초
```

**주의사항**:
- ⚠️ 최초 1회만 실행
- ⚠️ 데이터는 Docker volume에 영구 저장
- ⚠️ CSV 변경 시에만 재실행 필요

---

### 🐳 `docker/` - Docker 설정

```
docker/
├── Dockerfile.app         # 애플리케이션 이미지
├── docker-compose.yml     # 서비스 오케스트레이션
├── init.sql               # DB 초기화 SQL
└── initdb/                # DB 초기화 스크립트
    ├── 01_extensions.sql  # pgvector 확장 설치
    └── 02_schema.sql      # 테이블 스키마 생성
```

#### 🔧 `Dockerfile.app` vs `initdb/` 차이

**핵심 차이**:
| 항목 | Dockerfile.app | initdb/ |
|------|----------------|---------|
| **대상** | app 서비스 (애플리케이션) | db 서비스 (데이터베이스) |
| **실행 시점** | 이미지 빌드 시 | DB 컨테이너 최초 시작 시 |
| **역할** | Python 환경 구축 | DB 스키마 초기화 |
| **언어** | Dockerfile | SQL |
| **재실행** | 이미지 재빌드 시 | 볼륨 삭제 후 재시작 시 |

**Dockerfile.app** - 애플리케이션 컨테이너:
```dockerfile
FROM python:3.11-slim
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y gcc postgresql-client

# Python 패키지 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 코드 복사
COPY . .

# Streamlit 실행
CMD ["streamlit", "run", "app.py"]
```

**기능**:
- ✅ Python 3.11 환경 구축
- ✅ 라이브러리 설치 (LangChain, OpenAI, pgvector 등)
- ✅ 애플리케이션 코드 복사
- ✅ Streamlit 웹 서버 실행

**initdb/** - 데이터베이스 초기화:

**`01_extensions.sql`**:
```sql
-- pgvector 확장 설치
CREATE EXTENSION IF NOT EXISTS vector;
```

**`02_schema.sql`**:
```sql
-- documents 테이블 생성
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    embedding vector(3072),  -- 3072차원 벡터
    content TEXT,
    bank_name VARCHAR(100),
    product_type VARCHAR(50),
    ...
);

-- 벡터 인덱스 생성 (IVFFLAT)
CREATE INDEX documents_embedding_idx 
ON documents USING ivfflat (embedding vector_cosine_ops);

-- 메타데이터 인덱스
CREATE INDEX documents_bank_name_idx ON documents(bank_name);
```

**기능**:
- ✅ pgvector 확장 활성화
- ✅ 테이블 생성 (documents, rag.bank_clauses 등)
- ✅ 벡터 인덱스 생성 (검색 성능 향상)
- ✅ 메타데이터 인덱스 생성

**실행 흐름**:
```
docker-compose up -d
      │
      ├─────────────────────────────────┐
      │                                 │
  [db 서비스]                      [app 서비스]
      │                                 │
PostgreSQL 시작                  Dockerfile.app 빌드
      │                                 │
최초 시작?                         Python 설치
      │                                 │
    YES                            pip install
      │                                 │
initdb/ 실행                       코드 복사
  ├─ 01_extensions.sql                 │
  └─ 02_schema.sql              Streamlit 실행
      │                                 │
  ✅ DB 준비                       ✅ 앱 실행
      │                                 │
      └────────── 연결 ─────────────────┘
```

---

### 🎨 `LangGraph/` - 대체 LangGraph 구현

**역할**: `rag/graph/`와 유사하지만 독립적인 구현

```
LangGraph/
├── LangGraph.py       # 그래프 메인 로직
├── State.py           # 상태 정의
├── llm.py             # LLM 래퍼
├── nodes/             # 노드 구현
├── route/             # 라우팅 로직
└── debug_log.txt      # 디버그 로그
```

**차이점**:
- `rag/graph/`: 프로덕션용 (완성도 높음)
- `LangGraph/`: 개발/실험용 (유연성 높음)

---

### 🤖 `MultiAgent/` - 멀티 에이전트 시스템

```
MultiAgent/
└── sql_agent.py       # SQL 데이터베이스 쿼리 에이전트
```

**역할**: SQL 데이터베이스와 상호작용하는 에이전트

---

### 📊 `data/` - 데이터 파일

```
data/
├── final_embedding_data_v6.csv.csv  # 임베딩용 최종 데이터
├── RDB/                             # 관계형 DB 데이터
├── kb_bank/                         # 국민은행 약관
└── wo_bank/                         # 우리은행 약관
```

**데이터 구조**:
```csv
chunk_id,doc_id,은행명,상품종류,상품이름,조항,조항이름,조항내용
CHUNK_001,DOC_001,국민은행,대출,주택담보대출,제1조,대출대상,"만 19세 이상..."
```

---

## 🧠 핵심 개념 이해

### 1. RAG (Retrieval-Augmented Generation)

**정의**: 검색 + 생성을 결합한 AI 시스템

**동작 원리**:
```
사용자 질문: "국민은행 대출 금리는?"
      ↓
1. 검색 (Retrieval)
   - 질문을 벡터로 변환
   - 유사한 문서 검색
   - 관련 문서 5개 찾음
      ↓
2. 생성 (Generation)
   - 찾은 문서 + 질문 → LLM
   - "국민은행 대출 금리는 연 3.5%부터..."
      ↓
답변 + 참고 문서
```

**왜 RAG?**
- ❌ 순수 LLM: 최신 정보 없음, 환각(hallucination)
- ✅ RAG: 실제 문서 기반, 정확한 답변, 출처 제공

---

### 2. 임베딩 (Embedding)

**정의**: 텍스트를 숫자 벡터로 변환

**예시**:
```python
# 텍스트
"국민은행 대출"

↓ 임베딩 모델

# 벡터 (3072차원)
[0.123, -0.456, 0.789, ..., 0.234]
```

**왜 벡터로?**
- 컴퓨터는 숫자만 이해
- 의미 유사성을 거리로 계산 가능
- 빠른 검색 (벡터 인덱스)

**유사도 계산**:
```python
# 코사인 유사도
query = "대출 금리"      → [0.1, 0.9, 0.3]
doc1 = "대출 이자율"     → [0.2, 0.8, 0.4]  # 유사도: 0.95
doc2 = "예금 상품"       → [0.7, 0.1, 0.6]  # 유사도: 0.32

→ doc1이 더 유사함!
```

---

### 3. 벡터 데이터베이스 (pgvector)

**정의**: 벡터를 저장하고 유사도 검색을 수행하는 DB

**일반 DB vs 벡터 DB**:
```python
# 일반 DB (정확한 매칭)
SELECT * FROM products WHERE name = '주택담보대출';

# 벡터 DB (의미 유사도)
SELECT * FROM documents 
ORDER BY embedding <=> query_vector  # 코사인 거리
LIMIT 5;
```

**인덱스 종류**:
- **IVFFLAT**: 빠르지만 정확도 약간 낮음
- **HNSW**: 느리지만 정확도 높음

---

### 4. LangGraph

**정의**: LangChain 기반 워크플로우 그래프

**왜 그래프?**
- 복잡한 로직을 시각화
- 조건부 분기 (if-else)
- 재시도 로직
- 상태 관리

**예시**:
```python
# 일반 코드 (복잡함)
def rag_pipeline(query):
    normalized = normalize(query)
    metadata = extract_metadata(normalized)
    docs = search(normalized, metadata)
    if len(docs) < 3:
        rewritten = rewrite(query)
        docs = search(rewritten, metadata)
    answer = generate(query, docs)
    return format(answer)

# LangGraph (명확함)
workflow = StateGraph()
workflow.add_node("normalize", normalize_query)
workflow.add_node("route", route_metadata)
workflow.add_node("search", vector_search)
workflow.add_conditional_edges(
    "search",
    check_results,
    {"sufficient": "generate", "retry": "rewrite"}
)
```

---

### 5. 멀티 에이전트 시스템

**정의**: 여러 전문 에이전트가 협력하는 시스템

**에이전트 종류**:
- **분류 에이전트**: 질문 유형 분류
- **SQL 에이전트**: 데이터베이스 쿼리
- **생성 에이전트**: 답변 생성
- **평가 에이전트**: 답변 품질 평가

**협력 방식**:
```
사용자 질문
    ↓
분류 에이전트: "이건 대출 관련 질문이야"
    ↓
SQL 에이전트: "대출 상품 데이터 가져왔어"
    ↓
생성 에이전트: "답변 만들었어"
    ↓
평가 에이전트: "답변 품질 85점!"
    ↓
최종 답변
```

---

## 🔄 데이터 흐름

### 전체 시스템 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                    Phase 1: 데이터 준비 (최초 1회)           │
└─────────────────────────────────────────────────────────────┘

CSV 파일 (data/final_data.csv)
      ↓
load_csv.py → Document 객체 변환
      ↓
indexer.py → 배치 처리 (50개씩)
      ├─ embeddings.embed_texts() → 벡터 생성
      └─ vectorstore.add_documents() → DB 저장
      ↓
PostgreSQL + pgvector
  - documents 테이블에 500개 문서 저장
  - 각 문서는 3072차원 벡터 포함

┌─────────────────────────────────────────────────────────────┐
│                    Phase 2: 질의 응답 (매번)                │
└─────────────────────────────────────────────────────────────┘

사용자 질문: "국민은행 대출 금리는?"
      ↓
Streamlit UI (app.py)
      ↓
RAG Engine (engine.py)
      ↓
LangGraph Pipeline
      │
      ├─ 1. Normalize: "국민은행 대출 금리는" (정규화)
      │
      ├─ 2. Route: 은행명=국민은행, 상품종류=대출 (추출)
      │
      ├─ 3. Search:
      │    ├─ embeddings.embed_query() → [0.123, -0.456, ...]
      │    ├─ vectorstore.similarity_search() → 유사 문서 5개
      │    └─ 필터: bank_name='국민은행', product_type='대출'
      │
      ├─ 4. Generate:
      │    ├─ 프롬프트 생성 (질문 + 문서)
      │    ├─ llm.generate() → GPT 호출
      │    └─ 답변: "국민은행 대출 금리는..."
      │
      └─ 5. Format: 답변 + 참고 문서 정리
      ↓
Streamlit UI에 표시
  - 답변
  - 참고 문서 5개 (출처 표시)
```

---

### 인덱싱 상세 흐름

```
scripts/index_data.py 실행
      ↓
1. 설정 로드
   - DB_URL, OPENAI_API_KEY 등
      ↓
2. DB 연결
   - PostgreSQL 연결 풀 생성
   - 헬스 체크
      ↓
3. 임베딩 모델 초기화
   - OpenAIEmbeddings("text-embedding-3-large")
      ↓
4. CSV 로드
   - load_bank_data("data/final_data.csv")
   - 500개 Document 객체 생성
      ↓
5. 인덱서 초기화
   - DocumentIndexer(vectorstore, batch_size=50)
      ↓
6. 배치 처리 (10개 배치)
   
   Batch 1/10 (50개 문서)
      ├─ embeddings.embed_texts([doc1, doc2, ..., doc50])
      │  └─ OpenAI API 호출 → 50개 벡터 반환
      ├─ vectorstore.add_documents(batch)
      │  └─ INSERT INTO documents ... (50 rows)
      └─ logger.info("Progress: 10%")
   
   Batch 2/10 (50개 문서)
      ├─ embeddings.embed_texts([doc51, ..., doc100])
      ├─ vectorstore.add_documents(batch)
      └─ logger.info("Progress: 20%")
   
   ... (반복)
   
   Batch 10/10 (50개 문서)
      ├─ embeddings.embed_texts([doc451, ..., doc500])
      ├─ vectorstore.add_documents(batch)
      └─ logger.info("Progress: 100%")
      ↓
7. 통계 출력
   - 성공: 495개
   - 실패: 5개
   - 총 시간: 2분 30초
      ↓
8. 벡터 인덱스 생성
   - CREATE INDEX ... USING ivfflat
   - 검색 성능 향상
      ↓
완료! 이제 검색 가능
```

---

### 검색 상세 흐름

```
사용자 질문: "우리은행 예금 금리는?"
      ↓
1. Streamlit UI
   - 질문 입력
   - 필터 선택 (은행: 자동, 상품: 자동, Top-K: 8)
   - "검색" 버튼 클릭
      ↓
2. RAG Engine
   - rag_engine.query(
       question="우리은행 예금 금리는?",
       top_k=8,
       bank_name=None,
       product_type=None
     )
      ↓
3. LangGraph Pipeline 실행
   
   ┌─────────────────────────────────────────┐
   │  Node 1: Normalize Query                │
   │  - 입력: "우리은행 예금 금리는?"        │
   │  - 출력: "우리은행 예금 금리"           │
   │  - 작업: 공백 정리, 특수문자 제거       │
   └─────────────────────────────────────────┘
      ↓
   ┌─────────────────────────────────────────┐
   │  Node 2: Route Metadata                 │
   │  - 입력: "우리은행 예금 금리"           │
   │  - 분석: "우리은행" 키워드 발견         │
   │  - 분석: "예금" 키워드 발견             │
   │  - 출력: bank_name="우리은행"           │
   │          product_type="예적금"          │
   └─────────────────────────────────────────┘
      ↓
   ┌─────────────────────────────────────────┐
   │  Node 3: Vector Search                  │
   │                                          │
   │  Step 1: 쿼리 벡터화                    │
   │    embeddings.embed_query()             │
   │    → [0.234, -0.567, 0.123, ...]        │
   │                                          │
   │  Step 2: 유사도 검색                    │
   │    SELECT * FROM documents              │
   │    WHERE bank_name = '우리은행'         │
   │      AND product_type = '예적금'        │
   │    ORDER BY embedding <=> query_vector  │
   │    LIMIT 8;                             │
   │                                          │
   │  Step 3: 결과 반환                      │
   │    - 문서 1: 유사도 0.92 (정기예금)     │
   │    - 문서 2: 유사도 0.89 (적금)         │
   │    - 문서 3: 유사도 0.85 (예금)         │
   │    ... (총 8개)                         │
   └─────────────────────────────────────────┘
      ↓
   검색 결과 충분? (8개 >= 3개)
      ↓ YES
   ┌─────────────────────────────────────────┐
   │  Node 4: Generate Answer                │
   │                                          │
   │  Step 1: 프롬프트 생성                  │
   │    template = answer.j2                 │
   │    context = {                          │
   │      "query": "우리은행 예금 금리는?",  │
   │      "documents": [doc1, doc2, ...]     │
   │    }                                    │
   │    prompt = template.render(context)    │
   │                                          │
   │  Step 2: LLM 호출                       │
   │    llm.generate(                        │
   │      system="당신은 은행 전문가...",    │
   │      user=prompt                        │
   │    )                                    │
   │                                          │
   │  Step 3: 답변 생성                      │
   │    "우리은행 정기예금 금리는            │
   │     연 3.2%부터 시작하며..."            │
   └─────────────────────────────────────────┘
      ↓
   ┌─────────────────────────────────────────┐
   │  Node 5: Format Response                │
   │  - 답변 정리                            │
   │  - 참고 문서 정보 추가                  │
   │  - 메타데이터 포함                      │
   └─────────────────────────────────────────┘
      ↓
4. 결과 반환
   {
     "answer": "우리은행 정기예금 금리는...",
     "sources": [
       {
         "bank_name": "우리은행",
         "product_name": "정기예금",
         "clause": "제3조",
         "content": "..."
       },
       ...
     ],
     "num_sources": 8,
     "filters": {
       "bank_name": "우리은행",
       "product_type": "예적금"
     }
   }
      ↓
5. Streamlit UI 표시
   - 💬 답변 섹션
   - 📚 참고 문서 (8개, 접을 수 있음)
   - 🏦 적용된 필터 표시
```

---

## 🐳 Docker 구성 요소

### Docker Compose 구조

```yaml
# compose.yml
services:
  db:                          # PostgreSQL + pgvector
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: rag
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - ./docker/initdb:/docker-entrypoint-initdb.d  # 초기화 스크립트
      - pgdata:/var/lib/postgresql/data              # 데이터 영구 저장
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
  
  app:                         # Streamlit 애플리케이션
    build:
      context: .
      dockerfile: docker/Dockerfile.app
    environment:
      - DB_URL=postgresql://postgres:postgres@db:5432/rag
    env_file:
      - .env                   # OpenAI API 키 등
    ports:
      - "8501:8501"            # Streamlit 포트
    depends_on:
      db:
        condition: service_healthy  # DB 준비 완료 후 시작
    volumes:
      - ./data:/app/data       # 데이터 파일 마운트
      - ./rag:/app/rag         # 코드 마운트 (개발 시 편리)
    command: streamlit run app.py --server.port=8501

volumes:
  pgdata:                      # PostgreSQL 데이터 영구 저장
```

### 실행 시나리오

#### 시나리오 1: 최초 실행

```bash
$ docker-compose up -d

# 1. 이미지 다운로드/빌드
Pulling db (pgvector/pgvector:pg16)...
Building app...

# 2. 네트워크 생성
Creating network "skn18-3rd-3team_default"

# 3. 볼륨 생성
Creating volume "skn18-3rd-3team_pgdata"

# 4. db 서비스 시작
Creating rag_postgres...
  ├─ PostgreSQL 시작
  ├─ initdb/ 스크립트 실행
  │  ├─ 01_extensions.sql (pgvector 설치)
  │  └─ 02_schema.sql (테이블 생성)
  └─ 헬스 체크 통과

# 5. app 서비스 시작 (db 준비 완료 후)
Creating rag_app...
  ├─ Python 환경 구축
  ├─ RAG Engine 초기화
  └─ Streamlit 시작

# 6. 데이터 인덱싱 (수동)
$ docker-compose exec app python scripts/index_data.py
Loading 500 documents...
Batch 1/10: Progress 10%
...
Successfully indexed 495 documents!

# 7. 웹 접속
http://localhost:8501
```

#### 시나리오 2: 재시작 (데이터 유지)

```bash
$ docker-compose down
$ docker-compose up -d

# initdb/ 실행 안 됨 (볼륨 이미 존재)
# 인덱싱 불필요 (데이터 이미 존재)
# 바로 사용 가능!
```

#### 시나리오 3: 완전 초기화

```bash
$ docker-compose down -v  # 볼륨 삭제
$ docker-compose up -d

# initdb/ 다시 실행 (볼륨 비어있음)
# 인덱싱 다시 필요!
```

---

## ❓ FAQ

### Q1: embeddings와 ingestion의 차이는?

**A**: 
- **embeddings**: 텍스트 → 벡터 변환 **도구** (검색 시에도 사용)
- **ingestion**: CSV → DB 저장 **프로세스** (인덱싱 시에만 사용)

비유:
- embeddings = 용접기 (도구)
- ingestion = 자동차 공장 (전체 생산 라인)

---

### Q2: Dockerfile.app과 initdb/의 차이는?

**A**:
- **Dockerfile.app**: 애플리케이션 컨테이너 빌드 (Python 환경)
- **initdb/**: 데이터베이스 초기화 (테이블, 인덱스 생성)

| 항목 | Dockerfile.app | initdb/ |
|------|----------------|---------|
| 대상 | app 서비스 | db 서비스 |
| 실행 시점 | 이미지 빌드 시 | DB 최초 시작 시 |
| 재실행 | 이미지 재빌드 시 | 볼륨 삭제 시 |

---

### Q3: 인덱싱은 왜 필요한가?

**A**: RAG는 "검색 → 생성" 시스템입니다. 검색하려면 먼저 데이터를 벡터 DB에 넣어야 합니다!

```
인덱싱 없이는:
  사용자 질문 → 검색 → ❌ 문서 없음 → 답변 불가

인덱싱 후:
  사용자 질문 → 검색 → ✅ 문서 5개 → 답변 생성
```

---

### Q4: 인덱싱은 몇 번 해야 하나?

**A**: **최초 1회만!**

- ✅ 데이터는 Docker volume에 영구 저장
- ✅ 재시작해도 데이터 유지
- ⚠️ CSV 변경 시에만 재인덱싱 필요

확인 방법:
```bash
docker-compose exec app python -c "
from rag.db.connection import DatabaseConnection
from rag.db.repo import DocumentRepository
from rag.core.config import get_config

config = get_config()
db = DatabaseConnection(config.DB_URL)
repo = DocumentRepository(db)
print(f'문서 수: {repo.get_document_count()}')
"
```

---

### Q5: LangGraph는 왜 사용하나?

**A**: 복잡한 RAG 로직을 명확하게 구조화하기 위해!

**일반 코드**:
```python
def rag(query):
    q = normalize(query)
    m = extract_metadata(q)
    docs = search(q, m)
    if len(docs) < 3:
        q = rewrite(q)
        docs = search(q, m)
    return generate(q, docs)
```
→ 복잡하고 디버깅 어려움

**LangGraph**:
```python
workflow.add_node("normalize", normalize_query)
workflow.add_node("search", vector_search)
workflow.add_conditional_edges(
    "search",
    check_results,
    {"sufficient": "generate", "retry": "rewrite"}
)
```
→ 명확하고 시각화 가능

---

### Q6: 벡터 차원이 왜 3072인가?

**A**: OpenAI의 `text-embedding-3-large` 모델이 3072차원 벡터를 생성하기 때문!

| 모델 | 차원 | 성능 |
|------|------|------|
| text-embedding-ada-002 | 1536 | 보통 |
| text-embedding-3-small | 1536 | 좋음 |
| text-embedding-3-large | 3072 | 최고 |

차원이 높을수록:
- ✅ 더 정확한 의미 표현
- ✅ 더 높은 검색 정확도
- ⚠️ 더 많은 저장 공간
- ⚠️ 약간 느린 검색

---

### Q7: 검색 결과가 부족하면?

**A**: LangGraph가 자동으로 쿼리를 재작성하고 다시 검색합니다!

```
사용자 질문: "대출 금리"
    ↓
검색 → 문서 1개만 발견 (부족!)
    ↓
LLM으로 쿼리 재작성: "국민은행 주택담보대출 금리 조건"
    ↓
다시 검색 → 문서 5개 발견 (충분!)
    ↓
답변 생성
```

---

### Q8: 메타데이터 필터링이란?

**A**: 은행명, 상품종류로 검색 범위를 좁히는 기능!

```python
# 필터 없이
search("대출 금리")
→ 우리은행 + 국민은행 모든 대출 상품 (100개)

# 필터 적용
search("대출 금리", bank_name="국민은행", product_type="대출")
→ 국민은행 대출 상품만 (30개)
```

장점:
- ✅ 더 정확한 검색
- ✅ 더 빠른 속도
- ✅ 노이즈 감소

---

### Q9: 배치 처리는 왜 하나?

**A**: 효율성과 비용 절감!

```python
# 나쁜 방법 (1개씩)
for doc in documents:  # 1000개
    embed = openai.embed(doc)  # API 호출 1000번
    db.insert(embed)
# 시간: 10분, 비용: $10

# 좋은 방법 (50개씩)
for batch in chunks(documents, 50):  # 20번
    embeds = openai.embed(batch)  # API 호출 20번
    db.insert_many(embeds)
# 시간: 2분, 비용: $2
```

---

### Q10: 프로덕션 배포 시 주의사항은?

**A**:

1. **환경 변수 보안**
   ```bash
   # .env 파일을 git에 커밋하지 마세요!
   echo ".env" >> .gitignore
   ```

2. **DB 백업**
   ```bash
   docker-compose exec db pg_dump -U postgres rag > backup.sql
   ```

3. **로그 모니터링**
   ```bash
   docker-compose logs -f app
   ```

4. **리소스 제한**
   ```yaml
   # compose.yml
   services:
     app:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 4G
   ```

5. **HTTPS 설정** (Nginx 등)

---

## 🎓 학습 순서 추천

1. **기본 개념** (1일)
   - RAG란?
   - 임베딩이란?
   - 벡터 데이터베이스란?

2. **데이터 흐름** (1일)
   - CSV → 인덱싱 → 검색 → 답변

3. **코드 구조** (2일)
   - `rag/core/`, `rag/db/`
   - `rag/embeddings/`, `rag/llm/`
   - `rag/ingestion/`

4. **LangGraph** (2일)
   - 그래프 구조
   - 노드와 엣지
   - 조건부 분기

5. **실습** (3일)
   - Docker로 실행
   - 데이터 인덱싱
   - 질문 테스트
   - 코드 수정

---

## 📚 참고 자료

- [LangChain 공식 문서](https://python.langchain.com/)
- [LangGraph 가이드](https://langchain-ai.github.io/langgraph/)
- [pgvector 문서](https://github.com/pgvector/pgvector)
- [OpenAI API 문서](https://platform.openai.com/docs)

---

## 🤝 기여

이 문서는 프로젝트 이해를 돕기 위해 작성되었습니다.
질문이나 개선 사항이 있다면 팀원들과 공유해주세요!

---

**작성일**: 2025-10-25  
**버전**: 2.0  
**작성자**: AI Assistant (Claude Sonnet 4.5)

