from rag.llm.get_llm import get_llm_model
from rag.graph.multiAgent.classify_agent import run_intent_agent
from typing import Dict
from rag.graph.State import State

def intent_node(state: State) -> State:
    """LLM 기반 intent/키워드 추출 노드"""
    q = state.get("question", "") or ""

    # LLM 모델 로드
    try:
        llm = get_llm_model()
    except Exception as e:
        print(f"LLM 모델 로드 오류: {e}")
        return state

    # LLM 기반 의도/키워드 분석 실행
    result: Dict = run_intent_agent(q, llm=llm, debug=True)

    # 결과를 state에 반영
    state["intent"] = result.get("intent", "other")
    state["clause_keywords"] = result.get("clause_keywords", []) or []
    state["bank_name"] = result.get("bank_name")
    state["product_name"] = result.get("product_name")
    state["product_type"] = result.get("product_type")
    state["loan_type"] = result.get("loan_type")
    state["loan_target"] = result.get("loan_target")
    state["applicability_hint"] = result.get("applicability_hint")
    state["raw_keywords"] = result.get("raw_keywords", []) or []
    state["confidence"] = float(result.get("confidence") or 0.0)
    state["reasoning"] = result.get("reasoning", "") or ""

    # 디버그 정보 누적
    debug_info = state.get("debug", {})
    debug_info["intent_llm_agent"] = result
    state["debug"] = debug_info

    return state
