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

    query_result = agent.query(
        question=question or "",
        bank_name=bank_name,
        product_name=product_name,
        product_type=product_type,
        debug=True,
    )

    if isinstance(query_result, tuple):
        records, debug_info = query_result
    else:
        records, debug_info = query_result, {}

    sql_contents: List[str] = []
    sql_results: List[Dict[str, Any]] = []

    for record in records:
        sql_contents.append(record.to_bullet())
        sql_results.append(record.__dict__)

    state["sql_contents"] = sql_contents
    state["sql_results"] = sql_results

    debug = state.get("debug") or {}
    debug_info.setdefault("raw_bank_name", bank_name)
    debug_info.setdefault("raw_product_name", product_name)
    debug_info.setdefault("raw_product_type", product_type)
    debug["sql"] = debug_info
    state["debug"] = debug

    # SQL 근거는 이후 노드에서 벡터 결과와 결합하므로 여기서는 contents/sources를 건드리지 않는다.
    return state
