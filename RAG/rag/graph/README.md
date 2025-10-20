# RAG LangGraph Pipeline

이 폴더는 LangGraph를 사용한 RAG 파이프라인의 그래프 구조를 정의합니다.

## 그래프 구조 시각화

```
┌─────────────┐
│   START     │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  normalize_query    │  ← 질의 정규화 (공백 제거 등)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  route_metadata     │  ← 은행명/상품종류 자동 추출
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  vector_search      │◄─┐ ← 벡터 검색 (메타데이터 필터링)
└──────────┬──────────┘  │
           │              │
           ▼              │
      ┌────────┐          │
      │ 검색결과 │          │
      │  확인   │          │
      └───┬────┘          │
          │               │
    ┌─────┼─────┐         │
    │     │     │         │
    ▼     ▼     ▼         │
 충분함  부족   실패       │
    │     │     │         │
    │     └─────┴─────────┘ (retry: top_k 증가, 최대 2회)
    │
    ▼
┌─────────────────────┐
│  generate_answer    │  ← LLM 답변 생성
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  format_response    │  ← 출처 정보 포맷팅
└──────────┬──────────┘
           │
           ▼
      ┌────────┐
      │  END   │
      └────────┘
```

## 파일 구조

### `state.py`
**그래프 상태 정의**

파이프라인을 통과하면서 업데이트되는 상태 객체를 정의합니다.

```python
class GraphState(TypedDict):
    # 입력
    query: str                    # 사용자 질의
    top_k: int                    # 검색할 문서 수
    
    # 추출된 메타데이터
    bank_name: Optional[str]      # 은행명 (예: "우리은행")
    product_type: Optional[str]   # 상품종류 (예: "대출")
    
    # 검색 결과
    documents: List[Document]     # 검색된 문서들
    
    # 생성 결과
    answer: str                   # LLM이 생성한 답변
    sources: List[Dict]           # 출처 정보
    
    # 제어 흐름
    retry_count: int              # 재시도 횟수
    error: Optional[str]          # 에러 메시지
```

### `nodes.py`
**그래프 노드 함수들**

각 노드는 상태를 입력받아 처리하고 업데이트된 상태를 반환합니다.

#### 1. `normalize_query`
- **역할**: 질의 정규화
- **처리**: 공백 제거, 문자열 정리
- **입력**: `query`
- **출력**: 정규화된 `query`

#### 2. `route_metadata`
- **역할**: 메타데이터 자동 추출
- **처리**: 
  - 질의에서 은행명 추출 (우리은행, 국민은행, KB 등)
  - 상품종류 추출 (대출, 예금, 적금 등)
- **입력**: `query`
- **출력**: `bank_name`, `product_type`
- **예시**:
  - "우리은행 대출 금리는?" → bank_name="우리은행", product_type="대출"
  - "KB 예금 상품 알려줘" → bank_name="국민은행", product_type="예적금"

#### 3. `vector_search`
- **역할**: 벡터 유사도 검색
- **처리**:
  - 질의를 임베딩으로 변환
  - 메타데이터 필터 적용 (은행명, 상품종류)
  - pgvector를 사용한 유사도 검색
- **입력**: `query`, `top_k`, `bank_name`, `product_type`
- **출력**: `documents`
- **에러 처리**: 검색 실패 시 빈 리스트 반환

#### 4. `generate_answer`
- **역할**: LLM 답변 생성
- **처리**:
  - Jinja2 템플릿으로 프롬프트 생성
  - OpenAI API 호출
  - 검색된 문서 기반 답변 생성
- **입력**: `query`, `documents`
- **출력**: `answer`
- **특수 케이스**:
  - 문서가 없으면: "관련 정보를 찾을 수 없습니다" 반환
  - 생성 실패 시: 에러 메시지 반환

#### 5. `format_response`
- **역할**: 출처 정보 포맷팅
- **처리**:
  - 각 문서의 메타데이터 추출
  - 은행명, 상품명, 조항, 내용 미리보기 구성
- **입력**: `documents`
- **출력**: `sources` (리스트 형태)

### `edges.py`
**조건부 엣지 (분기 로직)**

#### `check_search_results`
검색 결과를 평가하고 다음 단계를 결정합니다.

**분기 조건**:

1. **"sufficient"** (충분함)
   - 조건: 문서 수 ≥ 3개
   - 동작: `generate_answer`로 진행

2. **"retry"** (재시도)
   - 조건: 문서 수 < 3개 AND 재시도 횟수 < 2
   - 동작: 
     - `top_k`를 5씩 증가 (예: 8 → 13 → 18)
     - `retry_count` 증가
     - `vector_search`로 돌아가서 재검색

3. **"failed"** (실패)
   - 조건: 재시도 횟수 ≥ 2
   - 동작: 현재 결과로 `generate_answer`로 진행

**재시도 로직 예시**:
```
1차 검색: top_k=8  → 결과 2개 → 재시도
2차 검색: top_k=13 → 결과 1개 → 재시도
3차 검색: top_k=18 → 결과 1개 → 포기하고 진행
```

### `build.py`
**그래프 빌드 및 컴파일**

#### `build_rag_graph(nodes: GraphNodes)`
LangGraph 워크플로우를 구성하고 컴파일합니다.

**구성 단계**:
1. StateGraph 생성
2. 노드 추가 (normalize, route, search, generate, format)
3. 엔트리 포인트 설정 (normalize)
4. 엣지 추가:
   - 순차 엣지: normalize → route → search
   - 조건부 엣지: search → (sufficient/retry/failed)
   - 순차 엣지: generate → format → END
5. 그래프 컴파일

## 실행 흐름 예시

### 성공 케이스 (충분한 결과)
```
입력: "우리은행 주택담보대출 금리는?"

1. normalize_query
   → query: "우리은행 주택담보대출 금리는?"

2. route_metadata
   → bank_name: "우리은행"
   → product_type: "대출"

3. vector_search (top_k=8)
   → documents: [doc1, doc2, doc3, doc4, doc5]  (5개 검색)

4. check_search_results
   → 5개 ≥ 3개 → "sufficient"

5. generate_answer
   → answer: "우리은행 주택담보대출의 금리는..."

6. format_response
   → sources: [{bank_name: "우리은행", ...}, ...]

7. END
```

### 재시도 케이스 (부족한 결과)
```
입력: "KB 특판 예금 조건은?"

1. normalize_query
   → query: "KB 특판 예금 조건은?"

2. route_metadata
   → bank_name: "국민은행"
   → product_type: "예적금"

3. vector_search (top_k=8)
   → documents: [doc1, doc2]  (2개만 검색)

4. check_search_results
   → 2개 < 3개 AND retry_count=0 → "retry"
   → top_k: 8 → 13
   → retry_count: 0 → 1

5. vector_search (top_k=13) [재시도]
   → documents: [doc1, doc2, doc3, doc4]  (4개 검색)

6. check_search_results
   → 4개 ≥ 3개 → "sufficient"

7. generate_answer
   → answer: "KB 특판 예금의 조건은..."

8. format_response
   → sources: [...]

9. END
```

### 실패 케이스 (결과 없음)
```
입력: "신한은행 펀드 상품"

1. normalize_query
   → query: "신한은행 펀드 상품"

2. route_metadata
   → bank_name: None (신한은행은 DB에 없음)
   → product_type: None

3. vector_search (top_k=8)
   → documents: []  (0개)

4. check_search_results
   → 0개 < 3개 AND retry_count=0 → "retry"

5. vector_search (top_k=13) [재시도 1]
   → documents: []  (0개)

6. check_search_results
   → 0개 < 3개 AND retry_count=1 → "retry"

7. vector_search (top_k=18) [재시도 2]
   → documents: []  (0개)

8. check_search_results
   → retry_count=2 → "failed"

9. generate_answer
   → answer: "죄송합니다. 관련된 정보를 찾을 수 없습니다."

10. format_response
    → sources: []

11. END
```

## 사용 방법

### 기본 사용
```python
from RAG.rag.graph import build_rag_graph, GraphNodes
from RAG.rag.retriever import BankRetriever
from RAG.llm.openai_chat import OpenAIChatModel
from jinja2 import Environment, FileSystemLoader

# 컴포넌트 초기화
retriever = BankRetriever()
llm = OpenAIChatModel()
jinja_env = Environment(loader=FileSystemLoader("RAG/rag/prompts"))

# 노드 생성
nodes = GraphNodes(retriever, llm, jinja_env)

# 그래프 빌드
graph = build_rag_graph(nodes)

# 실행
initial_state = {
    "query": "우리은행 대출 금리는?",
    "top_k": 8,
    "retry_count": 0
}

result = graph.invoke(initial_state)

print(result["answer"])
print(result["sources"])
```

### 메타데이터 지정
```python
# 은행명과 상품종류를 직접 지정
initial_state = {
    "query": "금리가 가장 낮은 상품은?",
    "bank_name": "우리은행",
    "product_type": "대출",
    "top_k": 8,
    "retry_count": 0
}

result = graph.invoke(initial_state)
```

## 장점

### 1. 명확한 흐름
- 각 단계가 독립적인 노드로 분리
- 디버깅 및 테스트 용이

### 2. 유연한 제어
- 조건부 분기로 동적 처리
- 재시도 로직으로 검색 품질 향상

### 3. 상태 관리
- 모든 중간 결과가 상태에 저장
- 각 단계의 입출력 추적 가능

### 4. 확장성
- 새로운 노드 추가 용이
- 다양한 분기 조건 구현 가능

## 개선 가능한 부분

1. **하이브리드 검색**: 벡터 검색 + 키워드 검색 결합
2. **리랭킹**: 검색 결과를 재정렬하는 노드 추가
3. **캐싱**: 동일 질의에 대한 결과 캐싱
4. **스트리밍**: LLM 응답을 스트리밍으로 반환
5. **멀티턴 대화**: 이전 대화 컨텍스트 유지

## 참고 자료

- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [LangGraph 튜토리얼](https://langchain-ai.github.io/langgraph/tutorials/)
- [StateGraph API](https://langchain-ai.github.io/langgraph/reference/graphs/)
