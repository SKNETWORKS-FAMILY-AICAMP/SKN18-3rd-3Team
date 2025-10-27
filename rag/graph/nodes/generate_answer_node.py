"""
LLM 답변 생성 노드

SQL 검색 결과, Vector DB 청크, 웹 검색 결과를 기반으로 최종 답변을 생성하는 노드
"""

from typing import Dict, Any, List
from rag.core.logger import get_logger
from rag.graph.multiAgent.gen_agent import GenerationAgent


logger = get_logger(__name__)


def create_generate_answer_node(llm: Any):
    """
    답변 생성 노드 생성 함수
    
    Parameters
    ----------
    llm : Any
        생성용 LLM 모델 (gpt-5-nano, temperature=1.0)
    
    Returns
    -------
    function
        generate_answer_node 함수
    """
    # GenerationAgent 초기화
    gen_agent = GenerationAgent(llm=llm)
    
    def generate_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM 답변 생성 노드
        
        SQL 검색 결과, Vector DB 청크, 웹 검색 결과를 기반으로
        최종 답변을 생성합니다.
        
        Parameters
        ----------
        state : Dict[str, Any]
            현재 그래프 상태
            - question: 사용자 질문
            - sql_results: SQL 검색 결과 (List[Dict])
            - relevant_chunks: 평가된 관련 청크 (List[Dict])
            - Vector DB 청크 (source != 'web_search')
            - 웹 검색 청크 (source == 'web_search')
        
        Returns
        -------
        Dict[str, Any]
            answer가 추가된 상태
        """
        question = state.get("question", "")
        sql_results = state.get("sql_results", [])
        relevant_chunks = state.get("relevant_chunks", [])
        
        logger.info(f"=== Generate Answer Node ===")
        logger.info(f"Question: {question[:50]}...")
        logger.info(f"SQL results: {len(sql_results)} products")
        logger.info(f"Relevant chunks: {len(relevant_chunks)} chunks")
        
        # 청크 소스 분석
        vector_chunks = [c for c in relevant_chunks if c.get('source') != 'web_search']
        web_chunks = [c for c in relevant_chunks if c.get('source') == 'web_search']
        logger.info(f"  - Vector DB: {len(vector_chunks)} chunks")
        logger.info(f"  - Web Search: {len(web_chunks)} chunks")
        
        # 데이터 없을 때 처리
        if not sql_results and not relevant_chunks:
            logger.warning("No data available for answer generation")
            return {
                **state,
                "answer": "죄송합니다. 질문과 관련된 정보를 찾지 못했습니다. 다른 방식으로 질문해 주시겠어요?"
            }
        
        try:
            # GenerationAgent를 사용하여 답변 생성
            answer = gen_agent.generate_answer(question, sql_results, relevant_chunks)
            
            logger.info(f"Answer generated: {len(answer)} characters")
            
            return {
                **state,
                "answer": answer
            }
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}", exc_info=True)
            return {
                **state,
                "answer": f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {str(e)}",
                "error": str(e)
            }
    
    return generate_answer_node


__all__ = ["create_generate_answer_node"]
