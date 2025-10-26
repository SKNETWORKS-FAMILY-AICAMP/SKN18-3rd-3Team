# RAG 시스템 아키텍처

Multi-Agent RAG 파이프라인 구조 및 실행 흐름

## 워크플로우

```
Start → Classify → SQL → Vector → Eval → Generate → Format → End
                     ↓                ↓
                  실패 시          부족 시
                     ↓                ↓
                    End      Rewrite + Web → Vector
```

### 실행 흐름

1. **Classify**: 질의 분류 및 키워드 추출 (은행, 상품, 대출종류)
2. **SQL**: RDB 검색 → 실패 시 "다시 질문하세요" 종료
3. **Vector**: VectorDB 검색 (top_k=8)
4. **Eval**: 청크 관련성 평가 (LLM) → 부족 시 재시도 (1회)
5. **Rewrite + Web**: 질문 재생성 + 웹 검색 (병렬)
6. **Generate**: 최종 답변 생성 (SQL + Vector + Web)
7. **Format**: 출처 포맷팅 (문서명 표시)

## 주요 컴포넌트

### Agents (비즈니스 로직)

| Agent | 파일 | 역할 | LLM |
|-------|------|------|-----|
| **Classify** | `classify_agent.py` | 질의 분류, 키워드 추출 | gpt-4o-mini |
| **SQL** | `sql_agent.py` | RDB 검색 (상품 정보) | - |
| **Eval** | `eval_agent.py` | 청크 관련성 평가 | gpt-4o |
| **Generate** | `gen_agent.py` | 최종 답변 생성 | gpt-4o-mini |

### Nodes (단순 변환)

| Node | 파일 | 역할 |
|------|------|------|
| **Vector Search** | `search_vectordb_node.py` | VectorDB 검색 |
| **Rewrite Query** | `rewrite_query_node.py` | 질문 재생성 |
| **Web Search** | `search_web_node.py` | Tavily 웹 검색 |
| **Format** | `format_response_node.py` | 출처 포맷팅 |

## 핵심 기능

- **Dual LLM**: 생성(gpt-4o-mini) + 평가(gpt-4o)
- **하이브리드 검색**: SQL + VectorDB + Web
- **재시도 로직**: 1회 재시도 (질문 재생성 + 웹 검색)
- **Fail-Fast**: SQL 실패 시 즉시 종료
- **LangSmith**: 선택적 추적 및 모니터링

## 데이터 흐름

```
question
  ↓
classify_agent → {intent, bank_name, product_name, loan_type}
  ↓
sql_agent → {sql_results: 상품 메타데이터}
  ↓
vector_search → {vector_chunks: 약관 청크 (top_k=8)}
  ↓
eval_agent → {relevant_chunks: 관련 청크 (임계값 35.0)}
  ↓ (부족 시)
rewrite + web → {재생성 쿼리 + 웹 결과}
  ↓
gen_agent → {answer: SQL + Vector + Web 통합}
  ↓
format → {formatted_answer: 출처 포함}
```

## 사용 예시

```python
from rag.graph.build import create_rag_system
from rag.llm.get_llm import get_llm_model

llm = get_llm_model()
graph = create_rag_system(
    llm=llm,
    vectorstore=vectorstore,
    top_k=8,
    relevance_threshold=35.0,
    enable_langsmith=True
)

result = graph.invoke({"question": "우리은행 전세자금대출 금리는?"})
print(result["answer"])
```
