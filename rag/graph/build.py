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

# Node imports (Agent가 없는 단순 변환 작업만)
from rag.graph.nodes.search_vectordb_node import create_vector_search_node
from rag.graph.nodes.rewrite_query_node import create_rewrite_query_node
from rag.graph.nodes.search_web_node import search_web_node
from rag.graph.nodes.format_response_node import GraphNodes

# LangSmith imports
from rag.langsmith.tracer import LangSmithTracer

# Core imports
from rag.core.logger import get_logger
from rag.vectorstore.pgvector_store import PgVectorStore
from rag.graph.State import State

logger = get_logger(__name__)


def build_rag_graph(
    llm: Any,
    vectorstore: PgVectorStore,
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
    vectorstore : PgVectorStore
        Vector DB store
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
    >>> from rag.vectorstore.pgvector_store import PgVectorStore
    >>> llm = get_llm_model()
    >>> vectorstore = PgVectorStore(...)
    >>> graph = build_rag_graph(llm, vectorstore, enable_routing=True)
    >>> result = graph.invoke({"question": "우리은행 전세자금대출 금리는?"})
    """
    logger.info("Building Multi-Agent RAG graph...")
    logger.info(f"  - Routing: {'enabled' if enable_routing else 'disabled'}")
    logger.info(f"  - LangSmith: {'enabled' if enable_langsmith else 'disabled'}")
    logger.info(f"  - Top-K: {top_k}, Threshold: {relevance_threshold}")
    
    # ═══════════════════════════════════════════════════════
    # 0. LangSmith 초기화 (선택적)
    # ═══════════════════════════════════════════════════════
    langsmith_tracer = None
    langsmith_config = {}
    
    if enable_langsmith:
        langsmith_tracer = LangSmithTracer()
        if langsmith_tracer.is_enabled():
            langsmith_config = langsmith_tracer.get_config()
            logger.info("✓ LangSmith tracing enabled")
        else:
            logger.warning("LangSmith requested but not configured (check LANGCHAIN_API_KEY)")
            enable_langsmith = False
    
    # ═══════════════════════════════════════════════════════
    # 1. Agent 초기화
    # ═══════════════════════════════════════════════════════
    sql_agent = SQLRetrievalAgent()
    eval_agent = EvaluationAgent(relevance_threshold=relevance_threshold)
    gen_agent = GenerationAgent(llm=llm)
    
    # Node 생성 함수들 (Agent가 없는 단순 변환 작업)
    vector_search_fn = create_vector_search_node(vectorstore)
    rewrite_query_fn = create_rewrite_query_node(llm)
    format_nodes = GraphNodes()
    
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
        
        search_state = {
            "query": state.get("rewritten_query", state["question"]),  # 재작성된 쿼리 우선 사용
            "top_k": state.get("top_k", top_k),
            "bank_name": state.get("bank_name"),
            "product_type": state.get("product_type"),
            "sql_results": state.get("sql_results", []),
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
        state["documents"] = documents  # format_response에서 사용
        state["used_fallback_search"] = result_state.get("used_fallback_search", False)
        
        debug = state.get("debug", {})
        debug["vector"] = {
            "query": search_state["query"],
            "top_k": search_state["top_k"],
            "results_count": len(vector_chunks),
            "used_fallback": state["used_fallback_search"]
        }
        state["debug"] = debug
        
        logger.info(f"Vector search found {len(vector_chunks)} chunks")
        return state
    
    def rewrite_query_node(state: State) -> State:
        """4-1. Query Rewrite Node"""
        logger.info("=== Step 4-1: Query Rewrite ===")
        
        rewrite_state = {
            "original_query": state["question"],
            "query": state.get("rewritten_query", state["question"]),
            "bank_name": state.get("bank_name"),
            "product_type": state.get("product_type")
        }
        
        result = rewrite_query_fn(rewrite_state)
        state["rewritten_query"] = result["query"]
        state["top_k"] = 4  # 재시도 시 top_k 줄임
        
        logger.info(f"Query rewritten: {result['query']}")
        return state
    
    def web_search_node(state: State) -> State:
        """4-2. Web Search Node (Tavily)"""
        logger.info("=== Step 4-2: Web Search ===")
        
        # TODO: Tavily API 연동 필요
        # 현재는 스킵하고 빈 결과 반환
        logger.warning("Web search not implemented yet (Tavily API required)")
        
        state["web_chunks"] = []
        state["web_used"] = False
        
        return state
    
    def eval_node(state: State) -> State:
        """5. Evaluation Node (양 + 질 통합 검증)"""
        logger.info("=== Step 5: Chunk Evaluation ===")
        
        # Agent 호출
        state = eval_agent.run(state)
        
        relevant_count = state.get("relevant_chunks_count", 0)
        retry_count = state.get("retry_count", 0)
        
        logger.info(f"Evaluation: {relevant_count} relevant chunks")
        
        # 재시도 판단 (최소 3개, 최대 1회)
        min_chunks = 3
        max_retries = 1
        
        if relevant_count < min_chunks and retry_count < max_retries:
            state["should_retry"] = True
            state["retry_reason"] = "insufficient_chunks"
            state["retry_count"] = retry_count + 1
            logger.warning(f"Retry needed: {relevant_count} < {min_chunks} (attempt {retry_count + 1}/{max_retries})")
        elif relevant_count < min_chunks and retry_count >= max_retries:
            state["should_retry"] = False
            state["retry_reason"] = "max_retries_reached"
            logger.warning(f"Max retries reached. Proceeding with {relevant_count} chunks")
        else:
            state["should_retry"] = False
            state["retry_reason"] = "sufficient"
            logger.info(f"Sufficient chunks: {relevant_count} >= {min_chunks}")
        
        return state
    
    def format_response_node(state: State) -> State:
        """7. Format Response Node"""
        logger.info("=== Step 7: Format Response ===")
        
        # 출처 포맷팅
        state = format_nodes.format_response(state)
        
        # 답변에 출처 첨부
        state = format_nodes.append_sources_to_answer(state)
        
        logger.info("Response formatted with sources")
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
    workflow.add_node("rewrite_query", rewrite_query_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("eval", eval_node)
    workflow.add_node("generate", generation_node)
    workflow.add_node("format", format_response_node)
    
    logger.info("Added all nodes to graph")
    
    # ═══════════════════════════════════════════════════════
    # 4. 엣지 추가 (조건부 분기 포함)
    # ═══════════════════════════════════════════════════════
    
    # 조건부 분기 함수
    def should_retry_search(state: State) -> str:
        """eval 후 재시도 필요 여부 판단"""
        if state.get("should_retry", False):
            return "retry"
        return "generate"
    
    def check_sql_results(state: State) -> str:
        """SQL 결과 확인"""
        sql_results = state.get("sql_results", [])
        if len(sql_results) == 0:
            logger.warning("No SQL results found. Returning 'retry' message.")
            state["answer"] = "다시 질문하세요."
            return "end"
        return "vector"
    
    # 기본 흐름
    workflow.set_entry_point("classify")
    workflow.add_edge("classify", "sql")
    
    # SQL 결과 확인 후 분기
    workflow.add_conditional_edges(
        "sql",
        check_sql_results,
        {
            "vector": "vector",
            "end": END
        }
    )
    
    workflow.add_edge("vector", "eval")
    
    # eval 후 재시도 분기
    workflow.add_conditional_edges(
        "eval",
        should_retry_search,
        {
            "retry": "rewrite_query",
            "generate": "generate"
        }
    )
    
    # 재시도 흐름: rewrite_query → web_search (병렬) → vector → eval
    workflow.add_edge("rewrite_query", "web_search")
    workflow.add_edge("web_search", "vector")
    
    # 최종 생성 및 포맷팅
    workflow.add_edge("generate", "format")
    workflow.add_edge("format", END)
    
    logger.info("Added all edges to graph (with conditional routing)")
    
    # ═══════════════════════════════════════════════════════
    # 5. 그래프 컴파일
    # ═══════════════════════════════════════════════════════
    compiled_graph = workflow.compile()
    logger.info("Graph compiled successfully")
    
    # LangSmith 설정을 그래프 메타데이터에 저장
    if enable_langsmith and langsmith_config:
        compiled_graph._langsmith_config = langsmith_config
        logger.info("LangSmith config attached to graph")
    
    return compiled_graph


def create_rag_system(
    llm: Any,
    vectorstore: PgVectorStore,
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
    vectorstore : PgVectorStore
        Vector DB store
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
    
    LangSmith 사용 시 환경변수 설정 필요:
    - LANGCHAIN_TRACING_V2=true
    - LANGCHAIN_API_KEY=your_api_key
    - LANGCHAIN_PROJECT=your_project_name (선택)
    
    Examples
    --------
    >>> from rag.llm.get_llm import get_llm_model
    >>> from rag.vectorstore.pgvector_store import PgVectorStore
    >>> llm = get_llm_model()
    >>> vectorstore = PgVectorStore(...)
    >>> 
    >>> # 기본 사용
    >>> graph = create_rag_system(llm, vectorstore)
    >>> result = graph.invoke({"question": "KB국민은행 주택담보대출 금리는?"})
    >>> print(result["answer"])
    >>> 
    >>> # LangSmith 추적 활성화
    >>> graph = create_rag_system(llm, vectorstore, enable_langsmith=True)
    >>> config = getattr(graph, '_langsmith_config', {})
    >>> result = graph.invoke({"question": "질문"}, config=config)
    """
    return build_rag_graph(
        llm=llm,
        vectorstore=vectorstore,
        top_k=top_k,
        relevance_threshold=relevance_threshold,
        enable_routing=enable_routing,
        enable_langsmith=enable_langsmith
    )


def invoke_with_langsmith(graph: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangSmith 추적과 함께 그래프 실행
    
    Parameters
    ----------
    graph : Any
        컴파일된 RAG 그래프
    state : Dict[str, Any]
        입력 상태 (question 포함)
    
    Returns
    -------
    Dict[str, Any]
        실행 결과 상태
    
    Examples
    --------
    >>> graph = create_rag_system(llm, vectorstore, enable_langsmith=True)
    >>> result = invoke_with_langsmith(graph, {"question": "질문"})
    """
    config = getattr(graph, '_langsmith_config', {})
    return graph.invoke(state, config=config if config else None)


__all__ = ["build_rag_graph", "create_rag_system", "invoke_with_langsmith", "State"]
