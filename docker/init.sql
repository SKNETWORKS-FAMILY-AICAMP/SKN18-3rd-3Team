\connect skn_bank_data;

-- Enable pgvector for embedding storage
CREATE EXTENSION IF NOT EXISTS vector;

-- Dedicated schema for RAG assets
CREATE SCHEMA IF NOT EXISTS rag;

COMMENT ON SCHEMA rag IS 'Vector search artifacts for bank clause RAG pipeline';

-- Bank clause chunks with OpenAI embeddings
CREATE TABLE IF NOT EXISTS rag.bank_clauses (
    id BIGSERIAL PRIMARY KEY,
    chunk_id TEXT UNIQUE NOT NULL,
    doc_id TEXT NOT NULL,
    chunk_index INT NOT NULL,
    bank_name TEXT,
    product_type TEXT,
    product_name TEXT,
    clause_number TEXT,
    clause_title TEXT,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata JSONB NOT NULL,
    source_file TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rag.bank_clauses IS 'Chunked bank documents with pgvector embeddings';

-- Vector index for cosine similarity search (populate after loading data)
CREATE INDEX IF NOT EXISTS ix_bank_clauses_embedding
    ON rag.bank_clauses
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Metadata filters and document level lookups
CREATE INDEX IF NOT EXISTS ix_bank_clauses_doc_id
    ON rag.bank_clauses (doc_id);

CREATE INDEX IF NOT EXISTS ix_bank_clauses_bank
    ON rag.bank_clauses (bank_name);

CREATE INDEX IF NOT EXISTS ix_bank_clauses_product
    ON rag.bank_clauses (product_name);

CREATE INDEX IF NOT EXISTS ix_bank_clauses_clause
    ON rag.bank_clauses (clause_number, clause_title);

CREATE INDEX IF NOT EXISTS ix_bank_clauses_metadata
    ON rag.bank_clauses USING GIN (metadata);

-- 분석 작업 후 ANALYZE 를 실행하면 ivfflat 통계가 최신 상태를 유지한다.

-- ---------------------------------------------------------------------------
-- RDB 스키마 및 대출 상품 기초 데이터 적재
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS rdb;

CREATE TABLE IF NOT EXISTS rdb.loan_products (
    id BIGSERIAL PRIMARY KEY,
    bank_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_category TEXT,
    product_detail_category TEXT,
    loan_target TEXT,
    loan_conditions TEXT,
    loan_period TEXT,
    loan_limit TEXT,
    source_file TEXT NOT NULL DEFAULT 'final_update_v4.csv',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rdb.loan_products IS '정형 RDB 조회용 은행 대출 상품 메타 데이터';

CREATE INDEX IF NOT EXISTS ix_loan_products_bank
    ON rdb.loan_products (bank_name);

CREATE INDEX IF NOT EXISTS ix_loan_products_product
    ON rdb.loan_products (product_name);

-- CSV가 제공되는 경우에만 적재 (단순 COPY. 실패 시 경고만 출력)
DO $$
BEGIN
    BEGIN
        EXECUTE $copy$
            COPY rdb.loan_products (
                bank_name,
                product_name,
                product_category,
                product_detail_category,
                loan_target,
                loan_conditions,
                loan_period,
                loan_limit
            )
            FROM '/docker-entrypoint-initdb.d/final_update_v4.csv'
            WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
        $copy$;
    EXCEPTION
        WHEN others THEN
            RAISE NOTICE 'CSV 적재를 건너뜁니다: %', SQLERRM;
    END;
END;
$$;
