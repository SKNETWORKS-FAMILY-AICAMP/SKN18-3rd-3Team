# LangSmith 모니터링

LLM 애플리케이션 추적 및 디버깅 도구

## 기능

- RAG 파이프라인 각 단계 추적
- 실행 시간 및 토큰 사용량 모니터링
- 사용자 피드백 수집

## 빠른 시작

### 1. 환경 설정 (.env)

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_api_key_here
LANGCHAIN_PROJECT=my-project
```

### 2. 사용

```python
from rag.graph.build import create_rag_system

# LangSmith 활성화
graph = create_rag_system(
    llm=llm,
    vectorstore=vectorstore,
    enable_langsmith=True
)

# 실행 (자동 추적)
result = graph.invoke({"question": "질문"})
```

## 파일

- `tracer.py`: 추적 설정 관리
- `utils.py`: 피드백 기록, 실행 정보 조회
- `USAGE.md`: 상세 사용 가이드

## 대시보드

https://smith.langchain.com 에서 추적 결과 확인

## 참고

- API 키: https://smith.langchain.com 에서 발급
- 상세 가이드: `USAGE.md` 참조
