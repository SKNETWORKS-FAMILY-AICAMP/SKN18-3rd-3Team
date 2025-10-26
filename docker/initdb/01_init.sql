-- ============================================================================
-- PostgreSQL + pgvector 초기화 스크립트
-- ============================================================================

\connect rag;

-- ---------------------------------------------------------------------------
-- 1. Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- 2. RAG Schema & Documents Table (Vector Store)
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS rag;

COMMENT ON SCHEMA rag IS 'Vector search artifacts for bank clause RAG pipeline';

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    embedding vector(3072),  -- text-embedding-3-large (3072 dimensions)
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

-- Metadata indexes
CREATE INDEX IF NOT EXISTS documents_bank_name_idx ON documents(bank_name);
CREATE INDEX IF NOT EXISTS documents_product_type_idx ON documents(product_type);
CREATE INDEX IF NOT EXISTS documents_doc_id_idx ON documents(doc_id);
CREATE INDEX IF NOT EXISTS documents_chunk_id_idx ON documents(chunk_id);

-- Vector index (데이터 삽입 후 생성 권장)
-- CREATE INDEX documents_embedding_idx 
-- ON documents USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 100);

-- Auto-update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_documents_updated_at 
    BEFORE UPDATE ON documents 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ---------------------------------------------------------------------------
-- 3. RDB Schema & Loan Products Table
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS rdb;

CREATE TABLE IF NOT EXISTS rdb.loan_info (
    id BIGSERIAL PRIMARY KEY,
    bank_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_category TEXT,
    product_detail_category TEXT,
    loan_target TEXT,
    loan_conditions TEXT,
    loan_period TEXT,
    loan_limit TEXT,
    source_file TEXT NOT NULL DEFAULT 'loan_products_RDB.csv',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rdb.loan_info IS '정형 RDB 조회용 은행 대출 상품 메타 데이터';

CREATE INDEX IF NOT EXISTS ix_loan_info_bank ON rdb.loan_info (bank_name);
CREATE INDEX IF NOT EXISTS ix_loan_info_product ON rdb.loan_info (product_name);

-- Load loan products data
DO $$
BEGIN
    BEGIN
        COPY rdb.loan_info (
            bank_name,
            product_name,
            product_category,
            product_detail_category,
            loan_target,
            loan_conditions,
            loan_period,
            loan_limit
        )
        FROM '/docker-entrypoint-initdb.d/loan_products_RDB.csv'
        WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
    EXCEPTION
        WHEN others THEN
            RAISE NOTICE 'loan_products_RDB.csv 적재 실패: %', SQLERRM;
    END;
END;
$$;

-- ---------------------------------------------------------------------------
-- 4. Bank Interest Rate Table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rdb.bank_interest_rate (
    id BIGSERIAL PRIMARY KEY,
    bank_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_category TEXT,
    rate_type TEXT,
    rate_condition TEXT,
    interest_rate TEXT,
    source_file TEXT NOT NULL DEFAULT 'bank_rate.csv',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rdb.bank_interest_rate IS '은행별 금리/조건 표준화 데이터';

CREATE INDEX IF NOT EXISTS ix_bank_interest_rate_bank ON rdb.bank_interest_rate (bank_name);
CREATE INDEX IF NOT EXISTS ix_bank_interest_rate_product ON rdb.bank_interest_rate (product_name);

-- Load bank rate data
DO $$
BEGIN
    BEGIN
        COPY rdb.bank_interest_rate (
            bank_name,
            product_name,
            product_category,
            rate_type,
            rate_condition,
            interest_rate
        )
        FROM '/docker-entrypoint-initdb.d/bank_rate.csv'
        WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
    EXCEPTION
        WHEN others THEN
            RAISE NOTICE 'bank_rate.csv 적재 실패: %', SQLERRM;
    END;
END;
$$;
