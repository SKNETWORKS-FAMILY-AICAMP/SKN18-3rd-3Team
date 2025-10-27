# 프로젝트 개요
- 목표: 
사회초년생인 우리는 아직 모아둔 돈이 많지 않고, 큰 위험을 감수할 여유도 없다. 그래서 먼저 예·적금처럼 안정적인 방법으로 종잣돈을 만들고, 필요한 경우에는 대출을 현명하게 선택하는 데 초점을 맞추기로 했다. 예·적금은 기본·우대금리, 납입 기간, 중도해지 조건 등에 따라 실제 손에 들어오는 이자가 크게 달라지고, 대출은 금리 유형(고정/변동), 한도, 보증·담보, 중도상환수수료 같은 요소가 생활비와 장기 계획에 직접적인 영향을 준다. 문제는 이런 정보가 은행·기관마다 흩어져 있어 비교가 번거롭고, 우대조건을 하나만 놓쳐도 금리가 달라진다는 점이다. 바로 이 지점을 해결하고자 한다.
사용자가 정보를 입력하면 그에 맞는 예·적금과 대출을 한 화면에서 추천해 줄 수 있고 우리는 이 서비스를 통해 복잡한 금융 정보를 “한눈에, 내 이야기처럼” 정리해 주고 싶다. 예·적금으로 안전하게 종잣돈을 만들고, 필요할 때는 무리하지 않는 선에서 대출을 고르는 일! 그 과정이 더는 막막하지 않도록. 정보의 비대칭을 줄이고, 조건을 놓쳐 손해 보는 일이 없도록 도와주려 한다.

# 우리은행 + 국민은행 대출 및 예적금 Q&A RAG 서비스

우리은행과 국민은행의 대출 및 예적금 상품에 대한 질문에 답변하는 RAG(Retrieval-Augmented Generation) 기반 Q&A 서비스입니다.

# 데이터 출처
국민은행 / 우리은행 약관

## 주요 기능

- 🏦 우리은행 및 국민은행 상품 정보 검색
- 💰 대출 및 예적금 상품 Q&A
- 🔍 벡터 기반 유사도 검색 (pgvector)
- 🤖 OpenAI GPT를 활용한 자연어 답변 생성
- 📊 메타데이터 필터링 (은행명, 상품종류)
- 🐳 Docker 기반 배포

## 기술 스택

- **Language**: Python 3.11
- **Frontend/Backend**: Streamlit
- **Database**: PostgreSQL 16 + pgvector
- **Embeddings**: OpenAI text-embedding-3-large (3072차원)
- **LLM**: OpenAI gpt-5-nano
- **Vector Store**: pgvector (IVFFLAT/HNSW)
- **Framework**: LangChain + LangGraph
- **Deployment**: Docker Compose

## 프로젝트 구조

```
SKN18-3rd-3Team/
├── app.py                                  # 메인 애플리케이션
├── docker-compose.yml                      # Docker Compose 설정
├── README.md                               # 프로젝트 구조 및 설명
├── Start.md                                # 프로젝트 실행 준비 및 과정
├── .env                                    # 환경 변수 (LLM 설정 추가)
│
├── rag/                                    # RAG 시스템 핵심 모듈
│   ├── core/                               # 핵심 설정
│   │   ├── config.py                       # 환경 설정 (LLM 모델 분리)
│   │   ├── logger.py                       # 프로젝트 로그 저장 및 출력
│   │   └── singleton.py                    # 싱글톤 class 정의
│   │
│   ├── llm/                                # LLM 모듈
│   │   └── get_llm.py                      # 생성용/평가용 LLM 호출
│   │
│   ├── embeddings/                         # 임베딩 모듈
│   │   ├── openai_embed.py                 # OpenAI Embeddings (1536차원)
│   │   └── provider.py                     # 임베딩 provider 인터페이스 정의
│   │
│   ├── vectorstore/                        # 벡터 저장소
│   │   ├── pgvector_store.py               # PostgreSQL + pgvector
│   │   └── sql.py                          # 3072차원
│   │
│   ├── db/                                 # 데이터베이스
│   │   ├── connection.py                   # DB 연결 관리
│   │   └── repo.py                         # DB 레포지토리
│   │
│   ├── ingestion/                          # 데이터 수집
│   │   ├── load_csv.py                     # 은행 약관/대출정보/금리 문서 로드
│   │   └── indexer.py                      # 문서 리스트를 받아 벡터스토어(DB)에 추가
│   │
│   ├── graph/                              # LangGraph 구조
│   │   ├── build.py                        # LangGraph node-edge 연결 및 조건분기(구성)
│   │   ├── State.py                        # 사용자 정의 State
│   │   │
│   │   ├── multiAgent/                       # Multi-Agent 시스템
│   │   │   ├── classify_agent.py             # 분류 에이전트
│   │   │   ├── sql_agent.py                  # SQL 검색 에이전트
│   │   │   ├── eval_agent.py                 # 웹 검색/vectordb 검색 결과 평가 및 선택
│   │   │   └── gen_agent.py                  # 답변 취합 및 생성
│   │   │
│   │   ├── nodes/                            # LangGraph 노드들
│   │   │   ├── classify_node.py              # 분류 노드
│   │   │   ├── search_sql_node.py            # SQL 검색 노드
│   │   │   ├── search_vectordb_node.py       # 벡터 검색 노드
│   │   │   ├── search_web_node.py            # 웹 검색 노드
│   │   │   ├── eval_node.py                  # 웹 검색/vectordb 검색 결과 평가 및 선택 노드
│   │   │   ├── generate_answer_node.py       # 답변 생성 노드
│   │   │   ├── format_response_node.py       # 응답 포맷팅 노드
│   │   │   ├── response_formatting_node.py   # 응답 포맷팅 노드
│   │   │   └── rewrite_query_node.py         # 쿼리 재작성 노드
│   │   │
│   │   └── route/                            # 라우팅 로직
│   │       ├── __init__.py
│   │       ├── route_classify.py             # 분류 기반 라우팅
│   │       └── route_eval.py                 # 평가 기반 라우팅
│   │
│   └── langsmith/                            # LangSmith 모니터링
│       ├── tracer.py                         # 트레이싱 설정
│       └── utils.py                          # 유틸리티 함수
│  
│  
├── scripts/                          # 실행 스크립트
│   ├── index_data.py                 # 은행 데이터를 벡터스토어에 적재
│   ├── test.py                       # RAG 테스트, 임계값 35.0
│   └── visualize_graph.py            # 그래프 시각화
│
├── data/                             # 데이터 파일
│   ├── final_embedding_data_v7.csv   # Vector DB용 데이터 (8,097개 청크)
│   └── RDB/                          # RDB용 데이터
│       ├── bank_rate.csv             # 은행 금리 데이터
│       └── loan_products_RDB.csv     # 대출 상품 데이터
│
└── docker/                           # Docker 설정
    ├── Dockerfile.app                # 앱 Dockerfile
    ├── requirements.txt                        # Python 패키지 의존성
    └── initdb/                       # DB 초기화 스크립트
        ├── 01_init.sql         # PostgreSQL 확장
        ├── bank_rate.csv             # 금리 데이터
        ├── final_embedding_data_v7.csv   # 임베딩 데이터
        └── loan_products_RDB.csv     # 대출 상품 데이터
```

## Vector Database, Relational Database 설계
---

![ERD](image/erd_ver1.png)


## 프로젝트 설계
---
![Architecture Diagram](image/diagram.png)


---
                             작동 방식

                      ┏ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┓
                      ┃         Start         ┃
                      ┗ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┛
                                 🔽
                      ┏ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┓
                      ┃       질의정규화      ┃
                      ┗ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┛
                                 🔽
                      ┏ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┓
                      ┃      Keyword 추출     ┃
                      ┗ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┛
                                 🔽
                      ┏ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┓
                      ┃ SQL Database RDB 검색 ┃
                      ┗ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┛
            ┏━━━━━━━━━━━━━━━━━━━━🔽
            ┃         ┏ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┓
            ┃         ┃     Vector DB 검색    ┃
            ┃         ┗ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┛
            ┃                     ┃                        
                                  ┃ ◀━━━━━━━━━━━━━━━━━━┓
            S                     ┃                    ┃
            Q                top_k = 8개        ┏ ━ ━ ━ ━ ━━ ┓  
            L           ┏━━━━━━━━━╋━━━━━━━━━┓   ┃ 질문재생성 ┣━━━┓
                        ┃         ┃         ┃   ┗ ━━ ━ ━ ━ ━ ┛   ┃  
           검          충분      부족      0개         ┃         ┃
           색           ┃         ┃         ┃          ┃         ┃
           결           ┃         ┗━━━━━━━━━┻━━━━━━━━━━┛         ┃
           과           ┃                                        ▼
                   top_k = 4개                            ┏ ━ ━ ━ ━ ━━ ┓  
            ┃           ┃ ◀━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫   웹검색   ┃
            ┃           ┃                                 ┗ ━━ ━ ━ ━ ━ ┛ 
            ┃           ┃
            ┃           ┃
            ┃           ┃
            ┃           ┗━━━━━━━━━┓
            ┃                     ▼
            ┃         ┏ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┓
            ┃         ┃    Chunk 내용 검증    ┣━━━━━━━▶ 다시 질문을 입력하세요!
            ┃         ┗ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┛
            ┗━━━━━━━━━━━━━━━━━━▶ 🔽
                      ┏ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┓
                      ┃     LLM 답변 생성     ┃
                      ┗ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┛
                                 🔽
                      ┏ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┓
                      ┃     출처 Fomatting    ┃
                      ┗ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┛
                                 🔽
                      ┏ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┓
                      ┃         E N D         ┃
                      ┗ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ┛


## 데이터 적재 파이프라인 (프로젝트 반영 버전)

1. **CSV → LangChain Document**
   - 원본: `data/final_embedding_data_v4.csv` (현재 스크립트 기본값)
   - 필수 컬럼: `chunk_id`, `doc_id`, `은행명`, `상품종류`, `상품이름`, `조항`, `조항이름`, `조항내용`
   - 구현: `rag/ingestion/load_csv.py`
     - 본문: `조항내용` → 없으면 `context`/`text`
     - 유효성: 공백/NaN/10자 미만 본문은 스킵
     - 메타데이터: `chunk_id`, `doc_id`, `은행명`, `상품종류`, `상품이름`, `조항`, `조항이름`

2. **임베딩 생성 (OpenAI)**
   - 파일: `rag/embeddings/openai_embed.py`
   - 모델: `.env`의 `EMBED_MODEL` (예: `text-embedding-3-large`)
   - 설정: `OPENAI_API_KEY`, `OPENAI_TIMEOUT`

3. **PgVector 저장 (Upsert)**
   - 테이블: `documents` (초기 스키마 `docker/initdb/02_schema.sql`)
   - SQL 템플릿: `rag/vectorstore/sql.py`
   - 메타 인덱스: `은행명`, `상품종류` 등 기본 인덱스 포함
   - 보조 스키마/데이터: `docker/initdb/03_rdb_load.sql`에서 `rdb.loan_info`, `rdb.bank_interest_rate` 자동 적재

4. **인덱싱 실행 (`scripts/index_data.py`)**
   - 필요: DB 컨테이너 기동 (`docker compose up -d`)
   - 실행: `docker compose exec app python scripts/index_data.py`
   - 기본 CSV 경로는 스크립트 내에서 `./data/final_embedding_data_v4.csv`
   - 배치 처리, 진행 로그, 최종 문서 수 출력

5. **벡터 인덱스(선택)**
   - 대량 데이터 시 COPY 후 생성 권장
   - IVFFLAT:
     ```
     CREATE INDEX IF NOT EXISTS documents_embedding_idx
       ON documents USING ivfflat (embedding vector_cosine_ops)
       WITH (lists = 100);
     ```
   - HNSW:
     ```
     CREATE INDEX IF NOT EXISTS documents_embedding_idx
       ON documents USING hnsw (embedding vector_cosine_ops)
       WITH (m = 16, ef_construction = 64);
     ```

6. **적재 검증**
   - 컨테이너 내부에서 문서 수 확인:
     ```
     docker compose exec db psql -U postgres -d rag -c "SELECT COUNT(*) FROM documents;"
     ```

---

## 노드/에이전트 구성 (route 폴더 제외 최신 구조 기준)

### Nodes (`rag/graph/nodes`)
1. **`classify_node.py`**
   - `run_intent_agent` 호출 → intent, 은행, 상품명 등 추출 후 상태에 저장.
   - LLM confidence가 낮으면 규칙 기반 fallback 적용 기록을 함께 남깁니다.

2. **`search_sql_node.py`**
   - intent가 금융 관련(`rate_fee_lookup`, `clause_lookup`, `compare`, `definition`)이고 confidence ≥ 0.5일 때만 `SQLRetrievalAgent.run` 호출.
   - `sql_results`, `sql_contents`, `debug["sql"]`에 SQL/금리 정보를 정리해 넣습니다.
   - 조건 미달이면 SQL을 스킵하고 빈 결과를 반환합니다.

3. **`search_vectordb_node.py`**
   - PgVector 기반 유사도 검색. SQL 결과 또는 분류 키워드를 활용해 쿼리를 구성합니다.
   - 검색 결과를 LangChain Document → dict 형태로 변환해 `vector_chunks` 등에 저장합니다.

4. **`eval_node.py`**
   - `EvaluationAgent.run` 호출로 각 청크의 관련성(점수+YES/NO)을 평가.
   - 임계값(`relevance_threshold`) 미만 청크 제거, 디버그에 점수/판정 기록.

5. **`generate_answer_node.py` & `format_response_node.py`**
   - `GenerationAgent.run`으로 SQL 요약 + 관련 청크를 조합해 답변 생성.
   - `format_response`에서 출력 구조(답변, 참고 소스 등)를 정리하고 그래프를 종료합니다.

### Multi-Agent (`rag/graph/multiAgent`)
1. **`classify_agent.py`**
   - LLM으로 intent, bank_name, product_name, loan_type, loan_target, clause_keywords 추출.
   - 규칙 기반 fallback과 키워드 토큰화(`raw_keywords`)로 downstream LIKE 검색을 보조합니다.

2. **`sql_agent.py` (`SQLRetrievalAgent`)**
   - `rdb.loan_info`에서 상품 후보, `rdb.bank_interest_rate`에서 금리 정보를 결합.
   - `selection_reason`, `interest_rates`, `loan_info_match` 같은 필드를 구성하고, intent/신뢰도 검사를 통해 무관한 질문을 필터링합니다.
   - `product_keywords`가 없을 경우에도 fallback으로 금리 테이블 검색을 수행합니다.

3. **`eval_agent.py`**
   - Vector 검색 결과 청크를 LLM으로 평가(0~100, YES/NO).
   - 임계값 이상 청크만 `relevant_chunks`로 유지하여 생성 단계의 품질을 높입니다.

4. **`gen_agent.py`**
   - SQL 요약과 청크를 사용해 최종 답변 텍스트를 생성하고, 출처(`sources`)를 함께 제공합니다.



# 설치 및 실행
## 1. 사전 요구사항
- Docker 및 Docker Compose 설치
- OpenAI API 키

## 2. 환경 변수 설정
`.env` 파일을 생성하고 다음 내용을 입력하세요:
```bash
# OpenAI
OPENAI_API_KEY=your-api-key-here
EMBED_MODEL=text-embedding-3-large     # 3세대 임베딩(3072차원)
LLM_MODEL=gpt-5-nano                   # 응답 생성 모델
OPENAI_TIMEOUT=30

# DB
DB_URL=postgresql://postgres:postgres@db:5432/rag
PGVECTOR_INDEX=ivfflat                 # 또는 hnsw
TOP_K=8
```
### 3. Docker로 실행

```bash
# 1. Docker Compose로 전체 시스템 시작
docker-compose up -d

# 2. 데이터 인덱싱 (최초 1회만 실행)
docker-compose exec app python scripts/index_data.py

docker-compose exec app python -c "from RAG.db.connection import DatabaseConnection; from RAG.db.repo import DocumentRepository; from RAG.core.config import get_config; config = get_config(); db = DatabaseConnection(config.DB_URL); repo = DocumentRepository(db); print(f'문서 수: {repo.get_document_count()}')"
# 인덱싱되어있는지 확인

# 3. 브라우저에서 접속
# http://localhost:8501
```

**추가 명령어:**
```bash
# 로그 확인
docker-compose logs -f app

# 시스템 종료
docker-compose down

# 데이터베이스까지 완전 삭제 (재인덱싱 필요)
docker-compose down -v
```

**참고:**
- 인덱싱은 **최초 1회만** 실행하면 됩니다
- 데이터는 Docker volume에 저장되어 재시작해도 유지됩니다
- CSV 데이터 변경 시에만 재인덱싱이 필요합니다

## 사용 방법

### 웹 인터페이스

1. 브라우저에서 `http://localhost:8501` 접속
2. 질문 입력창에 질문 작성
3. 사이드바에서 검색 옵션 설정 (선택사항):
   - 은행 선택: 자동 감지 / 우리은행 / 국민은행
   - 상품 종류: 자동 감지 / 대출 / 예적금
   - 검색 문서 수: 3~15개
4. "🔍 검색" 버튼 클릭
5. 답변 및 참고 문서 확인

### 질문 예시

- "국민은행 대출 금리는 어떻게 되나요?"
- "우리은행 예금 상품에는 어떤 것이 있나요?"
- "중도상환수수료는 얼마인가요?"
- "대출 한도는 어떻게 결정되나요?"
- "금리 우대 조건은 무엇인가요?"

## 데이터 인덱싱

CSV 데이터를 벡터 데이터베이스에 인덱싱하려면:

```bash
# Docker 환경 (권장)
docker-compose exec app python scripts/index_data.py

# 가상환경
python scripts/index_data.py
```

**인덱싱 관련 참고사항:**
- 인덱싱은 **최초 1회만** 실행하면 됩니다
- 데이터는 PostgreSQL volume에 영구 저장됩니다
- Docker 재시작 후에도 데이터가 유지되므로 재인덱싱 불필요
- 인덱싱 완료 여부 확인:
```bash
docker-compose exec app python -c "from RAG.db.connection import DatabaseConnection; from RAG.db.repo import DocumentRepository; from RAG.core.config import get_config; config = get_config(); db = DatabaseConnection(config.DB_URL); repo = DocumentRepository(db); print(f'인덱싱된 문서 수: {repo.get_document_count()}')"
```

**재인덱싱이 필요한 경우:**
- CSV 데이터 파일이 변경되었을 때
- `docker-compose down -v`로 volume을 삭제했을 때
- 데이터베이스를 초기화했을 때

## 개발

### 코드 구조

- **Core 모듈**: 설정, 로깅, 싱글톤 패턴
- **Database 모듈**: PostgreSQL 연결 및 CRUD
- **Embeddings 모듈**: OpenAI 임베딩 생성
- **LLM 모듈**: OpenAI GPT 답변 생성
- **VectorStore 모듈**: pgvector 기반 벡터 검색
- **Ingestion 모듈**: CSV 로딩 및 인덱싱
- **RAG 모듈**: 검색 및 생성 파이프라인

### 로깅

시스템은 자동으로 로그를 출력합니다:
- 인덱싱 진행 상황
- 검색 쿼리 및 결과
- 에러 및 경고 메시지
- 데이터베이스 연결 상태

## 문제 해결

### 데이터베이스 연결 실패

```bash
# PostgreSQL이 실행 중인지 확인
docker-compose ps

# 데이터베이스 로그 확인
docker-compose logs db
```

### OpenAI API 에러

- `.env` 파일의 `OPENAI_API_KEY`가 올바른지 확인
- API 사용량 및 한도 확인

### 인덱싱 실패

- CSV 파일 경로 확인: `data/final_data.csv`
- 데이터베이스 테이블이 생성되었는지 확인
- 로그에서 상세한 에러 메시지 확인


# 테스트 성능 및 평가


# 실행 화면


# 실행 확인


# 후기
이태호(팀장) : 
박세영 :
임승옥 :
최준호 :
김영우 :
김창현 :
