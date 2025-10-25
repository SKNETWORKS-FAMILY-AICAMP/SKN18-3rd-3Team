"""LangGraph 그래프 빌드"""

from langgraph.graph import StateGraph, END
from typing import Dict, Any

from RAG.rag.graph.nodes import GraphNodes
from RAG.rag.graph.edges import GraphEdges
from RAG.core.logger import get_logger


logger = get_logger(__name__)


def build_rag_graph(nodes: GraphNodes):
    """
    RAG 파이프라인 그래프 빌드 및 컴파일
    
    Args:
        nodes: GraphNodes instance with all node functions
    
    Returns:
        Compiled LangGraph workflow
    """
    logger.info("Building RAG graph...")
    
    # Define graph with state type
    workflow = StateGraph(Dict[str, Any])
    
    # Add nodes
    workflow.add_node("normalize", nodes.normalize_query)
    workflow.add_node("route", nodes.route_metadata)
    workflow.add_node("search", nodes.vector_search)
    workflow.add_node("generate", nodes.generate_answer)
    workflow.add_node("format", nodes.format_response)
    workflow.add_node("append_sources", nodes.append_sources_to_answer)
    
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
            "retry": "search",
            "failed": "generate"
        }
    )
    
    workflow.add_edge("generate", "format")
    workflow.add_edge("format", "append_sources")
    workflow.add_edge("append_sources", END)
    
    logger.info("Added all edges to graph")
    
    # Compile graph
    compiled_graph = workflow.compile()
    logger.info("Graph compiled successfully")
    
    return compiled_graph
