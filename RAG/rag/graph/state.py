"""LangGraph state definition"""

from typing import TypedDict, List, Optional, Dict, Any
from langchain.schema import Document


class GraphState(TypedDict):
    """
    LangGraph 파이프라인 상태
    
    이 상태는 파이프라인의 각 노드를 통과하면서 업데이트됩니다.
    """
    # Input fields
    query: str
    top_k: int
    
    # Extracted metadata
    bank_name: Optional[str]
    product_type: Optional[str]
    
    # Search results
    documents: List[Document]
    
    # Generation results
    answer: str
    sources: List[Dict[str, Any]]
    
    # Control flow
    retry_count: int
    error: Optional[str]
