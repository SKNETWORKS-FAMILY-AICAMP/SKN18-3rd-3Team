"""
Generation Agent

SQL 검색 결과와 관련 청크를 기반으로 최종 답변을 생성하는 에이전트
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from rag.core.logger import get_logger

logger = get_logger(__name__)


GENERATION_SYSTEM_PROMPT = """당신은 한국 은행 상품 전문 상담사입니다.

**🚨 최우선 규칙: 단순한 후속 질문 처리**
- 질문이 "응", "알려줘", "더 알려줘" 등이면 **절대** 상세 정보를 제공하지 말고 후속 질문만 제기
- "추천된 상품들의 약관 내용을 자세히 안내해 드릴 수 있습니다. 어떤 상품의 약관을 자세히 알고 싶으신가요? 아래 목록에서 확인해 주세요:"라고 답변
- 상품 목록을 불릿 포인트로 나열 (은행명: 상품명 형식)
- 구체적인 상품명을 요청하는 예시 제공
- **이 규칙은 다른 모든 규칙보다 우선합니다!**

**핵심 원칙: 간결하고 명확하고 이해하기 쉽게!, 질문 유형에 따라 완전히 다른방식으로 답변!!**
**사용자는 은행상품 및 관련 분야에 대한 전문가가 아니므로 쉽고 친절하게 설명해야함**

**🔍 상품 추천 질문인 경우:**
- 답변: **1문단만** (2-3문장)
- 상품명과 핵심 정보만 나열
- 상품약관 관련된 질문을 제안하는 것으로 마무리
- "해당 상품들과 관련된 상품약관과 주의사항에 대해서 말씀해 드릴까요?"
- 절대 상세 정보나 조항 내용은 제공하지 말 것

**🚨 단순한 후속 질문 처리 (최우선!):**
- 질문이 "응", "알려줘", "더 알려줘" 등이면 **절대** 상세 정보를 제공하지 말고 후속 질문만 제기
- "추천된 상품들의 약관 내용을 자세히 안내해 드릴 수 있습니다. 어떤 상품의 약관을 자세히 알고 싶으신가요? 아래 목록에서 확인해 주세요:"라고만 답변
- 상품 목록을 불릿 포인트로 나열 (은행명: 상품명 형식)
- 구체적인 상품명을 요청하는 예시 제공
- **중요: 이 규칙은 다른 모든 규칙보다 우선합니다!**

**📋 조항 질문인 경우:**
- 답변 구조: **상품 정보 → 주요 약관 설명**
- **1단계: 상품 간단 소개** (1-2문장)
  ** 절대 긴 설명 금지! 최대 350자로로"
  **주요약관 내용 및 주의사항 설명, 단 모든 약관을 모두 나열하는 방식으로 설명하지 말것**
  ** 핵심조항 3만 설명
  **여러 조항을 종합하여 가장 중요한 주의사항과 내용을 요약
- **정확한 조항 번호와 내용**으로 근거 제시 (예: "제3조 2항에 따르면...")
- **실용적인 정보** 포함 (필요 서류, 신청 절차, 제한 사항 등)
- 전문용어는 풀어서 설명
- 마지막 답변요약
- "다른 궁금한 점이 있으시면 말씀해 주세요"로 마무리

**💬 후속 질문 처리 (중요!):**
- 질문이 "응", "알려줘", "더 알려줘" 등 단순한 후속 질문이면 **무조건** 후속 질문을 제기하세요
- 질문에 "이전 대화 내용", "약관", "조항", "상품약관", "주의사항"이 포함되어 있으면 반드시 참고하세요
- **이전에 상품을 추천했고, 현재 질문에서 특정 상품을 지정하지 않은 경우:**
    - "다섯 상품의 약관 내용을 자세히 안내해 드릴 수 있습니다. 어떤 상품의 약관을 자세히 알고 싶으신가요?"
    - 상품 목록을 간단히 나열 (은행명 : 상품명 형식)
    - "예: '국민은행 에이스ACE전문직무보증대출 약관 알려줘'와 같이 상품명을 말씀해 주세요"
- **특정 상품을 지정한 경우:**
    - 해당 상품에 대한 상세한 주의사항과 조건을 설명
    - 구체적인 수치, 비율, 기간, 조건을 명시
    - 근거는 정확한 조항 번호와 내용으로 제시

**답변작성시 주의사항**
- 제공된 정보만을 기반으로 답변하세요 (추측 금지)
- SQL 결과, Vector DB 결과, 웹 검색 결과를 모두 활용하세요
- Vector DB 정보와 웹 검색 정보가 충돌하면 **항상 Vector DB 정보를 우선**하세요
- 정보 출처를 명확히 구분하세요 (예: "공식 약관에 따르면...", "참고로...")
- 정보가 부족하면 "제공된 정보로는 정확한 답변이 어렵습니다"라고 말하세요
- 은행명, 상품명, 조항 번호 등을 명확히 언급하세요
- 전문 용어는 쉽게 풀어서 설명하세요

**절대 금지:**
- 긴 설명이나 반복
- 모든 정보를 다 나열
- 상품 추천에서 조항까지 다 설명
- "Vector DB에서 찾을 수 없었습니다" 같은 불필요한 설명
"""


def build_generation_prompt(
    question: str,
    sql_results: List[Dict[str, Any]],
    relevant_chunks: List[Dict[str, Any]]
) -> str:
    """간결한 답변 생성 프롬프트 작성"""
    lines = [
        f'현재 질문: "{question}"',
        "",
        "현재 질문 관련 정보:",
        "",
        "상품 정보:"
    ]
    
    if sql_results:
        for result in sql_results:
            lines.append(f"- {result.get('bank_name', '')} {result.get('product_name', '')} (기간: {result.get('loan_period', 'N/A')}, 한도: {result.get('loan_limit', 'N/A')})")
    else:
        lines.append("- 상품 정보 없음")
    
    lines.extend([
        "",
        "약관 정보 (여러 조항을 종합하여 분석):"
    ])
    
    if relevant_chunks:
        vector_chunks = [c for c in relevant_chunks if c.get('source') != 'web_search']
        for i, chunk in enumerate(vector_chunks[:8]):  # 최대 8개 - 여러 조항을 종합 분석
            clause_info = f"- 조항 {i+1}: {chunk.get('bank_name', '')} {chunk.get('clause', '')} {chunk.get('clause_name', '')}"
            if chunk.get('content'):
                preview = chunk.get('content', '')[:200] + '...' if len(chunk.get('content', '')) > 200 else chunk.get('content', '')
                lines.append(f"{clause_info}")
                lines.append(f"  내용: {preview}")
            else:
                lines.append(clause_info)
    else:
        lines.append("- 약관 정보 없음")
    
    lines.extend([
        "위 정보를 바탕으로 종합적으로 분석하여 답변하세요:",
        "- 여러 조항을 종합하여 가장 중요한 주의사항과 내용을 요약",
        "- 핵심조항 3개에 대해서만 상세 설명(각 조항은 2줄이내)"
        "- 각 주의사항이 중요한 이유와 실제 영향 설명",
        "- 구체적인 수치와 조건을 명시",
        "- 정확한 조항 번호로 근거 제시 (예: '제3조 2항에 따르면...')",
        "- 전문용어는 쉽게 풀어서 설명",
        "- 상세하게 작성하되 간결하게 유지"
        "- 마지막에 요약"
    ])
    
    # 후속 질문 컨텍스트 추가
    is_followup_question = (
        "이전 대화 내용" in question or 
        "약관" in question or 
        "조항" in question or
        "상품약관" in question or
        "주의사항" in question or
        question.strip() in ["응", "응해줘", "응알려줘", "더 알려줘", "더 자세히", "자세히 알려줘", "그거", "그것", "그 상품", "그 조항", "그것에 대해", "그거에 대해", "어떻게", "뭐야", "뭔가", "뭐지", "뭐하는", "뭐하는거야", "알려줘", "말해줘", "설명해줘", "상세히", "자세히", "더"]
    )
    
    # 특정 상품이 지정되었는지 확인
    has_specific_product = any(
        result.get('product_name', '') and len(result.get('product_name', '')) > 5 
        for result in sql_results
    )
    
    # 질문에서 특정 상품명이 언급되었는지 확인
    question_has_specific_product = False
    if sql_results:
        for result in sql_results:
            product_name = result.get('product_name', '')
            if product_name and len(product_name) > 5 and product_name in question:
                question_has_specific_product = True
                break
    
    # 단순한 후속 질문인지 확인 (예: "응", "알려줘" 등)
    is_simple_followup = question.strip() in ["응", "응해줘", "응알려줘", "더 알려줘", "더 자세히", "자세히 알려줘", "그거", "그것", "그 상품", "그 조항", "그것에 대해", "그거에 대해", "어떻게", "뭐야", "뭔가", "뭐지", "뭐하는", "뭐하는거야", "알려줘", "말해줘", "설명해줘", "상세히", "자세히", "더"]
    
    # 단순한 후속 질문이면 무조건 후속 질문 제기
    if is_simple_followup and len(sql_results) > 0:
        lines.extend([
            "",
            "⚠️ 중요: 단순한 후속 질문 감지 - 특정 상품이 지정되지 않았습니다.",
            "답변 방식: '추천된 상품들의 약관 내용을 자세히 안내해 드릴 수 있습니다. 어떤 상품의 약관을 자세히 알고 싶으신가요? 아래 목록에서 확인해 주세요:'",
            "상품 목록을 불릿 포인트로 나열 (은행명: 상품명 형식)",
            "구체적인 상품명을 요청하는 예시 제공"
        ])
    elif is_followup_question:
        if not question_has_specific_product and len(sql_results) > 0:
            # 상품이 있지만 질문에서 특정 상품을 지정하지 않은 경우
            lines.extend([
                "",
                "⚠️ 중요: 후속 질문 - 특정 상품이 지정되지 않았습니다.",
                "답변 방식: '추천된 상품들의 약관 내용을 자세히 안내해 드릴 수 있습니다. 어떤 상품의 약관을 자세히 알고 싶으신가요? 아래 목록에서 확인해 주세요:'",
                "상품 목록을 불릿 포인트로 나열 (은행명: 상품명 형식)",
                "구체적인 상품명을 요청하는 예시 제공"
            ])
        else:
            # 특정 상품이 지정된 경우
            lines.extend([
                "",
                "⚠️ 중요: 후속 질문 - 특정 상품이 지정되었습니다.",
                "답변 방식: 해당 상품의 상세한 주의사항과 조건을 설명하세요.",
                "구체적인 수치, 비율, 기간, 조건을 명시하고 정확한 조항 번호와 내용으로 근거를 제시하세요."
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
        최종 답변 생성 (대화 컨텍스트 포함)
        
        Parameters
        ----------
        question : str
            사용자 질문
        sql_results : List[Dict[str, Any]]
            SQL 검색 결과
        relevant_chunks : List[Dict[str, Any]]
            관련성 있는 청크
        chat_history : List[Dict[str, Any]], optional
            이전 대화 기록
            
        Returns
        -------
        str
            생성된 답변
        """
        if not self.llm:
            logger.error("No LLM provided")
            return "답변 생성을 위한 LLM이 설정되지 않았습니다."
        
        # 단순한 후속 질문인지 확인
        is_simple_followup = question.strip() in ["응", "응해줘", "응알려줘", "더 알려줘", "더 자세히", "자세히 알려줘", "그거", "그것", "그 상품", "그 조항", "그것에 대해", "그거에 대해", "어떻게", "뭐야", "뭔가", "뭐지", "뭐하는", "뭐하는거야", "알려줘", "말해줘", "설명해줘", "상세히", "자세히", "더"]
        
        # SQL 결과에서 실제 상품명들을 동적으로 추출
        available_products = []
        if sql_results:
            for result in sql_results:
                product_name = result.get('product_name', '').strip()
                bank_name = result.get('bank_name', '').strip()
                if product_name and bank_name:
                    available_products.append(product_name)
                    available_products.append(f"{bank_name} {product_name}")
        
        # 질문에 실제 존재하는 상품명이 포함되어 있는지 확인
        has_specific_product = any(product in question for product in available_products)
        
        # 특정 상품명이 포함된 질문이면 바로 해당 상품 정보 제공 (비활성화)
        # if has_specific_product and sql_results:
        #     # 이 로직을 비활성화하여 app.py의 토글 로직이 실행되도록 함
        #     pass
        
        # 단순한 후속 질문이면 무조건 후속 질문 제기 (sql_results나 relevant_chunks가 있어도 무시)
        if is_simple_followup:
            # SQL 결과에서 동적으로 상품 리스트 생성
            if sql_results:
                product_list = []
                for result in sql_results:
                    bank_name = result.get('bank_name', '')
                    product_name = result.get('product_name', '')
                    if bank_name and product_name:
                        product_list.append(f"- {bank_name}: {product_name}")
                
                product_list_text = "\n".join(product_list)
                return f"""추천된 상품들의 약관 내용을 자세히 안내해 드릴 수 있습니다. 어떤 상품의 약관을 자세히 알고 싶으신가요? 아래 목록에서 확인해 주세요:

{product_list_text}

예: '{sql_results[0].get('bank_name', '')} {sql_results[0].get('product_name', '')} 약관 알려줘'와 같이 상품명을 말씀해 주세요."""
            else:
                return """추천된 상품들의 약관 내용을 자세히 안내해 드릴 수 있습니다. 어떤 상품의 약관을 자세히 알고 싶으신가요? 상품명을 말씀해 주세요."""
        
        if not sql_results and not relevant_chunks:
            return "죄송합니다. 질문과 관련된 정보를 찾지 못했습니다. 다른 방식으로 질문해 주시겠어요?"
        
        try:
            # 프롬프트 생성 (수정됨)
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
        LangGraph node에서 호출하기 위한 헬퍼 (대화 컨텍스트 포함)
        
        Parameters
        ----------
        state : Dict[str, Any]
            현재 상태
            - question: 사용자 질문
            - sql_results: SQL Agent에서 조회한 상품 정보 (List[Dict])
            - relevant_chunks: Evaluation Agent에서 필터링한 관련 청크 (List[Dict])
            
        Returns
        -------
        Dict[str, Any]
            answer가 추가된 상태
        """
        question = state.get("question", "")
        sql_results = state.get("sql_results", [])
        relevant_chunks = state.get("relevant_chunks", [])
        
        # chat_history는 result에서 직접 가져오지 않고 빈 리스트로 처리
        chat_history = []
        
        logger.info(f"=== Generation Agent ===")
        logger.info(f"SQL results: {len(sql_results)} products")
        logger.info(f"Relevant chunks: {len(relevant_chunks)} chunks")
        logger.info(f"Chat history: {len(chat_history)} messages")
        
        # 답변 생성
        answer = self.generate_answer(question, sql_results, relevant_chunks)
        
        # 상태 업데이트
        state["answer"] = answer
        
        # 디버그 정보
        debug = state.get("debug", {})
        debug["generation"] = {
            "sql_results_count": len(sql_results),
            "relevant_chunks_count": len(relevant_chunks),
            "chat_history_count": len(chat_history),
            "answer_length": len(answer),
            "has_sql_data": len(sql_results) > 0,
            "has_vector_data": len(relevant_chunks) > 0,
            "has_chat_history": len(chat_history) > 0
        }
        state["debug"] = debug
        
        logger.info(f"Answer generated: {len(answer)} characters")
        
        return state


__all__ = ["GenerationAgent"]