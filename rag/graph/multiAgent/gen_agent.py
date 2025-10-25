"""
Generation Agent

SQL 검색 결과와 관련 청크를 기반으로 최종 답변을 생성하는 에이전트
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from rag.core.logger import get_logger

logger = get_logger(__name__)


GENERATION_SYSTEM_PROMPT = """당신은 한국 은행 상품 전문 상담사입니다.

사용자의 질문에 대해 다음 세 가지 정보원을 활용하여 정확하고 친절한 답변을 제공하세요:

**정보원 1: SQL 검색 결과 (RDB에서 조회)**
- 상품의 기본 메타데이터 (은행명, 상품명, 대출조건, 기간, 한도 등)
- 구조화된 상품 정보
- 대출 대상, 카테고리 등 필터링된 결과

**정보원 2: Vector DB 조회 결과 (내부 약관 데이터)**
- 상품 약관의 구체적인 조항 내용
- 금리, 수수료, 우대조건 등 상세 정보
- LLM이 관련성을 평가하여 필터링한 고품질 정보
- **최우선 신뢰 정보**: 공식 은행 약관 데이터

**정보원 3: 웹 검색 결과 (보조 정보)**
- Vector DB에 정보가 충분하지 않을 때 추가로 수집된 정보
- 최신 정보, 참고 자료
- **주의**: Vector DB 정보와 충돌 시 Vector DB 우선

**중요한 우선순위 규칙:**
1. Vector DB 정보와 웹 검색 정보가 충돌하면 **항상 Vector DB 정보를 우선**하세요
2. Vector DB는 공식 은행 약관이므로 가장 신뢰할 수 있습니다
3. 웹 검색 결과는 보조 정보로만 활용하세요

답변 작성 시 주의사항:
- 제공된 정보만을 기반으로 답변하세요 (추측 금지)
- SQL 결과, Vector DB 결과, 웹 검색 결과를 모두 활용하세요
- 정보 출처를 명확히 구분하세요 (예: "공식 약관에 따르면...", "참고로...")
- 정보가 부족하면 "제공된 정보로는 정확한 답변이 어렵습니다"라고 말하세요
- 은행명, 상품명, 조항 번호 등을 명확히 언급하세요
- 전문 용어는 쉽게 풀어서 설명하세요
- 답변은 3-5문단으로 구조화하세요

권장 답변 구조:
1. 질문 요약 및 검색된 상품 소개
2. SQL 검색 결과 기반 기본 정보 (대출 조건, 기간, 한도)
3. Vector DB 약관 조항 기반 상세 내용 (금리, 수수료, 우대조건)
4. 웹 검색 기반 추가 정보 (있는 경우)
5. 주의사항 및 마무리
"""


def build_generation_prompt(
    question: str,
    sql_results: List[Dict[str, Any]],
    relevant_chunks: List[Dict[str, Any]]
) -> str:
    """답변 생성 프롬프트 작성"""
    lines = [
        f'질문: "{question}"',
        "",
        "=" * 80,
        "1. SQL 검색 결과 (상품 기본 정보)",
        "=" * 80,
        ""
    ]
    
    if not sql_results:
        lines.append("검색된 상품이 없습니다.")
    else:
        for idx, result in enumerate(sql_results, 1):
            lines.append(f"[상품 {idx}]")
            lines.append(f"은행: {result.get('bank_name', '')}")
            lines.append(f"상품명: {result.get('product_name', '')}")
            lines.append(f"종류: {result.get('product_category', '')} > {result.get('product_detail_category', '')}")
            
            if result.get('loan_target'):
                lines.append(f"대출대상: {result.get('loan_target')}")
            if result.get('loan_conditions'):
                lines.append(f"대출조건: {result.get('loan_conditions')}")
            if result.get('loan_period'):
                lines.append(f"대출기간: {result.get('loan_period')}")
            if result.get('loan_limit'):
                lines.append(f"대출한도: {result.get('loan_limit')}")
            
            if result.get('selection_reason'):
                lines.append(f"\n선정 이유:\n{result.get('selection_reason')}")
            
            lines.append("")
    
    lines.extend([
        "",
        "=" * 80,
        "2. 관련 약관 조항 (상세 내용)",
        "=" * 80,
        ""
    ])
    
    if not relevant_chunks:
        lines.append("관련 약관 조항을 찾지 못했습니다.")
    else:
        # Vector DB 청크와 웹 검색 결과 분리
        vector_chunks = [c for c in relevant_chunks if c.get('source') != 'web_search']
        web_chunks = [c for c in relevant_chunks if c.get('source') == 'web_search']
        
        # Vector DB 청크 (우선 표시)
        if vector_chunks:
            lines.append("【Vector DB 조회 결과 - 공식 약관】")
            lines.append("")
            for idx, chunk in enumerate(vector_chunks, 1):
                lines.append(f"[조항 {idx}]")
                lines.append(f"은행: {chunk.get('bank_name', '')}")
                lines.append(f"문서: {chunk.get('document_name', '')}")
                lines.append(f"상품: {chunk.get('product_name', '')}")
                lines.append(f"조항: {chunk.get('clause', '')} - {chunk.get('clause_name', '')}")
                
                if chunk.get('eval_result'):
                    eval_result = chunk['eval_result']
                    lines.append(f"관련성: {eval_result.get('relevance_score', 0.0):.2f}")
                    lines.append(f"이유: {eval_result.get('reason', '')}")
                
                lines.append(f"\n내용:\n{chunk.get('content', '')}")
                lines.append("")
        
        # 웹 검색 결과 (보조 정보)
        if web_chunks:
            lines.append("")
            lines.append("【웹 검색 결과 - 참고 정보】")
            lines.append("※ Vector DB 정보와 충돌 시 Vector DB 우선")
            lines.append("")
            for idx, chunk in enumerate(web_chunks, 1):
                lines.append(f"[웹 검색 {idx}]")
                
                # 웹 검색 결과는 구조가 다를 수 있음
                if chunk.get('title'):
                    lines.append(f"제목: {chunk.get('title', '')}")
                if chunk.get('url'):
                    lines.append(f"출처: {chunk.get('url', '')}")
                
                if chunk.get('eval_result'):
                    eval_result = chunk['eval_result']
                    lines.append(f"관련성: {eval_result.get('relevance_score', 0.0):.2f}")
                    lines.append(f"이유: {eval_result.get('reason', '')}")
                
                lines.append(f"\n내용:\n{chunk.get('content', '')}")
                lines.append("")
    
    lines.extend([
        "",
        "=" * 80,
        "",
        "위 정보를 바탕으로 사용자 질문에 대한 정확하고 친절한 답변을 작성하세요."
    ])
    
    return "\n".join(lines)


class GenerationAgent:
    """최종 답변 생성 에이전트"""
    
    def __init__(self, llm: Optional[Any] = None):
        """
        Parameters
        ----------
        llm : Optional[Any]
            LLM 모델 객체
        """
        self.llm = llm
        logger.info("GenerationAgent initialized")
    
    def generate_answer(
        self,
        question: str,
        sql_results: List[Dict[str, Any]],
        relevant_chunks: List[Dict[str, Any]]
    ) -> str:
        """
        최종 답변 생성
        
        Parameters
        ----------
        question : str
            사용자 질문
        sql_results : List[Dict[str, Any]]
            SQL 검색 결과
        relevant_chunks : List[Dict[str, Any]]
            관련성 있는 청크
            
        Returns
        -------
        str
            생성된 답변
        """
        if not self.llm:
            logger.error("No LLM provided")
            return "답변 생성을 위한 LLM이 설정되지 않았습니다."
        
        if not sql_results and not relevant_chunks:
            return "죄송합니다. 질문과 관련된 정보를 찾지 못했습니다. 다른 방식으로 질문해 주시겠어요?"
        
        try:
            # 프롬프트 생성
            system_prompt = GENERATION_SYSTEM_PROMPT
            user_prompt = build_generation_prompt(question, sql_results, relevant_chunks)
            
            # LLM 호출
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.llm.invoke(messages)
            answer = response.content if hasattr(response, "content") else str(response)
            
            logger.info(f"Generated answer: {len(answer)} characters")
            return answer
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node에서 호출하기 위한 헬퍼
        
        Parameters
        ----------
        state : Dict[str, Any]
            현재 상태
            - question: 사용자 질문
            - sql_results: SQL Agent에서 조회한 상품 정보 (List[Dict])
            - sql_contents: SQL 결과 텍스트 요약 (List[str])
            - relevant_chunks: Evaluation Agent에서 필터링한 관련 청크 (List[Dict])
            
        Returns
        -------
        Dict[str, Any]
            answer가 추가된 상태
        """
        question = state.get("question", "")
        sql_results = state.get("sql_results", [])
        sql_contents = state.get("sql_contents", [])
        relevant_chunks = state.get("relevant_chunks", [])
        
        logger.info(f"=== Generation Agent ===")
        logger.info(f"SQL results: {len(sql_results)} products")
        logger.info(f"Relevant chunks: {len(relevant_chunks)} chunks")
        
        # 청크 소스 분석
        vector_chunks = [c for c in relevant_chunks if c.get('source') != 'web_search']
        web_chunks = [c for c in relevant_chunks if c.get('source') == 'web_search']
        logger.info(f"  - Vector DB: {len(vector_chunks)} chunks")
        logger.info(f"  - Web Search: {len(web_chunks)} chunks")
        
        # SQL 결과 로깅 (상세)
        if sql_results:
            logger.info("SQL Results:")
            for idx, result in enumerate(sql_results[:3], 1):  # 처음 3개만
                logger.info(f"  [{idx}] {result.get('bank_name', '')} - {result.get('product_name', '')}")
        
        # 답변 생성
        answer = self.generate_answer(question, sql_results, relevant_chunks)
        
        # 상태 업데이트
        state["answer"] = answer
        
        # 디버그 정보
        debug = state.get("debug", {})
        debug["generation"] = {
            "sql_results_count": len(sql_results),
            "sql_contents_count": len(sql_contents),
            "relevant_chunks_count": len(relevant_chunks),
            "vector_chunks_count": len(vector_chunks),
            "web_chunks_count": len(web_chunks),
            "answer_length": len(answer),
            "has_sql_data": len(sql_results) > 0,
            "has_vector_data": len(vector_chunks) > 0,
            "has_web_data": len(web_chunks) > 0
        }
        state["debug"] = debug
        
        logger.info(f"Answer generated: {len(answer)} characters")
        
        return state


__all__ = ["GenerationAgent"]
