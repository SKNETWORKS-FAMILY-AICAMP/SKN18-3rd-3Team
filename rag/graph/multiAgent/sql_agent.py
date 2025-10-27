"""
SQL Retrieval Agent for loan product metadata.

이 모듈은 LangGraph 파이프라인과 연동할 수 있도록
은행 대출 상품 정보를 RDB(PostgreSQL)에서 조회하는 경량 에이전트를 제공한다.

주요 기능
---------
- intent 노드가 추출한 은행/상품 정보를 기반으로 파라미터화된 SQL을 생성
- rdb.loan_info 테이블에서 조건에 맞는 행을 조회
- 검색 결과를 바로 사용할 수 있도록 dict 형태로 반환
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from psycopg import connect  # psycopg3
from psycopg.rows import dict_row

try:
    from rag.core.config import get_config
except ModuleNotFoundError:  # 스크립트 단독 실행 시 루트 경로를 추가
    from pathlib import Path
    import sys

    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from rag.core.config import get_config


# ---------------------------------------------------------------------------
# 데이터 클래스 및 유틸
# ---------------------------------------------------------------------------


@dataclass
class LoanProductRecord:
    """단일 대출 상품 정보를 표현하는 데이터 클래스."""

    bank_name: str
    product_name: str
    product_category: Optional[str]
    product_detail_category: Optional[str]
    loan_target: Optional[str]
    loan_conditions: Optional[str]
    loan_period: Optional[str]
    loan_limit: Optional[str]

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "LoanProductRecord":
        return cls(
            bank_name=row.get("bank_name", ""),
            product_name=row.get("product_name", ""),
            product_category=row.get("product_category"),
            product_detail_category=row.get("product_detail_category"),
            loan_target=row.get("loan_target"),
            loan_conditions=row.get("loan_conditions"),
            loan_period=row.get("loan_period"),
            loan_limit=row.get("loan_limit"),
        )

    def to_bullet(self) -> str:
        """간단한 bullet 문자열로 변환."""
        parts: List[str] = [
            f"은행: {self.bank_name}",
            f"상품명: {self.product_name}",
        ]
        if self.product_category:
            parts.append(f"종류: {self.product_category}")
        if self.product_detail_category:
            parts.append(f"상세종류: {self.product_detail_category}")
        if self.loan_target:
            parts.append(f"대출대상: {self.loan_target}")
        if self.loan_conditions:
            parts.append(f"대출조건: {self.loan_conditions}")
        if self.loan_period:
            parts.append(f"대출기간: {self.loan_period}")
        if self.loan_limit:
            parts.append(f"대출한도: {self.loan_limit}")
        return "\n".join(parts)


def _normalize(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    value = str(text).strip()
    return value or None


def _tokenize_keywords(text: Optional[str]) -> List[str]:
    """질문/상품명에서 검색에 사용할 토큰만 추출."""
    if not text:
        return []
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text)
    return [tok for tok in tokens if len(tok) > 1]


def _filter_product_tokens(tokens: Iterable[str]) -> List[str]:
    filtered: List[str] = []
    seen = set()
    for tok in tokens:
        if not tok:
            continue
        normalized = tok.strip()
        if not normalized or normalized in GENERIC_PRODUCT_TOKENS:
            continue
        if normalized not in seen:
            seen.add(normalized)
            filtered.append(normalized)
    return filtered


def _map_loan_type_to_categories(loan_type: Optional[str]) -> List[str]:
    """classify_node가 반환한 loan_type을 detail category 필터로 변환."""
    if not loan_type:
        return []
    key = loan_type.strip()
    if not key:
        return []
    mapped = LOAN_TYPE_TO_DETAIL_CATEGORY.get(key)
    if mapped:
        return list(mapped)
    # 매핑이 없다면 그대로 사용해 LIKE 조건을 구성한다.
    return [key]


def _fetch_rate_summary(rates: List[Dict[str, Any]], max_lines: int = 3) -> List[str]:
    """금리 결과를 간단히 요약한 문자열 목록으로 변환."""
    if not rates:
        return []
    lines: List[str] = ["[금리 정보]"]
    for rate in rates[:max_lines]:
        rate_type = rate.get("rate_type") or "-"
        condition = rate.get("rate_condition") or "-"
        interest = rate.get("interest_rate") or "-"
        lines.append(f"- {rate_type} ({condition}): {interest}")
    if len(rates) > max_lines:
        lines.append(f"- ...외 {len(rates) - max_lines}건")
    return lines


def _group_rates_by_product(rates: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in rates:
        key = (row.get("bank_name", ""), row.get("product_name", ""))
        groups.setdefault(key, []).append(row)
    return groups


def _build_selection_reason(record: "LoanProductRecord") -> str:
    """SQL 결과가 선택된 이유를 2줄 요약으로 생성."""
    bank = record.bank_name or "미지정 은행"
    detail = record.product_detail_category or record.product_category or "기타 상품"
    target = record.loan_target or "대상 미기재"
    lines = [
        f"- 질문에서 지정된 은행 '{bank}'과 대출 유형 '{detail}' 조건을 충족했습니다.",
        f"- 대출대상 '{target}' 요건과 일치해 필터링을 통과한 상품입니다.",
    ]
    return "\n".join(lines)

# classify_node가 추출한 대출 대상 및 상품 종류의 동의어 매핑
LOAN_TARGET_SYNONYMS: Dict[str, Iterable[str]] = {
    "전문직": ("전문직", "의사", "의료", "법조인", "판사", "검사", "변호사", "변호인"),
    "개인사업자": ("개인사업자", "자영업자", "사업자"),
    "군인": ("군인", "장교", "병사"),
    "부부": ("부부", "신혼부부", "맞벌이"),
    "청년": ("청년", "청년층", "청년전용"),
    "근로소득자": ("근로소득자", "근로자", "직장인", "재직자"),
    "개인": ("개인", "개인고객", "누구나"),
    "기업": ("기업", "법인"),
    "세대주": ("세대주", "세대 장", "세대장"),
}

DETAIL_CATEGORY_SYNONYMS: Dict[str, Iterable[str]] = {
    "담보대출": ("담보대출", "담보", "담보로", "부동산대출", "부동산 담보", "부동산담보", "부동산담보대출", "부동산 담보대출"),
    "전세자금대출": ("전세자금대출", "전세자금", "전세 대출", "전세대출", "전세"),
    "주택담보대출": ("주택담보대출", "주택담보", "주택 대출", "주택대출"),
    "신용대출": ("신용대출", "신용"),
    "기업대출": ("기업대출", "기업 자금"),
    "정책자금대출": ("정책자금대출", "정책 자금"),
}

# classify_node가 추출한 loan_type은 자유 텍스트이므로,
# 실제 SQL 조건에 쓰이는 detail_category 값으로 매핑해 둔다.
LOAN_TYPE_TO_DETAIL_CATEGORY: Dict[str, Tuple[str, ...]] = {
    "전세자금대출": ("전세자금대출",),
    "담보대출": ("담보대출", "주택담보대출"),
    "주택도시기금대출": ("전세자금대출", "정책자금대출"),
    "신용대출": ("신용대출",),
    "기업대출": ("기업대출",),
    "부동산대출": ("담보대출", "주택담보대출"),
    "정책자금대출": ("정책자금대출",),
}

GENERIC_PRODUCT_TOKENS = {"예금", "적금", "대출", "상품", "금리"}


# ---------------------------------------------------------------------------
# SQL DB 조회 에이전트
# ---------------------------------------------------------------------------

class SQLRetrievalAgent:
    """rdb.loan_info 테이블에서 질의하는 에이전트."""

    def __init__(
        self,
        *,
        conn_str: Optional[str] = None,
        default_limit: int = 5,
    ) -> None:
        config = get_config()
        self.conn_str = conn_str or config.DB_URL
        self.default_limit = default_limit

    # -- 내부 유틸 ---------------------------------------------------------

    def _connect(self):
        """psycopg3 커넥션을 생성한다. with 문에서 호출된다."""
        return connect(self.conn_str)

    @staticmethod
    def _build_like_pattern(value: Optional[str]) -> Optional[str]:
        """사용자 입력을 ILIKE 패턴(%%foo%%)으로 변환한다."""
        if not value:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return f"%{normalized}%"

    @staticmethod
    def _detect_target(question: str, product_name: Optional[str]) -> Optional[str]:
        """질문/상품명 텍스트에서 loan_target 후보를 규칙으로 감지한다."""
        text = f"{question} {product_name or ''}"
        for canonical, synonyms in LOAN_TARGET_SYNONYMS.items():
            if any(syn in text for syn in synonyms):
                return canonical
        return None

    @staticmethod
    def _detect_detail_categories(question: str, product_name: Optional[str]) -> List[str]:
        """질문/상품명에서 상세 대출 유형(담보/전세 등)을 규칙으로 감지한다."""
        text = f"{question} {product_name or ''}"
        normalized_product = (product_name or "").replace(" ", "")
        hits: List[str] = []
        for canonical, synonyms in DETAIL_CATEGORY_SYNONYMS.items():
            for syn in synonyms:
                if not syn:
                    continue
                if syn in text or syn.replace(" ", "") in normalized_product:
                    hits.append(canonical)
                    break
        return hits

    @staticmethod
    def _detect_period(question: str) -> Optional[str]:
        """'30년', '24개월' 같은 기간 표현을 추출한다."""
        match = re.search(r"(\d+\s*(?:년|개월))", question)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _detect_limit(question: str) -> Optional[str]:
        """'3억원', '5천만원' 처럼 금액 표현을 추출한다."""
        match = re.search(r"((?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?\s*(?:억원|억|천만원|백만원|십만원|만원|원))", question)
        if match:
            return match.group(1)
        return None

    def _fetch_interest_rates(
        self,
        bank_name: Optional[str],
        product_name: Optional[str],
        *,
        keywords: Optional[List[str]] = None,
        exact_match: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """bank_interest_rate 테이블에서 금리 정보를 조회한다."""
        params: List[Any] = []
        conditions: List[str] = []

        if bank_name:
            conditions.append("bank_name = %s")
            params.append(bank_name)

        tokens: List[str] = []
        if product_name:
            tokens.append(product_name)
        if keywords:
            tokens.extend(keywords)
        tokens = [tok.strip() for tok in tokens if tok and tok.strip()]

        product_conditions: List[str] = []
        if exact_match and product_name:
            product_conditions.append("product_name = %s")
            params.append(product_name)
        else:
            for token in tokens:
                product_conditions.append("product_name ILIKE %s")
                params.append(f"%{token}%")
                compact = token.replace(" ", "")
                if compact and compact != token:
                    product_conditions.append("REPLACE(product_name, ' ', '') ILIKE %s")
                    params.append(f"%{compact}%")

        if product_conditions:
            conditions.append("(" + " OR ".join(product_conditions) + ")")

        if not conditions:
            return []

        params.append(limit)
        sql = f"""
            SELECT bank_name, product_name, product_category, rate_type, rate_condition, interest_rate
            FROM rdb.bank_interest_rate
            WHERE {' AND '.join(conditions)}
            ORDER BY bank_name, product_name, rate_type NULLS LAST, rate_condition NULLS LAST
            LIMIT %s
        """
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    # -- 공개 메서드 ------------------------------------------------------

    def query(
        self,
        *,
        question: str,
        bank_name: Optional[str] = None,
        product_name: Optional[str] = None,
        product_type: Optional[str] = None,
        loan_target: Optional[str] = None,
        loan_type_hint: Optional[str] = None,
        product_keywords: Optional[List[str]] = None,
        detail_categories: Optional[Iterable[str]] = None,
        loan_period_hint: Optional[str] = None,
        loan_limit_hint: Optional[str] = None,
        limit: Optional[int] = None,
        debug: bool = False,
    ) -> Tuple[List[LoanProductRecord], Dict[str, Any]] | List[LoanProductRecord]:
        """
        질문과 intent 정보를 바탕으로 loan_info를 조회한다.

        Parameters
        ----------
        question: str
            사용자 원문 질문.
        bank_name/product_name/product_type: Optional[str]
            intent 노드에서 추출한 구조화 정보. None이면 조건에 포함시키지 않는다.
        limit: Optional[int]
            반환할 최대 행 수 (기본값 self.default_limit).
        """
        base_product_tokens = _tokenize_keywords(product_name)
        merged_tokens = []
        if product_keywords:
            merged_tokens.extend(product_keywords)
        merged_tokens.extend(base_product_tokens)
        product_tokens = _filter_product_tokens(merged_tokens)

        sql_parts = [
            """
            SELECT
                bank_name,
                product_name,
                product_category,
                product_detail_category,
                loan_target,
                loan_conditions,
                loan_period,
                loan_limit
            FROM rdb.loan_info
            WHERE 1=1
            """
        ]

        params: List[Any] = []

        if not any([
            bank_name,
            product_name,
            product_type,
            loan_target,
            detail_categories,
            product_tokens,
        ]):
            debug_info = {
                "skipped": True,
                "reason": "no_filters",
                "message": "검색 조건이 없어 SQL 검색을 생략했습니다.",
            }
            return ([], debug_info) if debug else []

        if bank_name:
            sql_parts.append("AND bank_name = %s")
            params.append(bank_name)

        product_like = self._build_like_pattern(product_name)
        product_like_compact = None
        product_filter_clauses: List[str] = []
        product_filter_params: List[Any] = []
        if product_like:
            raw_product = (product_name or "").strip()
            compact = raw_product.replace(" ", "")
            if compact and compact != raw_product:
                product_like_compact = f"%{compact}%"
            product_conditions = ["product_name ILIKE %s"]
            product_filter_params.append(product_like)
            if product_like_compact:
                product_conditions.append("REPLACE(product_name, ' ', '') ILIKE %s")
                product_filter_params.append(product_like_compact)
            product_filter_clauses.append("(" + " OR ".join(product_conditions) + ")")
        if product_tokens:
            token_conditions: List[str] = []
            for token in product_tokens:
                token_conditions.append("product_name ILIKE %s")
                product_filter_params.append(f"%{token}%")
            product_filter_clauses.append("(" + " OR ".join(token_conditions) + ")")

        type_like = self._build_like_pattern(product_type)

        detail_categories_raw: List[str] = list(detail_categories or [])
        detail_category_filters: List[str] = []
        for category in detail_categories or []:
            normalized_category = _normalize(category)
            if normalized_category:
                detail_category_filters.append(normalized_category)
        if loan_type_hint:
            # loan_type도 detail category 후보에 포함시켜 LIKE 조건을 강화
            detail_categories_raw.append(loan_type_hint)
            detail_category_filters.extend(_map_loan_type_to_categories(loan_type_hint))
        detail_category_filters = list(dict.fromkeys(detail_category_filters))

        skip_product_filter = False
        if product_name:
            normalized_prod = product_name.replace(" ", "")
            if detail_category_filters and normalized_prod:
                for category in detail_category_filters:
                    normalized_category = (category or "").replace(" ", "")
                    if normalized_prod and normalized_prod in normalized_category:
                        skip_product_filter = True
                        break
        elif not product_tokens:
            skip_product_filter = True

        optional_clauses: List[str] = []
        optional_params: List[Any] = []

        if type_like:
            optional_clauses.append("(product_category ILIKE %s OR product_detail_category ILIKE %s)")
            optional_params.extend([type_like, type_like])

        if detail_category_filters:
            placeholders: List[str] = []
            clause_params: List[Any] = []
            for category in detail_category_filters:
                category_like = self._build_like_pattern(category)
                if category_like:
                    placeholders.append("product_detail_category ILIKE %s")
                    clause_params.append(category_like)
            if placeholders:
                optional_clauses.append("(" + " OR ".join(placeholders) + ")")
                optional_params.extend(clause_params)

        if product_filter_clauses and not skip_product_filter:
            optional_clauses.append("(" + " OR ".join(product_filter_clauses) + ")")
            optional_params.extend(product_filter_params)
        else:
            product_like = None
            product_like_compact = None

        if loan_target:
            optional_clauses.append("loan_target ILIKE %s")
            optional_params.append(f"%{loan_target}%")

        if not optional_clauses and type_like:
            optional_clauses.append("(product_category ILIKE %s OR product_detail_category ILIKE %s)")
            optional_params.extend([type_like, type_like])

        if not optional_clauses:
            debug_info = {
                "skipped": True,
                "reason": "no_optional_filters",
                "message": "적용 가능한 검색 조건이 없어 SQL 검색을 생략했습니다.",
            }
            return ([], debug_info) if debug else []

        sql_parts.append("AND (" + " OR ".join(optional_clauses) + ")")
        params.extend(optional_params)

        period_like = self._build_like_pattern(loan_period_hint)
        if period_like:
            sql_parts.append("AND loan_period ILIKE %s")
            params.append(period_like)

        limit_like = self._build_like_pattern(loan_limit_hint)
        if limit_like:
            sql_parts.append("AND loan_limit ILIKE %s")
            params.append(limit_like)

        sql_parts.append("ORDER BY bank_name, product_name")
        sql_parts.append("LIMIT %s")
        params.append(limit or self.default_limit)

        query_str = "\n".join(sql_parts)
        debug_info = {
            "sql": query_str,
            "params": [str(p) for p in params],
            "bank_exact": bank_name,
            "product_pattern": product_like,
            "product_pattern_compact": product_like_compact,
            "product_tokens": product_tokens,
            "type_pattern": type_like,
            "target_exact": loan_target,
            "detected_target": loan_target,
            "detail_categories": detail_category_filters,
            "detail_categories_raw": detail_categories_raw,
            "loan_type_hint": loan_type_hint,
            "loan_period_pattern": period_like,
            "loan_limit_pattern": limit_like,
        }

        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query_str, params)
                rows = cur.fetchall()

        records = [LoanProductRecord.from_row(row) for row in rows]
        if debug:
            return records, debug_info
        return records

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node에서 호출하기 위한 헬퍼.
        state에 SQL 검색 결과와 텍스트 요약을 추가해 반환한다.
        """
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

        question = state.get("question", "")
        bank_name = _normalize(state.get("bank_name"))
        product_name = _normalize(state.get("product_name"))
        product_type = _normalize(state.get("product_type"))
        loan_target = _normalize(state.get("loan_target"))
        loan_type = _normalize(state.get("loan_type"))
        raw_keywords = state.get("raw_keywords") or []
        raw_keyword_tokens: List[str] = []
        for kw in raw_keywords:
            raw_keyword_tokens.extend(_tokenize_keywords(kw))
        raw_keyword_tokens = _filter_product_tokens(raw_keyword_tokens)

        detected_target = loan_target or self._detect_target(question, product_name)
        detected_details = self._detect_detail_categories(question, product_name)
        detected_period = self._detect_period(question)
        detected_limit = self._detect_limit(question)

        detail_categories_list = list(dict.fromkeys(detected_details))
        if "담보" in (product_name or "") or "담보" in question:
            if "담보대출" not in detail_categories_list:
                detail_categories_list.append("담보대출")

        if loan_type:
            # classify_node가 뽑은 loan_type을 SQL 필터로 재활용
            detail_categories_list.extend(_map_loan_type_to_categories(loan_type))

        detail_categories_list = list(dict.fromkeys(detail_categories_list))

        detail_categories = detail_categories_list or None
        product_token_candidates = _tokenize_keywords(product_name)
        if raw_keyword_tokens:
            product_token_candidates.extend(raw_keyword_tokens)
        product_tokens = _filter_product_tokens(product_token_candidates)

        product_name_for_query = product_name if not detail_categories_list else None
        debug_snapshot = {
            "detected_target": detected_target,
            "detected_details": detected_details,
            "detected_period": detected_period,
            "detected_limit": detected_limit,
            "product_name": product_name,
            "loan_type": loan_type,
        }

        query_result = self.query(
            question=question,
            bank_name=bank_name,
            product_name=product_name_for_query,
            product_type=product_type,
            loan_target=detected_target,
            loan_type_hint=loan_type,
            detail_categories=detail_categories,
            loan_period_hint=detected_period,
            loan_limit_hint=detected_limit,
            product_keywords=product_tokens,
            debug=True,
        )
        if isinstance(query_result, tuple):
            records, debug_info = query_result
        else:  # pragma: no cover - backward safety
            records, debug_info = query_result, {}

        if debug_info.get("skipped"):
            message = debug_info.get("message") or "SQL 검색을 생략했습니다."
            state["sql_results"] = []
            state["sql_contents"] = [message]
            debug = state.get("debug") or {}
            debug["sql"] = debug_info
            state["debug"] = debug
            return state

        for key, value in debug_snapshot.items():
            debug_info.setdefault(key, value)

        if not records:
            question_tokens = _filter_product_tokens(_tokenize_keywords(question))
            rate_keywords = product_tokens or raw_keyword_tokens or question_tokens
            rate_rows = self._fetch_interest_rates(
                bank_name=bank_name,
                product_name=product_name,
                keywords=rate_keywords,
                exact_match=False,
            )
            if rate_rows:
                grouped = _group_rates_by_product(rate_rows)
                sql_results: List[Dict[str, Any]] = []
                sql_contents: List[str] = []
                rate_debug: List[Dict[str, Any]] = []
                for (rate_bank, rate_product), group_rows in grouped.items():
                    summary_lines = _fetch_rate_summary(group_rows)
                    reason = (
                        f"- loan_info 테이블에서 일치 항목은 없었지만 '{rate_product}' 금리 데이터를 bank_interest_rate에서 찾았습니다.\n"
                        f"- 질문 키워드를 기반으로 금리 정보를 제공하는 결과입니다."
                    )
                    sql_results.append(
                        {
                            "bank_name": rate_bank,
                            "product_name": rate_product,
                            "product_category": group_rows[0].get("product_category"),
                            "interest_rates": group_rows,
                            "loan_info_match": False,
                            "selection_reason": reason,
                        }
                    )
                    content_lines = [
                        f"은행: {rate_bank}",
                        f"상품명: {rate_product}",
                    ]
                    category = group_rows[0].get("product_category")
                    if category:
                        content_lines.append(f"종류: {category}")
                    content = "\n".join(content_lines)
                    if summary_lines:
                        content += "\n" + "\n".join(summary_lines)
                    sql_contents.append(content + "\n" + reason)
                    rate_debug.append(
                        {
                            "bank_name": rate_bank,
                            "product_name": rate_product,
                            "rates_found": len(group_rows),
                            "loan_info_match": False,
                        }
                    )

                state["sql_results"] = sql_results
                state["sql_contents"] = sql_contents
                debug = state.get("debug") or {}
                debug_info["interest_rate_lookup"] = rate_debug
                debug["sql"] = debug_info
                state["debug"] = debug
                return state

            state["sql_results"] = []
            state["sql_contents"] = []
            debug = state.get("debug") or {}
            debug["sql"] = debug_info
            state["debug"] = debug
            return state

        rate_debug: List[Dict[str, Any]] = []
        sql_results: List[Dict[str, Any]] = []
        sql_contents: List[str] = []

        for record in records:
            reason = _build_selection_reason(record)
            rates = self._fetch_interest_rates(
                record.bank_name, record.product_name, exact_match=True
            )
            rate_debug.append(
                {
                    "bank_name": record.bank_name,
                    "product_name": record.product_name,
                    "rates_found": len(rates),
                    "loan_info_match": True,
                }
            )

            record_dict = record.__dict__.copy()
            record_dict["selection_reason"] = reason
            record_dict["loan_info_match"] = True
            if rates:
                record_dict["interest_rates"] = rates
            sql_results.append(record_dict)

            summary_lines = _fetch_rate_summary(rates)
            bullet = record.to_bullet()
            if summary_lines:
                bullet = bullet + "\n" + "\n".join(summary_lines)
            sql_contents.append(bullet + "\n" + reason)

        state["sql_results"] = sql_results
        state["sql_contents"] = sql_contents
        debug = state.get("debug") or {}
        debug_info["interest_rate_lookup"] = rate_debug
        debug["sql"] = debug_info
        state["debug"] = debug
        return state

# class 은닉
__all__ = ["SQLRetrievalAgent", "LoanProductRecord"]


if __name__ == "__main__":
    from pathlib import Path
    import sys
    import json

    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    try:
        from intent_llm_agent import run_intent_agent  # type: ignore
    except ModuleNotFoundError:
        from rag.graph.multiAgent.classify_agent import run_intent_agent  # type: ignore
    from rag.llm.get_llm import get_llm_model

    model = get_llm_model()

    question = "국민은행 신혼부부 대출 금리 알려줘"
    intent_result = run_intent_agent(question, llm=model, debug=True)
    print("=== Intent Result ===")
    print(json.dumps(intent_result, ensure_ascii=False, indent=2))

    # classify_node → SQL 노드 연결 흐름을 단독으로 검증하기 위한 샘플 실행
    agent = SQLRetrievalAgent()
    state = intent_result.copy()
    state["question"] = question
    state = agent.run(state)

    print("\n=== SQL Debug Info ===")
    print(json.dumps(state.get("debug", {}).get("sql", {}), ensure_ascii=False, indent=2))

    print("\n=== SQL Records ===")
    results = state.get("sql_results") or []
    if not results:
        print("검색 결과가 없습니다.")
    else:
        for idx, record in enumerate(results, start=1):
            print(f"[{idx}] {record.get('bank_name')} - {record.get('product_name')}")
            if "interest_rates" in record:
                summary = _fetch_rate_summary(record["interest_rates"])
                if summary:
                    print("\n".join(summary))
            if record.get("selection_reason"):
                print(record["selection_reason"])
            print()

