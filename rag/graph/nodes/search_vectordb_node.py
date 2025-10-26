"""벡터 검색 노드"""

from typing import Dict, Any
from rag.core.logger import get_logger
from rag.vectorstore.pgvector_store import PgVectorStore


logger = get_logger(__name__)


def create_vector_search_node(vectorstore: PgVectorStore):
    """
    벡터 검색 노드 생성 함수
    
    Args:
        vectorstore: PgVectorStore instance
    
    Returns:
        vector_search function
    """
    def vector_search(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        벡터 검색 노드
        
        메타데이터 필터를 사용하여 관련 문서를 검색합니다.
        SQL 결과가 없는 경우 Classification 결과를 기반으로 검색합니다.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with retrieved documents
        """
        logger.info("=== VECTOR_SEARCH FUNCTION CALLED ===")
        
        query = state.get("query") or state.get("question") or ""
        top_k = state.get("top_k", 8)
        
        if not query:
            logger.error("No query provided in state!")
            return {
                **state,
                "documents": [],
                "used_fallback_search": False,
                "error": "No query provided"
            }
        
        logger.info(f"Vector search input: query='{query[:50]}...', top_k={top_k}")
        
        # SQL 결과 확인
        sql_results = state.get("sql_results", [])
        has_sql_results = len(sql_results) > 0
        
        # 메타데이터 필터 설정
        bank_name = state.get("bank_name")
        product_type = state.get("product_type")
        
        logger.info(f"Initial filters: bank_name='{bank_name}', product_type='{product_type}'")
        
        # SQL 결과가 없는 경우 Classification 결과 활용
        if not has_sql_results:
            logger.warning("No SQL results found. Using Classification results for Vector search.")
            
            # Classification에서 추출된 정보 활용
            if not bank_name:
                bank_name = state.get("bank_name")
            if not product_type:
                product_type = state.get("product_type")
            
            # 추가 정보 활용 (상품명, 대출종류 등)
            product_name = state.get("product_name")
            loan_type = state.get("loan_type")
            
            logger.info(f"Fallback search with Classification results:")
            logger.info(f"  - bank_name: {bank_name}")
            logger.info(f"  - product_type: {product_type}")
            logger.info(f"  - product_name: {product_name}")
            logger.info(f"  - loan_type: {loan_type}")
            
            # 쿼리 보강: 상품명이나 대출종류가 있으면 쿼리에 추가
            enhanced_query = query
            if product_name and product_name not in query:
                enhanced_query = f"{query} {product_name}"
            if loan_type and loan_type not in enhanced_query:
                enhanced_query = f"{enhanced_query} {loan_type}"
            
            if enhanced_query != query:
                logger.info(f"Enhanced query: '{query}' -> '{enhanced_query}'")
                query = enhanced_query
        else:
            logger.info(f"SQL results found ({len(sql_results)} products). Using standard Vector search.")
        
        logger.info(f"Searching with top_k={top_k}, bank={bank_name}, product={product_type}")
        
        try:
            # 필터 구성
            filters = {}
            if bank_name:
                filters["bank_name"] = bank_name
            if product_type:
                filters["product_type"] = product_type
            
            logger.info(f"Vector search filters: {filters}")
            logger.info(f"Calling vectorstore.similarity_search(query='{query[:50]}...', k={top_k}, filter={filters})")
            
            # 벡터 검색 실행
            documents = vectorstore.similarity_search(
                query=query,
                k=top_k,
                filter=filters if filters else None
            )
            
            logger.info(f"Initial search returned {len(documents)} documents")
            
            if len(documents) > 0:
                logger.info(f"Sample result: bank={documents[0].metadata.get('은행명')}, product={documents[0].metadata.get('상품이름')}, type={documents[0].metadata.get('상품종류')}")
            else:
                logger.warning(f"No documents found with filters: {filters}")
            
            # 예금/적금 관련 검색인데 결과가 없으면, 다른 타입으로도 검색
            if len(documents) == 0 and product_type in ["예금", "예적금"]:
                logger.info(f"No results for {product_type}, trying alternative product type...")
                alternative_type = "예적금" if product_type == "예금" else "예금"
                alt_filters = filters.copy()
                alt_filters["product_type"] = alternative_type
                
                documents = vectorstore.similarity_search(
                    query=query,
                    k=top_k,
                    filter=alt_filters if alt_filters else None
                )
                logger.info(f"Found {len(documents)} documents with alternative type: {alternative_type}")
            
            logger.info(f"Found {len(documents)} documents")
            
            # SQL 결과가 없었던 경우 추가 정보 기록
            if not has_sql_results and len(documents) > 0:
                logger.info(f"✓ Fallback search successful: {len(documents)} documents retrieved using Classification results")
            elif not has_sql_results and len(documents) == 0:
                logger.warning(f"✗ Fallback search failed: No documents found even with Classification results")
            
            return {
                **state,
                "documents": documents,
                "used_fallback_search": not has_sql_results
            }
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return {
                **state,
                "documents": [],
                "error": str(e),
                "used_fallback_search": not has_sql_results
            }
    
    return vector_search
