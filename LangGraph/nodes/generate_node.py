from typing import Any, Dict, List

from llm import get_llm_model
from langchain.prompts import PromptTemplate

# 최종 답변 생성을 위한 프롬프트
ANSWER_PROMPT = PromptTemplate.from_template(
    """
당신은 은행 상품 약관을 안내하는 전문 상담사입니다.
아래 근거만을 이용해 사용자의 질문에 대해 명확하고 정중한 한국어 답변을 작성하세요.
근거가 부족하면 그 사실을 먼저 밝히고 추가 조사가 필요하다고 안내합니다.

사용자 질문: {question}
수집된 근거:
{contents}
"""
)


def _join_contents(contents: List[str]) -> str:
    """여러 근거 텍스트를 번호와 함께 연결한다."""
    if not contents:
        return "(근거 없음)"
    return "\n\n".join(f"[근거 {idx+1}]\n{chunk}" for idx, chunk in enumerate(contents))


def generate_node(state: Dict[str, Any], deps: Any = None) -> Dict[str, Any]:
    """벡터/웹 검색으로 수집한 근거를 바탕으로 최종 답변을 생성한다."""
    contents_value = state.get("contents") or []
    contents: List[str] = contents_value if isinstance(contents_value, list) else [str(contents_value)]

    if not contents:
        # 근거가 없으면 사용자에게 추가 확인을 요청한다.
        state["final_answer"] = (
            "죄송하지만 해당 질문에 대해 참고할 수 있는 근거를 찾지 못했습니다. "
            "조금 더 구체적인 은행명이나 상품명을 알려주시면 다시 찾아보겠습니다."
        )
        return state

    chain = ANSWER_PROMPT | get_llm_model()
    prompt_vars = {
        "question": state.get("question", ""),
        "contents": _join_contents(contents),
    }
    result = chain.invoke(prompt_vars)

    # LangChain 결과 형식을 문자열로 정규화
    answer_content = getattr(result, "content", result)
    if isinstance(answer_content, list):
        answer_content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in answer_content
        )

    state["final_answer"] = str(answer_content).strip()
    return state
