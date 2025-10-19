# Implementation Plan

- [x] 1. LangGraph 의존성 추가





  - requirements.txt에 langgraph 패키지 추가
  - 버전 호환성 확인
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 2. 상태(State) 정의 구현




  - [x] 2.1 GraphState TypedDict 정의




    - query, top_k, bank_name, product_type 필드 추가
    - documents, answer, sources 필드 추가
    - retry_count, error 제어 필드 추가
    - _Requirements: 8.1, 8.2, 8.3_







- [ ] 3. Graph Nodes 구현
  - [x] 3.1 `RAG/rag/graph/nodes.py` - GraphNodes 클래스 작성


    - __init__ 메서드: retriever, llm, jinja_env 저장
    - _Requirements: 1.1_
  - [x] 3.2 normalize_query 노드 구현


    - 질의 정규화 (공백 제거, strip)
    - 로깅 추가
    - _Requirements: 1.1, 1.3_


  - [ ] 3.3 route_metadata 노드 구현
    - 질의에서 은행명 추출 (우리은행/국민은행)
    - 질의에서 상품종류 추출 (대출/예적금)


    - 로깅 추가
    - _Requirements: 1.2, 1.4_





  - [ ] 3.4 vector_search 노드 구현
    - retriever를 사용하여 검색
    - 메타데이터 필터 적용
    - 로깅 추가
    - _Requirements: 1.2, 1.5_
  - [x] 3.5 generate_answer 노드 구현




    - Jinja2 템플릿 로드
    - LLM을 사용하여 답변 생성
    - 빈 결과 처리
    - _Requirements: 1.1, 1.3_
  - [x] 3.6 format_response 노드 구현




    - 출처 정보 추출 및 포맷팅
    - sources 리스트 생성
    - _Requirements: 1.1_



- [ ] 4. Graph Edges 구현
  - [ ] 4.1 `RAG/rag/graph/edges.py` - GraphEdges 클래스 작성
    - _Requirements: 2.1_




  - [x] 4.2 check_search_results 조건 함수 구현




    - 검색 결과 개수 확인
    - 재시도 횟수 확인


    - TOP_K 증가 로직
    - "sufficient", "retry", "failed" 반환
    - 로깅 추가

    - _Requirements: 2.2, 2.3, 2.4, 2.5_

- [x] 5. Graph Build 구현


  - [x] 5.1 `RAG/rag/graph/build.py` - build_rag_graph 함수 작성

    - StateGraph 생성
    - 모든 노드 추가
    - 엣지 연결
    - 조건부 엣지 추가

    - 그래프 컴파일
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. RAG Engine LangGraph 통합

  - [ ] 6.1 `RAG/rag/engine.py` 수정
    - GraphNodes 인스턴스 생성
    - build_rag_graph 호출하여 그래프 빌드
    - 그래프를 인스턴스 변수로 저장

    - _Requirements: 4.1_
  - [ ] 6.2 query 메서드 수정
    - 초기 상태 생성
    - 그래프 실행 (invoke)
    - 최종 상태에서 결과 추출
    - 에러 핸들링
    - _Requirements: 4.2, 4.3, 4.4, 4.5_

- [ ] 7. Docker requirements.txt 완성
  - [ ] 7.1 `docker/requirements.txt` 작성
    - 루트 requirements.txt 내용 복사
    - _Requirements: 5.1, 5.2, 5.3_

- [ ] 8. PostgreSQL 초기화 스크립트 완성
  - [ ] 8.1 `docker/initdb/01_extensions.sql` 작성
    - pgvector 확장 활성화
    - IF NOT EXISTS 사용
    - _Requirements: 6.1, 6.4_
  - [ ] 8.2 `docker/initdb/02_schema.sql` 작성
    - documents 테이블 생성
    - 메타데이터 인덱스 생성
    - 벡터 인덱스 주석 (데이터 삽입 후 생성)
    - _Requirements: 6.2, 6.4_
  - [ ] 8.3 `docker/initdb/init.sql` 확인 및 정리
    - 기존 init.sql과 중복 제거
    - 01, 02 스크립트로 분리된 내용 확인
    - _Requirements: 6.3_

- [ ] 9. 통합 테스트
  - [ ] 9.1 LangGraph 파이프라인 테스트
    - 간단한 질의로 전체 파이프라인 실행
    - 각 노드가 순서대로 실행되는지 확인
    - 로그 출력 확인
    - _Requirements: 1.1, 1.2, 1.3_
  - [ ] 9.2 재시도 로직 테스트
    - 검색 결과가 부족한 질의 테스트
    - TOP_K 증가 확인
    - 재시도 횟수 제한 확인
    - _Requirements: 2.2, 2.3_
  - [ ] 9.3 메타데이터 필터링 테스트
    - 은행명 필터 테스트
    - 상품종류 필터 테스트
    - 자동 추출 테스트
    - _Requirements: 1.4, 1.5_
  - [ ] 9.4 Docker 환경 테스트
    - Docker Compose로 시스템 시작
    - 데이터베이스 초기화 확인
    - 의존성 설치 확인
    - _Requirements: 5.2, 6.3, 6.5_
