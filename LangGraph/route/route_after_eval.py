def is_banking_domain(state) -> bool:
    q = (state.get("question") or "").lower()
    bank = state.get("bank_name")
    prod = state.get("product_name")
    tags = state.get("clause_keywords", [])
    # 은행/상품/약관 단서가 하나도 없으면 비(非)도메인으로 간주
    signals = [
        bank, prod,
        any(t in ["rate","fee","early_close","preferential","eligibility"] for t in tags),
        any(k in q for k in ["은행","약관","예금","적금","대출","금리","수수료","중도해지","우대","가입"])
    ]
    return any(signals)

def route_after_eval(state):
    """평가 결과와 도메인 신뢰도를 바탕으로 다음 노드를 결정한다."""
    # 0) 은행/약관 도메인 여부 판단
    if not is_banking_domain(state):
        state["generation_strategy"] = "clarify"
        state["followup_question"] = "은행/상품/약관과 관련된 질문으로 다시 말씀해 주세요. (예: 우리은행 정기예금 금리)"
        return "clarify_node"

    # 1) 내부 근거가 충분하면 바로 생성
    if state.get("eval_results") == "YES" and float(state.get("eval_score", 0)) >= 50:
        state["generation_strategy"] = "vector"
        return "generate_node"

    # 2) 내부가 부족하면 웹 보강 (월렛+금리도 여기로 허용)
    state["generation_strategy"] = "web_search"
    return "search_web_node"
