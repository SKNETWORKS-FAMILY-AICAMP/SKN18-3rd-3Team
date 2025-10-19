# Requirements Document

## Introduction

현재 프로젝트에 비어있거나 주석만 있는 파일들을 완성하여 전체 시스템을 완전하게 만듭니다. 특히 LangGraph를 활용한 RAG 파이프라인을 구현하고, Docker 관련 설정 파일들을 완성합니다.

## Requirements

### Requirement 1: LangGraph 파이프라인 구현

**User Story:** 개발자로서, LangGraph를 사용하여 RAG 파이프라인의 각 단계를 명확하게 정의하고 관리하고 싶습니다.

#### Acceptance Criteria

1. WHEN `RAG/rag/graph/nodes.py`를 구현할 때 THEN 질의 정규화, 메타데이터 라우팅, 벡터 검색, LLM 생성, 응답 포맷팅 노드를 포함해야 합니다
2. WHEN 각 노드가 실행될 때 THEN 상태(state)를 입력받고 업데이트된 상태를 반환해야 합니다
3. WHEN 노드가 실행될 때 THEN 로깅을 통해 진행 상황을 추적할 수 있어야 합니다
4. WHEN 메타데이터 라우팅 노드가 실행될 때 THEN 질의에서 은행명과 상품종류를 자동으로 추출해야 합니다
5. WHEN 벡터 검색 노드가 실행될 때 THEN 추출된 메타데이터를 필터로 사용하여 검색해야 합니다

### Requirement 2: LangGraph 엣지 및 조건 분기

**User Story:** 개발자로서, 검색 결과가 부족하거나 품질이 낮을 때 자동으로 재시도하는 로직을 구현하고 싶습니다.

#### Acceptance Criteria

1. WHEN `RAG/rag/graph/edges.py`를 구현할 때 THEN 조건부 분기 함수들을 포함해야 합니다
2. WHEN 검색 결과가 부족할 때 THEN TOP_K를 증가시켜 재검색을 시도해야 합니다
3. WHEN 재시도 횟수가 최대치에 도달하면 THEN 현재 결과로 진행해야 합니다
4. IF 검색 결과가 0개이면 THEN "정보를 찾을 수 없음" 응답을 생성해야 합니다
5. WHEN 조건 분기가 실행될 때 THEN 로그에 분기 이유를 기록해야 합니다

### Requirement 3: LangGraph 그래프 빌드

**User Story:** 개발자로서, 노드와 엣지를 조합하여 실행 가능한 RAG 그래프를 생성하고 싶습니다.

#### Acceptance Criteria

1. WHEN `RAG/rag/graph/build.py`를 구현할 때 THEN LangGraph StateGraph를 사용해야 합니다
2. WHEN 그래프를 빌드할 때 THEN 모든 노드를 추가하고 엣지로 연결해야 합니다
3. WHEN 조건부 엣지를 추가할 때 THEN edges.py의 조건 함수를 사용해야 합니다
4. WHEN 그래프를 컴파일할 때 THEN 실행 가능한 CompiledGraph를 반환해야 합니다
5. WHEN 그래프가 실행될 때 THEN 시작 노드부터 종료 노드까지 순차적으로 실행되어야 합니다

### Requirement 4: RAG Engine LangGraph 통합

**User Story:** 개발자로서, 기존 RAG Engine을 LangGraph 파이프라인을 사용하도록 업데이트하고 싶습니다.

#### Acceptance Criteria

1. WHEN RAG Engine을 초기화할 때 THEN LangGraph 그래프를 빌드하고 저장해야 합니다
2. WHEN query 메서드가 호출될 때 THEN LangGraph 그래프를 실행해야 합니다
3. WHEN 그래프가 실행될 때 THEN 초기 상태를 설정하고 최종 상태를 반환해야 합니다
4. IF 그래프 실행 중 에러가 발생하면 THEN 적절한 에러 메시지를 반환해야 합니다
5. WHEN 그래프 실행이 완료되면 THEN 답변과 출처 정보를 포함한 결과를 반환해야 합니다

### Requirement 5: Docker Requirements 파일 완성

**User Story:** 시스템 관리자로서, Docker 컨테이너에서 필요한 모든 의존성이 설치되도록 하고 싶습니다.

#### Acceptance Criteria

1. WHEN `docker/requirements.txt`를 작성할 때 THEN 루트의 requirements.txt와 동일한 내용을 포함해야 합니다
2. WHEN Docker 이미지를 빌드할 때 THEN 모든 의존성이 정상적으로 설치되어야 합니다
3. WHEN 컨테이너가 시작될 때 THEN 모든 Python 패키지가 사용 가능해야 합니다
4. IF 의존성 버전 충돌이 있으면 THEN 명확한 에러 메시지를 출력해야 합니다
5. WHEN requirements.txt가 업데이트되면 THEN docker/requirements.txt도 동기화되어야 합니다

### Requirement 6: PostgreSQL 초기화 스크립트 완성

**User Story:** 시스템 관리자로서, Docker 컨테이너 시작 시 데이터베이스가 자동으로 초기화되도록 하고 싶습니다.

#### Acceptance Criteria

1. WHEN `docker/initdb/01_extensions.sql`을 작성할 때 THEN pgvector 확장을 활성화해야 합니다
2. WHEN `docker/initdb/02_schema.sql`을 작성할 때 THEN documents 테이블과 인덱스를 생성해야 합니다
3. WHEN Docker 컨테이너가 시작될 때 THEN SQL 스크립트가 순서대로 실행되어야 합니다
4. WHEN 스크립트가 실행될 때 THEN 이미 존재하는 객체는 건너뛰어야 합니다 (IF NOT EXISTS)
5. IF 스크립트 실행 중 에러가 발생하면 THEN 컨테이너 시작이 실패하고 에러를 로그에 기록해야 합니다

### Requirement 7: LangGraph 의존성 추가

**User Story:** 개발자로서, LangGraph를 사용하기 위한 필요한 패키지가 설치되어야 합니다.

#### Acceptance Criteria

1. WHEN requirements.txt를 업데이트할 때 THEN langgraph 패키지를 추가해야 합니다
2. WHEN langgraph를 설치할 때 THEN 호환되는 버전을 사용해야 합니다
3. WHEN 시스템이 시작될 때 THEN langgraph가 정상적으로 import되어야 합니다
4. IF langgraph 버전이 호환되지 않으면 THEN 명확한 에러 메시지를 출력해야 합니다
5. WHEN langgraph를 사용할 때 THEN 타입 힌팅이 정상적으로 작동해야 합니다

### Requirement 8: 상태(State) 정의

**User Story:** 개발자로서, LangGraph 파이프라인에서 사용할 상태 구조를 명확하게 정의하고 싶습니다.

#### Acceptance Criteria

1. WHEN GraphState를 정의할 때 THEN TypedDict 또는 Pydantic 모델을 사용해야 합니다
2. WHEN 상태를 정의할 때 THEN query, documents, answer, sources, metadata 필드를 포함해야 합니다
3. WHEN 노드가 상태를 업데이트할 때 THEN 타입 안정성이 보장되어야 합니다
4. WHEN 상태가 전달될 때 THEN 불변성(immutability)을 유지해야 합니다
5. IF 잘못된 타입의 값이 상태에 할당되면 THEN 타입 에러를 발생시켜야 합니다
