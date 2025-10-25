"""Document repository for database operations"""

from typing import List, Dict, Any, Optional
import json

from rag.db.connection import DatabaseConnection
from rag.core.logger import get_logger


logger = get_logger(__name__)


class DocumentRepository:
    """Repository for document metadata CRUD operations"""
    
    def __init__(self, connection: DatabaseConnection):
        """
        Initialize repository.
        
        Args:
            connection: Database connection manager
        """
        self.connection = connection
    
    def create_tables(self) -> None:
        """Create documents table and indexes if they don't exist"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            doc_id VARCHAR(255) UNIQUE NOT NULL,
            chunk_id VARCHAR(255) NOT NULL,
            embedding vector(3072),
            content TEXT NOT NULL,
            bank_name VARCHAR(100) NOT NULL,
            product_type VARCHAR(50) NOT NULL,
            product_name VARCHAR(255),
            clause VARCHAR(255),
            clause_name VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        create_indexes_sql = [
            "CREATE INDEX IF NOT EXISTS documents_bank_name_idx ON documents(bank_name);",
            "CREATE INDEX IF NOT EXISTS documents_product_type_idx ON documents(product_type);",
            "CREATE INDEX IF NOT EXISTS documents_doc_id_idx ON documents(doc_id);",
            "CREATE INDEX IF NOT EXISTS documents_chunk_id_idx ON documents(chunk_id);"
        ]
        
        try:
            with self.connection.get_connection() as conn:
                with conn.cursor() as cur:
                    # Create table
                    cur.execute(create_table_sql)
                    logger.info("Documents table created/verified")
                    
                    # Create indexes
                    for idx_sql in create_indexes_sql:
                        cur.execute(idx_sql)
                    logger.info("Indexes created/verified")
                    
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    
    def upsert_document(
        self,
        doc_id: str,
        chunk_id: str,
        embedding: List[float],
        content: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Insert or update a document.
        
        Args:
            doc_id: Unique document identifier
            chunk_id: Chunk identifier
            embedding: Document embedding vector
            content: Document text content
            metadata: Document metadata (bank_name, product_type, etc.)
        """
        upsert_sql = """
        INSERT INTO documents (
            doc_id, chunk_id, embedding, content,
            bank_name, product_type, product_name, clause, clause_name
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (doc_id) DO UPDATE SET
            chunk_id = EXCLUDED.chunk_id,
            embedding = EXCLUDED.embedding,
            content = EXCLUDED.content,
            bank_name = EXCLUDED.bank_name,
            product_type = EXCLUDED.product_type,
            product_name = EXCLUDED.product_name,
            clause = EXCLUDED.clause,
            clause_name = EXCLUDED.clause_name,
            updated_at = CURRENT_TIMESTAMP;
        """
        
        try:
            with self.connection.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(upsert_sql, (
                        doc_id,
                        chunk_id,
                        embedding,
                        content,
                        metadata.get("은행명", ""),
                        metadata.get("상품종류", ""),
                        metadata.get("상품이름", ""),
                        metadata.get("조항", ""),
                        metadata.get("조항이름", "")
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to upsert document {doc_id}: {e}")
            raise

    
    def search_similar(
        self,
        query_vector: List[float],
        top_k: int = 8,
        filters: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            filters: Optional filters (bank_name, product_type)
        
        Returns:
            List of documents with similarity scores
        """
        # Build WHERE clause for filters
        where_clauses = []
        params = [query_vector, top_k]
        
        if filters:
            if "bank_name" in filters:
                where_clauses.append("bank_name = %s")
                params.insert(1, filters["bank_name"])
            if "product_type" in filters:
                where_clauses.append("product_type = %s")
                params.insert(1, filters["product_type"])
        
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
        
        search_sql = f"""
        SELECT 
            doc_id, chunk_id, content,
            bank_name, product_type, product_name, clause, clause_name,
            1 - (embedding <=> %s::vector) as similarity
        FROM documents
        {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        
        # Adjust params order for the query
        if filters:
            filter_params = []
            if "bank_name" in filters:
                filter_params.append(filters["bank_name"])
            if "product_type" in filters:
                filter_params.append(filters["product_type"])
            params = [query_vector] + filter_params + [query_vector, top_k]
        else:
            params = [query_vector, query_vector, top_k]
        
        try:
            with self.connection.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(search_sql, params)
                    results = cur.fetchall()
                    
                    documents = []
                    for row in results:
                        documents.append({
                            "doc_id": row[0],
                            "chunk_id": row[1],
                            "content": row[2],
                            "metadata": {
                                "은행명": row[3],
                                "상품종류": row[4],
                                "상품이름": row[5],
                                "조항": row[6],
                                "조항이름": row[7]
                            },
                            "similarity": float(row[8])
                        })
                    
                    return documents
        except Exception as e:
            logger.error(f"Failed to search similar documents: {e}")
            raise
    
    def get_document_count(self) -> int:
        """Get total number of documents"""
        try:
            with self.connection.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM documents;")
                    result = cur.fetchone()
                    return result[0] if result else 0
        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            return 0
