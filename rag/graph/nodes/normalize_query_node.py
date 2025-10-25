"""질의 정규화 노드"""

from typing import Dict, Any
from rag.core.logger import get_logger


logger = get_logger(__name__)


def normalize_query(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    질의 정규화 노드
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with normalized query
    """
    query = state["query"].strip()
    logger.info(f"Normalized query: {query[:100]}...")
    
    # 원본 질문 저장 (재작성 시 참조용)
    if "original_query" not in state:
        state["original_query"] = query
    
    return {
        **state,
        "query": query
    }
