"""
Evaluation Node

청크 관련성 평가 노드
"""

from typing import Dict, Any
from rag.core.logger import get_logger
from rag.graph.multiAgent.eval_agent import EvaluationAgent

logger = get_logger(__name__)


def create_eval_node(
    relevance_threshold: float = 35.0,
    min_chunks: int = 3,
    max_retries: int = 1
):
    """
    평가 노드 생성 함수
    
    Parameters
    ----------
    relevance_threshold : float
        관련성 임계값 (0-100, 기본값: 35.0)
    min_chunks : int
        최소 필요 청크 개수 (기본값: 3)
    max_retries : int
        최대 재시도 횟수 (기본값: 1)
    
    Returns
    -------
    function
        eval_node 함수
    """
    # EvaluationAgent 초기화 (내부에서 gpt-5-mini 자동 생성)
    eval_agent = EvaluationAgent(relevance_threshold=relevance_threshold)
    
    def eval_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        청크 관련성 평가 노드 (양 + 질 통합 검증)
        
        Vector DB에서 검색된 청크들을 LLM으로 평가하여
        실제로 질문과 관련성이 높은 청크만 필터링합니다.
        
        평가 후 청크가 부족하면 재시도 여부를 결정합니다.
        
        Parameters
        ----------
        state : Dict[str, Any]
            현재 그래프 상태
            - question: 사용자 질문
            - vector_chunks: Vector DB 검색 결과
            - retry_count: 재시도 횟수 (선택)
        
        Returns
        -------
        Dict[str, Any]
            업데이트된 상태
            - relevant_chunks: 관련성이 높은 청크 리스트
            - relevant_chunks_count: 관련 청크 개수
            - should_retry: 재시도 필요 여부
            - retry_reason: 재시도 사유
        """
        question = state.get("question", "")
        vector_chunks = state.get("vector_chunks", [])
        retry_count = state.get("retry_count", 0)
        
        logger.info(f"=== Evaluation Node (Retry: {retry_count}/{max_retries}) ===")
        logger.info(f"Input chunks: {len(vector_chunks)}")
        
        # 1. 청크가 없는 경우
        if not vector_chunks:
            logger.warning("No chunks to evaluate")
            
            # 재시도 가능 여부 확인
            if retry_count < max_retries:
                logger.info(f"No chunks found. Retry available ({retry_count + 1}/{max_retries})")
                return {
                    **state,
                    "relevant_chunks": [],
                    "relevant_chunks_count": 0,
                    "should_retry": True,
                    "retry_reason": "no_chunks",
                    "retry_count": retry_count + 1
                }
            else:
                logger.warning(f"No chunks found. Max retries reached ({max_retries})")
                return {
                    **state,
                    "relevant_chunks": [],
                    "relevant_chunks_count": 0,
                    "should_retry": False,
                    "retry_reason": "max_retries_reached"
                }
        
        try:
            # 2. 청크 품질 평가 (LLM)
            relevant_chunks = eval_agent.evaluate_chunks(question, vector_chunks)
            relevant_count = len(relevant_chunks)
            
            logger.info(f"Quality evaluation: {relevant_count}/{len(vector_chunks)} chunks are relevant")
            
            # 3. 양 + 질 통합 판단
            if relevant_count >= min_chunks:
                # 충분한 청크 확보
                logger.info(f"✓ Sufficient chunks: {relevant_count} ≥ {min_chunks}")
                return {
                    **state,
                    "relevant_chunks": relevant_chunks,
                    "relevant_chunks_count": relevant_count,
                    "should_retry": False,
                    "retry_reason": "sufficient"
                }
            
            # 4. 청크 부족 - 재시도 판단
            if retry_count < max_retries:
                logger.warning(f"✗ Insufficient chunks: {relevant_count} < {min_chunks}")
                logger.info(f"Retry available ({retry_count + 1}/{max_retries})")
                return {
                    **state,
                    "relevant_chunks": relevant_chunks,
                    "relevant_chunks_count": relevant_count,
                    "should_retry": True,
                    "retry_reason": "insufficient_chunks",
                    "retry_count": retry_count + 1
                }
            else:
                logger.warning(f"✗ Insufficient chunks: {relevant_count} < {min_chunks}")
                logger.warning(f"Max retries reached ({max_retries}). Proceeding with available chunks.")
                return {
                    **state,
                    "relevant_chunks": relevant_chunks,
                    "relevant_chunks_count": relevant_count,
                    "should_retry": False,
                    "retry_reason": "max_retries_reached"
                }
            
        except Exception as e:
            logger.error(f"Evaluation node failed: {e}", exc_info=True)
            logger.warning("Returning all chunks due to evaluation error")
            
            # 에러 발생 시 모든 청크 반환 (재시도 없음)
            return {
                **state,
                "relevant_chunks": vector_chunks,
                "relevant_chunks_count": len(vector_chunks),
                "should_retry": False,
                "retry_reason": "evaluation_error",
                "error": str(e)
            }
    
    return eval_node


__all__ = ["create_eval_node"]

