"""LangGraph 그래프 빌드"""

from langgraph.graph import StateGraph, END
from typing import Dict, Any
from jinja2 import Environment

from rag.graph.nodes.normalize_query_node import normalize_query
from rag.graph.nodes.route_metadata_node import route_metadata
from rag.graph.nodes.vector_search_node import create_vector_search_node
from rag.graph.nodes.rewrite_query_node import create_rewrite_query_node
from rag.graph.nodes.generate_answer_node import create_generate_answer_node
from rag.graph.nodes.format_response_node import format_response
from rag.graph.route.route_search_vectordb import GraphEdges
from rag.core.logger import get_logger
from rag.retriever import BankRetriever
from rag.llm.openai_chat import OpenAIChatModel


logger = get_logger(__name__)


def build_rag_graph(
    retriever: BankRetriever,
    llm: OpenAIChatModel,
    jinja_env: Environment
):
    """
    RAG 파이프라인 그래프 빌드 및 컴파일
    
    Args:
        retriever: BankRetriever instance
        llm: OpenAIChatModel instance
        jinja_env: Jinja2 Environment instance
    
    Returns:
        Compiled LangGraph workflow
    """
    logger.info("Building RAG graph...")
    
    # Create node functions
    vector_search = create_vector_search_node(retriever)
    rewrite_query = create_rewrite_query_node(llm)
    generate_answer = create_generate_answer_node(llm, jinja_env)
    
    # Define graph with state type
    workflow = StateGraph(Dict[str, Any])
    
    # Add nodes
    workflow.add_node("normalize", normalize_query)
    workflow.add_node("route", route_metadata)
    workflow.add_node("search", vector_search)
    workflow.add_node("rewrite", rewrite_query)
    workflow.add_node("generate", generate_answer)
    workflow.add_node("format", format_response)
    
    logger.info("Added all nodes to graph")
    
    # Set entry point
    workflow.set_entry_point("normalize")
    
    # Add edges
    workflow.add_edge("normalize", "route")
    workflow.add_edge("route", "search")
    
    # Conditional edge after search
    workflow.add_conditional_edges(
        "search",
        GraphEdges.check_search_results,
        {
            "sufficient": "generate",
            "retry": "rewrite",
            "failed": "generate"
        }
    )
    
    # rewrite 후 다시 search로
    workflow.add_edge("rewrite", "search")
    
    workflow.add_edge("generate", "format")
    workflow.add_edge("format", END)
    
    logger.info("Added all edges to graph")
    
    # Compile graph
    compiled_graph = workflow.compile()
    logger.info("Graph compiled successfully")
    
    return compiled_graph
