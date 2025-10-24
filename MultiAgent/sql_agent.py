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
from typing import Any, Dict, Iterable, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from db_ingest.create_vectordb import load_config, build_connection_string
except ImportError:  # pragma: no cover - fallback when running as module
    from ..db_ingest.create_vectordb import load_config, build_connection_string  # type: ignore


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


# ---------------------------------------------------------------------------
# SQL Retrieval Agent
# ---------------------------------------------------------------------------


class SQLRetrievalAgent:
    """rdb.loan_products 테이블에서 질의하는 에이전트."""

    def __init__(
        self,
        *,
        conn_str: Optional[str] = None,
        default_limit: int = 5,
    ) -> None:
        config = load_config()
        self.conn_str = conn_str or build_connection_string(config)
        self.default_limit = default_limit

    # -- 내부 유틸 ---------------------------------------------------------

    def _connect(self):
        return psycopg2.connect(self.conn_str)

    @staticmethod
    def _build_like_pattern(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return f"%{normalized}%"

    @staticmethod
    def _detect_target(question: str, product_name: Optional[str]) -> Optional[str]:
        text = f"{question} {product_name or ''}"
        for canonical, synonyms in LOAN_TARGET_SYNONYMS.items():
            if any(syn in text for syn in synonyms):
                return canonical
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
        limit: Optional[int] = None,
    ) -> List[LoanProductRecord]:
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
        sql = [
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

        bank_like = self._build_like_pattern(bank_name)
        if bank_like:
            sql.append("AND bank_name ILIKE %s")
            params.append(bank_like)

        product_like = self._build_like_pattern(product_name)
        if product_like:
            sql.append("AND product_name ILIKE %s")
            params.append(product_like)

        type_like = self._build_like_pattern(product_type)
        if type_like:
            sql.append("AND (product_category ILIKE %s OR product_detail_category ILIKE %s)")
            params.extend([type_like, type_like])

        target_like = self._build_like_pattern(loan_target)
        if target_like:
            sql.append("AND loan_target ILIKE %s")
            params.append(target_like)

        sql.append("ORDER BY bank_name, product_name")
        sql.append("LIMIT %s")
        params.append(limit or self.default_limit)

        query_str = "\n".join(sql)

        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query_str, params)
                rows = cur.fetchall()

        return [LoanProductRecord.from_row(row) for row in rows]

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

        detected_target = loan_target or self._detect_target(question, product_name)

        records = self.query(
            question=question,
            bank_name=bank_name,
            product_name=product_name,
            product_type=product_type,
            loan_target=detected_target,
        )

        if not records:
            state["sql_results"] = []
            state["sql_contents"] = []
            return state

        state["sql_results"] = [record.__dict__ for record in records]
        state["sql_contents"] = [record.to_bullet() for record in records]
        return state


__all__ = ["SQLRetrievalAgent", "LoanProductRecord"]
LOAN_TARGET_SYNONYMS: Dict[str, Iterable[str]] = {
    "전문직": ("전문직", "의사", "의료", "법조인", "판사", "검사", "변호사", "변호인"),
    "개인사업자": ("개인사업자", "자영업자", "사업자"),
    "군인": ("군인", "장교", "병사"),
    "부부": ("부부", "신혼부부", "맞벌이"),
    "청년": ("청년", "청년층", "청년전용"),
}
