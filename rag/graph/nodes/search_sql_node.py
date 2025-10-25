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
    result_state = agent.run(state)
    return result_state
