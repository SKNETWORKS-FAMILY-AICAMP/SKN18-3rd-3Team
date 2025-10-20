# Embedding 폴더

은행 약관 문서의 의미론적 청킹(Semantic Chunking) 및 임베딩 생성을 위한 스크립트와 데이터가 포함된 폴더입니다.

## 📁 파일 구조

### 📜 스크립트

#### `semantic_chunk_pipeline_nokss.py`
KSS 없이 정규식 기반으로 문장을 분리하고 의미론적 청킹을 수행하는 메인 파이프라인입니다.

**기능:**
- 정규식 기반 문장 분리 (빠른 처리)
- OpenAI `text-embedding-3-small` 모델로 문장별 임베딩 생성
- 코사인 유사도 기반 청크 병합
- 진행바 표시로 실시간 진행 상황 확인

**사용법:**
```bash
python semantic_chunk_pipeline_nokss.py \
  --input "우리+국민_약관_병합본_v2.csv" \
  --out_chunks "우리+국민_약관_semantic_chunks.csv" \
  --out_sents "우리+국민_약관_sentences.csv" \
  --cos_threshold 0.80 \
  --max_tokens 600 \
  --target_tokens 480 \
  --batch_size 128 \
  --model "text-embedding-3-small"
```

**파라미터:**
- `--input`: 입력 CSV 파일 (병합된 약관 데이터)
- `--out_chunks`: 출력 청크 CSV 파일
- `--out_sents`: 출력 문장 CSV 파일
- `--cos_threshold`: 청크 병합 코사인 유사도 임계값 (기본: 0.80)
- `--max_tokens`: 청크 최대 토큰 수 (기본: 600)
- `--target_tokens`: 청크 목표 토큰 수 (기본: 480)
- `--batch_size`: 임베딩 배치 크기 (기본: 128)
- `--model`: OpenAI 임베딩 모델 (기본: text-embedding-3-small)

#### `load_embedding.py`
청크 CSV 파일을 PostgreSQL + pgvector 데이터베이스에 로드하는 스크립트입니다.

**기능:**
- CSV 파일에서 청크 데이터 읽기
- OpenAI API로 각 청크의 임베딩 생성
- PostgreSQL + pgvector 데이터베이스에 UPSERT

**사용법:**
```bash
# 환경 변수 설정
$env:POSTGRES_DB="bank_rag_db"

# 실행
python load_embedding.py --csv "우리+국민_약관_semantic_chunks_reassigned.csv" --batch_size 128
```

**필수 환경 변수:**
- `OPENAI_API_KEY`: OpenAI API 키
- `POSTGRES_HOST`: PostgreSQL 호스트 (기본: localhost)
- `POSTGRES_PORT`: PostgreSQL 포트 (기본: 5432)
- `POSTGRES_DB`: 데이터베이스 이름 (기본: ragdb)
- `POSTGRES_USER`: 사용자 이름 (기본: postgres)
- `POSTGRES_PASSWORD`: 비밀번호

#### `reassign_chunk_ids.py`
중복된 chunk_id에 고유한 ID를 재할당하는 유틸리티 스크립트입니다.

**사용법:**
```bash
python reassign_chunk_ids.py
```

자동으로 `우리+국민_약관_semantic_chunks.csv`를 읽고 `우리+국민_약관_semantic_chunks_reassigned.csv`를 생성합니다.

---

## 📊 데이터 파일

### 입력 데이터

#### `우리+국민_약관_병합본_v2.csv`
우리은행과 국민은행의 약관 데이터를 병합한 원본 파일입니다.

**컬럼:**
- `chunk_id`: 청크 고유 ID
- `doc_id`: 문서 ID
- `은행명`: 은행 이름 (우리은행, 국민은행)
- `상품종류`: 상품 종류 (예금, 대출 등)
- `상품이름`: 상품명
- `조항`: 조항 번호
- `조항이름`: 조항 제목
- `text`: 약관 본문 텍스트

### 출력 데이터

#### `우리+국민_약관_semantic_chunks.csv`
의미론적 청킹이 완료된 청크 데이터입니다.

**특징:**
- 코사인 유사도 0.80 이상인 인접 문장들을 하나의 청크로 병합
- 최대 600 토큰, 목표 480 토큰으로 청크 크기 제한
- 청크 ID 형식: `{doc_id}:{조항}:{청크번호}`

#### `우리+국민_약관_semantic_chunks_reassigned.csv`
중복 제거 및 chunk_id가 재할당된 최종 데이터입니다.

**개선 사항:**
- 모든 청크가 고유한 chunk_id 보유
- 중복된 ID에는 `_0`, `_1`, `_2` 등의 접미사 추가
- 총 3,959개의 고유한 청크

#### `우리+국민_약관_sentences.csv`
문장 단위로 분리된 데이터 (디버깅 및 분석용)입니다.

**컬럼:**
- `doc_id`: 문서 ID
- `chunk_id`: 원본 청크 ID
- `은행명`: 은행 이름
- `상품이름`: 상품명
- `조항`: 조항 번호
- `조항이름`: 조항 제목
- `sent_idx`: 문장 인덱스
- `sentence`: 분리된 문장 텍스트

#### `우리+국민_약관_semantic_chunks_boundary_similarity.csv`
청크 경계 결정 시 코사인 유사도 값 (분석 및 튜닝용)입니다.

**컬럼:**
- `doc_id`: 문서 ID
- `orig_chunk_id`: 원본 청크 ID
- `i`: 문장 인덱스
- `cosine`: 인접 문장 간 코사인 유사도
- `decision`: 병합 결정 (merge/split)

---

## 🔧 의존성

### 필수 패키지
```txt
pandas
numpy
openai>=1.0.0
psycopg2-binary
python-dotenv
tqdm
```

### 설치
```bash
pip install pandas numpy openai psycopg2-binary python-dotenv tqdm
```

---

## 🚀 전체 워크플로우

### 1단계: 의미론적 청킹 수행
```bash
python semantic_chunk_pipeline_nokss.py \
  --input "우리+국민_약관_병합본_v2.csv" \
  --out_chunks "우리+국민_약관_semantic_chunks.csv" \
  --out_sents "우리+국민_약관_sentences.csv" \
  --cos_threshold 0.80 \
  --max_tokens 600 \
  --target_tokens 480 \
  --batch_size 128
```

### 2단계: Chunk ID 재할당
```bash
python reassign_chunk_ids.py
```

### 3단계: PostgreSQL + pgvector에 로드
```bash
# 환경 변수 설정
$env:POSTGRES_DB="bank_rag_db"

# 데이터 로드
python load_embedding.py \
  --csv "우리+국민_약관_semantic_chunks_reassigned.csv" \
  --batch_size 128
```

---

## 📈 통계

### 처리 결과
- **입력 청크**: 약 3,900개
- **출력 청크**: 3,959개 (의미론적 재구성)
- **고유 청크**: 3,959개 (중복 제거 후)
- **평균 토큰**: ~480 토큰/청크
- **최대 토큰**: 600 토큰
- **임베딩 차원**: 1536차원 (text-embedding-3-small)

### 청킹 전략
- **코사인 유사도 임계값**: 0.80
  - 0.80 이상: 청크 병합
  - 0.80 미만: 새 청크 생성
- **토큰 제한**:
  - 목표: 480 토큰 (최적 컨텍스트 크기)
  - 최대: 600 토큰 (안전 상한선)

---

## 🔍 참고사항

### 환경 변수 설정
프로젝트 루트의 `.env` 파일에 다음 변수를 설정하세요:

```bash
# OpenAI
OPENAI_API_KEY=sk-proj-...

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bank_rag_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

### 처리 시간
- **의미론적 청킹**: 약 5-10분 (3,900개 청크, OpenAI API 호출)
- **데이터베이스 로드**: 약 2-5분 (3,959개 청크, 임베딩 생성 포함)

### 비용 추정
- **text-embedding-3-small**: $0.00002 / 1K 토큰
- **약 3,959개 청크 × 평균 480 토큰**: ~1,900K 토큰
- **예상 비용**: 약 $0.04 (임베딩 생성 1회)

---

## 🐛 트러블슈팅

### 문제: UnicodeEncodeError
**원인**: Windows 콘솔에서 이모지 출력 불가

**해결**: 이모지를 텍스트로 변경 (이미 적용됨)

### 문제: Chunk ID 중복
**원인**: 의미론적 청킹 과정에서 동일 ID 생성

**해결**: `reassign_chunk_ids.py` 실행으로 고유 ID 재할당

### 문제: 파일 경로 인코딩 오류
**원인**: Windows에서 한글 경로 처리 문제

**해결**: 
- 절대 경로 사용
- 또는 해당 폴더로 이동 후 실행

### 문제: OpenAI API 키 미설정
**원인**: OPENAI_API_KEY 환경 변수 누락

**해결**: `.env` 파일에 API 키 추가

---

## 📝 라이센스

이 프로젝트는 교육 목적으로 작성되었습니다.

