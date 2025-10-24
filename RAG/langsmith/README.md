# LangSmith 통합 모듈

이 폴더는 LangSmith를 사용한 LLM 애플리케이션 모니터링, 추적, 디버깅 기능을 제공합니다.

## LangSmith란?

LangSmith는 LangChain에서 제공하는 LLM 애플리케이션 개발 플랫폼으로, 다음과 같은 기능을 제공합니다:

- **추적(Tracing)**: LLM 호출, 체인 실행, 에이전트 동작 등을 실시간으로 추적
- **모니터링**: 응답 시간, 토큰 사용량, 비용 등을 모니터링
- **디버깅**: 각 단계별 입출력을 확인하여 문제 진단
- **평가**: 프롬프트 및 모델 성능을 평가하고 비교
- **피드백**: 사용자 피드백을 수집하여 모델 개선

## 왜 필요한가?

RAG 시스템은 여러 단계(검색, 임베딩, LLM 호출 등)로 구성되어 있어 디버깅이 어렵습니다. LangSmith를 사용하면:

1. **투명성**: 각 단계에서 무슨 일이 일어나는지 명확히 파악
2. **성능 최적화**: 병목 지점을 찾아 개선
3. **비용 관리**: 토큰 사용량과 API 호출 비용 추적
4. **품질 개선**: 실제 사용 데이터를 기반으로 프롬프트 및 검색 로직 개선
5. **문제 해결**: 프로덕션 환경에서 발생한 오류를 빠르게 진단

## 파일 구조

### `__init__.py`
모듈 초기화 파일로, 외부에서 사용할 주요 클래스를 export합니다.

```python
from RAG.langsmith import LangSmithTracer
```

### `tracer.py`
**핵심 추적 기능을 담당하는 파일**

#### 주요 기능:
- LangSmith 추적 활성화/비활성화 관리
- 환경 변수에서 설정 로드
- LangChain 콜백 매니저 생성
- 실행 컨텍스트 설정 (프로젝트명, 태그, 메타데이터)

#### 사용 예시:
```python
from RAG.langsmith import LangSmithTracer

tracer = LangSmithTracer()

if tracer.is_enabled():
    # LangChain 실행 시 config 전달
    config = tracer.get_config()
    result = chain.invoke(input_data, config=config)
```

#### 왜 필요한가:
- RAG 파이프라인의 모든 단계를 자동으로 추적
- 검색된 문서, 생성된 프롬프트, LLM 응답 등을 시각화
- 각 단계의 실행 시간과 비용을 측정

### `utils.py`
**피드백 및 실행 정보 조회 유틸리티**

#### 주요 기능:

1. **`get_langsmith_client()`**
   - LangSmith API 클라이언트 생성
   - 환경 변수에서 API 키와 엔드포인트 로드

2. **`log_feedback()`**
   - 사용자 피드백을 LangSmith에 기록
   - 점수(score), 코멘트 등을 저장
   - 모델 성능 개선을 위한 데이터 수집

3. **`get_run_info()`**
   - 특정 실행(run)의 상세 정보 조회
   - 입력, 출력, 실행 시간, 에러 등을 확인
   - 디버깅 및 분석에 활용

#### 사용 예시:
```python
from RAG.langsmith.utils import log_feedback, get_run_info

# 사용자가 답변에 만족했을 때
log_feedback(
    run_id="abc123",
    score=1.0,
    feedback_key="user_satisfaction",
    comment="정확한 답변이었습니다"
)

# 특정 실행 정보 조회
run_info = get_run_info("abc123")
print(f"실행 시간: {run_info['end_time'] - run_info['start_time']}")
```

#### 왜 필요한가:
- 사용자 피드백을 수집하여 모델 개선
- A/B 테스트 결과 분석
- 프로덕션 환경에서 발생한 문제 추적

## 설정 방법

### 1. 환경 변수 설정 (.env)

```bash
# LangSmith 추적 활성화
LANGCHAIN_TRACING_V2=true

# LangSmith API 엔드포인트
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# LangSmith API 키 (https://smith.langchain.com에서 발급)
LANGCHAIN_API_KEY=your_api_key_here

# 프로젝트 이름 (LangSmith 대시보드에서 구분용)
LANGCHAIN_PROJECT=my-rag-project
```

### 2. LangSmith 계정 생성

1. https://smith.langchain.com 방문
2. 계정 생성 및 로그인
3. Settings > API Keys에서 API 키 발급
4. `.env` 파일에 API 키 추가

### 3. 의존성 설치

```bash
pip install langsmith langchain
```

## 통합 예시

### RAG 엔진에 통합

```python
from RAG.langsmith import LangSmithTracer
from RAG.rag.engine import RAGEngine

class MonitoredRAGEngine(RAGEngine):
    def __init__(self):
        super().__init__()
        self.tracer = LangSmithTracer()
    
    def query(self, question: str):
        config = self.tracer.get_config()
        # LangChain 체인 실행 시 config 전달
        return self.chain.invoke(
            {"question": question},
            config=config
        )
```

### 피드백 수집

```python
from RAG.langsmith.utils import log_feedback

def handle_user_feedback(run_id: str, is_helpful: bool, comment: str = None):
    score = 1.0 if is_helpful else 0.0
    log_feedback(
        run_id=run_id,
        score=score,
        feedback_key="helpfulness",
        comment=comment
    )
```

## 대시보드 활용

LangSmith 대시보드(https://smith.langchain.com)에서 확인할 수 있는 정보:

1. **Traces**: 각 실행의 전체 흐름 시각화
   - 검색 쿼리 → 임베딩 → 벡터 검색 → LLM 호출 → 응답 생성

2. **Runs**: 모든 실행 기록
   - 실행 시간, 토큰 사용량, 비용
   - 입력/출력 데이터
   - 에러 로그

3. **Feedback**: 수집된 피드백 분석
   - 평균 만족도
   - 문제가 있는 쿼리 패턴 파악

4. **Datasets**: 테스트 데이터셋 관리
   - 프롬프트 버전 비교
   - 회귀 테스트

## 주의사항

1. **API 키 보안**: `.env` 파일을 `.gitignore`에 추가하여 커밋하지 않도록 주의
2. **비용**: LangSmith는 무료 티어가 있지만, 대량 사용 시 비용 발생 가능
3. **성능**: 추적 기능이 약간의 오버헤드를 추가하므로, 필요시 비활성화 가능
4. **개인정보**: 민감한 데이터가 LangSmith 서버로 전송되므로 데이터 정책 확인 필요

## 개발 vs 프로덕션

### 개발 환경
```bash
LANGCHAIN_TRACING_V2=true  # 모든 실행 추적
LANGCHAIN_PROJECT=dev-rag
```

### 프로덕션 환경
```bash
LANGCHAIN_TRACING_V2=true  # 샘플링 또는 에러만 추적
LANGCHAIN_PROJECT=prod-rag
```

프로덕션에서는 샘플링 비율을 조정하거나, 에러가 발생한 경우만 추적하여 비용을 절감할 수 있습니다.

## 참고 자료

- [LangSmith 공식 문서](https://docs.smith.langchain.com/)
- [LangChain 콜백 가이드](https://python.langchain.com/docs/modules/callbacks/)
- [LangSmith Python SDK](https://github.com/langchain-ai/langsmith-sdk)
