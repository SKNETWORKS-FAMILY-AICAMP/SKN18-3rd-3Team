"""SQL queries for vector store operations"""


def get_create_table_query() -> str:
    """Get SQL query to create documents table"""
    return """
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        doc_id VARCHAR(255) UNIQUE NOT NULL,
        chunk_id VARCHAR(255) NOT NULL,
        embedding vector(1536),
        content TEXT NOT NULL,
        bank_name VARCHAR(100) NOT NULL,
        document_name TEXT NOT NULL,
        product_type VARCHAR(50) NOT NULL,
        product_name VARCHAR(255),
        clause VARCHAR(255),
        clause_name VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """


def get_create_indexes_query(index_type: str = "ivfflat") -> list:
    """
    Get SQL queries to create indexes.
    
    Args:
        index_type: Type of vector index ('ivfflat' or 'hnsw')
    
    Returns:
        List of SQL queries
    """
    queries = [
        "CREATE INDEX IF NOT EXISTS documents_bank_name_idx ON documents(bank_name);",
        "CREATE INDEX IF NOT EXISTS documents_product_type_idx ON documents(product_type);",
        "CREATE INDEX IF NOT EXISTS documents_doc_id_idx ON documents(doc_id);",
        "CREATE INDEX IF NOT EXISTS documents_chunk_id_idx ON documents(chunk_id);"
    ]
    
    # Vector index (created after data insertion for better performance)
    if index_type == "ivfflat":
        vector_index = """
        CREATE INDEX IF NOT EXISTS documents_embedding_idx 
        ON documents USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
        """
    elif index_type == "hnsw":
        vector_index = """
        CREATE INDEX IF NOT EXISTS documents_embedding_idx 
        ON documents USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
        """
    else:
        raise ValueError(f"Unsupported index type: {index_type}")
    
    queries.append(vector_index)
    return queries


def get_upsert_query() -> str:
    """Get SQL query for upserting documents"""
    return """
    INSERT INTO documents (
        doc_id, chunk_id, embedding, content,
        bank_name, document_name, product_type, product_name, clause, clause_name
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (doc_id) DO UPDATE SET
        chunk_id = EXCLUDED.chunk_id,
        embedding = EXCLUDED.embedding,
        content = EXCLUDED.content,
        bank_name = EXCLUDED.bank_name,
        document_name = EXCLUDED.document_name,
        product_type = EXCLUDED.product_type,
        product_name = EXCLUDED.product_name,
        clause = EXCLUDED.clause,
        clause_name = EXCLUDED.clause_name,
        updated_at = CURRENT_TIMESTAMP;
    """


def get_search_query(filters: dict = None) -> tuple:
    """
    Get SQL query for similarity search.
    
    Args:
        filters: Optional filters (bank_name, product_type)
    
    Returns:
        Tuple of (query_string, needs_filter_params)
    """
    where_clauses = []
    
    if filters:
        if "bank_name" in filters:
            where_clauses.append("bank_name = %s")
        if "product_type" in filters:
            where_clauses.append("product_type = %s")
    
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
    
    query = f"""
    SELECT 
        doc_id, chunk_id, content,
        bank_name, document_name, product_type, product_name, clause, clause_name,
        1 - (embedding <=> %s::vector) as similarity
    FROM documents
    {where_sql}
    ORDER BY embedding <=> %s::vector
    LIMIT %s;
    """
    
    return query


def get_delete_query() -> str:
    """Get SQL query for deleting documents"""
    return "DELETE FROM documents WHERE doc_id = %s;"


def get_count_query() -> str:
    """Get SQL query for counting documents"""
    return "SELECT COUNT(*) FROM documents;"
