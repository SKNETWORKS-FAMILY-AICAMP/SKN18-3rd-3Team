# Design Document

## Overview

우리은행+국민은행 대출 및 예적금 Q&A RAG 서비스는 LangChain과 OpenAI를 활용한 검색 증강 생성(RAG) 시스템입니다. 시스템은 CSV 데이터를 PostgreSQL의 pgvector에 인덱싱하고, 사용자 질의에 대해 관련 문서를 검색한 후 LLM을 통해 답변을 생성합니다.

핵심 설계 원칙:
- **모듈화**: 각 기능을 독립적인 모듈로 분리하여 유지보수성 향상
- **싱글톤 패턴**: 리소스 집약적인 객체(LLM, 임베더, DB)는 한 번만 초기화
- **환경 기반 설정**: 하드코딩 제거, `.env` 파일을 통한 설정 관리
- **확장성**: LangGraph를 활용한 유연한 파이프라인 구성

## Architecture

### High-Level Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP Request
       ▼
┌─────────────────────────────────────┐
│         Flask Application           │
│  (app.py - API Endpoint)            │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│         RAG Engine                  │
│  (Singleton - rag/rag/engine.py)    │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│      LangGraph Pipeline             │
│  (rag/rag/graph/)                   │
│  ┌─────────────────────────────┐    │
│  │ 1. Query Normalization      │    │
│  │ 2. Metadata Routing         │    │
│  │ 3. Vector Search            │    │
│  │ 4. LLM Generation           │    │
│  │ 5. Response Formatting      │    │
│  └─────────────────────────────┘    │
└──────┬──────────────────────────────┘
       │
       ├──────────────┬──────────────┐
       ▼              ▼              ▼
┌─────────────┐ ┌──────────┐ ┌────────────┐
│ VectorStore │ │   LLM    │ │ Embeddings │
│  (pgvector) │ │ (OpenAI) │ │  (OpenAI)  │
└─────────────┘ └──────────┘ └────────────┘
```

### Data Flow

1. **Indexing Flow**:
   ```
   CSV File → load_csv.py → Document Objects → 
   Embeddings → pgvector_store.py → PostgreSQL
   ```

2. **Query Flow**:
   ```
   User Query → API → RAG Engine → LangGraph Pipeline →
   Vector Search → LLM Generation → Response
   ```

## Components and Interfaces

### 1. Core Module (`rag/core/`)

#### config.py
```python
class Config:
    """환경 변수 기반 설정 관리"""
    OPENAI_API_KEY: str
    DB_URL: str
    EMBED_MODEL: str = "text-embedding-3-large"
    LLM_MODEL: str = "gpt-5-nano"
    TOP_K: int = 8
    PGVECTOR_INDEX: str = "ivfflat"
    OPENAI_TIMEOUT: int = 30
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from .env file"""
```

#### singleton.py
```python
class SingletonMeta(type):
    """Thread-safe singleton metaclass"""
    _instances = {}
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
```

#### logger.py
```python
def get_logger(name: str) -> logging.Logger:
    """구조화된 로거 생성"""
    # JSON 포맷 로깅 설정
    # 레벨별 핸들러 구성
```

### 2. Database Module (`rag/db/`)

#### connection.py
```python
class DatabaseConnection(metaclass=SingletonMeta):
    """PostgreSQL 커넥션 풀 관리"""
    
    def __init__(self, db_url: str):
        self.pool = psycopg_pool.ConnectionPool(db_url)
    
    def get_connection(self) -> psycopg.Connection:
        """커넥션 풀에서 커넥션 획득"""
    
    def health_check(self) -> bool:
        """데이터베이스 연결 상태 확인"""
```

#### repo.py
```python
class DocumentRepository:
    """문서 메타데이터 CRUD 작업"""
    
    def create_tables(self) -> None:
        """테이블 및 인덱스 생성"""
    
    def upsert_document(self, doc_id: str, vector: List[float], 
                       text: str, metadata: Dict) -> None:
        """문서 업서트"""
    
    def search_similar(self, query_vector: List[float], 
                      top_k: int, filters: Dict) -> List[Dict]:
        """유사도 검색"""
    
    def get_document_count(self) -> int:
        """전체 문서 수 조회"""
```

### 3. Embeddings Module (`rag/embeddings/`)

#### provider.py
```python
class EmbeddingProvider(ABC):
    """임베딩 추상 인터페이스"""
    
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """텍스트 리스트를 벡터로 변환"""
    
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """단일 쿼리를 벡터로 변환"""
```

#### openai_embed.py
```python
class OpenAIEmbeddings(EmbeddingProvider, metaclass=SingletonMeta):
    """OpenAI 임베딩 구현"""
    
    def __init__(self, model: str, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """배치 임베딩 with 재시도 로직"""
    
    def embed_query(self, text: str) -> List[float]:
        """단일 쿼리 임베딩"""
```

### 4. LLM Module (`rag/llm/`)

#### openai_chat.py
```python
class OpenAIChatModel(metaclass=SingletonMeta):
    """OpenAI 채팅 모델 래퍼"""
    
    def __init__(self, model: str, api_key: str, timeout: int):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.timeout = timeout
    
    def generate(self, system_prompt: str, user_prompt: str,
                temperature: float = 0.7) -> str:
        """답변 생성"""
```

### 5. VectorStore Module (`rag/vectorstore/`)

#### pgvector_store.py
```python
class PgVectorStore(VectorStore):
    """LangChain VectorStore 인터페이스 구현"""
    
    def __init__(self, connection: DatabaseConnection, 
                embeddings: EmbeddingProvider):
        self.connection = connection
        self.embeddings = embeddings
    
    def add_documents(self, documents: List[Document]) -> List[str]:
        """문서 추가 (임베딩 + 저장)"""
    
    def similarity_search_with_score(
        self, query: str, k: int, filter: Dict
    ) -> List[Tuple[Document, float]]:
        """유사도 검색"""
    
    @classmethod
    def from_documents(cls, documents: List[Document], 
                      embeddings: EmbeddingProvider,
                      connection: DatabaseConnection) -> 'PgVectorStore':
        """초기화 헬퍼"""
```

#### sql.py
```python
# SQL 쿼리 함수들
def get_upsert_query() -> str:
    """UPSERT SQL 반환"""

def get_search_query(index_type: str) -> str:
    """벡터 검색 SQL 반환 (IVFFLAT/HNSW)"""

def get_create_table_query() -> str:
    """테이블 생성 SQL 반환"""
```

#### types.py
```python
@dataclass
class SearchResult:
    """검색 결과 DTO"""
    document: Document
    score: float
    metadata: Dict[str, Any]
```

### 6. RAG Module (`rag/rag/`)

#### retriever.py
```python
class BankRetriever:
    """메타데이터 필터링을 지원하는 검색기"""
    
    def __init__(self, vectorstore: PgVectorStore):
        self.vectorstore = vectorstore
    
    def retrieve(self, query: str, top_k: int,
                bank_name: Optional[str] = None,
                product_type: Optional[str] = None) -> List[Document]:
        """필터링된 검색"""
```

#### graph/nodes.py
```python
class GraphNodes:
    """LangGraph 노드 함수들"""
    
    @staticmethod
    def normalize_query(state: Dict) -> Dict:
        """질의 정규화"""
    
    @staticmethod
    def route_metadata(state: Dict) -> Dict:
        """은행명/상품종류 추출"""
    
    @staticmethod
    def vector_search(state: Dict) -> Dict:
        """벡터 검색 수행"""
    
    @staticmethod
    def generate_answer(state: Dict) -> Dict:
        """LLM 답변 생성"""
    
    @staticmethod
    def format_response(state: Dict) -> Dict:
        """응답 포맷팅"""
```

#### graph/edges.py
```python
class GraphEdges:
    """LangGraph 엣지 조건"""
    
    @staticmethod
    def should_retry_search(state: Dict) -> str:
        """검색 결과 부족 시 재시도 여부"""
    
    @staticmethod
    def should_expand_k(state: Dict) -> str:
        """TOP_K 확장 여부"""
```

#### graph/build.py
```python
def build_rag_graph() -> CompiledGraph:
    """RAG 파이프라인 그래프 구성"""
    workflow = StateGraph(GraphState)
    
    # 노드 추가
    workflow.add_node("normalize", GraphNodes.normalize_query)
    workflow.add_node("route", GraphNodes.route_metadata)
    workflow.add_node("search", GraphNodes.vector_search)
    workflow.add_node("generate", GraphNodes.generate_answer)
    workflow.add_node("format", GraphNodes.format_response)
    
    # 엣지 추가
    workflow.add_edge("normalize", "route")
    workflow.add_conditional_edge("search", 
                                 GraphEdges.should_retry_search,
                                 {"retry": "search", "continue": "generate"})
    
    return workflow.compile()
```

#### prompts/answer.j2
```jinja2
당신은 은행 상품 전문가입니다. 다음 문서를 참고하여 질문에 답변하세요.

{% for doc in documents %}
[출처: {{ doc.metadata.은행명 }} - {{ doc.metadata.상품이름 }} - {{ doc.metadata.조항이름 }}]
{{ doc.page_content }}
{% endfor %}

질문: {{ query }}

답변 시 다음을 준수하세요:
1. 출처를 명확히 밝히세요
2. 정확한 정보만 제공하세요
3. 모르는 내용은 "관련 정보를 찾을 수 없습니다"라고 답변하세요
```

#### engine.py
```python
class RAGEngine(metaclass=SingletonMeta):
    """RAG 엔진 싱글톤"""
    
    def __init__(self):
        self.config = Config.from_env()
        self.db = DatabaseConnection(self.config.DB_URL)
        self.embeddings = OpenAIEmbeddings(
            self.config.EMBED_MODEL, 
            self.config.OPENAI_API_KEY
        )
        self.vectorstore = PgVectorStore(self.db, self.embeddings)
        self.llm = OpenAIChatModel(
            self.config.LLM_MODEL,
            self.config.OPENAI_API_KEY,
            self.config.OPENAI_TIMEOUT
        )
        self.graph = build_rag_graph()
    
    def query(self, question: str) -> Dict[str, Any]:
        """질의 처리"""
        result = self.graph.invoke({"query": question})
        return result
```

### 7. Ingestion Module (`rag/ingestion/`)

#### load_csv.py
```python
def load_bank_data(csv_path: str) -> List[Document]:
    """CSV 파일을 Document 객체로 변환"""
    df = pd.read_csv(csv_path)
    documents = []
    
    for _, row in df.iterrows():
        metadata = {
            "은행명": row["은행명"],
            "상품종류": row["상품종류"],
            "상품이름": row["상품이름"],
            "조항": row["조항"],
            "조항이름": row["조항이름"],
            "chunk_id": row["chunk_id"],
            "doc_id": row["doc_id"]
        }
        doc = Document(
            page_content=row["context"],
            metadata=metadata
        )
        documents.append(doc)
    
    return documents
```

#### indexer.py
```python
class DocumentIndexer:
    """대량 인덱싱 관리"""
    
    def __init__(self, vectorstore: PgVectorStore, batch_size: int = 100):
        self.vectorstore = vectorstore
        self.batch_size = batch_size
        self.logger = get_logger(__name__)
    
    def index_documents(self, documents: List[Document]) -> None:
        """배치 인덱싱 with 진행률 로깅"""
        total = len(documents)
        for i in range(0, total, self.batch_size):
            batch = documents[i:i+self.batch_size]
            try:
                self.vectorstore.add_documents(batch)
                self.logger.info(f"Indexed {i+len(batch)}/{total} documents")
            except Exception as e:
                self.logger.error(f"Failed to index batch {i}: {e}")
                # 재시도 로직
```

#### chunking.py
```python
def rechunk_documents(documents: List[Document], 
                     chunk_size: int = 1300,
                     overlap: int = 150) -> List[Document]:
    """문서 재청킹 (옵션)"""
    # RecursiveCharacterTextSplitter 사용
```

## Data Models

### Database Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    embedding vector(3072),  -- text-embedding-3-large dimension
    content TEXT NOT NULL,
    bank_name VARCHAR(100) NOT NULL,
    product_type VARCHAR(50) NOT NULL,
    product_name VARCHAR(255),
    clause VARCHAR(255),
    clause_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 벡터 인덱스 (IVFFLAT)
CREATE INDEX documents_embedding_idx 
ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 메타데이터 인덱스
CREATE INDEX documents_bank_name_idx ON documents(bank_name);
CREATE INDEX documents_product_type_idx ON documents(product_type);
CREATE INDEX documents_doc_id_idx ON documents(doc_id);
```

### Application Models

```python
@dataclass
class GraphState:
    """LangGraph 상태"""
    query: str
    normalized_query: str
    bank_name: Optional[str]
    product_type: Optional[str]
    documents: List[Document]
    answer: str
    sources: List[Dict]
    top_k: int
    retry_count: int
```

## Error Handling

### Error Categories

1. **Configuration Errors**: 환경 변수 누락, 잘못된 설정 값
2. **Database Errors**: 연결 실패, 쿼리 오류, 트랜잭션 실패
3. **API Errors**: OpenAI API 호출 실패, 타임아웃, 레이트 리밋
4. **Data Errors**: CSV 파싱 오류, 잘못된 데이터 형식
5. **Runtime Errors**: 메모리 부족, 예상치 못한 예외

### Error Handling Strategy

```python
class RAGException(Exception):
    """Base exception for RAG system"""
    pass

class ConfigurationError(RAGException):
    """Configuration related errors"""
    pass

class DatabaseError(RAGException):
    """Database related errors"""
    pass

class APIError(RAGException):
    """External API errors"""
    pass

# 재시도 데코레이터
@retry(stop=stop_after_attempt(3), 
       wait=wait_exponential(multiplier=1, min=2, max=10))
def call_openai_api(...):
    """OpenAI API 호출 with 재시도"""
```

### Logging Strategy

```python
# 각 모듈별 로거 사용
logger = get_logger(__name__)

# 구조화된 로깅
logger.info("Indexing started", extra={
    "document_count": len(documents),
    "batch_size": batch_size
})

logger.error("API call failed", extra={
    "error_type": type(e).__name__,
    "error_message": str(e),
    "retry_count": retry_count
}, exc_info=True)
```

## Testing Strategy

### Unit Tests

1. **Core Module Tests**
   - Config 로딩 테스트
   - Singleton 패턴 테스트
   - Logger 설정 테스트

2. **Database Module Tests**
   - 커넥션 풀 테스트
   - CRUD 작업 테스트
   - 트랜잭션 테스트

3. **Embeddings Module Tests**
   - 임베딩 생성 테스트 (Mock)
   - 배치 처리 테스트
   - 에러 핸들링 테스트

4. **VectorStore Module Tests**
   - 문서 추가 테스트
   - 검색 테스트
   - 필터링 테스트

### Integration Tests

1. **End-to-End RAG Pipeline**
   - CSV 로드 → 인덱싱 → 검색 → 생성
   - 메타데이터 필터링 통합 테스트
   - 에러 복구 테스트

2. **API Tests**
   - 엔드포인트 테스트
   - 요청/응답 검증
   - 에러 응답 테스트

### Test Environment

```python
# pytest fixtures
@pytest.fixture
def test_db():
    """테스트용 DB 설정"""
    # 테스트 DB 생성
    yield db
    # 테스트 DB 정리

@pytest.fixture
def mock_openai():
    """OpenAI API Mock"""
    with patch('openai.OpenAI') as mock:
        yield mock
```

## Deployment Considerations

### Docker Configuration

```yaml
# compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: rag
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - ./docker/initdb:/docker-entrypoint-initdb.d
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
  
  app:
    build:
      context: .
      dockerfile: docker/Dockerfile.app
    environment:
      - DB_URL=postgresql://postgres:postgres@db:5432/rag
    env_file:
      - .env
    ports:
      - "5000:5000"
    depends_on:
      - db
    volumes:
      - ./data:/app/data

volumes:
  pgdata:
```

### Environment Variables

```bash
# .env
OPENAI_API_KEY=sk-...
EMBED_MODEL=text-embedding-3-large
LLM_MODEL=gpt-5-nano
OPENAI_TIMEOUT=30

DB_URL=postgresql://postgres:postgres@localhost:5432/rag
PGVECTOR_INDEX=ivfflat
TOP_K=8

LOG_LEVEL=INFO
```

### Performance Optimization

1. **Indexing Optimization**
   - 배치 크기 조정 (100-500)
   - 병렬 처리 고려
   - 중복 체크 최적화

2. **Search Optimization**
   - 적절한 벡터 인덱스 선택 (IVFFLAT vs HNSW)
   - 메타데이터 인덱스 활용
   - 쿼리 캐싱 고려

3. **Resource Management**
   - 커넥션 풀 크기 조정
   - 싱글톤 인스턴스 재사용
   - 메모리 사용량 모니터링

## Security Considerations

1. **API Key Management**
   - 환경 변수로 관리
   - `.env` 파일 `.gitignore`에 추가
   - 프로덕션 환경에서는 시크릿 관리 서비스 사용

2. **Database Security**
   - 강력한 비밀번호 사용
   - 네트워크 격리
   - SQL 인젝션 방지 (파라미터화된 쿼리)

3. **Input Validation**
   - 사용자 입력 검증
   - 쿼리 길이 제한
   - 특수 문자 처리

## Design Decisions and Rationales

### 1. LangChain vs Custom Implementation
**Decision**: LangChain 사용  
**Rationale**: 표준 인터페이스, 풍부한 생태계, 빠른 개발 속도

### 2. PostgreSQL + pgvector vs Specialized Vector DB
**Decision**: PostgreSQL + pgvector  
**Rationale**: 단일 데이터베이스로 관계형 + 벡터 데이터 관리, 운영 복잡도 감소

### 3. LangGraph vs Simple Pipeline
**Decision**: LangGraph 사용  
**Rationale**: 복잡한 분기 로직, 재시도 메커니즘, 디버깅 용이성

### 4. Singleton Pattern for Resources
**Decision**: 싱글톤 패턴 적용  
**Rationale**: 리소스 효율성, 초기화 비용 절감, 일관된 상태 관리

### 5. Jinja2 for Prompts
**Decision**: Jinja2 템플릿 사용  
**Rationale**: 프롬프트 관리 용이성, 버전 관리, 재사용성
