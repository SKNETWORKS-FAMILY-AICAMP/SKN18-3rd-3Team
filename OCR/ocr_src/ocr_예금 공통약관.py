#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KB '특약' PDF Parser with OCR + JSON
- '특약'이름이 포함된 PDF만 처리 (--only-tyak 1)
- 제목(1p 상단 큰 글자)을 상품이름으로 사용
- CSV 스키마(조항): [은행, 예/적금 또는 대출, 상품이름, 조항, 조항이름, 조항내용]
- 표는 페이지 좌표 기반으로 '해당 조항'에만 매핑
- 조항내용 끝에 [표(JSON)] <계층형 JSON> 형식으로 삽입
- 표는 별도 CSV/JSON로도 저장(메타 3컬럼 프리픽스 포함)
"""

import os, re, sys, math, argparse, json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import pandas as pd
import pdfplumber

# OCR(텍스트 레이어가 거의 없을 때 폴백)
try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None
try:
    import pytesseract
except Exception:
    pytesseract = None

# 줄 시작에서만 '제 N조' 인식 (본문 중 "제4조에 따라" 오인식 방지)
ARTICLE_HDR = re.compile(r"(?m)^\s*제\s*(\d+)\s*조\s*([^\n\r]*)")

# ------------------------ 유틸 ------------------------
def sanitize_filename(name: str, max_len: int = 120) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:max_len].rstrip() if len(name) > max_len else name

def infer_bank(title: str) -> str:
    t = (title or "")
    return "국민은행" if ("국민" in t or "KB" in t or "kb" in t) else "은행미상"

def infer_product_type(title: str) -> str:
    return "대출" if "대출" in (title or "") else "예/적금"

def df_to_records_json(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """테이블을 평면 레코드 JSON으로 변환(빈칸/NaN 보정)."""
    def fix(v):
        import pandas as _pd, numpy as _np
        if v is None:
            return ""
        if isinstance(v, _pd.Series):    # 중복컬럼 등 edge 대응
            try:
                return " ".join(str(x) for x in v.tolist())
            except Exception:
                return str(v)
        try:
            if isinstance(v, float) and math.isnan(v):
                return ""
        except Exception:
            pass
        try:
            if isinstance(v, (_np.generic,)):
                return v.item()
        except Exception:
            pass
        return v

    cols = list(df.columns)
    return [{c: fix(row[c]) for c in cols} for _, row in df.iterrows()]

def df_to_nested_table_json(df: pd.DataFrame) -> Dict[str, Any]:
    """
    표를 계층형 JSON으로 변환.
    - 첫 번째 유효 컬럼을 '항목'축, '면제'가 들어간 컬럼(없으면 마지막)을 '면제횟수'축으로 가정.
    - '항목'셀에 불릿(-/•/·)이 있으면 '세부' 배열로 분해.
    """
    cols = list(df.columns)
    first_col = next((c for c in cols if str(c).strip()), cols[0] if cols else None)
    last_col  = next((c for c in cols if "면제" in str(c)), cols[-1] if cols else None)
    table_name = f"{first_col} / {last_col}" if first_col and last_col else "table"

    def split_lines(s):
        s = "" if s is None else str(s)
        return [p.strip() for p in s.split("\n") if p.strip()]
    def is_bullet(l):  # '- xxx' / '• xxx' / '· xxx'
        return l.lstrip().startswith(("-", "•", "·"))
    def clean_bullet(l):
        return l.lstrip().lstrip("-•·").strip()

    rows = []
    for _, row in df.iterrows():
        key_lines = split_lines(row.get(first_col, "") if first_col is not None else "")
        val_lines = split_lines(row.get(last_col, "") if last_col is not None else "")

        if any(is_bullet(k) for k in key_lines):
            top = clean_bullet(key_lines[0]) if is_bullet(key_lines[0]) else key_lines[0]
            subs = [clean_bullet(k) for k in key_lines if is_bullet(k)]
            out = []
            for i, s in enumerate(subs):
                cnt = val_lines[i] if i < len(val_lines) else (val_lines[0] if len(val_lines)==1 else "")
                out.append({"항목": s, "면제횟수": cnt})
            rows.append({"항목": top, "세부": out})
        else:
            item = " ".join(key_lines) if len(key_lines) > 1 else (key_lines[0] if key_lines else "")
            cnt  = val_lines[0] if val_lines else ""
            rows.append({"항목": item, "면제횟수": cnt})

    return {"table_name": str(table_name), "rows": rows}

# ------------------------ 제목/조항 파싱 ------------------------
def pick_top_title_from_chars(page) -> Optional[str]:
    """1페이지 상단 큰 폰트 라인을 제목 후보로 선택."""
    try:
        chars = page.chars
        if not chars:
            return None
        height = page.height
        top_chars = [c for c in chars if c.get("top", height) <= height*0.35 and c.get("text","").strip()] or chars
        from collections import defaultdict
        lines = defaultdict(list)
        for c in top_chars:
            lines[round(c.get("top",0),1)].append(c)
        candidates = []
        for y, line_chars in lines.items():
            line_chars = sorted(line_chars, key=lambda d: d.get("x0",0))
            text = "".join(d.get("text","") for d in line_chars).strip()
            if not text:
                continue
            sizes = [d.get("size",0) for d in line_chars]
            score = (max(sizes)*10) + ((sum(sizes)/len(sizes) if sizes else 0)*2) + (len(text)**0.5)
            candidates.append((score, -y, text))
        if not candidates:
            return None
        return candidates[0][2].strip(" -\u00a0")
    except Exception:
        return None

def extract_title(pdf: pdfplumber.PDF) -> str:
    try:
        p = pdf.pages[0]
        title = pick_top_title_from_chars(p)
        if title:
            return title
        txt = (p.extract_text() or "").strip()
        for line in txt.splitlines():
            if line.strip():
                return line.strip()
    except Exception:
        pass
    return ""

def parse_articles(full_text: str) -> List[Tuple[str,str,str]]:
    text = re.sub(r"\r", "\n", full_text)
    text = re.sub(r"[ \t]+", " ", text)
    matches = list(ARTICLE_HDR.finditer(text))
    results: List[Tuple[str,str,str]] = []
    if not matches:
        return results

    def line_bounds(idx: int):
        start = text.rfind("\n", 0, idx) + 1
        end   = text.find("\n", idx)
        return (start, len(text)) if end == -1 else (start, end)

    # 부칙 및 기타 행정적 내용 필터링
    def is_administrative_content(body: str) -> bool:
        body_lower = body.lower()
        # 부칙, 시행일, 법령 관련 내용 필터링
        admin_keywords = [
            "부칙", "시행", "법령", "내부통제", "절차", "제공", "기준",
            "이 약관은", "부터 시행", "본 특약은", "거쳐서"
        ]
        return any(keyword in body_lower for keyword in admin_keywords)

    for i, m in enumerate(matches):
        num, inline_name = m.group(1), (m.group(2) or "").strip()
        start = m.end()
        end   = matches[i+1].start() if i+1 < len(matches) else len(text)

        name = inline_name
        body_start = start
        if not name:
            ln_start, ln_end = line_bounds(start)
            next_line = text[ln_start:ln_end].strip()
            if next_line and not next_line.startswith("제") and len(next_line) <= 40:
                name = next_line
                body_start = ln_end + 1

        body = re.sub(r"\n{3,}", "\n\n", text[body_start:end].strip())
        
        # 부칙 내용만 제거하고 조항 내용은 유지
        # 부칙으로 시작하는 부분을 찾아서 제거
        lines = body.split('\n')
        filtered_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            # 부칙으로 시작하는 줄을 만나면 그 이후 모든 줄을 제거
            if (line_stripped.startswith("부칙") or 
                line_stripped.startswith("본 특약은") or
                ("부칙" in line_stripped and "시행" in line_stripped) or
                ("이 약관은" in line_stripped and "시행" in line_stripped) or
                line_stripped == "부 칙"):
                break
            filtered_lines.append(line)
        
        if filtered_lines:
            body = '\n'.join(filtered_lines).strip()
        
        # 빈 내용이 아니면 추가
        if body.strip():
            results.append((num, name, body))
    return results

# ------------------------ 좌표 기반 조항/표 매핑 ------------------------
def find_article_headers_with_positions(page, pidx: int) -> List[Dict[str, Any]]:
    """페이지에서 '제 N조' 줄의 y좌표를 식별."""
    items = []
    try:
        chars = [c for c in page.chars if c.get("text","").strip()]
        if not chars:
            return items
        from collections import defaultdict
        lines = defaultdict(list)
        for c in chars:
            lines[round(c.get("top",0),1)].append(c)
        for y, line_chars in lines.items():
            line_chars = sorted(line_chars, key=lambda d: d.get("x0",0))
            text = "".join(d.get("text","") for d in line_chars)
            m = re.match(r"^\s*제\s*(\d+)\s*조\s*(.*)$", text)
            if m:
                items.append({"page": pidx, "y": y, "num": m.group(1), "raw": text.strip()})
    except Exception:
        pass
    return sorted(items, key=lambda d: d["y"])

def extract_tables_with_positions(page) -> List[Dict[str, Any]]:
    """표의 bbox와 데이터를 추출. find_tables가 없으면 extract_tables로 폴백(위치정보 없음)."""
    tables = []
    try:
        if hasattr(page, "find_tables"):
            for t in page.find_tables():
                try:
                    data = t.extract()
                    if not data or not any(any(c for c in r) for r in data):
                        continue
                    tables.append({"bbox": t.bbox, "data": data})
                except Exception:
                    continue
        else:
            data_list = page.extract_tables() or []
            for data in data_list:
                if data and any(any(c for c in r) for r in data):
                    tables.append({"bbox": None, "data": data})
    except Exception:
        pass
    return tables

def map_tables_to_articles(pdf: pdfplumber.PDF) -> Dict[str, List[pd.DataFrame]]:
    """표를 같은 페이지의 '직전' 조항(없으면 직전 페이지 마지막 조항)에 매핑."""
    headers_by_page: Dict[int, List[Dict[str, Any]]] = {}
    tables_meta: List[Dict[str, Any]] = []

    for pidx, page in enumerate(pdf.pages):
        headers_by_page[pidx] = find_article_headers_with_positions(page, pidx)
        for t in extract_tables_with_positions(page):
            ymid = None
            if t["bbox"] is not None:
                _, top, _, bottom = t["bbox"]
                ymid = (top + bottom)/2.0
            tables_meta.append({"page": pidx, "ymid": ymid, "data": t["data"]})

    mapping: Dict[str, List[pd.DataFrame]] = {}
    last_seen_article = None

    for tm in tables_meta:
        pidx, ymid = tm["page"], tm["ymid"]
        cand = [h for h in headers_by_page.get(pidx, []) if (ymid is None or h["y"] <= ymid)]
        chosen = sorted(cand, key=lambda h: h["y"])[-1] if cand else None
        if not chosen:
            # 같은 페이지에 직전 헤더가 없으면 이전 페이지의 마지막 헤더
            for back in range(pidx-1, -1, -1):
                prev = headers_by_page.get(back, [])
                if prev:
                    chosen = prev[-1]
                    break
        if chosen:
            last_seen_article = chosen["num"]
        art_num = chosen["num"] if chosen else (last_seen_article or "0")

        # 표를 DataFrame으로 정규화(첫 행/헤더 자동 판별)
        raw = tm["data"]
        header = raw[0] if raw else []
        data = raw[1:] if len(raw) > 1 else []
        if header and sum(1 for h in header if h and str(h).strip()) >= max(1, len(header)//2):
            df = pd.DataFrame(data, columns=[(str(h).strip() if h else "") for h in header])
        else:
            df = pd.DataFrame(raw)
        df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
        mapping.setdefault(art_num, []).append(df)

    return mapping

# ------------------------ OCR 폴백 ------------------------
def pdf_text_with_ocr_fallback(pdf_path: Path, ocr: bool, ocr_lang: str, dpi: int = 300) -> str:
    text_layers: List[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for p in pdf.pages:
                text_layers.append(p.extract_text() or "")
    except Exception:
        text_layers = []

    joined = "\n".join(text_layers).strip()
    if (not joined or len(joined) < 30) and ocr:
        if convert_from_path is None or pytesseract is None:
            print("[WARN] No text layer and OCR modules not available.", file=sys.stderr)
            return joined
        try:
            images = convert_from_path(str(pdf_path), dpi=dpi)
            ocr_chunks = []
            for img in images:
                conf = f"-l {ocr_lang}" if ocr_lang else ""
                ocr_chunks.append(pytesseract.image_to_string(img, config=conf).strip())
            return "\n".join(ocr_chunks)
        except Exception as e:
            print(f"[WARN] OCR fallback failed: {e}", file=sys.stderr)
            return joined
    return joined

# ------------------------ 메인 처리 ------------------------
def process_pdf(pdf_path: Path, out_dir: Path, only_tyak: bool, ocr: bool, ocr_lang: str, base_input_dir: Path):
    stem = pdf_path.stem
    try:
        with pdfplumber.open(pdf_path) as pdf:
            title         = extract_title(pdf).strip() or stem
            product_name  = title.strip()
            
            # 특약 필터링: 제목 또는 PDF 내용에서 "특약" 확인
            full_text = None
            if only_tyak:
                # 먼저 제목에서 확인
                if "특약" not in title:
                    # 제목에 없으면 PDF 내용 전체에서 확인
                    full_text = pdf_text_with_ocr_fallback(pdf_path, ocr=ocr, ocr_lang=ocr_lang)
                    if "특약" not in full_text:
                        return None
                
            bank_name     = infer_bank(title)
            product_type  = infer_product_type(title)
            base_name     = sanitize_filename(title)
            
            # 입력 폴더 구조를 유지하여 출력 폴더 생성
            relative_path = pdf_path.relative_to(base_input_dir)
            output_subdir = out_dir / relative_path.parent
            output_subdir.mkdir(parents=True, exist_ok=True)

            # 1) 표 → 조항 매핑
            tables_by_article = map_tables_to_articles(pdf)

            # 2) 표 파일 저장(프리픽스 3컬럼 추가)
            table_paths = []
            ti = 0
            for _, dfs in tables_by_article.items():
                for df in dfs:
                    ti += 1
                    df_pref = df.copy()
                    df_pref.insert(0, "상품이름", product_name)
                    df_pref.insert(0, "예/적금 또는 대출", product_type)
                    df_pref.insert(0, "은행", bank_name)
                    t_out = output_subdir / f"{base_name}_table_{ti}.csv"
                    df_pref.to_csv(t_out, index=False, encoding="utf-8-sig")
                    table_paths.append(t_out)
                    with open(output_subdir / f"{base_name}_table_{ti}.json", "w", encoding="utf-8") as jf:
                        json.dump(df_to_records_json(df_pref), jf, ensure_ascii=False, indent=2)

            # 3) 본문 텍스트 → 조항 파싱
            if full_text is None:  # 이미 추출했다면 재사용
                full_text = pdf_text_with_ocr_fallback(pdf_path, ocr=ocr, ocr_lang=ocr_lang)
            articles  = parse_articles(full_text)

            # 4) CSV(요청 스키마) — 해당 조항에만 계층형 표 JSON 삽입
            rows = []
            if not articles:
                body = (full_text or "").strip()
                rows.append({
                    "은행": bank_name, "예/적금 또는 대출": product_type, "상품이름": product_name,
                    "조항": "", "조항이름": "", "조항내용": body
                })
            else:
                for (num, name, body) in articles:
                    body_text = (body or "").strip()
                    if num in tables_by_article and tables_by_article[num]:
                        nested_list = [df_to_nested_table_json(d) for d in tables_by_article[num]]
                        body_text += "\n\n[표(JSON)] " + json.dumps(nested_list, ensure_ascii=False)
                    rows.append({
                        "은행": bank_name, "예/적금 또는 대출": product_type, "상품이름": product_name,
                        "조항": str(num), "조항이름": name, "조항내용": body_text
                    })

            df = pd.DataFrame(rows, columns=["은행","예/적금 또는 대출","상품이름","조항","조항이름","조항내용"])
            out_csv = output_subdir / f"{base_name}.csv"
            df.to_csv(out_csv, index=False, encoding="utf-8-sig")

            # (참고) 통합 JSON도 필요하면 유지
            combined = {
                "은행": bank_name, "예/적금 또는 대출": product_type, "상품이름": product_name,
                "articles": df_to_records_json(df)
            }
            with open(output_subdir / f"{base_name}.json", "w", encoding="utf-8") as jf:
                json.dump(combined, jf, ensure_ascii=False, indent=2)

            return out_csv, table_paths
    except Exception as e:
        print(f"[ERROR] Failed to process {pdf_path.name}: {e}", file=sys.stderr)
        return None

def main():
    ap = argparse.ArgumentParser(description="KB '특약' PDF Parser (조항별 표 매핑 + 계층형 표 JSON)")
    ap.add_argument("--in-dir",   type=str, default=".", help="PDF 폴더")
    ap.add_argument("--out-dir",  type=str, default="./parsed_csv", help="출력 폴더")
    ap.add_argument("--only-tyak",type=int, default=1, help="'특약' 포함 파일만 처리(1/0)")
    ap.add_argument("--use-ocr",  type=int, default=1, help="텍스트 없을 때 OCR 폴백(1/0)")
    ap.add_argument("--ocr-lang", type=str, default="kor", help="Tesseract 언어 코드")
    args = ap.parse_args()

    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    only_tyak, use_ocr, ocr_lang = bool(args.only_tyak), bool(args.use_ocr), args.ocr_lang

    # 모든 하위 폴더를 재귀적으로 탐색하여 PDF 파일 찾기
    pdfs = sorted(in_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"[INFO] No PDFs found in {in_dir} and its subdirectories")
        return
    
    print(f"[INFO] Found {len(pdfs)} PDF files in {in_dir} and its subdirectories")

    processed = 0
    for p in pdfs:
        res = process_pdf(p, out_dir, only_tyak, use_ocr, ocr_lang, in_dir)
        if res:
            art_csv, tbl_csvs = res
            print(f"[OK] {p.name} -> {art_csv.relative_to(out_dir)} + {len(tbl_csvs)} table(s)")
            processed += 1
        else:
            print(f"[SKIP] {p.name} (not 특약)")
    print(f"[DONE] Processed {processed} file(s). Output: {out_dir.resolve()}")

if __name__ == "__main__":
    main()
