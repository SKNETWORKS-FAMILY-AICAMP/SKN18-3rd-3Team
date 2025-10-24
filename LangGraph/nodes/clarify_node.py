# 국민은행, 우리은행 상품 관련 질문이 아닐 때 재질문 요청

def clarify_node(state, deps):
    state["followup_question"] = (
            "국민은행/우리은행 상품과 약관 관련 질문을 부탁드립니다. 예시:\n"
            "- 우리은행 WON 정기예금 금리 알려줘\n"
        )
    return state