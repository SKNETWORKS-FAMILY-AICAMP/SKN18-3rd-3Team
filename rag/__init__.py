"""
rag (Retrieval-Augmented Generation) System for Bank Q&A
우리은행 + 국민은행 대출 및 예적금 Q&A 서비스

Multi-Agent RAG 시스템:
- Classify Agent: 질문 의도 분류 (gpt-5-nano)
- SQL Agent: RDB 검색 (loan_info, bank_interest_rate)
- Vector Search: pgvector 유사도 검색
- Evaluation Agent: 청크 관련성 평가 (gpt-5-mini)
- Generation Agent: 최종 답변 생성 (gpt-5-nano)
"""

__version__ = "0.1.0"
__all__ = []
