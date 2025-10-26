"""RAG Engine - Main orchestrator for RAG pipeline"""

import os
import re
from typing import Dict, Any, Optional, List
from jinja2 import Environment, FileSystemLoader

from rag.core.config import get_config
from rag.core.logger import get_logger
from rag.db.connection import DatabaseConnection
from rag.db.repo import DocumentRepository
from rag.embeddings.openai_embed import OpenAIEmbeddings
from rag.llm.get_llm import get_llm_model
from rag.vectorstore.pgvector_store import PgVectorStore
from rag.retriever import BankRetriever
from rag.graph.build import create_rag_system


logger = get_logger(__name__)


class RAGEngine:
    """
    RAG Engine singleton that orchestrates the entire RAG pipeline.
    
    Initializes all components once and reuses them for all queries.
    """
    
    def __init__(self):
        """Initialize RAG engine with all components"""
        import time
        import sys
        start_time = time.time()
        
        print("🚀 [DEBUG] Starting RAG Engine initialization...", flush=True)
        logger.info("🚀 Initializing RAG Engine...")
        
        # Load configuration
        print("📊 [DEBUG] [1/7] Loading configuration...", flush=True)
        logger.info("📊 [1/7] Loading configuration...")
        self.config = get_config()
        print(f"✓ [DEBUG] Configuration loaded ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Configuration loaded ({time.time() - start_time:.1f}s)")
        
        # Initialize database connection
        print("🗄️ [DEBUG] [2/7] Configuring database connection...", flush=True)
        logger.info("🗄️ [2/7] Configuring database connection...")
        self.db = DatabaseConnection(db_url=self.config.DB_URL)
        print(f"✓ [DEBUG] Database configured ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Database configured ({time.time() - start_time:.1f}s)")
        
        # Initialize repository
        print("📚 [DEBUG] [3/7] Initializing repository...", flush=True)
        logger.info("📚 [3/7] Initializing repository...")
        self.repo = DocumentRepository(self.db)
        print(f"✓ [DEBUG] Repository ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Repository ready ({time.time() - start_time:.1f}s)")
        
        # Initialize embeddings
        print(f"🔤 [DEBUG] [4/7] Initializing embeddings ({self.config.EMBED_MODEL})...", flush=True)
        logger.info(f"🔤 [4/7] Initializing embeddings ({self.config.EMBED_MODEL})...")
        self.embeddings = OpenAIEmbeddings(
            model=self.config.EMBED_MODEL,
            api_key=self.config.OPENAI_API_KEY
        )
        print(f"✓ [DEBUG] Embeddings ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Embeddings ready ({time.time() - start_time:.1f}s)")
        
        # Initialize vector store
        print("🔍 [DEBUG] [5/7] Initializing vector store...", flush=True)
        logger.info("🔍 [5/7] Initializing vector store...")
        self.vectorstore = PgVectorStore(
            connection=self.db,
            embeddings=self.embeddings
        )
        print(f"✓ [DEBUG] Vector store ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Vector store ready ({time.time() - start_time:.1f}s)")
        
        # Initialize retriever
        print("📖 [DEBUG] [6/7] Initializing retriever...", flush=True)
        logger.info("📖 [6/7] Initializing retriever...")
        self.retriever = BankRetriever(vectorstore=self.vectorstore)
        print(f"✓ [DEBUG] Retriever ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Retriever ready ({time.time() - start_time:.1f}s)")
        
        # Initialize LLM
        print("🤖 [DEBUG] [7/7] Initializing LLM (gpt-5-nano)...", flush=True)
        logger.info("🤖 [7/7] Initializing LLM (gpt-5-nano)...")
        self.llm = get_llm_model()
        print(f"✓ [DEBUG] LLM ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ LLM ready ({time.time() - start_time:.1f}s)")
        
        # Initialize RAG system (Multi-Agent)
        print("🔧 [DEBUG] Building Multi-Agent RAG system...", flush=True)
        logger.info("🔧 Building Multi-Agent RAG system...")
        self.graph = create_rag_system(
            llm=self.llm,
            retriever=self.retriever,
            top_k=8,
            relevance_threshold=35.0,  # test.py와 동일한 임계값
            enable_routing=False,
            enable_langsmith=False
        )
        print("✓ [DEBUG] RAG system compiled", flush=True)
        
        total_time = time.time() - start_time
        print(f"✅ [DEBUG] RAG Engine initialization complete! (Total: {total_time:.1f}s)", flush=True)
        logger.info(f"✅ RAG Engine initialization complete! (Total: {total_time:.1f}s)")
        
        if total_time > 10:
            logger.warning(f"⚠️ Initialization took {total_time:.1f}s - this is longer than expected. Check database/API connectivity.")


    def _extract_metadata_from_query(self, query: str) -> Dict[str, Optional[str]]:
        """
        Extract bank name and product type from query.
        
        Args:
            query: User query
        
        Returns:
            Dictionary with bank_name and product_type
        """
        metadata = {
            "bank_name": None,
            "product_type": None
        }
        
        # Extract bank name
        if "우리은행" in query or "우리" in query:
            metadata["bank_name"] = "우리은행"
        elif "국민은행" in query or "국민" in query or "KB" in query:
            metadata["bank_name"] = "국민은행"
        
        # Extract product type
        if "대출" in query:
            metadata["product_type"] = "대출"
        elif "예금" in query or "적금" in query or "예적금" in query:
            metadata["product_type"] = "예적금"
        
        logger.debug(f"Extracted metadata: {metadata}")
        return metadata
    
    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        bank_name: Optional[str] = None,
        product_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a query through the Multi-Agent RAG pipeline.
        
        Args:
            question: User question
            top_k: Number of documents to retrieve (default from config)
            bank_name: Optional bank name filter
            product_type: Optional product type filter
        
        Returns:
            Dictionary with answer, sources, and metadata
        """
        logger.info(f"Processing query through Multi-Agent RAG: {question}")
        
        try:
            # Use config default if not specified
            if top_k is None:
                top_k = self.config.TOP_K
            
            # Execute Multi-Agent RAG pipeline
            logger.info("Executing Multi-Agent RAG pipeline...")
            initial_state = {
                "question": question,
                "bank_name": bank_name,
                "product_type": product_type
            }
            result = self.graph.invoke(initial_state)
            
            # Extract and format results
            formatted_result = {
                "answer": result.get("answer", ""),
                "sources": self._prepare_sources_from_result(result),
                "num_sources": len(self._prepare_sources_from_result(result)),
                "filters": {
                    "bank_name": result.get("bank_name"),
                    "product_type": result.get("product_type")
                },
                "debug": {
                    "intent": result.get("intent"),
                    "confidence": result.get("confidence", 0.0),
                    "sql_results_count": len(result.get("sql_results", [])),
                    "vector_chunks_count": result.get("vector_chunks_count", 0),
                    "relevant_chunks_count": result.get("relevant_chunks_count", 0)
                }
            }
            
            # Include error if present
            if result.get("error"):
                formatted_result["error"] = result["error"]
            
            logger.info(f"Query processed successfully with {formatted_result['num_sources']} sources")
            return formatted_result
        
        except Exception as e:
            logger.error(f"Failed to process query: {e}", exc_info=True)
            return {
                "answer": f"죄송합니다. 처리 중 오류가 발생했습니다: {str(e)}",
                "sources": [],
                "num_sources": 0,
                "error": str(e)
            }


    def _prepare_sources_from_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Prepare source information from Multi-Agent RAG result.
        
        Args:
            result: Result from Multi-Agent RAG pipeline
        
        Returns:
            List of source dictionaries
        """
        sources = []
        
        # Add SQL results as sources
        sql_results = result.get("sql_results", [])
        for i, product in enumerate(sql_results):
            source = {
                "index": i + 1,
                "source_type": "sql",
                "bank_name": product.get("bank_name", ""),
                "product_name": product.get("product_name", ""),
                "product_category": product.get("product_category", ""),
                "loan_target": product.get("loan_target", ""),
                "loan_period": product.get("loan_period", ""),
                "loan_limit": product.get("loan_limit", ""),
                "clause": "",  # SQL 결과에는 clause 없음
                "clause_name": "",  # SQL 결과에는 clause_name 없음
                "document_name": "",  # SQL 결과에는 document_name 없음
                "relevance_score": 0.0,  # SQL 결과에는 관련성 점수 없음
                "content_preview": f"상품명: {product.get('product_name', '')}, 대출기간: {product.get('loan_period', '')}, 대출한도: {product.get('loan_limit', '')}"
            }
            sources.append(source)
        
        # Add relevant vector chunks as sources
        relevant_chunks = result.get("relevant_chunks", [])
        for i, chunk in enumerate(relevant_chunks):
            source = {
                "index": len(sources) + i + 1,
                "source_type": "vector",
                "bank_name": chunk.get("bank_name", ""),
                "product_name": chunk.get("product_name", ""),
                "document_name": chunk.get("document_name", ""),
                "clause": chunk.get("clause", ""),
                "clause_name": chunk.get("clause_name", ""),
                "relevance_score": chunk.get("eval_result", {}).get("relevance_score", 0.0),
                "product_category": "",  # Vector 결과에는 product_category 없음
                "loan_target": "",  # Vector 결과에는 loan_target 없음
                "loan_period": "",  # Vector 결과에는 loan_period 없음
                "loan_limit": "",  # Vector 결과에는 loan_limit 없음
                "content_preview": chunk.get("content", "")[:200] + "..." if len(chunk.get("content", "")) > 200 else chunk.get("content", "")
            }
            sources.append(source)
        
        return sources
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check health of all components.
        
        Returns:
            Dictionary with health status
        """
        health = {
            "status": "healthy",
            "components": {}
        }
        
        # Check database
        try:
            db_healthy = self.db.health_check()
            health["components"]["database"] = "healthy" if db_healthy else "unhealthy"
        except Exception as e:
            health["components"]["database"] = f"error: {str(e)}"
            health["status"] = "unhealthy"
        
        # Check document count
        try:
            doc_count = self.repo.get_document_count()
            health["components"]["documents"] = f"{doc_count} documents indexed"
        except Exception as e:
            health["components"]["documents"] = f"error: {str(e)}"
        
        return health
