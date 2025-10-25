"""LLM 답변 생성 노드"""

from typing import Dict, Any
from jinja2 import Environment
from rag.core.logger import get_logger
from rag.llm.openai_chat import OpenAIChatModel


logger = get_logger(__name__)


def create_generate_answer_node(llm: OpenAIChatModel, jinja_env: Environment):
    """
    답변 생성 노드 생성 함수
    
    Args:
        llm: OpenAIChatModel instance
        jinja_env: Jinja2 Environment instance
    
    Returns:
        generate_answer function
    """
    def generate_answer(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM 답변 생성 노드
        
        검색된 문서를 기반으로 LLM을 사용하여 답변을 생성합니다.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with generated answer
        """
        query = state.get("original_query", state["query"])  # 원본 질문 사용
        documents = state.get("documents", [])
        
        # Handle empty results
        if not documents:
            logger.warning("No documents found for query")
            return {
                **state,
                "answer": "죄송합니다. 관련된 정보를 찾을 수 없습니다. 질문을 다시 확인해주세요."
            }
        
        try:
            # Load template
            template = jinja_env.get_template("answer.j2")
            prompt = template.render(query=query, documents=documents)
            
            # Generate answer
            system_prompt = "당신은 은행 상품 전문가입니다. 제공된 문서를 기반으로 정확하게 답변하세요."
            answer = llm.generate(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=0.7
            )
            
            logger.info("Answer generated successfully")
            
            return {
                **state,
                "answer": answer
            }
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return {
                **state,
                "answer": f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {str(e)}",
                "error": str(e)
            }
    
    return generate_answer
