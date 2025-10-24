"""Retriever with metadata filtering"""

from typing import List, Optional, Dict
from langchain.schema import Document

from rag.vectorstore.pgvector_store import PgVectorStore
from rag.core.logger import get_logger


logger = get_logger(__name__)


class BankRetriever:
    """
    Retriever with metadata filtering for bank documents.
    
    Supports filtering by bank name and product type to ensure
    accurate retrieval of relevant documents.
    """
    
    def __init__(self, vectorstore: PgVectorStore):
        """
        Initialize retriever.
        
        Args:
            vectorstore: PgVector store instance
        """
        self.vectorstore = vectorstore
        logger.info("Initialized BankRetriever")
    
    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        bank_name: Optional[str] = None,
        product_type: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[Document]:
        """
        Retrieve relevant documents with optional filtering.
        
        Args:
            query: Query text
            top_k: Number of documents to retrieve
            bank_name: Filter by bank name (우리은행 or 국민은행)
            product_type: Filter by product type (대출 or 예적금)
            min_score: Minimum similarity score threshold
        
        Returns:
            List of relevant Document objects
        """
        logger.info(f"Retrieving documents for query: {query[:100]}...")
        logger.info(f"Filters - bank: {bank_name}, product: {product_type}, top_k: {top_k}")
        
        # Build filter dictionary
        filters = {}
        if bank_name:
            filters["bank_name"] = bank_name
        if product_type:
            filters["product_type"] = product_type
        
        # Search with filters
        try:
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=top_k,
                filter=filters if filters else None
            )
            
            # 예금/적금 관련 검색인데 결과가 없으면, 다른 타입으로도 검색
            # (우리은행="예금", 국민은행="예적금" 차이 때문)
            if len(results) == 0 and product_type in ["예금", "예적금"]:
                logger.info(f"No results for {product_type}, trying alternative product type...")
                alternative_type = "예적금" if product_type == "예금" else "예금"
                alt_filters = filters.copy()
                alt_filters["product_type"] = alternative_type
                
                results = self.vectorstore.similarity_search_with_score(
                    query=query,
                    k=top_k,
                    filter=alt_filters if alt_filters else None
                )
                logger.info(f"Found {len(results)} documents with alternative type: {alternative_type}")
            
            # Filter by minimum score
            filtered_results = [
                (doc, score) for doc, score in results
                if score >= min_score
            ]
            
            logger.info(f"Retrieved {len(filtered_results)} documents (filtered from {len(results)})")
            
            # Return documents only (without scores)
            documents = [doc for doc, _ in filtered_results]
            
            # Log document metadata for debugging
            for i, doc in enumerate(documents[:3]):  # Log first 3
                logger.debug(f"Doc {i+1}: {doc.metadata.get('은행명')} - {doc.metadata.get('상품이름')}")
            
            return documents
        
        except Exception as e:
            logger.error(f"Failed to retrieve documents: {e}")
            raise
    
    def retrieve_with_scores(
        self,
        query: str,
        top_k: int = 8,
        bank_name: Optional[str] = None,
        product_type: Optional[str] = None
    ) -> List[tuple]:
        """
        Retrieve documents with similarity scores.
        
        Args:
            query: Query text
            top_k: Number of documents to retrieve
            bank_name: Filter by bank name
            product_type: Filter by product type
        
        Returns:
            List of (Document, score) tuples
        """
        filters = {}
        if bank_name:
            filters["bank_name"] = bank_name
        if product_type:
            filters["product_type"] = product_type
        
        try:
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=top_k,
                filter=filters if filters else None
            )
            
            logger.info(f"Retrieved {len(results)} documents with scores")
            return results
        
        except Exception as e:
            logger.error(f"Failed to retrieve documents with scores: {e}")
            raise
