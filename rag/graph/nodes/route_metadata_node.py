"""메타데이터 라우팅 노드"""

from typing import Dict, Any
from rag.core.logger import get_logger


logger = get_logger(__name__)


def route_metadata(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    메타데이터 라우팅 노드
    
    질의에서 은행명과 상품종류를 자동으로 추출합니다.
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with extracted metadata
    """
    query = state["query"]
    
    # Extract bank name (if not already provided)
    bank_name = state.get("bank_name")
    if not bank_name:
        if "우리은행" in query or "우리" in query:
            bank_name = "우리은행"
        elif "국민은행" in query or "국민" in query or "KB" in query:
            bank_name = "국민은행"
    
    # Extract product type (if not already provided)
    product_type = state.get("product_type")
    if not product_type:
        if "대출" in query:
            product_type = "대출"
        elif "예금" in query or "적금" in query or "예적금" in query:
            product_type = "예적금"
    
    logger.info(f"Routed metadata - bank: {bank_name}, product: {product_type}")
    
    return {
        **state,
        "bank_name": bank_name,
        "product_type": product_type
    }
