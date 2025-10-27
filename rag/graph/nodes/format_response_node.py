# -*- coding: utf-8 -*-
"""
출처 포맷팅 전용 노드 모듈 (슬림 버전)

포함된 기능
- format_response: 문서 메타에서 출처 정보 리스트 구성
- append_sources_to_answer: 답변에 출처 섹션을 안전하게 부착/치환
"""

from __future__ import annotations
from typing import Dict, Any, List
import re

from rag.core.logger import get_logger

logger = get_logger(__name__)


def _build_source_title(src: Dict[str, Any]) -> str:
    """출처용 타이틀 문자열 구성 (은행/상품/조항명)."""
    bank = (src.get("bank_name") or "").strip()
    product = (src.get("product_name") or "").strip()
    clause_name = (src.get("clause_name") or "").strip()
    parts = [p for p in (bank, product, clause_name) if p]
    return " - ".join(parts) if parts else "문서"


class GraphNodes:
    """
    출처 포맷팅 전용 노드
    - 외부 의존(retriever/llm/jinja_env) 제거
    """

    def __init__(self):
        logger.info("GraphNodes (source-formatting only) initialized")

    # ---------------------------------------------------------------------
    # 1) 출처 포맷팅
    # ---------------------------------------------------------------------
    def format_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        응답 포맷팅 노드
        - 문서 메타에서 출처 정보 추출/정리
        - SQL 결과를 sources에 추가
        - 미리보기는 개행/다중 공백 정리 후 200자 제한
        """
        documents = state.get("documents", []) or []
        sql_results = state.get("sql_results", []) or []
        
        # Debug logging
        logger.info(f"format_response: sql_results count = {len(sql_results)}")
        logger.info(f"format_response: documents count = {len(documents)}")
        
        sources: List[Dict[str, Any]] = []
        source_index = 0

        # Add SQL results to sources
        for sql_result in sql_results[:10]:  # Limit to top 10
            source_index += 1
            bank_name = sql_result.get("bank_name", "")
            product_name = sql_result.get("product_name", "")
            product_category = sql_result.get("product_category", "")
            
            source_parts = []
            if bank_name:
                source_parts.append(bank_name)
            if product_name:
                source_parts.append(product_name)
            if product_category:
                source_parts.append(product_category)
            
            simple_preview = " - ".join(source_parts) if source_parts else "상품 정보"
            
            sources.append({
                "index": source_index,
                "source_type": "sql",
                "bank_name": bank_name,
                "product_name": product_name,
                "product_category": product_category,
                "content_preview": simple_preview,
                # Store full product data for app.py
                **sql_result
            })

        # Limit to top 10 sources to avoid overwhelming output
        limited_documents = documents[:10]

        for i, doc in enumerate(limited_documents):
            source_index += 1
            meta = getattr(doc, "metadata", {}) or {}
            
            # 간단한 출처 정보만 생성 (내용 제외)
            bank_name = meta.get("은행명", "") or meta.get("bank_name", "")
            document_name = meta.get("문서명", "") or meta.get("document_name", "")
            product_name = meta.get("상품이름", "") or meta.get("product_name", "")
            clause = meta.get("조항", "") or meta.get("clause", "")
            clause_name = meta.get("조항이름", "") or meta.get("clause_name", "")
            
            # 간단한 출처 설명 생성
            source_parts = []
            if bank_name:
                source_parts.append(bank_name)
            if document_name:
                source_parts.append(document_name)
            if product_name:
                source_parts.append(product_name)
            if clause:
                source_parts.append(clause)
            if clause_name:
                source_parts.append(clause_name)
            
            simple_preview = " - ".join(source_parts) if source_parts else "문서"

            sources.append({
                "index": source_index,
                "source_type": "vector",
                "bank_name": bank_name,
                "document_name": document_name,
                "product_name": product_name,
                "clause": clause,
                "clause_name": clause_name,
                "content_preview": simple_preview,
            })

        logger.info(f"Formatted {len(sources)} sources")
        return {**state, "sources": sources}

    # ---------------------------------------------------------------------
    # 2) 답변에 출처 첨부(안전한 숫자 치환 또는 섹션 생성)
    # ---------------------------------------------------------------------
    def append_sources_to_answer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        답변 뒤에 출처(문서 제목 기반)를 추가하는 노드
        - '출처' 라인이 이미 있으면: 숫자만 경계 기반으로 안전 치환
        - 없으면: 맨 아래에 출처 섹션 자동 생성
        """
        logger.info("🧩 append_sources_to_answer 실행됨")
        answer = state.get("answer", "") or ""
        sources = state.get("sources", []) or []

        if not sources:
            # 출처가 없으면 그대로 반환
            return {**state, "answer": answer}

        # 번호 -> 제목 매핑
        id_to_title = {i + 1: f"📄 {_build_source_title(s)}" for i, s in enumerate(sources)}

        # '출처' 라인 탐지 (콜론/공백 변형 허용)
        lines = answer.splitlines()
        src_line_idx = None
        for idx, line in enumerate(lines):
            if re.search(r"출\s*처\s*[:：]?", line):
                src_line_idx = idx
                break

        if src_line_idx is not None:
            # 해당 라인에서 '단어 경계 숫자'만 안전 치환
            def sub_fn(m):
                try:
                    num = int(m.group(1))
                except Exception:
                    return m.group(0)
                return id_to_title.get(num, m.group(0))

            # 불필요한 '출처' 반복/공백 정리
            replaced = re.sub(r"\b(\d+)\b", sub_fn, lines[src_line_idx])
            replaced = re.sub(r"(출\s*처\s*[:：]?\s*)+", "출처: ", replaced).strip()
            lines[src_line_idx] = replaced
            final_answer = "\n".join(lines).rstrip() + "\n"

        else:
            # 출처 섹션 새로 생성
            bullets = []
            for i in range(1, len(sources) + 1):
                title = id_to_title[i]
                preview = (sources[i - 1].get("content_preview") or "").strip()
                if preview:
                    # 너무 길면 자르고 한 줄로
                    p = re.sub(r"\s+", " ", preview)
                    if len(p) > 120:
                        p = p[:120] + "…"
                    bullets.append(f"{i}. {title} — {p}")
                else:
                    bullets.append(f"{i}. {title}")

            sources_block = "출처:\n" + "\n".join(bullets)
            final_answer = (answer.rstrip() + "\n\n" + sources_block).rstrip() + "\n"

        return {**state, "answer": final_answer}
