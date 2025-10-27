# 🏦 은행상품 검색 LLM - 시작 가이드

## 📋 시스템 구성

### Multi-Agent RAG 시스템
- **생성용 LLM**: gpt-5-nano (분류, 답변생성, 쿼리재작성)
- **평가용 LLM**: gpt-5-mini (청크 관련성 평가)
- **임베딩**: text-embedding-3-large (3072차원)
- **데이터베이스**: PostgreSQL + pgvector
- **검색**: RDB (loan_info, bank_interest_rate) + VectorDB (documents)

---

## 🚀 빠른 시작

### 준비사항

`.env` 파일 설정:

#### 필수

```bash
# OpenAI API 키 (필수)
OPENAI_API_KEY=your_openai_api_key_here

# LLM 모델 설정 (기본값 사용 가능)
GEN_LLM_MODEL=gpt-5-nano
EVAL_LLM_MODEL=gpt-5-mini
EMBED_MODEL=text-embedding-3-large
```

#### 선택 (기능 사용 시)

```bash
# 웹 검색 사용 시 (Tavily)
TAVILY_API_KEY=your_tavily_api_key_here

# LangSmith 추적 사용 시
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=bank_rag
```

**참고**: Tavily와 LangSmith 없이도 기본 기능은 동작합니다.

---

## 📦 실행 방법 (Docker)

### 1단계: Docker 컨테이너 시작

```bash
# DB + App 컨테이너 시작
docker-compose up -d

# 컨테이너 상태 확인
docker-compose ps
```

**예상 출력**:
```
NAME          IMAGE                    STATUS
rag_postgres  pgvector/pgvector:pg16   Up (healthy)
rag_app       rag-app                  Up
```

### 2단계: 데이터베이스 초기화 확인

Docker가 자동으로 다음을 수행합니다:
- ✅ PostgreSQL + pgvector 확장 설치
- ✅ `rag` 스키마 생성 (Vector Store)
- ✅ `rdb` 스키마 생성 (Relational Data)
- ✅ CSV 데이터 자동 로드 (`loan_info`, `bank_interest_rate`)

**로그 확인**:
```bash
docker-compose logs db | grep -i "database system is ready"
```

### 3단계: 벡터 데이터 인덱싱 (최초 1회)

```bash
# Docker 컨테이너 내부에서 임베딩 생성 및 인덱싱
docker-compose exec app python scripts/index_data.py
```

**처리 과정**:
1. `data/final_embedding_data_v7.csv` 로드
2. OpenAI API로 임베딩 생성 (text-embedding-3-large)
3. PostgreSQL `documents` 테이블에 저장
4. 벡터 인덱스 생성 (IVFFlat)

**예상 소요 시간**: 데이터 크기에 따라 5-30분

**진행 상황 확인**:
```bash
# 실시간 로그 확인
docker-compose logs -f app
```

### 4단계: 웹 애플리케이션 접속

브라우저에서 접속:
```
http://localhost:8501
```

**Streamlit UI가 자동으로 열립니다!**

---

## 💬 질문 예시

### 금리 조회
```
우리은행 전세자금대출 금리는?
국민은행 주택담보대출 금리 알려줘
```

### 상품 조건
```
국민은행 신용대출 조건 알려줘
우리은행 전세자금대출 한도는?
```

### 대상별 추천
```
전문직 대상 대출 상품 추천해줘
청년 전용 대출 있어?
```

### 비교
```
우리은행과 국민은행 전세자금대출 비교해줘
```

---

## 🛠️ Docker 명령어 요약

### 기본 명령어

```bash
# 1. 컨테이너 시작 (DB + App)
docker-compose up -d

# 2. 상태 확인
docker-compose ps

# 3. 벡터 데이터 인덱싱 (최초 1회)
docker-compose exec app python scripts/index_data.py

# 4. 브라우저 접속
# http://localhost:8501
```

### 관리 명령어

```bash
# 재시작
docker-compose restart

# 중지
docker-compose stop

# 완전 삭제 (데이터 포함)
docker-compose down -v

# 로그 확인
docker-compose logs -f app        # App 로그
docker-compose logs -f db         # DB 로그
docker-compose logs -f            # 전체 로그
```

### 디버깅 명령어

```bash
# App 컨테이너 내부 접속
docker-compose exec app bash

# DB 컨테이너 내부 접속
docker-compose exec db psql -U postgres -d rag

# 데이터베이스 확인
docker-compose exec db psql -U postgres -d rag -c "SELECT COUNT(*) FROM documents;"
docker-compose exec db psql -U postgres -d rag -c "SELECT COUNT(*) FROM rdb.loan_info;"
docker-compose exec db psql -U postgres -d rag -c "SELECT COUNT(*) FROM rdb.bank_interest_rate;"
```

### 재빌드 (코드 변경 시)

```bash
# 이미지 재빌드
docker-compose build

# 재빌드 후 시작
docker-compose up -d --build
```

---

## 🔧 문제 해결

### 1. 포트 충돌 (5432, 8501)

**증상**: `port is already allocated` 오류

**해결**:
```bash
# 사용 중인 프로세스 확인 (Windows)
netstat -ano | findstr :5432
netstat -ano | findstr :8501

# 또는 docker-compose.yml에서 포트 변경
ports:
  - "5433:5432"  # DB
  - "8502:8501"  # App
```

### 2. 데이터베이스 연결 실패

**증상**: `connection refused` 오류

**해결**:
```bash
# DB 컨테이너 상태 확인
docker-compose ps db

# DB 로그 확인
docker-compose logs db

# DB 재시작
docker-compose restart db

# Health check 확인
docker-compose exec db pg_isready -U postgres
```

### 3. 임베딩 실패

**증상**: OpenAI API 오류

**해결**:
```bash
# .env 파일의 OPENAI_API_KEY 확인
cat .env | grep OPENAI_API_KEY

# API 키 테스트
docker-compose exec app python -c "import os; print(os.getenv('OPENAI_API_KEY'))"
```

### 4. 메모리 부족

**증상**: 컨테이너가 자주 재시작됨

**해결**:
- Docker Desktop 설정에서 메모리 할당 증가 (최소 4GB 권장)
- `scripts/index_data.py`의 `batch_size` 줄이기 (현재 20)

### 5. OpenAI API 에러

- `.env` 파일의 `OPENAI_API_KEY`가 올바른지 확인
- API 사용량 및 한도 확인

### 6. 인덱싱 실패

- CSV 파일 경로 확인: `data/final_data.csv`
- 데이터베이스 테이블이 생성되었는지 확인
- 로그에서 상세한 에러 메시지 확인

---

## 📚 추가 정보

### 프로젝트 구조

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

### 데이터베이스 스키마

**`rag` 스키마** (Vector Store):
- `documents`: 문서 청크 + 임베딩 (vector 3072)

**`rdb` 스키마** (Relational Data):
- `loan_info`: 대출 상품 메타데이터
- `bank_interest_rate`: 금리 정보

### 참고 문서

- `LLM_MODEL_VERIFICATION.md` - LLM 모델 사용 검증
- `DATABASE_VERIFICATION.md` - 데이터베이스 사용 검증
- `INIT_FILES_VERIFICATION.md` - __init__.py 검증
- `VERIFICATION_SUMMARY.md` - 전체 검증 요약

---

## ⚠️ 중요 사항

1. **모든 명령어는 Docker 컨테이너에서 실행됩니다**
   - 로컬 Python 설치 불필요
   - `docker-compose exec app python ...`은 app 컨테이너 내부의 Python 사용

2. **데이터 인덱싱은 최초 1회만 필요**
   - 이후에는 데이터가 DB에 저장되어 있음
   - 데이터 변경 시에만 재실행

3. **OpenAI API 키 필수**
   - 임베딩 생성 및 LLM 호출에 사용
   - `.env` 파일에 설정 필요

4. **벡터 차원 일치**
   - 임베딩 모델: text-embedding-3-large (3072차원)
   - DB 테이블: vector(3072)
   - 일치하지 않으면 오류 발생

---

## 🎉 완료!

이제 http://localhost:8501 에서 은행 상품 질의응답 서비스를 사용할 수 있습니다!
