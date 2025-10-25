"""SQL Retrieval Node that queries structured loan product metadata."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..multiAgent.sql_agent import SQLRetrievalAgent

_sql_agent: Optional[SQLRetrievalAgent] = None


def _get_agent() -> SQLRetrievalAgent:
    global _sql_agent
    if _sql_agent is None:
        _sql_agent = SQLRetrievalAgent()
    return _sql_agent


def sql_retrieval_node(state: Dict[str, Any], deps: Any = None) -> Dict[str, Any]:
    """
    은행/상품 intent 결과(state)에 기반해 대출 상품 메타데이터를 조회한다.
    classify_node가 채운 bank_name, product_name, product_type, loan_type, loan_target
    등을 그대로 받아 SQL 에이전트에 전달한다.
    """
    agent = _get_agent()
    question = state.get("question", "") or ""
    bank_name = state.get("bank_name")
    product_name = state.get("product_name")
    product_type = state.get("product_type")
    loan_type = state.get("loan_type")
    loan_target = state.get("loan_target")

    query_result = agent.query(
        question=question,
        bank_name=bank_name,
        product_name=product_name,
        product_type=product_type,
        loan_target=loan_target,
        loan_type_hint=loan_type,
        debug=True,
    )

    if isinstance(query_result, tuple):
        records, debug_info = query_result
    else:
        records, debug_info = query_result, {}

    sql_contents: List[str] = []
    sql_results: List[Dict[str, Any]] = []

    for record in records:
        reason = (
            f"- 은행 '{record.bank_name}'의 '{record.product_detail_category or record.product_category or '기타 상품'}' 범주와 일치합니다.\n"
            f"- 대출대상 '{record.loan_target or '미기재'}' 조건이 intent 결과와 부합합니다."
        )
        sql_contents.append(record.to_bullet() + "\n" + reason)
        enriched = record.__dict__.copy()
        enriched["selection_reason"] = reason
        sql_results.append(enriched)

    state["sql_contents"] = sql_contents
    state["sql_results"] = sql_results

    debug = state.get("debug") or {}
    debug_info.setdefault("raw_bank_name", bank_name)
    debug_info.setdefault("raw_product_name", product_name)
    debug_info.setdefault("raw_product_type", product_type)
    debug_info.setdefault("raw_loan_type", loan_type)
    debug_info.setdefault("raw_loan_target", loan_target)
    debug_info["selection_reasons"] = [item["selection_reason"] for item in sql_results]
    debug["sql"] = debug_info
    state["debug"] = debug

    # SQL 근거는 이후 노드에서 벡터 결과와 결합하므로 여기서는 contents/sources를 건드리지 않는다.
    return state
