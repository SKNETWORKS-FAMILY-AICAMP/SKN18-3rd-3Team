# Requirements Document

## Introduction

우리은행과 국민은행의 대출 및 예적금 상품에 대한 Q&A를 제공하는 RAG(Retrieval-Augmented Generation) 서비스를 구축합니다. 이 시스템은 CSV 형식의 은행 데이터를 벡터 데이터베이스에 인덱싱하고, 사용자 질의에 대해 관련 문서를 검색한 후 LLM을 통해 정확한 답변을 생성합니다. 시스템은 가상환경과 Docker 환경 모두에서 구동 가능하도록 설계됩니다.

## Requirements

### Requirement 1: 데이터 인덱싱 시스템

**User Story:** 시스템 관리자로서, CSV 파일의 은행 데이터를 벡터 데이터베이스에 인덱싱하여 검색 가능한 상태로 만들고 싶습니다.

#### Acceptance Criteria

1. WHEN CSV 파일(`data/merged_bankdata.csv`)을 로드할 때 THEN 시스템은 은행명, 상품종류, 상품이름, 조항, 조항이름, context 필드를 포함한 Document 객체로 변환해야 합니다
2. WHEN 문서를 임베딩할 때 THEN 시스템은 OpenAI `text-embedding-3-large` 모델을 사용하여 벡터를 생성해야 합니다
3. WHEN 임베딩된 문서를 저장할 때 THEN 시스템은 PostgreSQL의 pgvector 확장을 사용하여 벡터와 메타데이터를 저장해야 합니다
4. WHEN 대량 인덱싱을 수행할 때 THEN 시스템은 배치 처리, 재시도 로직, 진행률 로깅을 제공해야 합니다
5. IF 중복 문서가 감지되면 THEN 시스템은 해당 문서를 스킵하고 로그를 남겨야 합니다

### Requirement 2: 벡터 검색 시스템

**User Story:** 사용자로서, 대출이나 예적금에 대한 질문을 입력하면 관련된 은행 정보를 검색하여 답변을 받고 싶습니다.

#### Acceptance Criteria

1. WHEN 사용자가 질의를 입력할 때 THEN 시스템은 질의를 임베딩하여 벡터로 변환해야 합니다
2. WHEN 벡터 검색을 수행할 때 THEN 시스템은 pgvector의 유사도 검색을 사용하여 TOP_K개의 관련 문서를 반환해야 합니다
3. WHEN 검색 시 은행명 필터가 제공되면 THEN 시스템은 해당 은행의 문서만 검색해야 합니다
4. WHEN 검색 시 상품종류 필터가 제공되면 THEN 시스템은 해당 상품종류(대출/예적금)의 문서만 검색해야 합니다
5. WHEN 검색 결과를 반환할 때 THEN 시스템은 문서 내용과 함께 유사도 점수, 은행명, 상품종류, 조항 정보를 포함해야 합니다

### Requirement 3: LLM 기반 답변 생성

**User Story:** 사용자로서, 검색된 문서를 기반으로 자연스럽고 정확한 답변을 받고 싶습니다.

#### Acceptance Criteria

1. WHEN 검색된 문서가 제공될 때 THEN 시스템은 OpenAI `gpt-5-nano` 모델을 사용하여 답변을 생성해야 합니다
2. WHEN 답변을 생성할 때 THEN 시스템은 검색된 문서의 context를 프롬프트에 포함해야 합니다
3. WHEN 답변을 생성할 때 THEN 시스템은 출처(은행명, 상품이름, 조항, 조항이름)를 명시해야 합니다
4. IF 검색된 문서가 질의와 관련이 없으면 THEN 시스템은 "관련 정보를 찾을 수 없습니다"라고 응답해야 합니다
5. WHEN 답변을 생성할 때 THEN 시스템은 일관된 톤과 포맷을 유지해야 합니다

### Requirement 4: RAG 파이프라인 구성

**User Story:** 개발자로서, 질의 처리부터 답변 생성까지의 전체 파이프라인을 모듈화하여 관리하고 싶습니다.

#### Acceptance Criteria

1. WHEN RAG 파이프라인이 실행될 때 THEN 시스템은 질의 정규화 → 메타 라우팅 → 벡터 검색 → LLM 생성 → 포맷팅 단계를 순차적으로 수행해야 합니다
2. WHEN 메타 라우팅 단계에서 THEN 시스템은 질의에서 은행명과 상품종류를 추출하여 검색 필터로 사용해야 합니다
3. IF 검색 결과가 부족하면 THEN 시스템은 TOP_K 값을 확장하여 재검색을 시도해야 합니다
4. WHEN 파이프라인의 각 단계가 실행될 때 THEN 시스템은 구조화된 로그를 남겨야 합니다
5. WHEN 파이프라인에서 에러가 발생하면 THEN 시스템은 적절한 에러 메시지와 함께 실패 단계를 로깅해야 합니다

### Requirement 5: 설정 관리 및 환경 구성

**User Story:** 시스템 관리자로서, 환경 변수를 통해 시스템 설정을 쉽게 변경하고 관리하고 싶습니다.

#### Acceptance Criteria

1. WHEN 시스템이 시작될 때 THEN `.env` 파일에서 설정을 로드해야 합니다
2. WHEN 설정을 로드할 때 THEN 시스템은 OPENAI_API_KEY, DB_URL, EMBED_MODEL, LLM_MODEL, TOP_K 등의 값을 읽어야 합니다
3. IF 필수 환경 변수가 누락되면 THEN 시스템은 명확한 에러 메시지를 출력하고 종료해야 합니다
4. WHEN 개발/배포 환경을 전환할 때 THEN `.env` 파일만 수정하면 설정이 변경되어야 합니다
5. WHEN 시스템이 실행될 때 THEN 하드코딩된 설정 값이 없어야 합니다

### Requirement 6: 싱글톤 패턴 및 리소스 관리

**User Story:** 개발자로서, LLM, 임베더, VectorStore, DB 커넥션을 한 번만 초기화하여 리소스를 효율적으로 사용하고 싶습니다.

#### Acceptance Criteria

1. WHEN 시스템이 시작될 때 THEN LLM, 임베더, VectorStore, DB 커넥션은 싱글톤 패턴으로 한 번만 초기화되어야 합니다
2. WHEN 여러 요청이 동시에 들어올 때 THEN 시스템은 동일한 싱글톤 인스턴스를 재사용해야 합니다
3. WHEN 싱글톤 인스턴스를 생성할 때 THEN 스레드 세이프하게 동작해야 합니다
4. WHEN DB 커넥션을 사용할 때 THEN 커넥션 풀을 통해 관리되어야 합니다
5. IF 리소스 초기화에 실패하면 THEN 시스템은 명확한 에러 메시지를 출력하고 재시도 또는 종료해야 합니다

### Requirement 7: Docker 및 가상환경 지원

**User Story:** 개발자로서, 로컬 가상환경과 Docker 환경 모두에서 시스템을 실행할 수 있어야 합니다.

#### Acceptance Criteria

1. WHEN Docker Compose를 실행할 때 THEN PostgreSQL(pgvector 포함)과 애플리케이션 컨테이너가 시작되어야 합니다
2. WHEN 가상환경에서 실행할 때 THEN `requirements.txt`의 모든 의존성이 설치되어야 합니다
3. WHEN Docker 환경에서 실행할 때 THEN 애플리케이션은 `compose.yml`에 정의된 환경 변수를 사용해야 합니다
4. WHEN 데이터베이스가 초기화될 때 THEN pgvector 확장과 필요한 테이블이 자동으로 생성되어야 합니다
5. WHEN 시스템이 시작될 때 THEN 데이터베이스 연결 상태를 확인하고 헬스체크를 수행해야 합니다

### Requirement 8: 로깅 및 모니터링

**User Story:** 시스템 관리자로서, 인덱싱, 검색, 생성 과정의 상태와 에러를 추적하고 싶습니다.

#### Acceptance Criteria

1. WHEN 시스템이 동작할 때 THEN 구조화된 로그(레벨, 타임스탬프, 메시지)를 출력해야 합니다
2. WHEN 인덱싱이 진행될 때 THEN 진행률과 처리된 문서 수를 로깅해야 합니다
3. WHEN 검색이 수행될 때 THEN 질의, 검색 결과 수, 소요 시간을 로깅해야 합니다
4. WHEN 에러가 발생할 때 THEN 에러 타입, 메시지, 스택 트레이스를 로깅해야 합니다
5. WHEN 로그 레벨을 설정할 때 THEN DEBUG, INFO, WARNING, ERROR 레벨을 지원해야 합니다

### Requirement 9: 데이터베이스 스키마 및 인덱스

**User Story:** 개발자로서, 효율적인 벡터 검색을 위한 데이터베이스 스키마와 인덱스를 구성하고 싶습니다.

#### Acceptance Criteria

1. WHEN 데이터베이스 테이블을 생성할 때 THEN 문서 ID, 벡터, 텍스트, 메타데이터(은행명, 상품종류, 조항 등) 컬럼을 포함해야 합니다
2. WHEN 벡터 인덱스를 생성할 때 THEN IVFFLAT 또는 HNSW 인덱스를 사용해야 합니다
3. WHEN 메타데이터 필터링을 수행할 때 THEN 은행명과 상품종류 컬럼에 B-tree 인덱스가 있어야 합니다
4. WHEN 문서를 업서트할 때 THEN 중복 문서 ID는 업데이트되어야 합니다
5. WHEN 데이터베이스 스키마를 변경할 때 THEN 마이그레이션 스크립트를 통해 관리되어야 합니다

### Requirement 10: API 엔드포인트

**User Story:** 클라이언트로서, HTTP API를 통해 질의를 전송하고 답변을 받고 싶습니다.

#### Acceptance Criteria

1. WHEN `/query` 엔드포인트에 POST 요청을 보낼 때 THEN 시스템은 질의를 처리하고 답변을 반환해야 합니다
2. WHEN 요청 본문에 질의 텍스트가 포함될 때 THEN 시스템은 JSON 형식으로 응답해야 합니다
3. WHEN 응답을 반환할 때 THEN 답변, 출처, 검색된 문서 수를 포함해야 합니다
4. IF 잘못된 요청이 들어오면 THEN 시스템은 400 에러와 함께 에러 메시지를 반환해야 합니다
5. WHEN 서버 에러가 발생하면 THEN 시스템은 500 에러와 함께 에러 메시지를 반환해야 합니다
