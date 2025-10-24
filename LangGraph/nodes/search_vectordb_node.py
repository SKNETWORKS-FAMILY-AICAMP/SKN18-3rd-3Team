from typing import Any, Dict, List

def _make_filters(state: Dict[str, Any]) -> Dict[str, Any]:
    filters = {}
    if state.get("bank_name"): filters["은행명"] = state["bank_name"]
    if state.get("product_name"): filters["상품이름"] = state["product_name"]
    if state.get("product_type"): filters["상품종류"] = state["product_type"]
    return filters

def _post_adjust_score(hit: Dict[str, Any], state: Dict[str, Any]) -> float:
    s = hit.get("score", 0.0)
    meta = hit.get("meta", {})

    if state.get("bank_name") and meta.get("은행명") == state["bank_name"]:
        s += 0.05
    if state.get("product_name") and meta.get("상품이름") == state["product_name"]:
        s += 0.05
    if state.get("product_type") and meta.get("상품종류") == state["product_type"]:
        s += 0.03
    return s

def search_vectordb_node(state: Dict[str, Any], deps: Any) -> Dict[str, Any]:
    """질문과 추출된 단서를 이용해 벡터 DB를 조회한다."""
    if not getattr(deps, "vector", None):
        raise ValueError("vector 검색기를 찾을 수 없습니다. deps.vector를 주입해 주세요.")

    query = state.get("question", "")
    filters = _make_filters(state)

    # 벡터 DB 검색 (deps.vector가 LangChain retriever든 자체 래퍼든 상관없음)
    results = deps.vector.search(query, top_k=20, filters=filters)

    for r in results:
        r["score"] = _post_adjust_score(r, state)

    # 상위 n개 정렬
    results = sorted(results, key=lambda x: x["score"], reverse=True)[:10]

    state.update({
        "contents": [r["text"] for r in results],
        "documents": results,
        "sources": [r.get("meta", {}) for r in results],
        "generation_strategy": "vector",
    })
    return state
