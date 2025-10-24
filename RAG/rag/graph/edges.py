"""LangGraph 조건부 엣지"""

from typing import Dict, Any, Literal
from RAG.core.logger import get_logger


logger = get_logger(__name__)


class GraphEdges:
    """LangGraph 조건부 분기 함수들"""
    
    @staticmethod
    def check_search_results(
        state: Dict[str, Any]
    ) -> Literal["sufficient", "retry", "failed"]:
        """
        검색 결과 확인 및 재시도 결정
        
        Args:
            state: Current graph state
        
        Returns:
            "sufficient": 결과가 충분함 -> generate_answer로 이동
            "retry": 결과가 부족하고 재시도 가능 -> vector_search로 재시도
            "failed": 재시도 불가능 -> generate_answer로 이동 (빈 결과)
        """
        documents = state.get("documents", [])
        retry_count = state.get("retry_count", 0)
        top_k = state.get("top_k", 8)
        
        num_docs = len(documents)
        
        # 결과가 충분한 경우
        if num_docs >= 3:
            logger.info(f"Search results sufficient: {num_docs} documents")
            return "sufficient"
        
        # 재시도 가능한 경우 (최대 2회)
        if retry_count < 2 and num_docs < 3:
            new_top_k = top_k + 5
            state["top_k"] = new_top_k
            state["retry_count"] = retry_count + 1
            logger.warning(f"Search results insufficient ({num_docs} docs). Retrying with top_k={new_top_k} (attempt {retry_count + 1}/2)")
            return "retry"
        
        # 재시도 불가능 (최대 재시도 도달)
        logger.warning(f"Max retries reached. Proceeding with {num_docs} documents")
        return "failed"
