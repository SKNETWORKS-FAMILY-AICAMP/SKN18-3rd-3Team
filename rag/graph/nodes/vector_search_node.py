"""벡터 검색 노드"""

from typing import Dict, Any
from rag.core.logger import get_logger
from rag.retriever import BankRetriever


logger = get_logger(__name__)


def create_vector_search_node(retriever: BankRetriever):
    """
    벡터 검색 노드 생성 함수
    
    Args:
        retriever: BankRetriever instance
    
    Returns:
        vector_search function
    """
    def vector_search(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        벡터 검색 노드
        
        메타데이터 필터를 사용하여 관련 문서를 검색합니다.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with retrieved documents
        """
        query = state["query"]
        top_k = state.get("top_k", 8)
        bank_name = state.get("bank_name")
        product_type = state.get("product_type")
        
        logger.info(f"Searching with top_k={top_k}, bank={bank_name}, product={product_type}")
        
        try:
            documents = retriever.retrieve(
                query=query,
                top_k=top_k,
                bank_name=bank_name,
                product_type=product_type
            )
            
            logger.info(f"Found {len(documents)} documents")
            
            return {
                **state,
                "documents": documents
            }
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return {
                **state,
                "documents": [],
                "error": str(e)
            }
    
    return vector_search
