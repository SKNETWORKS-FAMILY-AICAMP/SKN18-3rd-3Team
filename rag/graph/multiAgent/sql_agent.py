"""
SQL Retrieval Agent for loan product metadata.

이 모듈은 LangGraph 파이프라인과 연동할 수 있도록
은행 대출 상품 정보를 RDB(PostgreSQL)에서 조회하는 경량 에이전트를 제공한다.

주요 기능
---------
- intent 노드가 추출한 은행/상품 정보를 기반으로 파라미터화된 SQL을 생성
- rdb.loan_products 테이블에서 조건에 맞는 행을 조회
- 검색 결과를 바로 사용할 수 있도록 dict 형태로 반환
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from psycopg import connect  # psycopg3
from psycopg.rows import dict_row

try:
    from RAG.core.config import get_config
except ModuleNotFoundError:  # 스크립트 단독 실행 시 루트 경로를 추가
    from pathlib import Path
    import sys

    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from RAG.core.config import get_config


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


# ---------------------------------------------------------------------------
# SQL DB 조회 에이전트
# ---------------------------------------------------------------------------

class SQLRetrievalAgent:
    """rdb.loan_products 테이블에서 질의하는 에이전트."""

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
        detail_categories: Optional[Iterable[str]] = None,
        loan_period_hint: Optional[str] = None,
        loan_limit_hint: Optional[str] = None,
        limit: Optional[int] = None,
        debug: bool = False,
    ) -> Tuple[List[LoanProductRecord], Dict[str, Any]] | List[LoanProductRecord]:
        """
        질문과 intent 정보를 바탕으로 loan_products를 조회한다.

        Parameters
        ----------
        question: str
            사용자 원문 질문.
        bank_name/product_name/product_type: Optional[str]
            intent 노드에서 추출한 구조화 정보. None이면 조건에 포함시키지 않는다.
        limit: Optional[int]
            반환할 최대 행 수 (기본값 self.default_limit).
        """
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
            FROM rdb.loan_products
            WHERE 1=1
            """
        ]

        params: List[Any] = []

        if bank_name:
            sql_parts.append("AND bank_name = %s")
            params.append(bank_name)

        product_like = self._build_like_pattern(product_name)
        product_like_compact = None
        product_clause = ""
        product_params: List[Any] = []
        if product_like:
            raw_product = (product_name or "").strip()
            compact = raw_product.replace(" ", "")
            if compact and compact != raw_product:
                product_like_compact = f"%{compact}%"
            product_conditions = ["product_name ILIKE %s"]
            product_params.append(product_like)
            if product_like_compact:
                product_conditions.append("REPLACE(product_name, ' ', '') ILIKE %s")
                product_params.append(product_like_compact)
            product_clause = "AND (" + " OR ".join(product_conditions) + ")"

        type_like = self._build_like_pattern(product_type)
        if type_like:
            sql_parts.append("AND (product_category ILIKE %s OR product_detail_category ILIKE %s)")
            params.extend([type_like, type_like])

        if loan_target:
            sql_parts.append("AND loan_target = %s")
            params.append(loan_target)

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
        else:
            # 상품명이 비어 있으면 필터를 건너뛴다.
            skip_product_filter = True

        if detail_category_filters:
            placeholders: List[str] = []
            for category in detail_category_filters:
                category_like = self._build_like_pattern(category)
                if category_like:
                    placeholders.append("product_detail_category ILIKE %s")
                    params.append(category_like)
            if placeholders:
                sql_parts.append("AND (" + " OR ".join(placeholders) + ")")

        if product_clause and not skip_product_filter:
            sql_parts.append(product_clause)
            params.extend(product_params)
        else:
            product_like = None
            product_like_compact = None

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
        question = state.get("question", "")
        bank_name = _normalize(state.get("bank_name"))
        product_name = _normalize(state.get("product_name"))
        product_type = _normalize(state.get("product_type"))
        loan_target = _normalize(state.get("loan_target"))
        loan_type = _normalize(state.get("loan_type"))

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
            debug=True,
        )
        if isinstance(query_result, tuple):
            records, debug_info = query_result
        else:  # pragma: no cover - backward safety
            records, debug_info = query_result, {}

        for key, value in debug_snapshot.items():
            debug_info.setdefault(key, value)

        if not records:
            state["sql_results"] = []
            state["sql_contents"] = []
            debug = state.get("debug") or {}
            debug["sql"] = debug_info
            state["debug"] = debug
            return state

        reasons: List[str] = []
        for record in records:
            bank = record.bank_name or "미지정 은행"
            detail = record.product_detail_category or record.product_category or "기타 상품"
            target = record.loan_target or "대상 미기재"
            reason_lines = [
                f"- 질문에서 지정한 은행 '{bank}'와 대출유형 '{detail}'이 일치합니다.",
                f"- 대출대상 '{target}' 조건이 classify 노드 결과와 부합해 필터를 통과했습니다."
            ]
            reasons.append("\n".join(reason_lines))
        state["sql_results"] = [
            {**record.__dict__, "selection_reason": reasons[idx]}
            for idx, record in enumerate(records)
        ]
        state["sql_contents"] = [
            record.to_bullet() + "\n" + reasons[idx] for idx, record in enumerate(records)
        ]
        debug = state.get("debug") or {}
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
        from RAG.graph.multiAgent.classify_agent import run_intent_agent  # type: ignore
    from RAG.llm.get_llm import get_llm_model

    model = get_llm_model()

    question = "우리은행 전세자금대출 알려줘"
    intent_result = run_intent_agent(question, llm=model, debug=True)
    print("=== Intent Result ===")
    print(json.dumps(intent_result, ensure_ascii=False, indent=2))

    # classify_node → SQL 노드 연결 흐름을 단독으로 검증하기 위한 샘플 실행
    agent = SQLRetrievalAgent()
    query = agent.query(
        question=question,
        bank_name=intent_result.get("bank_name"),
        product_name=intent_result.get("product_name"),
        product_type=intent_result.get("product_type"),
        loan_target=intent_result.get("loan_target"),
        loan_type_hint=intent_result.get("loan_type"),
        debug=True,
    )

    if isinstance(query, tuple):
        records, debug_info = query
    else:
        records, debug_info = query, {}

    print("\n=== SQL Debug Info ===")
    print(json.dumps(debug_info, ensure_ascii=False, indent=2))

    print("\n=== SQL Records ===")
    if not records:
        print("검색 결과가 없습니다.")
    else:
        for idx, record in enumerate(records, start=1):
            print(f"[{idx}] {record.to_bullet()}\n")

