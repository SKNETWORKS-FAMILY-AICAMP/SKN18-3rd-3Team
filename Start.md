# 🏦 은행상품 검색 LLM - 시작 가이드

## 준비사항

`.env` 파일 설정:

### 필수

```bash
# OpenAI API 키 (필수)
OPENAI_API_KEY=your_openai_api_key_here
```

### 선택 (기능 사용 시)

```bash
# 웹 검색 사용 시 (Tavily)
TAVILY_API_KEY=your_tavily_api_key_here

# LangSmith 추적 사용 시
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=rag-banking-system
```

**참고**: Tavily와 LangSmith 없이도 기본 기능은 동작합니다.

## 실행 방법

### 1단계: Docker 시작

```bash
docker-compose up -d
```

DB와 앱이 함께 시작됩니다.

### 2단계: 데이터 임베딩 (최초 1회 또는 데이터 변경 시)

```bash
# Docker 컨테이너 내부에서 임베딩 실행
docker-compose exec app python scripts/index_data.py
```

### 3단계: 브라우저 접속

http://localhost:8501

## 질문 예시

```
우리은행 전세자금대출 금리는?
국민은행 신용대출 조건 알려줘
전문직 대상 대출 상품 추천해줘
```

## 명령어 요약

```bash
# 1. 시작 (DB + 앱)
docker-compose up -d

# 2. 데이터 임베딩 (최초 1회, Docker 내부에서 실행)
docker-compose exec app python scripts/index_data.py

# 재시작
docker-compose restart

# 중지
docker-compose down

# 로그 확인
docker-compose logs -f app
```

## 참고

- 모든 명령어는 Docker 컨테이너에서 실행됩니다
- 로컬 Python 설치 불필요
- `docker-compose exec app python ...`은 app 컨테이너 내부의 Python을 사용합니다
