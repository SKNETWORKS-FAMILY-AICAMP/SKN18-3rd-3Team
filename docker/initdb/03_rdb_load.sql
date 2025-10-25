\connect rag;

-- ---------------------------------------------------------------------------
-- RDB 스키마 및 대출 상품 기초 데이터 적재
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
    source_file TEXT NOT NULL DEFAULT 'final_update_v4.csv',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rdb.loan_info IS '정형 RDB 조회용 은행 대출 상품 메타 데이터';

CREATE INDEX IF NOT EXISTS ix_loan_info_bank
    ON rdb.loan_info (bank_name);

CREATE INDEX IF NOT EXISTS ix_loan_info_product
    ON rdb.loan_info (product_name);

-- CSV가 제공되는 경우에만 적재 (단순 COPY. 실패 시 경고만 출력)
DO $$
BEGIN
    BEGIN
        EXECUTE $copy$
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
            FROM '/docker-entrypoint-initdb.d/final_update_v4.csv'
            WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
        $copy$;
    EXCEPTION
        WHEN others THEN
            RAISE NOTICE 'CSV 적재를 건너뜁니다: %', SQLERRM;
    END;
END;
$$;

-- ---------------------------------------------------------------------------
-- 은행 금리 테이블 (bank_interest_rate)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS rdb.bank_interest_rate CASCADE;

CREATE TABLE rdb.bank_interest_rate (
    id BIGSERIAL PRIMARY KEY,
    bank_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_category TEXT,
    rate_type TEXT,
    rate_condition TEXT,
    interest_rate TEXT,
    source_file TEXT NOT NULL DEFAULT 'RDB2_cleaned.csv',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rdb.bank_interest_rate IS '은행별 금리/조건 표준화 데이터';

CREATE INDEX IF NOT EXISTS ix_bank_interest_rate_bank
    ON rdb.bank_interest_rate (bank_name);

CREATE INDEX IF NOT EXISTS ix_bank_interest_rate_product
    ON rdb.bank_interest_rate (product_name);

DO $$
BEGIN
    BEGIN
        EXECUTE $copy$
            COPY rdb.bank_interest_rate (
                bank_name,
                product_name,
                product_category,
                rate_type,
                rate_condition,
                interest_rate
            )
            FROM '/docker-entrypoint-initdb.d/RDB2_cleaned.csv'
            WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
        $copy$;
    EXCEPTION
        WHEN others THEN
            RAISE NOTICE '은행 금리 CSV 적재를 건너뜁니다: %', SQLERRM;
    END;
END;
$$;
