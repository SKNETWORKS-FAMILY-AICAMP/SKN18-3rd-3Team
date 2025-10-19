# Implementation Plan

- [x] 1. 프로젝트 구조 및 환경 설정


  - `.gitignore`, `.env.template`, `requirements.txt` 파일 생성
  - Docker 관련 파일(`compose.yml`, `docker/Dockerfile.app`, `docker/initdb/init.sql`) 생성
  - RAG 폴더 구조 및 `__init__.py` 파일 생성
  - _Requirements: 5.1, 5.2, 7.1, 7.2_

- [x] 2. Core 모듈 구현


  - [x] 2.1 `rag/core/config.py` 구현


    - `.env` 파일에서 환경 변수를 로드하는 Config 클래스 작성
    - 필수 환경 변수 검증 로직 추가
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  - [x] 2.2 `rag/core/singleton.py` 구현


    - 스레드 세이프 싱글톤 메타클래스 작성
    - _Requirements: 6.1, 6.2, 6.3_
  - [x] 2.3 `rag/core/logger.py` 구현


    - 구조화된 로깅 설정 함수 작성
    - 레벨별 핸들러 및 포맷터 구성
    - _Requirements: 8.1, 8.5_

- [x] 3. Database 모듈 구현


  - [x] 3.1 `rag/db/connection.py` 구현


    - psycopg 커넥션 풀을 사용하는 DatabaseConnection 클래스 작성
    - 헬스체크 메서드 구현
    - _Requirements: 6.4, 7.5_
  - [x] 3.2 `rag/db/repo.py` 구현


    - DocumentRepository 클래스 작성
    - 테이블 생성, 문서 업서트, 유사도 검색, 문서 수 조회 메서드 구현
    - _Requirements: 9.1, 9.4_
  - [x] 3.3 `docker/initdb/init.sql` 작성

    - pgvector 확장 활성화
    - documents 테이블 생성
    - 벡터 인덱스 및 메타데이터 인덱스 생성
    - _Requirements: 7.4, 9.1, 9.2, 9.3_

- [x] 4. Embeddings 모듈 구현


  - [x] 4.1 `rag/embeddings/provider.py` 구현


    - EmbeddingProvider 추상 클래스 작성
    - embed_texts, embed_query 추상 메서드 정의
    - _Requirements: 1.2_
  - [x] 4.2 `rag/embeddings/openai_embed.py` 구현


    - OpenAIEmbeddings 클래스 작성 (싱글톤)
    - 배치 임베딩 및 재시도 로직 구현
    - _Requirements: 1.2, 2.1_

- [x] 5. LLM 모듈 구현



  - [x] 5.1 `rag/llm/openai_chat.py` 구현


    - OpenAIChatModel 클래스 작성 (싱글톤)
    - 채팅 완성 API 호출 및 에러 핸들링 구현
    - _Requirements: 3.1, 3.2_

- [x] 6. VectorStore 모듈 구현


  - [x] 6.1 `rag/vectorstore/types.py` 구현


    - SearchResult 데이터클래스 작성
    - _Requirements: 2.5_
  - [x] 6.2 `rag/vectorstore/sql.py` 구현


    - UPSERT, 검색, 테이블 생성 SQL 쿼리 함수 작성
    - _Requirements: 9.1, 9.2, 9.4_
  - [x] 6.3 `rag/vectorstore/pgvector_store.py` 구현


    - LangChain VectorStore를 상속하는 PgVectorStore 클래스 작성
    - add_documents, similarity_search_with_score 메서드 구현
    - _Requirements: 1.3, 2.2, 2.3, 2.4, 2.5_

- [x] 7. Ingestion 모듈 구현


  - [x] 7.1 `rag/ingestion/load_csv.py` 구현


    - CSV 파일을 Document 객체로 변환하는 함수 작성
    - _Requirements: 1.1_
  - [x] 7.2 `rag/ingestion/indexer.py` 구현


    - DocumentIndexer 클래스 작성
    - 배치 인덱싱, 진행률 로깅, 재시도 로직 구현
    - _Requirements: 1.4, 1.5, 8.2_
  - [x] 7.3 `rag/ingestion/chunking.py` 구현 (옵션)

    - 문서 재청킹 함수 작성
    - _Requirements: N/A_

- [x] 8. RAG 모듈 - Retriever 구현


  - [x] 8.1 `rag/rag/retriever.py` 구현


    - BankRetriever 클래스 작성
    - 메타데이터 필터링을 지원하는 retrieve 메서드 구현
    - _Requirements: 2.3, 2.4_




- [ ] 9. RAG 모듈 - LangGraph 파이프라인 구현
  - [x] 9.1 `rag/rag/graph/nodes.py` 구현

    - GraphNodes 클래스 작성
    - normalize_query, route_metadata, vector_search, generate_answer, format_response 노드 함수 구현
    - _Requirements: 4.1, 4.2, 4.4_

  - [ ] 9.2 `rag/rag/graph/edges.py` 구현
    - GraphEdges 클래스 작성
    - should_retry_search, should_expand_k 조건 함수 구현



    - _Requirements: 4.3_
  - [x] 9.3 `rag/rag/graph/build.py` 구현

    - build_rag_graph 함수 작성
    - LangGraph StateGraph 구성 및 컴파일

    - _Requirements: 4.1, 4.5_

- [ ] 10. RAG 모듈 - Prompts 및 Engine 구현
  - [ ] 10.1 `rag/rag/prompts/answer.j2` 작성
    - LLM 답변 생성을 위한 Jinja2 템플릿 작성
    - 출처 명시 및 답변 규칙 포함
    - _Requirements: 3.2, 3.3, 3.5_
  - [ ] 10.2 `rag/rag/prompts/citations.j2` 작성 (옵션)
    - 출처 포맷팅 템플릿 작성
    - _Requirements: 3.3_
  - [x] 10.3 `rag/rag/engine.py` 구현

    - RAGEngine 싱글톤 클래스 작성
    - 모든 컴포넌트 초기화 및 query 메서드 구현
    - _Requirements: 6.1, 6.5_

- [x] 11. Flask API 애플리케이션 구현


  - [x] 11.1 `app.py` 구현


    - Flask 애플리케이션 생성
    - `/query` POST 엔드포인트 구현
    - 요청 검증 및 에러 핸들링 추가
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  - [x] 11.2 헬스체크 엔드포인트 추가

    - `/health` GET 엔드포인트 구현
    - 데이터베이스 연결 상태 확인
    - _Requirements: 7.5_

- [x] 12. Docker 및 배포 설정

  - [x] 12.1 `docker/Dockerfile.app` 작성

    - Python 베이스 이미지 사용
    - 의존성 설치 및 애플리케이션 복사
    - _Requirements: 7.1_
  - [x] 12.2 `compose.yml` 작성

    - PostgreSQL(pgvector) 및 애플리케이션 서비스 정의
    - 환경 변수 및 볼륨 설정
    - _Requirements: 7.1, 7.3_
  - [x] 12.3 `requirements.txt` 작성

    - 모든 Python 의존성 나열
    - _Requirements: 7.2_

- [x] 13. 인덱싱 스크립트 작성


  - [x] 13.1 `scripts/index_data.py` 작성


    - CSV 데이터를 로드하고 인덱싱하는 스크립트 작성
    - 진행률 출력 및 에러 로깅





    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 8.2_

- [ ] 14. 문서화 및 README 작성
  - [ ] 14.1 `README.md` 업데이트
    - 프로젝트 개요, 설치 방법, 사용 방법 작성
    - Docker 및 가상환경 실행 가이드 포함
    - API 엔드포인트 문서화
    - _Requirements: 7.1, 7.2, 10.1_

- [ ] 15. 통합 테스트 및 검증
  - [ ] 15.1 Docker 환경에서 전체 시스템 테스트
    - Docker Compose로 시스템 시작
    - 인덱싱 스크립트 실행
    - API 엔드포인트 테스트
    - _Requirements: 7.1, 7.3, 7.4, 7.5_
  - [ ] 15.2 가상환경에서 전체 시스템 테스트
    - 의존성 설치
    - 로컬 PostgreSQL 연결
    - 인덱싱 및 쿼리 테스트
    - _Requirements: 7.2_
  - [ ] 15.3 샘플 쿼리 테스트
    - 우리은행/국민은행 대출 관련 질의 테스트
    - 예적금 관련 질의 테스트
    - 메타데이터 필터링 검증
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_
