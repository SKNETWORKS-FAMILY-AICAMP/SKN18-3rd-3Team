# OCR 폴더

은행 약관 PDF 문서를 OCR 처리하여 구조화된 데이터로 변환하는 스크립트 모음입니다.

## 📁 폴더 구조

```
OCR/
├── ocr_대출_추가약정서.py      # 대출 추가약정서 OCR 파서
├── ocr_대출거래약정서.py        # 대출거래약정서 OCR 파서
├── ocr_대출_기타.py             # 기타 대출 약관 OCR 파서
├── ocr_대출_기타2.py            # 기타 대출 약관 OCR 파서 v2
├── ocr_예금 공통약관.py         # 예금 공통약관 OCR 파서
├── ocr_예금특약.py              # 예금 특약 OCR 파서
├── merge_csv.py                 # CSV 병합 유틸리티
├── run_ocr.bat                  # OCR 일괄 실행 배치 파일
├── run_merge.bat                # CSV 병합 배치 파일
└── ocr_output/                  # 출력 폴더
    ├── 대출_unique_csv/         # 대출 약관 CSV
    ├── 대출_unique_pdf/         # 대출 약관 PDF 원본
    ├── 대출_unique_md/          # 대출 약관 마크다운
    ├── 예금_unique_csv/         # 예금 약관 CSV
    └── kb_final_data/           # KB 최종 데이터
```

---

## 🔧 주요 스크립트

### 1. OCR 파서 스크립트

#### `ocr_대출_추가약정서.py`
대출 추가약정서 PDF 문서를 파싱하여 구조화된 CSV로 변환합니다.

**기능:**
- PDF 텍스트 추출 (pdfplumber 사용)
- 조항 자동 인식 및 분리
- 제목 및 본문 구조화
- CSV 및 마크다운 형식 출력

**사용법:**
```bash
python ocr_대출_추가약정서.py --input_dir "./대출_unique_pdf/추가약정서" --output_dir "./ocr_output/대출_unique_csv" --md_dir "./ocr_output/대출_unique_md"
```

**출력 형식:**
- CSV: 조항별로 분리된 구조화 데이터
- 마크다운: 원문 형태의 문서

#### `ocr_대출거래약정서.py`
대출거래약정서 PDF 문서를 파싱합니다.

**특징:**
- 복잡한 계약서 구조 분석
- 다단계 조항 처리 (제1조, 제2조...)
- 하위 항목 자동 인식

#### `ocr_대출_기타.py` / `ocr_대출_기타2.py`
기타 대출 관련 약관 문서를 파싱합니다.

**지원 문서:**
- 근질권 설정계약서
- 금리우대 추가약정서
- 채권양도계약서
- 안전망대출 약정서 등

#### `ocr_예금 공통약관.py`
예금 공통약관 PDF를 파싱합니다.

**특징:**
- 표준 약관 구조 분석
- 조항별 자동 분류
- 예금 상품 공통 조항 처리

#### `ocr_예금특약.py`
예금 특약 문서를 파싱합니다.

**특징:**
- 특약 조항 인식
- 상품별 특약 사항 추출
- 예외 조항 처리

---

### 2. 유틸리티 스크립트

#### `merge_csv.py`
여러 CSV 파일을 하나의 파일로 병합합니다.

**기능:**
- 재귀적 CSV 파일 탐색
- 자동 컬럼 통합
- UTF-8 BOM 인코딩 지원

**사용법:**
```bash
python merge_csv.py --source "ocr_output/대출_unique_csv" --output "ocr_output/merged_all_대출.csv"
```

**파라미터:**
- `--source`: 병합할 CSV 파일들이 있는 폴더
- `--output`: 병합된 결과 파일 경로

---

## 🎯 데이터 구조

### CSV 출력 컬럼

모든 OCR 파서는 다음과 같은 표준 컬럼 구조를 생성합니다:

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| `chunk_id` | 청크 고유 ID | `abc123:제1조:0` |
| `doc_id` | 문서 고유 ID | `abc123def456` |
| `은행명` | 은행 이름 | `국민은행`, `우리은행` |
| `상품종류` | 상품 카테고리 | `대출`, `예금` |
| `상품이름` | 구체적 상품명 | `주택담보대출`, `정기예금` |
| `조항` | 조항 번호 | `제1조`, `제2조` |
| `조항이름` | 조항 제목 | `대출의 목적`, `해지 사유` |
| `text` | 조항 본문 | 전체 텍스트 내용 |

### 텍스트 구조

`text` 컬럼은 다음과 같은 메타데이터를 포함합니다:

```
은행명: 국민은행
상품종류: 대출
상품이름: 주택담보대출 추가약정서
조항: 제1조
조항이름: 대출의 목적

[본문 내용이 이어집니다...]
```

---

## 🚀 실행 방법

### 방법 1: Python 직접 실행

```bash
# 1. 대출 추가약정서 파싱
python ocr_대출_추가약정서.py --input_dir "./대출_unique_pdf/추가약정서" --output_dir "./ocr_output/대출_unique_csv"

# 2. 대출거래약정서 파싱
python ocr_대출거래약정서.py --input_dir "./대출_unique_pdf/약정서" --output_dir "./ocr_output/대출_unique_csv"

# 3. 예금 약관 파싱
python ocr_예금\ 공통약관.py --input_dir "./예금_unique_pdf" --output_dir "./ocr_output/예금_unique_csv"

# 4. CSV 병합
python merge_csv.py --source "ocr_output/대출_unique_csv" --output "ocr_output/merged_all_대출.csv"
```

### 방법 2: 배치 파일 사용 (Windows)

```bash
# 모든 OCR 실행
run_ocr.bat

# CSV 병합만 실행
run_merge.bat
```

---

## 🔍 OCR 처리 로직

### 1. PDF 텍스트 추출
```python
import pdfplumber

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
```

### 2. 조항 인식
정규식을 사용하여 조항 구조를 파악합니다:

```python
# 제1조, 제2조 형태
clause_pattern = r'제\s*\d+\s*조'

# 1., 2., 3. 형태
number_pattern = r'^\s*\d+\.'

# ①, ②, ③ 형태  
circle_pattern = r'[①②③④⑤⑥⑦⑧⑨⑩]'
```

### 3. 구조화
- 제목과 본문 분리
- 조항별 세그먼트 생성
- 메타데이터 추가

### 4. 출력
- CSV: 조항별 행으로 저장
- 마크다운: 원문 형태 보존

---

## 📊 처리 통계

### 대출 약관
- **PDF 파일 수**: 약 45개
- **생성된 CSV 행**: 약 2,000개
- **주요 문서 유형**:
  - 추가약정서 (25개)
  - 대출거래약정서 (8개)
  - 기타 약관 (12개)

### 예금 약관
- **PDF 파일 수**: 약 30개
- **생성된 CSV 행**: 약 1,500개
- **주요 문서 유형**:
  - 공통약관 (15개)
  - 특약 (15개)

### 병합 결과
- **총 CSV 행**: 약 3,500개
- **고유 조항 수**: 약 800개
- **평균 조항 길이**: 200-500자

---

## 🛠️ 의존성

### 필수 패키지

```txt
pdfplumber        # PDF 텍스트 추출
pandas            # 데이터 처리
pathlib           # 파일 경로 처리
```

### 선택적 패키지 (OCR 필요 시)

```txt
pdf2image         # PDF → 이미지 변환
pytesseract       # OCR 엔진
Pillow           # 이미지 처리
```

### 설치

```bash
# 필수 패키지
pip install pdfplumber pandas

# OCR 패키지 (스캔 PDF 처리용)
pip install pdf2image pytesseract Pillow
```

---

## 🐛 트러블슈팅

### 문제 1: PDF 텍스트 추출 실패

**원인**: 스캔된 PDF 또는 이미지 기반 PDF

**해결**:
1. `pytesseract` 설치
2. Tesseract OCR 엔진 설치
3. OCR 모드로 실행

### 문제 2: 조항 인식 오류

**원인**: 비표준 조항 번호 형식

**해결**:
- 정규식 패턴 수정
- 수동 조항 번호 매핑 추가

### 문제 3: 인코딩 오류

**원인**: Windows 콘솔 인코딩 문제

**해결**:
```bash
# UTF-8 모드로 실행
chcp 65001
python ocr_script.py
```

### 문제 4: CSV 병합 시 Permission Denied

**원인**: 출력 파일이 Excel 등에서 열려 있음

**해결**:
1. 파일 닫기
2. 백업 생성 후 원본 삭제
3. 다시 실행

---

## 📈 성능 최적화

### 처리 속도
- **단일 PDF**: 0.5-2초
- **전체 대출 약관 (45개)**: 약 1-2분
- **전체 예금 약관 (30개)**: 약 1분

### 메모리 사용
- **평균**: 100-200MB
- **최대**: 500MB (대용량 PDF)

### 개선 방안
- 배치 처리로 메모리 효율 향상
- 멀티프로세싱 적용 가능
- 캐싱으로 중복 처리 방지

---

## 🔄 워크플로우

```
1. PDF 수집
   └─> 대출_unique_pdf/, 예금_unique_pdf/

2. OCR 실행
   ├─> ocr_대출_추가약정서.py
   ├─> ocr_대출거래약정서.py
   ├─> ocr_예금 공통약관.py
   └─> ocr_예금특약.py

3. CSV 생성
   ├─> 대출_unique_csv/
   └─> 예금_unique_csv/

4. CSV 병합
   └─> merge_csv.py
       └─> merged_all_대출.csv
       └─> merged_all_예금.csv

5. 데이터 정제 및 임베딩
   └─> ../embedding/ 폴더로 이동
```

---

## 📝 참고사항

### 지원 PDF 형식
- ✅ 텍스트 기반 PDF
- ✅ 스캔 PDF (OCR 사용 시)
- ⚠️ 보호된 PDF (제한적)

### 지원 약관 유형
- 대출 추가약정서
- 대출거래약정서
- 예금 공통약관
- 예금 특약
- 기타 계약서 (근질권, 채권양도 등)

### 출력 인코딩
- CSV: UTF-8 with BOM (Excel 호환)
- 마크다운: UTF-8

---

## 🎓 추가 리소스

### 정규식 패턴
```python
# 조항 패턴
CLAUSE_PATTERN = r'제\s*\d+\s*조'

# 번호 매기기
NUMBER_PATTERN = r'^\s*\d+\.'

# 원형 번호
CIRCLE_PATTERN = r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]'

# 괄호 번호
PAREN_PATTERN = r'\(\d+\)'
```

### CSV 병합 예시
```python
import pandas as pd
from pathlib import Path

# 모든 CSV 읽기
csv_files = Path("ocr_output/대출_unique_csv").rglob("*.csv")
df_list = [pd.read_csv(f, encoding='utf-8-sig') for f in csv_files]

# 병합
merged_df = pd.concat(df_list, ignore_index=True)

# 저장
merged_df.to_csv("merged.csv", index=False, encoding='utf-8-sig')
```

---

## 📄 라이센스

이 프로젝트는 교육 목적으로 작성되었습니다.

---

## 🤝 기여

버그 리포트나 개선 제안은 환영합니다!

