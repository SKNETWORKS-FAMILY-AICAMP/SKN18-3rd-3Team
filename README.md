# 우리은행 + 국민은행 대출 및 예적금 Q&A RAG 서비스

우리은행과 국민은행의 대출 및 예적금 상품에 대한 질문에 답변하는 RAG(Retrieval-Augmented Generation) 기반 Q&A 서비스입니다.

## 주요 기능

- 🏦 우리은행 및 국민은행 상품 정보 검색
- 💰 대출 및 예적금 상품 Q&A
- 🔍 벡터 기반 유사도 검색 (pgvector)
- 🤖 OpenAI GPT를 활용한 자연어 답변 생성
- 📊 메타데이터 필터링 (은행명, 상품종류)
- 🐳 Docker 기반 배포

## 기술 스택

- **Frontend/Backend**: Python 3.11, Streamlit
- **Database**: PostgreSQL 16 + pgvector
- **Embeddings**: OpenAI text-embedding-3-large (3072차원)
- **LLM**: OpenAI gpt-5-nano
- **Vector Store**: pgvector (IVFFLAT/HNSW)
- **Framework**: LangChain
- **Deployment**: Docker Compose

## 프로젝트 구조

```
.
├── RAG/                    # RAG 시스템 모듈
│   ├── core/              # 핵심 유틸리티 (config, logger, singleton)
│   ├── db/                # 데이터베이스 연결 및 레포지토리
│   ├── embeddings/        # 임베딩 프로바이더
│   ├── llm/               # LLM 모델
│   ├── vectorstore/       # 벡터 스토어 구현
│   ├── ingestion/         # 데이터 로딩 및 인덱싱
│   └── rag/               # RAG 엔진 및 파이프라인
├── data/                  # 데이터 파일
│   └── merged_bankdata.csv
├── docker/                # Docker 설정
│   ├── Dockerfile.app
│   └── initdb/
│       └── init.sql
├── scripts/               # 유틸리티 스크립트
│   └── index_data.py
├── app.py                 # Streamlit 웹 애플리케이션
├── compose.yml            # Docker Compose 설정
├── requirements.txt       # Python 의존성
└── .env                   # 환경 변수
```

## 설치 및 실행

### 1. 사전 요구사항

- Docker 및 Docker Compose 설치
- OpenAI API 키

### 2. 환경 변수 설정

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

- CSV 파일 경로 확인: `data/merged_bankdata.csv`
- 데이터베이스 테이블이 생성되었는지 확인
- 로그에서 상세한 에러 메시지 확인
