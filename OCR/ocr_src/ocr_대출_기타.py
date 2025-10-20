#!/usr/bin/env python3
"""
기타 폴더 파일에 있는 범용 금융문서 OCR 파서 - 파일 유형을 자동 감지하여 맞춤형으로 조항 추출
"""
import re
import argparse
from pathlib import Path
from typing import List, Tuple
import pandas as pd
import pdfplumber

def get_document_type(filename: str) -> str:
    """파일명 키워드를 기반으로 문서 유형을 반환합니다."""
    if '상품설명서' in filename or '설명서' in filename:
        return '상품설명서'
    if '약관' in filename:
        return '약관'
    if '약정서' in filename or '계약서' in filename:
        return '약정서'
    return '기타' # 기본값

def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자 제거 및 길이 제한"""
    name = re.sub(r'[\\/*?:"<>|]', '_', name).strip()
    return name[:100]

def extract_text_excluding_tables(page: pdfplumber.page.Page) -> str:
    """페이지에서 표(table) 영역을 제외한 텍스트만 추출합니다."""
    try:
        tables = page.find_tables()
        table_bboxes = [table.bbox for table in tables]

        if not table_bboxes:
            return page.extract_text(x_tolerance=2) or ""

        non_table_chars = []
        for char in page.chars:
            char_bbox = (char['x0'], char['top'], char['x1'], char['bottom'])
            in_table = any(
                (tbox[0] <= char['x0'] <= tbox[2] and tbox[1] <= char['top'] <= tbox[3])
                for tbox in table_bboxes
            )
            if not in_table:
                non_table_chars.append(char['text'])
        return "".join(non_table_chars)
    except Exception:
        return page.extract_text(x_tolerance=2) or ""

def clean_and_prepare_text(text: str) -> str:
    """추출된 전체 텍스트에서 불필요한 요소를 제거합니다."""
    # 체크박스 및 특정 기호 제거
    text = re.sub(r'[☐☑]', '', text)
    
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # 머리말/꼬리말, 페이지 번호, 양식 코드 등 필터링
        if re.match(r'^\(개정년월일.*', stripped) or \
           re.match(r'^준법감시인 심의필.*', stripped) or \
           re.match(r'^\s*[-‐‑‒–—―]*\s*\d+\s*[-‐‑‒–—―]*\s*$', stripped) or \
           re.match(r'^\s*[A-Z]?\d+.*\(.*개정\)$', stripped) or \
           re.match(r'^\(\d/\d\)$', stripped) or \
           stripped in ["은행용", "고객용"]:
            continue
        if stripped:
            cleaned_lines.append(stripped)
            
    # 부칙 이후 내용 제거
    full_text = '\n'.join(cleaned_lines)
    appendix_match = re.search(r'부\s*칙', full_text)
    if appendix_match:
        full_text = full_text[:appendix_match.start()]
        
    return full_text.strip()

def parse_formal_articles(text: str) -> List[Tuple[str, str, str]]:
    """'제N조' 형식의 정식 조항을 파싱합니다."""
    # 줄 시작(^)에서 '제 N조' 패턴을 찾아 분리
    chunks = re.split(r'(?m)(^제\s*\d+(?:의\d+)?\s*조)', text)
    articles = []
    if not chunks or len(chunks) < 2:
        return [("1", "전체 내용", text)]

    # 제1조부터 처리
    for i in range(1, len(chunks), 2):
        header = chunks[i]
        content = chunks[i+1].strip()
        
        article_num = re.sub(r'[^0-9의-]', '', header)
        lines = content.split('\n')
        first_line = lines[0].strip() if lines else ""
        
        article_title, article_body = "", ""
        match_paren = re.match(r'^\(([^)]*)\)\s*(.*)', first_line)
        if match_paren:
            article_title = match_paren.group(1).strip()
            body_parts = [match_paren.group(2).strip()] + lines[1:]
            article_body = '\n'.join(filter(None, body_parts))
        else:
            article_title = first_line
            article_body = '\n'.join(lines[1:])
            
        articles.append((article_num, article_title.strip(), article_body.strip()))
    return articles

def parse_descriptive_document(text: str) -> List[Tuple[str, str, str]]:
    """'■', '•' 등 기호로 시작하는 설명서 형식의 문서를 파싱합니다."""
    # 기호로 시작하는 제목을 기준으로 텍스트 분리
    chunks = re.split(r'(?m)(^[■•▶☑]\s*)', text)
    sections = []
    if not chunks or len(chunks) < 2:
        return [("1", "전체 내용", text)]

    # 첫 부분은 보통 문서 개요이므로 별도 처리
    if chunks[0].strip():
        sections.append(("개요", chunks[0].strip()))

    # 각 섹션 처리
    for i in range(1, len(chunks), 2):
        content = chunks[i+1].strip()
        lines = content.split('\n')
        title = lines[0].strip()
        body = '\n'.join(lines[1:]).strip()
        sections.append((title, body))
        
    # DataFrame 형식으로 변환
    return [(str(i+1), title, body) for i, (title, body) in enumerate(sections)]

def process_pdf(pdf_path: Path, out_dir: Path):
    """단일 PDF 파일을 처리하여 유형에 맞게 파싱하고 CSV로 저장합니다."""
    doc_type = get_document_type(pdf_path.name)
    
    full_text_raw = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text_raw += extract_text_excluding_tables(page) + "\n"

    prepared_text = clean_and_prepare_text(full_text_raw)
    
    articles = []
    if doc_type in ['약관', '약정서', '기타']:
        articles = parse_formal_articles(prepared_text)
    elif doc_type == '상품설명서':
        articles = parse_descriptive_document(prepared_text)

    if articles:
        df = pd.DataFrame(articles, columns=["조항", "조항이름", "조항내용"])
        df['은행'] = "KB_bank"
        df['상품이름'] = re.sub(r'_\d+$', '', pdf_path.stem).replace('_', ' ')
        df['예/적금 또는 대출'] = "대출"
        
        df = df[["은행", "예/적금 또는 대출", "상품이름", "조항", "조항이름", "조항내용"]]

        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv_path = out_dir / f"{sanitize_filename(pdf_path.stem)}.csv"
        df.to_csv(out_csv_path, index=False, encoding='utf-8-sig')
        print(f"[OK] '{pdf_path.name}' ({doc_type}) -> '{out_csv_path.name}'")
    else:
        print(f"[SKIP] '{pdf_path.name}' (내용을 파싱할 수 없음)")

def main():
    parser = argparse.ArgumentParser(description="범용 금융문서 OCR 파서")
    parser.add_argument("--in-dir", type=str, required=True, help="PDF 파일이 있는 입력 폴더")
    parser.add_argument("--out-dir", type=str, required=True, help="추출된 CSV를 저장할 출력 폴더")
    args = parser.parse_args()

    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    if not in_dir.is_dir():
        print(f"[ERROR] 입력 폴더를 찾을 수 없습니다: {in_dir}")
        return

    pdf_files = sorted(in_dir.rglob("*.pdf"))
    if not pdf_files:
        print(f"[INFO] '{in_dir}'에서 PDF 파일을 찾을 수 없습니다.")
        return

    for pdf_path in pdf_files:
        try:
            process_pdf(pdf_path, out_dir)
        except Exception as e:
            print(f"[ERROR] 처리 중 오류 발생 '{pdf_path.name}': {e}")

if __name__ == "__main__":
    main()