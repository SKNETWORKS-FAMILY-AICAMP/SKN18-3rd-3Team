from typing import Any, Dict, Iterable, List

# 은행/공식 공시 위주의 신뢰 가능한 도메인 화이트리스트
WHITELIST: Iterable[str] = (
    "wooribank.com",
    "kbstar.com",
    "kebhana.com",
    "hanafn.com",
    "shinhangroup.com",
    "ibk.co.kr",
    "fss.or.kr",
    "bok.or.kr",
)


def _build_queries(state: Dict[str, Any]) -> List[str]:
    """은행명/상품명/질문 키워드를 조합해 웹 검색용 쿼리를 생성한다."""
    question = (state.get("question") or "").strip()
    bank = (state.get("bank_name") or "").strip()
    product = (state.get("product_name") or "").strip()
    clause_keywords: List[str] = state.get("clause_keywords") or []

    queries: List[str] = []
    if bank and product:
        clause_piece = " ".join(clause_keywords[:3]) if clause_keywords else "약관"
        queries.append(f"{bank} {product} {clause_piece}")
    if bank and not product:
        queries.append(f"{bank} 은행 상품 약관 { ' '.join(clause_keywords[:3]) }".strip())
    if product and not bank:
        queries.append(f"{product} 약관 { ' '.join(clause_keywords[:3]) }".strip())

    # 원 질문도 항상 후보로 포함
    if question:
        queries.append(question)

    # 중복 제거
    unique_queries = []
    for q in queries:
        q = q.strip()
        if q and q not in unique_queries:
            unique_queries.append(q)
    return unique_queries or [question or "은행 약관"]


def _score_result(hit: Dict[str, Any]) -> float:
    """도메인과 키워드 포함 여부를 바탕으로 정렬 점수를 계산한다."""
    base = hit.get("priority", 0.0)
    text = hit.get("text", "")
    bonus_keywords = ["약관", "공시", "금리", "수수료", "중도해지", "우대", "가입"]
    if any(key in text for key in bonus_keywords):
        base += 0.2
    return base


def search_web_node(state: Dict[str, Any], deps: Any) -> Dict[str, Any]:
    """벡터 검색이 부족한 경우 Tavily 웹 검색으로 근거를 보강한다."""
    if not getattr(deps, "tavily", None):
        raise ValueError("웹 검색 도구(deps.tavily)가 설정되지 않았습니다.")

    queries = _build_queries(state)
    results: List[Dict[str, Any]] = []

    for query in queries[:8]:
        try:
            hits = deps.tavily.search(query, max_results=5) or []
        except RuntimeError as exc:
            # API 키 누락 등으로 Tavily를 사용할 수 없는 경우, 이후 노드가 안내하도록 상태에 기록한다.
            state["web_error"] = str(exc)
            break
        for hit in hits:
            url = hit.get("url", "")
            priority = 1 if any(domain in url for domain in WHITELIST) else 0
            text = (hit.get("content") or hit.get("snippet") or "")[:2000]
            results.append(
                {
                    "title": hit.get("title", ""),
                    "url": url,
                    "text": text,
                    "priority": priority,
                }
            )
        if len(results) >= 12:
            break

    if not results:
        # 검색 결과가 비어도 후속 노드에서 안내할 수 있도록 상태를 명시적으로 채운다.
        state["contents"] = []
        state["sources"] = []
        state["documents"] = []
        state["web_used"] = True
        state["generation_strategy"] = "web_search"
        return state

    results = sorted(results, key=_score_result, reverse=True)[:10]

    state["web_used"] = True
    state["generation_strategy"] = "web_search"
    state["contents"] = [r["text"] for r in results]
    state["sources"] = [{"title": r["title"], "url": r["url"]} for r in results]
    state["documents"] = []
    return state


# 하위 호환을 위해 기존 함수명도 유지
def web_fallback_node(state: Dict[str, Any], deps: Any) -> Dict[str, Any]:
    """기존 코드가 사용하던 함수명을 유지하기 위한 래퍼."""
    return search_web_node(state, deps)
