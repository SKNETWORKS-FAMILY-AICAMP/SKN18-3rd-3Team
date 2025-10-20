#!/usr/bin/env python3
"""
KB 특약 OCR 파서 - 지능형 조항 분석 로직으로 개선된 최종 버전
"""
import re
import argparse
from pathlib import Path
from typing import List, Tuple
import pandas as pd
import pdfplumber

# OCR 관련 라이브러리 (선택적)
try:
    from pdf2image import convert_from_path
    import pytesseract
except ImportError:
    convert_from_path = None
    pytesseract = None

# -------------------- 유틸리티 함수 --------------------
def remove_number_suffix(filename: str) -> str:
    """파일명에서 _숫자 부분 제거"""
    return re.sub(r'_\d+$', '', filename)

def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자 제거"""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

def create_product_name(base_filename: str) -> str:
    """상품이름을 '[파일명 기반 상품명] 추가약정서' 형태로 생성"""
    product_part = base_filename
    keywords = ['추가약정서', '약정서', '약관', '규정', '특약']
    for keyword in keywords:
        product_part = product_part.replace(keyword, '')
    product_part = product_part.replace('_', ' ').strip()
    product_part = re.sub(r'\s+', ' ', product_part)
    return f"{product_part} 추가약정서".strip()

# -------------------- 텍스트 추출 및 정제 --------------------
def extract_text_excluding_tables(page: pdfplumber.page.Page) -> str:
    """표 영역을 제외한 텍스트만 추출 (안정성 개선)"""
    try:
        tables = page.find_tables()
        table_bboxes = [table.bbox for table in tables if table.bbox]
        if not table_bboxes:
            return page.extract_text(x_tolerance=2) or ""

        def not_in_table(obj):
            def obj_in_bbox(obj, bbox):
                v_mid = (obj["top"] + obj["bottom"]) / 2
                h_mid = (obj["x0"] + obj["x1"]) / 2
                return (bbox[0] <= h_mid <= bbox[2] and bbox[1] <= v_mid <= bbox[3])
            return not any(obj_in_bbox(obj, bbox) for bbox in table_bboxes)

        return page.filter(not_in_table).extract_text(x_tolerance=2) or ""
    except Exception:
        return page.extract_text() or ""

def clean_text(text: str) -> str:
    """부칙, 페이지 번호, 공통 머리말/꼬리말 등 불필요한 텍스트 제거"""
    if not text: return ""
    
    appendix_match = re.search(r'부\s*칙', text)
    if appendix_match: text = text[:appendix_match.start()]
    
    lines, filtered_lines = text.split('\n'), []
    for line in lines:
        stripped = line.strip()
        if not stripped: continue
        if re.match(r'^\s*[-‐‑‒–—―]*\s*\d+\s*[-‐‑‒–—―]*\s*$', stripped) or \
           (stripped.isdigit() and len(stripped) <= 3) or \
           re.match(r'^\(개정년월일.*', stripped) or \
           re.match(r'^준법감시인 심의필.*', stripped):
            continue
        filtered_lines.append(stripped)
    return '\n'.join(filtered_lines)

# --- ✨✨✨ 핵심 개선: 지능형 조항 파서 ✨✨✨ ---
def parse_articles(text: str) -> List[Tuple[str, str, str]]:
    """
    개선된 조항 파싱 함수. 멀티라인 조항 처리 및 인라인 참조 방지
    """
    if not text: return []
    
    text = clean_text(text)
    
    # 조항의 시작을 찾는 강화된 패턴
    # - 줄의 시작에서만 매치 (^)
    # - 앞에 다른 문자가 없는 경우만 (문단 중간 참조 방지)
    # - "제"로 시작하고 숫자와 "조"가 포함된 패턴
    # - 조항 참조(예: "제 7조 제 4항")와 실제 조항을 구분하기 위해 뒤에 "제"가 바로 오지 않는 경우만
    article_pattern = r'(?m)^(제\s*\d+(?:의\d+)?\s*조)(?=\s*[\(]|\s+(?!제)\S|\s*$)'
    
    # 조항 분할점 찾기
    matches = list(re.finditer(article_pattern, text))
    
    if not matches:
        # 조항이 없으면 전체를 하나의 항목으로 처리
        return [("1", "전체 내용", text.strip())]
    
    articles = []
    
    # 첫 번째 조항 이전의 전문 처리
    preamble = text[:matches[0].start()].strip()
    if preamble:
        articles.append(("전문", "", preamble))
    
    # 각 조항 처리
    for i, match in enumerate(matches):
        # 조항 헤더 ("제 1조")
        article_header = match.group(1)
        article_start = match.end()
        
        # 조항 내용 범위 결정
        if i + 1 < len(matches):
            article_end = matches[i + 1].start()
        else:
            article_end = len(text)
        
        # 조항 내용 추출
        article_content = text[article_start:article_end].strip()
        
        # 조항 번호 추출 (숫자와 "의" 포함)
        article_num = re.sub(r'[^0-9의]', '', article_header)
        
        # 조항 제목과 내용 분리
        article_title = ""
        article_body = article_content
        
        if article_content:
            lines = article_content.split('\n')
            first_line = lines[0].strip()
            
            # 첫 줄에서 제목 패턴 찾기
            # 패턴 1: (제목) 내용
            title_match = re.match(r'^\s*\(([^)]*)\)\s*(.*)', first_line)
            if title_match:
                article_title = title_match.group(1).strip()
                remaining_first_line = title_match.group(2).strip()
                
                # 제목 다음 내용과 나머지 줄들 결합
                remaining_lines = lines[1:] if len(lines) > 1 else []
                if remaining_first_line:
                    remaining_lines.insert(0, remaining_first_line)
                article_body = '\n'.join(remaining_lines).strip()
            
            # 패턴 2: 제목만 있고 다음 줄부터 내용 (괄호 없이)
            elif len(lines) > 1 and not re.search(r'[①②③④⑤⑥⑦⑧⑨⑩]', first_line):
                # 첫 줄이 짧고 설명적이면 제목으로 간주
                if len(first_line) < 50 and not first_line.endswith('다.'):
                    article_title = first_line
                    article_body = '\n'.join(lines[1:]).strip()
        
        # 빈 제목 처리
        if not article_title:
            article_title = ""
        
        articles.append((article_num, article_title, article_body))
    
    return articles

# -------------------- 메인 파이프라인 --------------------
def process_pdf(pdf_path: Path, out_dir: Path, use_ocr: bool, ocr_lang: str, base_input_dir: Path):
    """PDF 처리 - 표 제외, 텍스트 조항만 추출"""
    original_stem = pdf_path.stem
    clean_filename = remove_number_suffix(original_stem)
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += extract_text_excluding_tables(page) + "\n"
            
        if not full_text.strip():
            print(f"[SKIP] {pdf_path.name} (텍스트 내용 없음)")
            return None

        # 파일명 기반으로 상품이름 생성
        product_name = create_product_name(clean_filename)
        
        # CSV 파일명 생성
        safe_filename = sanitize_filename(clean_filename)
        relative = pdf_path.relative_to(base_input_dir)
        out_sub = out_dir / relative.parent
        out_sub.mkdir(parents=True, exist_ok=True)
        
        # 새로 개선된 파서 사용
        articles = parse_articles(full_text)
        
        rows = []
        data_to_append = {
            "은행": "KB_bank",
            "예/적금 또는 대출": "대출",
            "상품이름": product_name
        }
        
        if not articles:
            rows.append({**data_to_append, "조항": "", "조항이름": "", "조항내용": clean_text(full_text)})
        else:
            for num, name, body in articles:
                rows.append({**data_to_append, "조항": str(num), "조항이름": name, "조항내용": body})
        
        df = pd.DataFrame(rows, columns=["은행", "예/적금 또는 대출", "상품이름", "조항", "조항이름", "조항내용"])
        out_csv = out_sub / f"{safe_filename}.csv"
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        return out_csv

def main():
    ap = argparse.ArgumentParser(description="KB 특약 OCR 파서 - 지능형 조항 분석 로직으로 개선된 최종 버전")
    ap.add_argument("--input", "--in-dir", type=str, default=".", help="PDF 루트 폴더 (하위 폴더 재귀 검색)")
    ap.add_argument("--output", "--out-dir", type=str, default="./parsed_csv", help="CSV 출력 폴더")
    ap.add_argument("--use-ocr", "--ocr", action="store_true", help="텍스트 없을 때 OCR 폴백 (Tesseract 필요)")
    ap.add_argument("--ocr-lang", type=str, default="kor", help="Tesseract 언어 코드")
    args = ap.parse_args()
    
    in_dir, out_dir = Path(args.input), Path(args.output)
    
    pdfs = sorted(in_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"[INFO] No PDFs found in {in_dir}")
        return
    
    cnt = 0
    for p in pdfs:
        try:
            # "상품설명서" 포함 파일은 건너뛰기
            if "상품설명서" in p.name:
                print(f"[SKIP] {p.name} (상품설명서 파일)")
                continue

            res = process_pdf(p, out_dir, args.use_ocr, args.ocr_lang, in_dir)
            if res:
                print(f"[OK] {p.name} -> {res.name}")
                cnt += 1
        except Exception as e:
            print(f"[ERROR] {p.name}: {e}")
    
    print(f"[DONE] {cnt} file(s) processed. Output: {out_dir.resolve()}")

if __name__ == "__main__":
    main()