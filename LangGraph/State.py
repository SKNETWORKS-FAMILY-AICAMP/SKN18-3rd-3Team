from typing import TypedDict, List, Dict, Any
from langchain_core.documents import Document

class State(TypedDict):
    question: str

    # 질문 분석
    bank_name: str
    product_name: str
    intent: str
    clause_keywords: List[str]

    # vectordb 검색
    contents: List[str]
    documents: List[Document]
    sources: List[Dict[str, Any]]
    sql_contents: List[str]
    sql_results: List[Dict[str, Any]]

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
