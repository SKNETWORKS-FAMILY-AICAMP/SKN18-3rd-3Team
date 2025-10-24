"""질문 재정의 노드"""

from typing import Dict, Any
from rag.core.logger import get_logger
from rag.llm.openai_chat import OpenAIChatModel


logger = get_logger(__name__)


def create_rewrite_query_node(llm: OpenAIChatModel):
    """
    질문 재정의 노드 생성 함수
    
    Args:
        llm: OpenAIChatModel instance
    
    Returns:
        rewrite_query function
    """
    def rewrite_query(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        질문 재정의 노드
        
        검색 결과가 부족할 때 질문을 재정의합니다.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with rewritten query
        """
        original_query = state.get("original_query", state.get("query"))
        current_query = state.get("query")
        bank_name = state.get("bank_name")
        product_type = state.get("product_type")
        
        logger.info(f"Rewriting query: {current_query}")
        
        try:
            system_prompt = """당신은 검색 쿼리 최적화 전문가입니다.
사용자의 질문을 더 구체적이고 검색하기 좋은 형태로 재작성하세요.

재작성 규칙:
1. 핵심 키워드를 유지하면서 다양한 표현 추가
2. 은행 상품 관련 전문 용어 활용
3. 질문을 서술형으로 변환
4. 불필요한 조사나 접속사 제거"""

            user_prompt = f"""원본 질문: {original_query}
은행명: {bank_name or '미지정'}
상품종류: {product_type or '미지정'}

위 질문을 더 나은 검색 결과를 얻을 수 있도록 재작성하세요.
재작성된 질문만 출력하세요."""

            rewritten_query = llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3
            ).strip()
            
            logger.info(f"Query rewritten: {rewritten_query}")
            
            return {
                **state,
                "query": rewritten_query
            }
            
        except Exception as e:
            logger.error(f"Query rewrite failed: {e}")
            return state
    
    return rewrite_query
