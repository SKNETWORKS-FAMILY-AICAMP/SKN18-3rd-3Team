CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS bank_chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id   TEXT NOT NULL,
    bank_name TEXT NOT NULL,
    product_type TEXT NOT NULL,
    product_name TEXT NOT NULL,
    clause_no TEXT,
    clause_name TEXT,
    text TEXT NOT NULL,
    embedding vector(1536) -- text-embedding-3-small
);

CREATE INDEX IF NOT EXISTS idx_bank_chunks_doc ON bank_chunks (doc_id);
CREATE INDEX IF NOT EXISTS idx_bank_chunks_bank ON bank_chunks (bank_name, product_type);

CREATE INDEX IF NOT EXISTS idx_bank_chunks_embed
    ON bank_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
