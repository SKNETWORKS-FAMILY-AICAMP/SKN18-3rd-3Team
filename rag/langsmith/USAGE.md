# LangSmith 사용 가이드

## 환경 설정

### 1. 환경변수 설정 (.env)

```bash
# LangSmith 추적 활성화
LANGCHAIN_TRACING_V2=true

# LangSmith API 키 (https://smith.langchain.com에서 발급)
LANGCHAIN_API_KEY=your_api_key_here

# 프로젝트 이름 (선택, 기본값: default)
LANGCHAIN_PROJECT=rag-banking-system

# LangSmith 엔드포인트 (선택, 기본값: https://api.smith.langchain.com)
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### 2. LangSmith 계정 생성

1. https://smith.langchain.com 방문
2. 계정 생성 및 로그인
3. Settings → API Keys에서 API 키 발급
4. `.env` 파일에 API 키 추가

## 사용 방법

### 방법 1: 그래프 생성 시 활성화

```python
from rag.llm.get_llm import get_llm_model
from rag.vectorstore.pgvector_store import PgVectorStore
from rag.graph.build import create_rag_system

# LLM 및 VectorStore 초기화
llm = get_llm_model()
vectorstore = PgVectorStore(...)

# LangSmith 활성화하여 그래프 생성
graph = create_rag_system(
    llm=llm,
    vectorstore=vectorstore,
    enable_langsmith=True  # ✅ LangSmith 활성화
)

# 실행 (자동으로 추적됨)
result = graph.invoke({"question": "우리은행 전세자금대출 금리는?"})
```

### 방법 2: 헬퍼 함수 사용

```python
from rag.graph.build import create_rag_system, invoke_with_langsmith

# 그래프 생성
graph = create_rag_system(
    llm=llm,
    vectorstore=vectorstore,
    enable_langsmith=True
)

# LangSmith와 함께 실행
result = invoke_with_langsmith(
    graph=graph,
    state={"question": "KB국민은행 주택담보대출 금리는?"}
)

print(result["answer"])
```

### 방법 3: 수동 설정

```python
from rag.langsmith.tracer import LangSmithTracer

# LangSmith 초기화
tracer = LangSmithTracer()

if tracer.is_enabled():
    config = tracer.get_config()
    
    # 그래프 실행 시 config 전달
    result = graph.invoke(
        {"question": "질문"},
        config=config
    )
else:
    print("LangSmith가 설정되지 않았습니다.")
```

## 추적 확인

### LangSmith 대시보드

1. https://smith.langchain.com 로그인
2. 프로젝트 선택 (LANGCHAIN_PROJECT 값)
3. Traces 탭에서 실행 기록 확인

### 추적 정보

각 실행에서 확인할 수 있는 정보:

- **입력**: 사용자 질문
- **출력**: 생성된 답변
- **중간 단계**:
  - Classification (질의 분류)
  - SQL 검색 결과
  - Vector 검색 결과
  - Evaluation (청크 평가)
  - Generation (답변 생성)
- **실행 시간**: 각 단계별 소요 시간
- **토큰 사용량**: LLM 호출 시 사용된 토큰
- **에러**: 발생한 오류 정보

## 피드백 기록

```python
from rag.langsmith.utils import log_feedback

# 실행 ID는 LangSmith 대시보드에서 확인 가능
run_id = "실행_ID"

# 긍정 피드백
log_feedback(
    run_id=run_id,
    score=1.0,
    feedback_key="user_satisfaction",
    comment="답변이 정확하고 유용했습니다."
)

# 부정 피드백
log_feedback(
    run_id=run_id,
    score=0.0,
    feedback_key="user_satisfaction",
    comment="답변이 부정확합니다."
)
```

## 실행 정보 조회

```python
from rag.langsmith.utils import get_run_info

run_id = "실행_ID"
info = get_run_info(run_id)

if info:
    print(f"실행 이름: {info['name']}")
    print(f"상태: {info['status']}")
    print(f"시작 시간: {info['start_time']}")
    print(f"종료 시간: {info['end_time']}")
    print(f"입력: {info['inputs']}")
    print(f"출력: {info['outputs']}")
```

## 비활성화

LangSmith를 비활성화하려면:

1. `.env` 파일에서 `LANGCHAIN_TRACING_V2=false` 설정
2. 또는 그래프 생성 시 `enable_langsmith=False` (기본값)

```python
# LangSmith 비활성화 (기본값)
graph = create_rag_system(
    llm=llm,
    vectorstore=vectorstore,
    enable_langsmith=False
)
```

## 주의사항

1. **API 키 보안**: `.env` 파일을 `.gitignore`에 추가
2. **비용**: LangSmith 무료 티어 제한 확인
3. **성능**: 추적 기능이 약간의 오버헤드 추가
4. **개인정보**: 민감한 데이터 전송 주의

## 문제 해결

### LangSmith가 활성화되지 않음

```
LangSmith requested but not configured (check LANGCHAIN_API_KEY)
```

**해결 방법**:
1. `.env` 파일에 `LANGCHAIN_API_KEY` 설정 확인
2. `LANGCHAIN_TRACING_V2=true` 설정 확인
3. API 키가 유효한지 확인

### 추적이 대시보드에 표시되지 않음

**해결 방법**:
1. 프로젝트 이름 확인 (`LANGCHAIN_PROJECT`)
2. 네트워크 연결 확인
3. API 키 권한 확인

## 참고 자료

- [LangSmith 공식 문서](https://docs.smith.langchain.com/)
- [LangChain 콜백 가이드](https://python.langchain.com/docs/modules/callbacks/)
- [LangSmith Python SDK](https://github.com/langchain-ai/langsmith-sdk)
