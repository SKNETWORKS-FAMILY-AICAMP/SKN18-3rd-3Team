"""응답 포맷팅 노드"""

from typing import Dict, Any
from rag.core.logger import get_logger


logger = get_logger(__name__)


def format_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    응답 포맷팅 노드
    
    출처 정보를 추출하고 포맷팅합니다.
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with formatted sources
    """
    documents = state.get("documents", [])
    
    sources = []
    for i, doc in enumerate(documents):
        source = {
            "index": i + 1,
            "bank_name": doc.metadata.get("은행명", ""),
            "product_name": doc.metadata.get("상품이름", ""),
            "clause": doc.metadata.get("조항", ""),
            "clause_name": doc.metadata.get("조항이름", ""),
            "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
        }
        sources.append(source)
    
    logger.info(f"Formatted {len(sources)} sources")
    
    return {
        **state,
        "sources": sources
    }
