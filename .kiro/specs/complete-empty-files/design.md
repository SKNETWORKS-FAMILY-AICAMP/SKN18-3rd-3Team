# Design Document

## Overview

비어있는 파일들을 완성하여 LangGraph 기반의 완전한 RAG 파이프라인을 구현합니다. LangGraph의 StateGraph를 사용하여 각 단계를 노드로 정의하고, 조건부 분기를 통해 동적인 파이프라인을 구성합니다.

## Architecture

### LangGraph Pipeline Flow

```
┌─────────────────────────────────────────────────────────┐
│                    LangGraph Pipeline                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐                                        │
│  │ START        │                                        │
│  └──────┬───────┘                                        │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────────┐                                    │
│  │ normalize_query  │  질의 정규화                       │
│  └──────┬───────────┘                                    │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────────┐                                    │
│  │ route_metadata   │  은행명/상품종류 추출              │
│  └──────┬───────────┘                                    │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────────┐                                    │
│  │ vector_search    │  벡터 검색                         │
│  └──────┬───────────┘                                    │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────────┐                                    │
│  │ check_results    │  결과 확인 (조건 분기)             │
│  └──────┬───────────┘                                    │
│         │                                                 │
│    ┌────┴────┐                                           │
│    │         │                                            │
│    ▼         ▼                                            │
│  부족?     충분?                                          │
│    │         │                                            │
│    │         ▼                                            │
│    │   ┌──────────────────┐                              │
│    │   │ generate_answer  │  LLM 답변 생성               │
│    │   └──────┬───────────┘                              │
│    │          │                                           │
│    │          ▼                                           │
│    │   ┌──────────────────┐                              │
│    │   │ format_response  │  응답 포맷팅                 │
│    │   └──────┬───────────┘                              │
│    │          │                                           │
│    │          ▼                                           │
│    │   ┌──────────────┐                                  │
│    │   │ END          │                                  │
│    │   └──────────────┘                                  │
│    │                                                      │
│    └──► (retry_count < 3) ──► vector_search (TOP_K++)   │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. State Definition

```python
from typing import TypedDict, List, Optional, Dict, Any
from langchain.schema import Document

class GraphState(TypedDict):
    """LangGraph 파이프라인 상태"""
    # Input
    query: str
    top_k: int
    
    # Extracted metadata
    bank_name: Optional[str]
    product_type: Optional[str]
    
    # Search results
    documents: List[Document]
    
    # Generation
    answer: str
    sources: List[Dict[str, Any]]
    
    # Control flow
    retry_count: int
    error: Optional[str]
```

### 2. Graph Nodes (`RAG/rag/graph/nodes.py`)

```python
from typing import Dict, Any
from RAG.core.logger import get_logger

logger = get_logger(__name__)

class GraphNodes:
    """LangGraph 노드 함수들"""
    
    def __init__(self, retriever, llm, jinja_env):
        self.retriever = retriever
        self.llm = llm
        self.jinja_env = jinja_env
    
    def normalize_query(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        질의 정규화 노드
        - 공백 제거, 소문자 변환 등
        """
        query = state["query"].strip()
        logger.info(f"Normalized query: {query[:100]}...")
        
        return {
            **state,
            "query": query
        }
    
    def route_metadata(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        메타데이터 라우팅 노드
        - 질의에서 은행명과 상품종류 추출
        """
        query = state["query"]
        
        # Extract bank name
        bank_name = state.get("bank_name")
        if not bank_name:
            if "우리은행" in query or "우리" in query:
                bank_name = "우리은행"
            elif "국민은행" in query or "국민" in query or "KB" in query:
                bank_name = "국민은행"
        
        # Extract product type
        product_type = state.get("product_type")
        if not product_type:
            if "대출" in query:
                product_type = "대출"
            elif "예금" in query or "적금" in query or "예적금" in query:
                product_type = "예적금"
        
        logger.info(f"Routed metadata - bank: {bank_name}, product: {product_type}")
        
        return {
            **state,
            "bank_name": bank_name,
            "product_type": product_type
        }
    
    def vector_search(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        벡터 검색 노드
        - 메타데이터 필터를 사용하여 검색
        """
        query = state["query"]
        top_k = state.get("top_k", 8)
        bank_name = state.get("bank_name")
        product_type = state.get("product_type")
        
        logger.info(f"Searching with top_k={top_k}")
        
        documents = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            bank_name=bank_name,
            product_type=product_type
        )
        
        logger.info(f"Found {len(documents)} documents")
        
        return {
            **state,
            "documents": documents
        }
    
    def generate_answer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM 답변 생성 노드
        """
        query = state["query"]
        documents = state["documents"]
        
        if not documents:
            return {
                **state,
                "answer": "죄송합니다. 관련된 정보를 찾을 수 없습니다.",
                "sources": []
            }
        
        # Load template
        template = self.jinja_env.get_template("answer.j2")
        prompt = template.render(query=query, documents=documents)
        
        # Generate answer
        system_prompt = "당신은 은행 상품 전문가입니다."
        answer = self.llm.generate(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.7
        )
        
        logger.info("Answer generated")
        
        return {
            **state,
            "answer": answer
        }
    
    def format_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        응답 포맷팅 노드
        - 출처 정보 추가
        """
        documents = state["documents"]
        
        sources = []
        for i, doc in enumerate(documents):
            source = {
                "index": i + 1,
                "bank_name": doc.metadata.get("은행명", ""),
                "product_name": doc.metadata.get("상품이름", ""),
                "clause": doc.metadata.get("조항", ""),
                "clause_name": doc.metadata.get("조항이름", ""),
                "content_preview": doc.page_content[:200] + "..."
            }
            sources.append(source)
        
        return {
            **state,
            "sources": sources
        }
```

### 3. Graph Edges (`RAG/rag/graph/edges.py`)

```python
from typing import Dict, Any, Literal

class GraphEdges:
    """LangGraph 조건부 엣지"""
    
    @staticmethod
    def check_search_results(
        state: Dict[str, Any]
    ) -> Literal["sufficient", "retry", "failed"]:
        """
        검색 결과 확인
        - 충분: generate_answer로 이동
        - 부족 & 재시도 가능: vector_search로 재시도
        - 실패: generate_answer로 이동 (빈 결과)
        """
        documents = state.get("documents", [])
        retry_count = state.get("retry_count", 0)
        top_k = state.get("top_k", 8)
        
        # 결과가 충분한 경우
        if len(documents) >= 3:
            return "sufficient"
        
        # 재시도 가능한 경우
        if retry_count < 2 and len(documents) < 3:
            # TOP_K 증가
            state["top_k"] = top_k + 5
            state["retry_count"] = retry_count + 1
            return "retry"
        
        # 재시도 불가능 (최대 재시도 도달)
        return "failed"
```

### 4. Graph Build (`RAG/rag/graph/build.py`)

```python
from langgraph.graph import StateGraph, END
from typing import Dict, Any

def build_rag_graph(nodes: GraphNodes) -> StateGraph:
    """
    RAG 파이프라인 그래프 빌드
    """
    # Define graph
    workflow = StateGraph(Dict[str, Any])
    
    # Add nodes
    workflow.add_node("normalize", nodes.normalize_query)
    workflow.add_node("route", nodes.route_metadata)
    workflow.add_node("search", nodes.vector_search)
    workflow.add_node("generate", nodes.generate_answer)
    workflow.add_node("format", nodes.format_response)
    
    # Add edges
    workflow.set_entry_point("normalize")
    workflow.add_edge("normalize", "route")
    workflow.add_edge("route", "search")
    
    # Conditional edge after search
    workflow.add_conditional_edges(
        "search",
        GraphEdges.check_search_results,
        {
            "sufficient": "generate",
            "retry": "search",
            "failed": "generate"
        }
    )
    
    workflow.add_edge("generate", "format")
    workflow.add_edge("format", END)
    
    # Compile
    return workflow.compile()
```

### 5. Engine Integration

RAG Engine을 LangGraph를 사용하도록 수정:

```python
# In RAG/rag/engine.py

from RAG.rag.graph.nodes import GraphNodes
from RAG.rag.graph.edges import GraphEdges
from RAG.rag.graph.build import build_rag_graph

class RAGEngine(metaclass=SingletonMeta):
    def __init__(self):
        # ... existing initialization ...
        
        # Initialize graph nodes
        graph_nodes = GraphNodes(
            retriever=self.retriever,
            llm=self.llm,
            jinja_env=self.jinja_env
        )
        
        # Build and compile graph
        self.graph = build_rag_graph(graph_nodes)
        logger.info("LangGraph pipeline compiled")
    
    def query(self, question: str, top_k: int = None, 
              bank_name: str = None, product_type: str = None):
        """Execute query through LangGraph pipeline"""
        
        # Initial state
        initial_state = {
            "query": question,
            "top_k": top_k or self.config.TOP_K,
            "bank_name": bank_name,
            "product_type": product_type,
            "documents": [],
            "answer": "",
            "sources": [],
            "retry_count": 0,
            "error": None
        }
        
        # Execute graph
        final_state = self.graph.invoke(initial_state)
        
        # Return result
        return {
            "answer": final_state["answer"],
            "sources": final_state["sources"],
            "num_sources": len(final_state["sources"]),
            "filters": {
                "bank_name": final_state.get("bank_name"),
                "product_type": final_state.get("product_type")
            }
        }
```

## Docker Configuration

### docker/requirements.txt

루트의 requirements.txt와 동일한 내용을 복사합니다.

### docker/initdb/01_extensions.sql

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### docker/initdb/02_schema.sql

```sql
-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    embedding vector(3072),
    content TEXT NOT NULL,
    bank_name VARCHAR(100) NOT NULL,
    product_type VARCHAR(50) NOT NULL,
    product_name VARCHAR(255),
    clause VARCHAR(255),
    clause_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS documents_bank_name_idx ON documents(bank_name);
CREATE INDEX IF NOT EXISTS documents_product_type_idx ON documents(product_type);
CREATE INDEX IF NOT EXISTS documents_doc_id_idx ON documents(doc_id);
CREATE INDEX IF NOT EXISTS documents_chunk_id_idx ON documents(chunk_id);

-- Vector index will be created after data insertion
-- CREATE INDEX documents_embedding_idx 
-- ON documents USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 100);
```

## Dependencies Update

requirements.txt에 LangGraph 추가:

```txt
# LangGraph
langgraph==0.0.20
```

## Testing Strategy

1. **Unit Tests**: 각 노드 함수 개별 테스트
2. **Integration Tests**: 전체 그래프 실행 테스트
3. **Edge Cases**: 빈 결과, 재시도 로직 테스트

## Design Decisions

1. **LangGraph 사용**: 파이프라인의 각 단계를 명확하게 분리하고 조건부 분기를 쉽게 구현
2. **상태 기반 설계**: 불변 상태를 전달하여 디버깅 용이
3. **재시도 로직**: 검색 결과가 부족할 때 자동으로 TOP_K를 증가시켜 재시도
4. **모듈화**: 노드, 엣지, 빌드를 별도 파일로 분리하여 유지보수성 향상
