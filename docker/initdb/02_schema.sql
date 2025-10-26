\connect rag;

-- Enable pgvector for embedding storage
CREATE EXTENSION IF NOT EXISTS vector;

-- Dedicated schema for RAG assets
CREATE SCHEMA IF NOT EXISTS rag;

COMMENT ON SCHEMA rag IS 'Vector search artifacts for bank clause RAG pipeline';

-- Create documents table
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

-- Create metadata indexes
CREATE INDEX IF NOT EXISTS documents_bank_name_idx ON documents(bank_name);
CREATE INDEX IF NOT EXISTS documents_product_type_idx ON documents(product_type);
CREATE INDEX IF NOT EXISTS documents_doc_id_idx ON documents(doc_id);
CREATE INDEX IF NOT EXISTS documents_chunk_id_idx ON documents(chunk_id);

-- Vector index will be created after data insertion for better performance
-- Uncomment and run after indexing data:
-- CREATE INDEX documents_embedding_idx 
-- ON documents USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 100);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_documents_updated_at 
    BEFORE UPDATE ON documents 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
