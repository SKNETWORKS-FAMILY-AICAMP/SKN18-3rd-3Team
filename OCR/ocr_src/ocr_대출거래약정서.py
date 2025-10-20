#!/usr/bin/env python3
"""
대출거래약정서 OCR 파서 - 여러 섹션 분리 및 표 제외 텍스트 추출 (상품이름 로직 수정)
"""
import re
import argparse
from pathlib import Path
from typing import List, Tuple, Dict
import pandas as pd
import pdfplumber

# OCR 관련 라이브러리 (선택적)
try:
    from pdf2image import convert_from_path
    import pytesseract
except ImportError:
    convert_from_path = None
    pytesseract = None

# -------------------- 텍스트 추출 및 정리 --------------------
def extract_title(page: pdfplumber.page.Page) -> str:
    """페이지에서 제목 추출"""
    text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines:
        if len(line) > 3 and ('대출거래약정서' in line or '약관' in line):
            return line
    return lines[0] if lines else ""

def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자 제거"""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

def infer_bank(title: str) -> str:
    """은행명을 KB_bank로 고정"""
    return "KB_bank"

def infer_product_type(title: str) -> str:
    """상품 유형을 '대출'로 고정"""
    return "대출"

# --- ✨✨✨ 새로운 함수 추가 ✨✨✨ ---
def create_base_product_name(filename_stem: str) -> str:
    """
    파일명(확장자 제외)에서 숫자 접미사와 약정서 관련 키워드를 제거하여
    순수한 상품 이름 부분을 추출합니다.
    """
    # 1. _숫자 또는 __숫자 제거
    base_name = re.sub(r'_\d+$', '', filename_stem)
    
    # 2. 약정서 관련 키워드 및 로마 숫자 제거
    keywords_to_remove = ['대출거래약정서', 'Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ']
    for keyword in keywords_to_remove:
        base_name = base_name.replace(keyword, '')
        
    # 3. 언더스코어(_)를 공백으로 바꾸고, 연속된 공백 정리
    product_part = base_name.replace('_', ' ').strip()
    product_part = re.sub(r'\s+', ' ', product_part)
    
    return product_part

def filter_unwanted_content(text: str) -> str:
    """기본적인 불필요한 내용 제거"""
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            filtered_lines.append("")
            continue
        if re.match(r'^\s*\(서명\s*또는\s*인\)\s*$', stripped) or \
           re.match(r'^\s*[A-Z]\d{3}[-–]\d{3}.*K\d+\s*$', stripped) or \
           re.match(r'^\s*\(\d{1,2}-\d{1,2}\)\s*$', stripped) or \
           re.match(r'^\s*\d{1,2}\s*$', stripped) or \
           re.match(r'^\s*[-‐‑‒–—―−_=+*·•●○\s]*\s*$', stripped):
            continue
        filtered_lines.append(stripped)
    return '\n'.join(filtered_lines)

def clean_raw_text(text: str) -> str:
    """본문에서 불필요한 공통 요소를 제거"""
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^\(개정년월일\s*:\s*\d+\)$', stripped) or \
           re.match(r'^\s*[-‐‑‒–—―]*\s*\d+\s*[-‐‑‒–—―]*\s*$', stripped):
            continue
        if stripped: cleaned_lines.append(stripped)
    text = '\n'.join(cleaned_lines)
    appendix_match = re.search(r'부\s*칙', text)
    if appendix_match: text = text[:appendix_match.start()]
    return text.strip()

# (표 감지 및 조항 파싱 등 다른 함수들은 이전과 동일하게 유지)
# -------------------- 표 영역 감지 및 제거 --------------------
def detect_table_regions(page) -> List[Tuple[float, float, float, float]]:
    table_regions = []
    try:
        if hasattr(page, "find_tables"):
            settings = [{}, {"vertical_strategy": "lines", "horizontal_strategy": "lines"}, {"vertical_strategy": "text", "horizontal_strategy": "text"}]
            for st in settings:
                try:
                    for t in page.find_tables(**st):
                        if t.bbox: table_regions.append(t.bbox)
                except Exception: continue
    except Exception: pass
    return table_regions

def extract_text_excluding_tables(page) -> str:
    table_regions = detect_table_regions(page)
    try:
        chars = page.chars
        if not chars: return ""
        filtered_chars = []
        for char in chars:
            char_bbox = (char['x0'], char['top'], char['x1'], char['bottom'])
            if not any(bbox_overlap(char_bbox, table_bbox) for table_bbox in table_regions):
                filtered_chars.append(char)
        if filtered_chars:
            text_parts, current_line, current_y = [], [], None
            for char in sorted(filtered_chars, key=lambda c: (c['top'], c['x0'])):
                if current_y is None or abs(char['top'] - current_y) > 5:
                    if current_line:
                        line_text = ''.join(current_line).strip()
                        if line_text: text_parts.append(line_text)
                    current_line, current_y = [char['text']], char['top']
                else:
                    current_line.append(char['text'])
            if current_line:
                line_text = ''.join(current_line).strip()
                if line_text: text_parts.append(line_text)
            return filter_unwanted_content('\n'.join(text_parts))
        else: return ""
    except Exception:
        return filter_unwanted_content(page.extract_text() or "")

def bbox_overlap(bbox1, bbox2) -> bool:
    x1_left, y1_top, x1_right, y1_bottom = bbox1
    x2_left, y2_top, x2_right, y2_bottom = bbox2
    return not (x1_right < x2_left or x2_right < x1_left or y1_bottom < y2_top or y2_bottom < y1_top)

# -------------------- 섹션 분리 --------------------
def split_document_sections(text: str) -> Dict[str, str]:
    sections = {}
    auto_transfer_match = re.search(r'계좌간\s*자동이체\s*약관', text)
    privacy_match = re.search(r'개인\s*\(\s*신용\s*\)\s*정보\s*수집\s*[·•]\s*이용\s*[·•]\s*제공\s*관련\s*고객권리\s*안내문', text)
    main_start, main_end = 0, len(text)
    if auto_transfer_match:
        main_end = auto_transfer_match.start()
        transfer_start, transfer_end = auto_transfer_match.start(), len(text)
        if privacy_match and privacy_match.start() > transfer_start:
            transfer_end = privacy_match.start()
        transfer_text = text[transfer_start:transfer_end].strip()
        if transfer_text: sections['계좌간_자동이체_약관'] = transfer_text
    if privacy_match:
        privacy_text = text[privacy_match.start():].strip()
        if privacy_text: sections['개인정보_안내문'] = privacy_text
        if not auto_transfer_match: main_end = min(main_end, privacy_match.start())
    main_text = text[main_start:main_end].strip()
    if main_text: sections['대출거래약정서'] = main_text
    return sections

# -------------------- 조항 파싱 (다양한 패턴) --------------------
def parse_main_articles(text: str) -> List[Tuple[str, str, str]]:
    if not text: return []
    text = clean_raw_text(filter_unwanted_content(text))
    articles, lines = [], text.split('\n')
    current_article, current_title, current_body, preamble_lines, found_first_article = None, "", [], [], False
    for line in lines:
        line = line.strip()
        if not line:
            if current_article: current_body.append("")
            elif not found_first_article: preamble_lines.append("")
            continue
        # 인라인 조항 참조를 방지하기 위해 뒤에 "제"가 바로 오지 않는 경우만 매치
        if not re.match(r'제\s*\d+(?:의\d+)?\s*조\s+제', line):  # "제 N조 제" 패턴 제외
            article_match = re.match(r'^제\s*(\d+(?:의\d+)?)\s*조\s*(?:\(([^)]*)\))?\s*(.*)', line)
        else:
            article_match = None
        if article_match:
            if current_article:
                body_text = '\n'.join(current_body).strip()
                if body_text: articles.append((current_article, current_title, body_text))
            if not found_first_article and preamble_lines:
                preamble_text = '\n'.join(preamble_lines).strip()
                if preamble_text: articles.append(("전문", "", preamble_text))
                found_first_article = True
            base_article, parentheses_content, remaining_text = article_match.group(1), article_match.group(2), (article_match.group(3) or "").strip()
            current_article = base_article.replace('의', '-')
            current_title = parentheses_content.strip() if parentheses_content else (remaining_text if remaining_text else "")
            current_body, found_first_article = [], True
        else:
            if current_article: current_body.append(line)
            elif not found_first_article: preamble_lines.append(line)
    if current_article:
        body_text = '\n'.join(current_body).strip()
        if body_text: articles.append((current_article, current_title, body_text))
    if not found_first_article and preamble_lines:
        preamble_text = '\n'.join(preamble_lines).strip()
        if preamble_text: articles.append(("전문", "", preamble_text))
    return articles

def parse_auto_transfer_articles(text: str) -> List[Tuple[str, str, str]]:
    if not text: return []
    text = clean_raw_text(filter_unwanted_content(text))
    articles, lines = [], text.split('\n')
    current_article, current_title, current_body, preamble_lines, found_first_article = None, "", [], [], False
    for line in lines:
        line = line.strip()
        if not line:
            if current_article: current_body.append("")
            elif not found_first_article: preamble_lines.append("")
            continue
        # 인라인 조항 참조를 방지하기 위해 뒤에 "제"가 바로 오지 않는 경우만 매치
        if not re.match(r'제\s*\d+\s*조\s+제', line):  # "제 N조 제" 패턴 제외
            article_match = re.match(r'^제\s*(\d+)\s*조\s*(?:\[\s*([^\]]+)\s*\]|\(([^\)]+)\)|[\\.\s]\s*(.+))', line)
        else:
            article_match = None
        if article_match:
            if current_article:
                body_text = '\n'.join(current_body).strip()
                if body_text: articles.append((current_article, current_title, body_text))
            if not found_first_article and preamble_lines:
                preamble_text = '\n'.join(preamble_lines).strip()
                if preamble_text: articles.append(("0", "약관 전문", preamble_text))
                found_first_article = True
            current_article, current_title = article_match.group(1), next((g for g in article_match.groups()[1:] if g is not None), "").strip()
            current_body, found_first_article = [], True
        else:
            if current_article: current_body.append(line)
            elif not found_first_article: preamble_lines.append(line)
    if current_article:
        body_text = '\n'.join(current_body).strip()
        if body_text: articles.append((current_article, current_title, body_text))
    if not found_first_article and preamble_lines:
        preamble_text = '\n'.join(preamble_lines).strip()
        if preamble_text: articles.append(("0", "약관 전문", preamble_text))
    if not articles and text.strip():
        articles.append(("0", "계좌간 자동이체 약관", text))
    return articles

def parse_privacy_articles(text: str) -> List[Tuple[str, str, str]]:
    if not text: return []
    text = clean_raw_text(filter_unwanted_content(text))
    articles, lines = [], text.split('\n')
    current_article, current_title, current_body = None, "", []
    for line in lines:
        line = line.strip()
        if not line:
            if current_article: current_body.append("")
            continue
        article_match = re.match(r'^(\d+)\.\s*(.+)', line)
        if article_match:
            if current_article:
                body_text = '\n'.join(current_body).strip()
                if body_text: articles.append((current_article, current_title, body_text))
            current_article, current_title, current_body = article_match.group(1), article_match.group(2).strip(), []
        else:
            if current_article: current_body.append(line)
    if current_article:
        body_text = '\n'.join(current_body).strip()
        if body_text: articles.append((current_article, current_title, body_text))
    return articles

# -------------------- OCR 텍스트 --------------------
def pdf_text_with_ocr_fallback(pdf_path: Path, use_ocr: bool, lang: str, dpi: int = 300) -> str:
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for p in pdf.pages:
                pages.append(extract_text_excluding_tables(p) or "")
    except Exception: pass
    joined = '\n'.join(pages).strip()
    if (not joined or len(joined) < 30) and use_ocr and convert_from_path and pytesseract:
        try:
            imgs = convert_from_path(str(pdf_path), dpi=dpi)
            ocrs = [pytesseract.image_to_string(img, config=f"-l {lang}").strip() for img in imgs]
            return '\n'.join(ocrs)
        except Exception: return joined
    return joined

# -------------------- 메인 파이프라인 --------------------
def process_pdf(pdf_path: Path, out_dir: Path, exclude_description: bool, use_ocr: bool, ocr_lang: str, base_input_dir: Path):
    """PDF 처리 - 대출거래약정서 파일 대상"""
    if "대출거래약정서" not in pdf_path.name: return None

    original_stem = pdf_path.stem
    try:
        with pdfplumber.open(pdf_path) as pdf:
            title_from_content = extract_title(pdf.pages[0]).strip() if pdf.pages else original_stem
    except Exception: title_from_content = original_stem

    if exclude_description and ("상품설명서" in title_from_content or "상품설명서" in original_stem): return None
    
    full_text = pdf_text_with_ocr_fallback(pdf_path, use_ocr, ocr_lang)
    if exclude_description and "상품설명서" in full_text: return None
    
    bank = infer_bank(title_from_content)
    ptype = infer_product_type(title_from_content)
    base_filename = sanitize_filename(original_stem)
    
    relative = pdf_path.relative_to(base_input_dir)
    out_sub = out_dir / relative.parent
    out_sub.mkdir(parents=True, exist_ok=True)
    
    sections = split_document_sections(full_text)
    all_rows = []
    
    # --- ✨✨✨ 여기가 핵심 수정 부분입니다 ✨✨✨ ---
    # 파일명 기반의 상품 이름을 미리 생성
    base_product_name = create_base_product_name(original_stem)

    for section_name, section_text in sections.items():
        if not section_text.strip(): continue
        
        product_name_for_section = ""
        articles = []
        
        if section_name == '대출거래약정서':
            articles = parse_main_articles(section_text)
            # 파일명 기반 상품이름과 섹션 이름을 조합
            product_name_for_section = f"{base_product_name} 대출거래약정서".strip()
        elif section_name == '계좌간_자동이체_약관':
            articles = parse_auto_transfer_articles(section_text)
            product_name_for_section = "계좌간 자동이체 약관"
        elif section_name == '개인정보_안내문':
            articles = parse_privacy_articles(section_text)
            product_name_for_section = "개인정보 안내문"
        else:
            articles = parse_main_articles(section_text)
            product_name_for_section = section_name

        data_to_append = {"은행": bank, "예/적금 또는 대출": ptype, "상품이름": product_name_for_section}
        
        if not articles:
            all_rows.append({**data_to_append, "조항": "", "조항이름": "", "조항내용": section_text})
        else:
            for (num, name, body) in articles:
                all_rows.append({**data_to_append, "조항": str(num), "조항이름": name, "조항내용": body})
    
    if all_rows:
        df = pd.DataFrame(all_rows, columns=["은행", "예/적금 또는 대출", "상품이름", "조항", "조항이름", "조항내용"])
        out_csv = out_sub / f"{base_filename}.csv"
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        return out_csv
    
    return None

def main():
    ap = argparse.ArgumentParser(description="대출거래약정서 OCR 파서 - 섹션별 분리 및 표 제외")
    ap.add_argument("--input", "--in-dir", type=str, default=".", help="PDF 루트 폴더 (하위 폴더 재귀 검색)")
    ap.add_argument("--output", "--out-dir", type=str, default="./parsed_csv", help="CSV 출력 폴더")
    ap.add_argument("--exclude-description", type=int, default=1, help="'상품설명서' 포함 PDF 제외 (1/0)")
    ap.add_argument("--use-ocr", "--ocr", action="store_true", help="텍스트 없을 때 OCR 폴백")
    ap.add_argument("--ocr-lang", type=str, default="kor", help="Tesseract 언어 코드")
    args = ap.parse_args()
    
    in_dir, out_dir = Path(args.input), Path(args.output)
    excl, ocr_on, ocr_lang = bool(args.exclude_description), args.use_ocr, args.ocr_lang
    
    pdfs = sorted(in_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"[INFO] No PDFs found in {in_dir}")
        return
    
    processed_files, skipped_files = 0, 0
    for p in pdfs:
        try:
            res = process_pdf(p, out_dir, excl, ocr_on, ocr_lang, in_dir)
            if res:
                print(f"[OK] {p.name} -> {res.relative_to(out_dir.parent)}")
                processed_files += 1
            else:
                skipped_files += 1
        except Exception as e:
            print(f"[ERROR] {p.name}: {e}")
    
    if skipped_files > 0: print(f"\n[INFO] Skipped {skipped_files} file(s) not matching the target name.")
    print(f"[DONE] {processed_files} file(s) processed. Output: {out_dir.resolve()}")

if __name__ == "__main__":
    main()