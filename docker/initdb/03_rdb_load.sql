\connect rag;

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
    source_file TEXT NOT NULL DEFAULT 'loan_products_RDB',
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
            FROM '/docker-entrypoint-initdb.d/loan_products_RDB'
            WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
        $copy$;
    EXCEPTION
        WHEN others THEN
            RAISE NOTICE 'CSV 적재를 건너뜁니다: %', SQLERRM;
    END;
END;
$$;
