"""SQL Retrieval Node that queries structured loan product metadata."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from MultiAgent.sql_agent import SQLRetrievalAgent

_sql_agent: Optional[SQLRetrievalAgent] = None


def _get_agent() -> SQLRetrievalAgent:
    global _sql_agent
    if _sql_agent is None:
        _sql_agent = SQLRetrievalAgent()
    return _sql_agent


def sql_retrieval_node(state: Dict[str, Any], deps: Any = None) -> Dict[str, Any]:
    """은행/상품 정보를 바탕으로 대출 상품 정보를 조회한다."""
    agent = _get_agent()
    question = state.get("question", "")
    bank_name = state.get("bank_name")
    product_name = state.get("product_name")
    product_type = state.get("product_type")

    records = agent.query(
        question=question or "",
        bank_name=bank_name,
        product_name=product_name,
        product_type=product_type,
    )

    sql_contents: List[str] = []
    sql_results: List[Dict[str, Any]] = []

    for record in records:
        sql_contents.append(record.to_bullet())
        sql_results.append(record.__dict__)

    state["sql_contents"] = sql_contents
    state["sql_results"] = sql_results

    if sql_contents:
        base_contents = state.get("contents") or []
        state["contents"] = [*base_contents, *sql_contents]

    return state
