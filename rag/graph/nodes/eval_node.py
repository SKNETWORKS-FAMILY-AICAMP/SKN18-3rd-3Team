"""
Evaluation Node

청크 관련성 평가 노드
"""

from typing import Dict, Any
from rag.core.logger import get_logger
from rag.graph.multiAgent.eval_agent import EvaluationAgent

logger = get_logger(__name__)


def create_eval_node(relevance_threshold: float = 35.0):
    """
    평가 노드 생성 함수
    
    Parameters
    ----------
    relevance_threshold : float
        관련성 임계값 (0-100, 기본값: 35.0)
    
    Returns
    -------
    function
        eval_node 함수
    """
    # EvaluationAgent 초기화 (내부에서 gpt-4o 자동 생성)
    eval_agent = EvaluationAgent(relevance_threshold=relevance_threshold)
    
    def eval_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        청크 관련성 평가 노드
        
        Vector DB에서 검색된 청크들을 LLM으로 평가하여
        실제로 질문과 관련성이 높은 청크만 필터링합니다.
        
        Parameters
        ----------
        state : Dict[str, Any]
            현재 그래프 상태
            - question: 사용자 질문
            - vector_chunks: Vector DB 검색 결과
        
        Returns
        -------
        Dict[str, Any]
            업데이트된 상태
            - relevant_chunks: 관련성이 높은 청크 리스트
            - relevant_chunks_count: 관련 청크 개수
        """
        question = state.get("question", "")
        vector_chunks = state.get("vector_chunks", [])
        
        logger.info(f"=== Evaluation Node ===")
        logger.info(f"Input chunks: {len(vector_chunks)}")
        
        if not vector_chunks:
            logger.warning("No chunks to evaluate")
            return {
                **state,
                "relevant_chunks": [],
                "relevant_chunks_count": 0
            }
        
        try:
            # 청크 평가 실행
            relevant_chunks = eval_agent.evaluate_chunks(question, vector_chunks)
            
            logger.info(f"Evaluation complete: {len(relevant_chunks)}/{len(vector_chunks)} chunks are relevant")
            
            # 상태 업데이트
            return {
                **state,
                "relevant_chunks": relevant_chunks,
                "relevant_chunks_count": len(relevant_chunks)
            }
            
        except Exception as e:
            logger.error(f"Evaluation node failed: {e}", exc_info=True)
            logger.warning("Returning all chunks due to evaluation error")
            
            # 에러 발생 시 모든 청크 반환
            return {
                **state,
                "relevant_chunks": vector_chunks,
                "relevant_chunks_count": len(vector_chunks),
                "error": str(e)
            }
    
    return eval_node


__all__ = ["create_eval_node"]

