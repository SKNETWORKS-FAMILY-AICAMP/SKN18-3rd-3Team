from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.documents import Document

class State(TypedDict, total=False):
    # 입력
    question: str

    # 질문 분석(LLM/정규화 결과)
    intent: str                              # rate_fee_lookup | clause_lookup | compare | definition | other
    clause_keywords: List[str]               # ["rate","fee","early_close","preferential","eligibility"]
    bank_name: Optional[str]
    product_name: Optional[str]
    product_type: Optional[str]              # "예금" | "적금" | "대출" | None
    loan_type: Optional[str]                 # (product_type=="대출"일 때) 지정된 7종 또는 None
    loan_target: Optional[str]               # (product_type=="대출"일 때) 지정된 대상 또는 None
    applicability_hint: Optional[bool]       # 선택: 적용 가능성 힌트
    raw_keywords: List[str]                  # 모델이 뽑은 원시 키워드
    confidence: float                        # 0.0~1.0
    reasoning: str                           # 간단 근거

    # vectordb 검색
    contents: List[str]
    documents: List[Document]
    sources: List[Dict[str, Any]]
    sql_contents: List[str]
    sql_results: List[Dict[str, Any]]
    vector_contents: List[str]
    vector_sources: List[Dict[str, Any]]
    
    # build.py용 추가 필드
    vector_chunks: List[Dict[str, Any]]      # Vector DB 조회된 청크 리스트
    vector_chunks_count: int                 # 조회된 청크 개수
    relevant_chunks: List[Dict[str, Any]]    # 관련성 있는 청크 리스트
    relevant_chunks_count: int               # 관련 청크 개수
    answer: str                              # 생성된 최종 답변
    used_fallback_search: bool               # SQL 결과 없을 때 Classification 기반 검색 사용 여부

    debug: Dict[str, Any]

    # vectordb 평가
    eval_results: str
    eval_score: float
    eval_reasoning: str

    # 연관 없는 질문 재작성
    followup_question: str
    generation_strategy: str

    # 최종 답변
    final_answer: str
    formatted_answer: str
