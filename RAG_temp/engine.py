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
from rag.llm.openai_chat import OpenAIChatModel
from rag.vectorstore.pgvector_store import PgVectorStore
from rag.retriever import BankRetriever
from rag.graph.build import build_rag_graph


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
        print("📊 [DEBUG] [1/8] Loading configuration...", flush=True)
        logger.info("📊 [1/8] Loading configuration...")
        self.config = get_config()
        print(f"✓ [DEBUG] Configuration loaded ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Configuration loaded ({time.time() - start_time:.1f}s)")
        
        # Initialize database connection
        print("🗄️ [DEBUG] [2/8] Configuring database connection...", flush=True)
        logger.info("🗄️ [2/8] Configuring database connection...")
        self.db = DatabaseConnection(self.config.DB_URL)
        print(f"✓ [DEBUG] Database configured ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Database configured ({time.time() - start_time:.1f}s)")
        
        # Initialize repository
        print("📚 [DEBUG] [3/8] Initializing repository...", flush=True)
        logger.info("📚 [3/8] Initializing repository...")
        self.repo = DocumentRepository(self.db)
        print(f"✓ [DEBUG] Repository ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Repository ready ({time.time() - start_time:.1f}s)")
        
        # Initialize embeddings
        print(f"🔤 [DEBUG] [4/8] Initializing embeddings ({self.config.EMBED_MODEL})...", flush=True)
        logger.info(f"🔤 [4/8] Initializing embeddings ({self.config.EMBED_MODEL})...")
        self.embeddings = OpenAIEmbeddings(
            model=self.config.EMBED_MODEL,
            api_key=self.config.OPENAI_API_KEY,
            timeout=self.config.OPENAI_TIMEOUT
        )
        print(f"✓ [DEBUG] Embeddings ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Embeddings ready ({time.time() - start_time:.1f}s)")
        
        # Initialize vector store
        print("🔍 [DEBUG] [5/8] Initializing vector store...", flush=True)
        logger.info("🔍 [5/8] Initializing vector store...")
        self.vectorstore = PgVectorStore(
            connection=self.db,
            embeddings=self.embeddings
        )
        print(f"✓ [DEBUG] Vector store ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Vector store ready ({time.time() - start_time:.1f}s)")
        
        # Initialize retriever
        print("📖 [DEBUG] [6/8] Initializing retriever...", flush=True)
        logger.info("📖 [6/8] Initializing retriever...")
        self.retriever = BankRetriever(self.vectorstore)
        print(f"✓ [DEBUG] Retriever ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ Retriever ready ({time.time() - start_time:.1f}s)")
        
        # Initialize LLM
        print(f"🤖 [DEBUG] [7/8] Initializing LLM ({self.config.LLM_MODEL})...", flush=True)
        logger.info(f"🤖 [7/8] Initializing LLM ({self.config.LLM_MODEL})...")
        # gpt-5-nano는 temperature=1만 지원하므로 기본값 사용
        self.llm = OpenAIChatModel(
            model=self.config.LLM_MODEL,
            api_key=self.config.OPENAI_API_KEY,
            timeout=self.config.OPENAI_TIMEOUT,
            temperature=1.0  # gpt-5-nano는 1.0만 지원
        )
        print(f"✓ [DEBUG] LLM ready ({time.time() - start_time:.1f}s)", flush=True)
        logger.info(f"✓ LLM ready ({time.time() - start_time:.1f}s)")
        
        # Initialize Jinja2 environment for prompts
        print("📝 [DEBUG] [8/8] Loading prompt templates and building graph...", flush=True)
        logger.info("📝 [8/8] Loading prompt templates and building graph...")
        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        print("✓ [DEBUG] Jinja2 templates loaded", flush=True)
        
        # Initialize LangGraph pipeline
        print("🔧 [DEBUG] Building LangGraph pipeline...", flush=True)
        self.graph = build_rag_graph(
            retriever=self.retriever,
            llm=self.llm,
            jinja_env=self.jinja_env
        )
        print("✓ [DEBUG] Graph compiled", flush=True)
        
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
        Process a query through the LangGraph RAG pipeline.
        
        Args:
            question: User question
            top_k: Number of documents to retrieve (default from config)
            bank_name: Optional bank name filter
            product_type: Optional product type filter
        
        Returns:
            Dictionary with answer, sources, and metadata
        """
        logger.info(f"Processing query through LangGraph: {question}")
        
        try:
            # Use config default if not specified
            if top_k is None:
                top_k = self.config.TOP_K
            
            # Create initial state
            initial_state = {
                "query": question,
                "top_k": top_k,
                "bank_name": bank_name,
                "product_type": product_type,
                "documents": [],
                "answer": "",
                "sources": [],
                "retry_count": 0,
                "error": None
            }
            
            # Execute LangGraph pipeline
            logger.info("Executing LangGraph pipeline...")
            final_state = self.graph.invoke(initial_state)
            
            # Extract results from final state
            result = {
                "answer": final_state.get("answer", ""),
                "sources": final_state.get("sources", []),
                "num_sources": len(final_state.get("sources", [])),
                "filters": {
                    "bank_name": final_state.get("bank_name"),
                    "product_type": final_state.get("product_type")
                }
            }
            
            # Include error if present
            if final_state.get("error"):
                result["error"] = final_state["error"]
            
            logger.info(f"Query processed successfully with {result['num_sources']} sources")
            return result
        
        except Exception as e:
            logger.error(f"Failed to process query: {e}", exc_info=True)
            return {
                "answer": f"죄송합니다. 처리 중 오류가 발생했습니다: {str(e)}",
                "sources": [],
                "num_sources": 0,
                "error": str(e)
            }


    def _generate_answer(self, query: str, documents: List) -> str:
        """
        Generate answer using LLM with retrieved documents.
        
        Args:
            query: User query
            documents: Retrieved documents
        
        Returns:
            Generated answer
        """
        try:
            # Load prompt template
            template = self.jinja_env.get_template("answer.j2")
            
            # Render prompt
            prompt = template.render(
                query=query,
                documents=documents
            )
            
            # Generate answer
            system_prompt = "당신은 은행 상품 전문가입니다. 제공된 문서를 기반으로 정확하게 답변하세요."
            answer = self.llm.generate(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=0.7
            )
            
            return answer
        
        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            return "죄송합니다. 답변 생성 중 오류가 발생했습니다."
    
    def _prepare_sources(self, documents: List) -> List[Dict[str, Any]]:
        """
        Prepare source information from documents.
        
        Args:
            documents: Retrieved documents
        
        Returns:
            List of source dictionaries
        """
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
