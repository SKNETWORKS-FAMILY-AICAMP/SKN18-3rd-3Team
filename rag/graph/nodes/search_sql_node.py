"""SQL Retrieval Node that queries structured loan product metadata."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..multiAgent.sql_agent import SQLRetrievalAgent

_sql_agent: Optional[SQLRetrievalAgent] = None


def _get_agent() -> SQLRetrievalAgent:
    global _sql_agent
    if _sql_agent is None:
        _sql_agent = SQLRetrievalAgent()
    return _sql_agent


def sql_retrieval_node(state: Dict[str, Any], deps: Any = None) -> Dict[str, Any]:
    """
    은행/상품 intent 결과(state)에 기반해 대출 상품 메타데이터/금리 정보를 조회한다.
    SQLRetrievalAgent.run을 호출해 loan_info/bank_interest_rate를 모두 활용한다.
    """
    agent = _get_agent()
    state.setdefault("question", state.get("question", "") or "")
    intent = (state.get("intent") or "other").lower()
    confidence = float(state.get("confidence") or 0.0)
    allowed_intents = {"rate_fee_lookup", "clause_lookup", "compare", "definition"}
    if intent not in allowed_intents or confidence < 0.5:
        message = "질문이 금융 상품과 관련 없어 SQL 검색을 생략했습니다."
        state["sql_results"] = []
        state["sql_contents"] = [message]
        debug = state.get("debug") or {}
        sql_debug = debug.get("sql") or {}
        sql_debug.update({
            "skipped": True,
            "reason": f"intent={intent}, confidence={confidence:.2f}",
        })
        debug["sql"] = sql_debug
        state["debug"] = debug
        return state

    result_state = agent.run(state)
    return result_state
