#!/usr/bin/env python3
"""
기타2 폴더 파일에 있는 범용 금융문서 OCR 파서 - 지능형 섹션 분리 및 텍스트 추출 품질 향상 (오류 수정)
"""
import re
import argparse
from pathlib import Path
from typing import List, Tuple, Dict
import pandas as pd
import pdfplumber

# --- ✨✨✨ 누락된 함수 추가 ✨✨✨ ---
def get_document_type(filename: str) -> str:
    """파일명 키워드를 기반으로 문서 유형을 반환합니다."""
    if '상품설명서' in filename or '설명서' in filename:
        return '상품설명서'
    if '약관' in filename:
        return '약관'
    if '약정서' in filename or '계약서' in filename:
        return '약정서'
    return '기타'

def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자 제거 및 길이 제한"""
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()[:100]

def create_base_product_name(filename_stem: str) -> str:
    """파일명에서 숫자와 문서 종류 키워드를 제거하여 순수 상품명을 추출합니다."""
    base_name = re.sub(r'_\d+$', '', filename_stem)
    keywords = ['대출거래약정서', '상품설명서', '약관', '계약서', '설명서', 'Ⅰ', 'Ⅱ', 'Ⅲ', '채권양도계약서', '근질권설정계약서']
    for keyword in keywords:
        base_name = base_name.replace(keyword, '')
    product_part = base_name.replace('_', ' ').strip()
    return re.sub(r'\s+', ' ', product_part)

def extract_text_robust(page: pdfplumber.page.Page) -> str:
    """[핵심 개선] 표 영역의 문자를 필터링하여 제외하고 텍스트를 추출합니다."""
    try:
        tables = page.find_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
        if not tables: tables = page.find_tables()
        table_bboxes = [table.bbox for table in tables if table.bbox]

        if not table_bboxes: return page.extract_text(x_tolerance=2) or ""

        def not_within_bboxes(obj):
            def obj_in_bbox(obj, bbox):
                v_mid = (obj["top"] + obj["bottom"]) / 2
                h_mid = (obj["x0"] + obj["x1"]) / 2
                return (bbox[0] <= h_mid <= bbox[2] and bbox[1] <= v_mid <= bbox[3])
            return not any(obj_in_bbox(obj, bbox) for bbox in table_bboxes)

        page_without_tables = page.filter(not_within_bboxes)
        return page_without_tables.extract_text(x_tolerance=2) or ""
    except Exception:
        return page.extract_text(x_tolerance=2) or ""

def clean_common_patterns(text: str) -> str:
    """문서에서 공통적으로 나타나는 불필요한 패턴을 제거합니다."""
    patterns_to_remove = [
        r'^\(개정년월일.*\n?', r'^준법감시인 심의필.*\n?', r'^\s*[A-Z]?\d+.*\(.*개정\)\s*\n?',
        r'.*\(서명\s*또는\s*인\)', r'^\s*팀원\s*팀장\s*부점장\s*$', r'^본인\s*및\s*자서확인\s*$',
        r'^\(\d/\d\)\s*\n?', r'은행용|고객용', r'^\s*\[생년월일.*', r'^\s*\[법인등록번호.*'
    ]
    for pattern in patterns_to_remove:
        text = re.sub(pattern, '', text, flags=re.MULTILINE)
    
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()

def parse_formal_articles(text: str) -> List[Tuple[str, str, str]]:
    """'제N조' 형식의 정식 조항을 '전문'과 함께 파싱합니다."""
    chunks = re.split(r'(?m)(^제\s*\d+(?:의\d+)?\s*조)', text)
    articles = []
    
    preamble = chunks[0].strip()
    if preamble: articles.append(("전문", "", preamble))
        
    for i in range(1, len(chunks), 2):
        header, content = chunks[i], chunks[i+1].strip()
        num = re.sub(r'[^0-9의-]', '', header)
        lines = content.split('\n')
        first_line = lines[0].strip() if lines else ""
        
        title, body = "", ""
        match = re.match(r'^\s*([^\(]*)(?:\(([^)]*)\))?\s*(.*)', first_line)
        if match:
            title_part1, title_part2, body_start = match.group(1).strip(), (match.group(2) or "").strip(), match.group(3).strip()
            title = f"{title_part1} {title_part2}".strip()
            body = '\n'.join([body_start] + lines[1:]).strip()
        else:
            title, body = first_line, '\n'.join(lines[1:]).strip()
            
        articles.append((num, title, body))
        
    if not articles and text: articles.append(("1", "전체 내용", text))
    return articles

def parse_explanation_page(text: str) -> List[Tuple[str, str, str]]:
    """'알아두어야 할 사항' 페이지의 구조를 파싱합니다."""
    major_headings = ['채권양도 란', '담보종류에 따른 책임범위', '담보제공자가 연대보증까지 서는 경우']
    pattern = f"({'|'.join(re.escape(h) for h in major_headings)})"
    chunks = re.split(pattern, text)
    
    articles, num = [], 1
    for i in range(1, len(chunks), 2):
        title, body = chunks[i].strip(), chunks[i+1].strip()
        clean_title = re.sub(r'[「」]', '', title)
        body_lines = [re.sub(r'^\s*-\s*', '', line).strip() for line in body.split('\n')]
        clean_body = '\n'.join(filter(None, body_lines))
        articles.append((str(num), clean_title, clean_body))
        num += 1
    return articles

def process_pdf(pdf_path: Path, out_dir: Path):
    """PDF를 섹션별로 처리하고 CSV로 저장합니다."""
    full_text_raw = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text_raw += extract_text_robust(page) + "\n"

    base_product_name = create_base_product_name(pdf_path.stem)
    all_rows = []
    
    explanation_keyword = r'(채권양도인이\s*꼭\s*알아두어야\s*할\s*사항|담보제공자\s*\(.*가\s*꼭\s*알아두어야\s*할\s*사항)'
    match = re.search(explanation_keyword, full_text_raw, re.MULTILINE)
    
    main_text = full_text_raw
    if match:
        main_text = full_text_raw[:match.start()]
        explanation_text = full_text_raw[match.start():]
        
        cleaned_explanation = clean_common_patterns(explanation_text)
        articles = parse_explanation_page(cleaned_explanation)
        product_name = f"{base_product_name} 알아두어야 할 사항".strip()
        for num, name, body in articles:
            all_rows.append({ "은행": "KB_bank", "예/적금 또는 대출": "대출", "상품이름": product_name, "조항": num, "조항이름": name, "조항내용": body })

    cleaned_main = clean_common_patterns(main_text)
    if cleaned_main:
        doc_type = get_document_type(pdf_path.name)
        articles = parse_formal_articles(cleaned_main)
        product_name = f"{base_product_name} {doc_type}".strip()
        for num, name, body in articles:
            all_rows.append({ "은행": "KB_bank", "예/적금 또는 대출": "대출", "상품이름": product_name, "조항": num, "조항이름": name, "조항내용": body })

    if all_rows:
        df = pd.DataFrame(all_rows)[["은행", "예/적금 또는 대출", "상품이름", "조항", "조항이름", "조항내용"]]
        out_csv_path = out_dir / f"{sanitize_filename(pdf_path.stem)}.csv"
        out_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_csv_path, index=False, encoding="utf-8-sig")
        print(f"[OK] '{pdf_path.name}' -> '{out_csv_path.name}'")
    else:
        print(f"[SKIP] '{pdf_path.name}' (파싱할 내용 없음)")

def main():
    parser = argparse.ArgumentParser(description="범용 금융문서 OCR 파서 (지능형 텍스트 추출 및 섹션 분리)")
    parser.add_argument("--input", type=str, required=True, help="PDF 파일이 있는 입력 폴더")
    parser.add_argument("--output", type=str, required=True, help="추출된 CSV를 저장할 출력 폴더")
    args = parser.parse_args()

    in_dir, out_dir = Path(args.input), Path(args.output)
    if not in_dir.is_dir():
        print(f"[ERROR] 입력 폴더를 찾을 수 없습니다: {in_dir}")
        return

    for pdf_path in sorted(in_dir.rglob("*.pdf")):
        try:
            process_pdf(pdf_path, out_dir)
        except Exception as e:
            print(f"[ERROR] 처리 중 오류 발생 '{pdf_path.name}': {e}")

if __name__ == "__main__":
    main()