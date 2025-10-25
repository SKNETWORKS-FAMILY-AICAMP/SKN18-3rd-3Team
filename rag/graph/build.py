"""
Multi-Agent RAG Graph Builder

전체 RAG 플로우를 LangGraph로 구현
- Multi-Agent 구조 (Classify, SQL, Vector, Eval, Generation)
- Route 기반 조건부 분기
- LangSmith 추적 및 모니터링
"""

from __future__ import annotations
from typing import Any, Dict, Optional, TypedDict
from langgraph.graph import StateGraph, END

# Agent imports
from rag.graph.multiAgent.classify_agent import run_intent_agent
from rag.graph.multiAgent.sql_agent import SQLRetrievalAgent
from rag.graph.multiAgent.eval_agent import EvaluationAgent
from rag.graph.multiAgent.gen_agent import GenerationAgent

# Node imports (실제 사용하는 것만)
from rag.graph.nodes.search_vectordb_node import create_vector_search_node

# LangSmith imports
from rag.langsmith.tracer import LangSmithTracer

# Core imports
from rag.core.logger import get_logger
from rag.retriever import BankRetriever
from rag.graph.State import State

logger = get_logger(__name__)


def build_rag_graph(
    llm: Any,
    retriever: BankRetriever,
    top_k: int = 8,
    relevance_threshold: float = 60.0,
    enable_routing: bool = False,
    enable_langsmith: bool = False
):
    """
    Multi-Agent RAG 파이프라인 그래프 빌드
    
    Parameters
    ----------
    llm : Any
        생성용 LLM 모델 (gpt-5-nano, temperature=1.0)
    retriever : BankRetriever
        Vector DB retriever
    top_k : int
        Vector 검색 시 가져올 청크 개수 (기본값: 8)
    relevance_threshold : float
        청크 관련성 임계값 0-100 (기본값: 60.0)
    enable_routing : bool
        조건부 라우팅 활성화 여부 (기본값: False)
    enable_langsmith : bool
        LangSmith 추적 활성화 여부 (기본값: False)
    
    Returns
    -------
    compiled_graph
        컴파일된 LangGraph workflow
    
    Examples
    --------
    >>> from rag.llm.get_llm import get_llm_model
    >>> from rag.retriever import BankRetriever
    >>> llm = get_llm_model()
    >>> retriever = BankRetriever()
    >>> graph = build_rag_graph(llm, retriever, enable_routing=True)
    >>> result = graph.invoke({"question": "우리은행 전세자금대출 금리는?"})
    """
    logger.info("Building Multi-Agent RAG graph...")
    logger.info(f"  - Routing: {'enabled' if enable_routing else 'disabled'}")
    logger.info(f"  - LangSmith: {'enabled' if enable_langsmith else 'disabled'}")
    logger.info(f"  - Top-K: {top_k}, Threshold: {relevance_threshold}")
    
    # ═══════════════════════════════════════════════════════
    # 1. Agent 초기화
    # ═══════════════════════════════════════════════════════
    sql_agent = SQLRetrievalAgent()
    eval_agent = EvaluationAgent(relevance_threshold=relevance_threshold)
    gen_agent = GenerationAgent(llm=llm)
    
    # ═══════════════════════════════════════════════════════
    # 2. Node 생성 함수
    # ═══════════════════════════════════════════════════════
    
    def classify_node(state: State) -> State:
        """1. Classification Node"""
        logger.info("=== Step 1: Classification ===")
        question = state["question"]
        
        # Agent 호출
        result = run_intent_agent(
            question=question,
            llm=llm,
            debug=True
        )
        
        # 상태 업데이트
        state["intent"] = result.get("intent", "")
        state["bank_name"] = result.get("bank_name")
        state["product_name"] = result.get("product_name")
        state["product_type"] = result.get("product_type")
        state["loan_type"] = result.get("loan_type")
        state["loan_target"] = result.get("loan_target")
        state["clause_keywords"] = result.get("clause_keywords", [])
        state["confidence"] = result.get("confidence", 0.0)
        state["reasoning"] = result.get("reasoning", "")
        state["debug"] = {"classify": result.get("debug", {})}
        
        logger.info(f"Classified: intent={state['intent']}, bank={state['bank_name']}")
        return state
    
    def sql_node(state: State) -> State:
        """2. SQL Retrieval Node"""
        logger.info("=== Step 2: SQL Retrieval ===")
        
        # Agent 호출
        state = sql_agent.run(state)
        
        sql_count = len(state.get("sql_results", []))
        logger.info(f"SQL search found {sql_count} products")
        return state
    
    def vector_node(state: State) -> State:
        """3. Vector DB Retrieval Node"""
        logger.info("=== Step 3: Vector DB Retrieval ===")
        
        # Vector 검색 함수 생성 및 실행
        vector_search_fn = create_vector_search_node(retriever)
        search_state = {
            "query": state["question"],
            "top_k": top_k,
            "bank_name": state.get("bank_name"),
            "product_type": state.get("product_type"),
            # SQL 결과 전달 (Fallback 로직용)
            "sql_results": state.get("sql_results", []),
            # Classification 결과 전달 (Fallback 로직용)
            "product_name": state.get("product_name"),
            "loan_type": state.get("loan_type")
        }
        
        result_state = vector_search_fn(search_state)
        
        # documents를 vector_chunks로 변환
        documents = result_state.get("documents", [])
        vector_chunks = []
        
        for doc in documents:
            chunk = {
                "content": doc.page_content if hasattr(doc, "page_content") else str(doc),
                "metadata": doc.metadata if hasattr(doc, "metadata") else {},
                "doc_id": doc.metadata.get("doc_id", "") if hasattr(doc, "metadata") else "",
                "chunk_id": doc.metadata.get("chunk_id", "") if hasattr(doc, "metadata") else "",
                "bank_name": doc.metadata.get("은행명", "") if hasattr(doc, "metadata") else "",
                "document_name": doc.metadata.get("문서명", "") if hasattr(doc, "metadata") else "",
                "product_type": doc.metadata.get("상품종류", "") if hasattr(doc, "metadata") else "",
                "product_name": doc.metadata.get("상품이름", "") if hasattr(doc, "metadata") else "",
                "clause": doc.metadata.get("조항", "") if hasattr(doc, "metadata") else "",
                "clause_name": doc.metadata.get("조항이름", "") if hasattr(doc, "metadata") else ""
            }
            vector_chunks.append(chunk)
        
        state["vector_chunks"] = vector_chunks
        state["vector_chunks_count"] = len(vector_chunks)
        state["used_fallback_search"] = result_state.get("used_fallback_search", False)
        
        debug = state.get("debug", {})
        debug["vector"] = {
            "query": state["question"],
            "top_k": top_k,
            "results_count": len(vector_chunks),
            "used_fallback": state["used_fallback_search"]
        }
        state["debug"] = debug
        
        if state["used_fallback_search"]:
            logger.info(f"Vector search found {len(vector_chunks)} chunks (using Classification fallback)")
        else:
            logger.info(f"Vector search found {len(vector_chunks)} chunks (using SQL results)")
        return state
    
    def eval_node(state: State) -> State:
        """4. Evaluation Node"""
        logger.info("=== Step 4: Chunk Evaluation ===")
        
        # Agent 호출
        state = eval_agent.run(state)
        
        relevant_count = state.get("relevant_chunks_count", 0)
        logger.info(f"Evaluation: {relevant_count} relevant chunks")
        return state
    
    def generation_node(state: State) -> State:
        """5. Answer Generation Node"""
        logger.info("=== Step 5: Answer Generation ===")
        
        # Agent 호출
        state = gen_agent.run(state)
        
        answer_len = len(state.get("answer", ""))
        logger.info(f"Generated answer: {answer_len} characters")
        return state
    
    # ═══════════════════════════════════════════════════════
    # 3. 그래프 정의
    # ═══════════════════════════════════════════════════════
    workflow = StateGraph(State)
    
    # 노드 추가
    workflow.add_node("classify", classify_node)
    workflow.add_node("sql", sql_node)
    workflow.add_node("vector", vector_node)
    workflow.add_node("eval", eval_node)
    workflow.add_node("generate", generation_node)
    
    logger.info("Added all nodes to graph")
    
    # ═══════════════════════════════════════════════════════
    # 4. 엣지 추가 (순차 실행 - 라우팅 비활성화)
    # ═══════════════════════════════════════════════════════
    workflow.set_entry_point("classify")
    workflow.add_edge("classify", "sql")
    workflow.add_edge("sql", "vector")
    workflow.add_edge("vector", "eval")
    workflow.add_edge("eval", "generate")
    workflow.add_edge("generate", END)
    
    logger.info("Added all edges to graph (sequential mode)")
    
    # ═══════════════════════════════════════════════════════
    # 5. 그래프 컴파일
    # ═══════════════════════════════════════════════════════
    compiled_graph = workflow.compile()
    logger.info("Graph compiled successfully")
    
    return compiled_graph


def create_rag_system(
    llm: Any,
    retriever: BankRetriever,
    top_k: int = 8,
    relevance_threshold: float = 60.0,
    enable_routing: bool = False,
    enable_langsmith: bool = False
):
    """
    RAG 시스템 생성 헬퍼 함수 (build_rag_graph 래퍼)
    
    Parameters
    ----------
    llm : Any
        생성용 LLM (gpt-5-nano, temperature=1.0)
    retriever : BankRetriever
        Vector DB retriever
    top_k : int
        검색할 청크 개수
    relevance_threshold : float
        관련성 임계값 (0-100)
    enable_routing : bool
        조건부 라우팅 활성화 여부 (기본값: False)
    enable_langsmith : bool
        LangSmith 추적 활성화 여부 (기본값: False)
    
    Returns
    -------
    compiled_graph
        컴파일된 RAG 그래프
    
    Note
    ----
    평가용 LLM (gpt-4o, temperature=0.0)은 EvaluationAgent 내부에서 자동 생성됨
    
    Examples
    --------
    >>> from rag.llm.get_llm import get_llm_model
    >>> from rag.retriever import BankRetriever
    >>> llm = get_llm_model()
    >>> retriever = BankRetriever()
    >>> graph = create_rag_system(llm, retriever)
    >>> result = graph.invoke({"question": "KB국민은행 주택담보대출 금리는?"})
    >>> print(result["answer"])
    """
    return build_rag_graph(
        llm=llm,
        retriever=retriever,
        top_k=top_k,
        relevance_threshold=relevance_threshold,
        enable_routing=enable_routing,
        enable_langsmith=enable_langsmith
    )


__all__ = ["build_rag_graph", "create_rag_system", "State"]
