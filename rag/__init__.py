"""
rag (Retrieval-Augmented Generation) System for Bank Q&A
우리은행 + 국민은행 대출 및 예적금 Q&A 서비스
"""

from .retriever import BankRetriever

try:
    from .engine import RAGEngine  # pragma: no cover
except ModuleNotFoundError:
    RAGEngine = None  # type: ignore

__version__ = "0.1.0"
__all__ = ["RAGEngine", "BankRetriever"]
