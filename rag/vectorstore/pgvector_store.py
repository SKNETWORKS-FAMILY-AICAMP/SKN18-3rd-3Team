"""PgVector store implementation"""

from typing import List, Dict, Any, Optional, Tuple
from langchain.schema import Document
from langchain_core.vectorstores import VectorStore

from rag.db.connection import DatabaseConnection
from rag.embeddings.provider import EmbeddingProvider
from rag.vectorstore.types import SearchResult
from rag.vectorstore.sql import get_upsert_query, get_search_query
from rag.core.logger import get_logger


logger = get_logger(__name__)


class PgVectorStore(VectorStore):
    """
    Vector store implementation using PostgreSQL with pgvector extension.
    
    This class provides methods to add documents and search for similar documents
    using vector similarity.
    """
    
    def __init__(
        self,
        connection: DatabaseConnection,
        embeddings: EmbeddingProvider
    ):
        """
        Initialize PgVector store.
        
        Args:
            connection: Database connection manager
            embeddings: Embedding provider
        """
        self.connection = connection
        self.embeddings = embeddings
        logger.info("Initialized PgVectorStore")
    
    def add_documents(
        self,
        documents: List[Document],
        batch_size: int = 100
    ) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of LangChain Document objects
            batch_size: Number of documents to process in each batch
        
        Returns:
            List of document IDs
        """
        doc_ids = []
        total = len(documents)
        
        logger.info(f"Adding {total} documents to vector store")
        
        for i in range(0, total, batch_size):
            batch = documents[i:i+batch_size]
            batch_texts = [doc.page_content for doc in batch]
            
            # Embed batch
            try:
                embeddings = self.embeddings.embed_texts(batch_texts)
            except Exception as e:
                logger.error(f"Failed to embed batch {i//batch_size + 1}: {e}")
                continue
            
            # Insert batch
            upsert_sql = get_upsert_query()
            
            for doc, embedding in zip(batch, embeddings):
                metadata = doc.metadata
                doc_id = f"{metadata.get('doc_id', '')}_{metadata.get('chunk_id', '')}"
                
                try:
                    with self.connection.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(upsert_sql, (
                                doc_id,
                                metadata.get("chunk_id", ""),
                                embedding,
                                doc.page_content,
                                metadata.get("은행명", ""),
                                metadata.get("문서명", ""),
                                metadata.get("상품종류", ""),
                                metadata.get("상품이름", ""),
                                metadata.get("조항", ""),
                                metadata.get("조항이름", "")
                            ))
                            conn.commit()
                            doc_ids.append(doc_id)
                except Exception as e:
                    logger.error(f"Failed to insert document {doc_id}: {e}")
                    continue
            
            logger.info(f"Processed batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")
        
        logger.info(f"Successfully added {len(doc_ids)} documents")
        return doc_ids

    
    def similarity_search_with_score(
        self,
        query: str,
        k: int = 8,
        filter: Optional[Dict[str, str]] = None
    ) -> List[Tuple[Document, float]]:
        """
        Search for similar documents.
        
        Args:
            query: Query text
            k: Number of results to return
            filter: Optional filters (bank_name, product_type)
        
        Returns:
            List of (Document, score) tuples
        """
        logger.debug(f"Searching for similar documents: {query[:100]}...")
        
        # Embed query
        try:
            query_embedding = self.embeddings.embed_query(query)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise
        
        # Build search query
        search_sql = get_search_query(filter)
        
        # Prepare parameters
        params = [query_embedding]
        if filter:
            if "bank_name" in filter:
                params.append(filter["bank_name"])
            if "product_type" in filter:
                params.append(filter["product_type"])
        params.extend([query_embedding, k])
        
        # Execute search
        try:
            with self.connection.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(search_sql, params)
                    results = cur.fetchall()
                    
                    documents = []
                    for row in results:
                        doc = Document(
                            page_content=row[2],
                            metadata={
                                "doc_id": row[0],
                                "chunk_id": row[1],
                                "은행명": row[3],
                                "문서명": row[4],
                                "상품종류": row[5],
                                "상품이름": row[6],
                                "조항": row[7],
                                "조항이름": row[8]
                            }
                        )
                        score = float(row[9])
                        documents.append((doc, score))
                    
                    logger.info(f"Found {len(documents)} similar documents")
                    return documents
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            raise
    
    def similarity_search(
        self,
        query: str,
        k: int = 8,
        filter: Optional[Dict[str, str]] = None
    ) -> List[Document]:
        """
        Search for similar documents (without scores).
        
        Args:
            query: Query text
            k: Number of results to return
            filter: Optional filters
        
        Returns:
            List of Document objects
        """
        results = self.similarity_search_with_score(query, k, filter)
        return [doc for doc, _ in results]
    
    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any
    ) -> List[str]:
        """
        Add texts to the vector store (required by VectorStore).
        
        Args:
            texts: List of text strings
            metadatas: Optional list of metadata dicts
            **kwargs: Additional arguments
        
        Returns:
            List of document IDs
        """
        # Convert texts to Documents
        documents = []
        for i, text in enumerate(texts):
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            doc = Document(page_content=text, metadata=metadata)
            documents.append(doc)
        
        return self.add_documents(documents)
    
    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: EmbeddingProvider,
        metadatas: Optional[List[dict]] = None,
        connection: Optional[DatabaseConnection] = None,
        **kwargs: Any
    ) -> "PgVectorStore":
        """
        Create a PgVectorStore from texts (required by VectorStore).
        
        Args:
            texts: List of text strings
            embedding: Embedding provider
            metadatas: Optional metadata
            connection: Database connection
            **kwargs: Additional arguments
        
        Returns:
            PgVectorStore instance
        """
        if connection is None:
            raise ValueError("connection parameter is required")
        
        store = cls(connection, embedding)
        store.add_texts(texts, metadatas)
        return store
    
    @classmethod
    def from_documents(
        cls,
        documents: List[Document],
        embedding: EmbeddingProvider,
        connection: Optional[DatabaseConnection] = None,
        **kwargs: Any
    ) -> "PgVectorStore":
        """
        Create a PgVectorStore from documents (required by VectorStore).
        
        Args:
            documents: List of documents to add
            embedding: Embedding provider
            connection: Database connection
            **kwargs: Additional arguments
        
        Returns:
            PgVectorStore instance
        """
        if connection is None:
            raise ValueError("connection parameter is required")
        
        store = cls(connection, embedding)
        store.add_documents(documents)
        return store
