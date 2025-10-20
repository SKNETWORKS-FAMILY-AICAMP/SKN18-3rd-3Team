#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KB '특약' PDF OCR 파서 (상품설명서 제외, 조항별 표→텍스트(KV) 삽입, CSV만 저장)

규칙:
• "상품설명서" 포함 PDF 제외
• 컬럼명은 "컬럼1: 컬럼2:" 헤더 한 줄 생성
• 항목은 "key:" 다음 줄에 value들(줄 단위)로 기록
• 하위 항목은 "- content" → "- content:" 형태(불릿 기호 제거)
• 표는 해당 조항의 조항내용에 텍스트로 삽입
• 모든 PDF에 일관 적용

필수 패키지: pdfplumber pandas pdf2image pytesseract
(시스템: poppler, tesseract + kor 데이터)
"""

import os, re, sys, math, argparse
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import pandas as pd
import pdfplumber

# OCR fallback
try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None
try:
    import pytesseract
except Exception:
    pytesseract = None

# "제 N조"는 줄 시작에서만 인식(본문의 '제4조에 따라' 방지)
ARTICLE_HDR = re.compile(r"(?m)^\s*제\s*(\d+)\s*조\s*([^\n\r]*)")

# -------------------- 유틸 --------------------
def sanitize_filename(name: str, max_len: int = 120) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:max_len].rstrip() if len(name) > max_len else name

def infer_bank(title: str) -> str:
    t = (title or "")
    return "국민은행" if ("국민" in t or "KB" in t or "kb" in t) else "은행미상"

def infer_product_type(title: str) -> str:
    return "대출" if "대출" in (title or "") else "예/적금"

def pick_top_title_from_chars(page) -> Optional[str]:
    try:
        chars = page.chars
        if not chars: return None
        height = page.height
        top_chars = [c for c in chars if c.get("top", height) <= height*0.35 and c.get("text","").strip()] or chars
        from collections import defaultdict
        lines = defaultdict(list)
        for c in top_chars: lines[round(c.get("top",0),1)].append(c)
        cands = []
        for y, line in lines.items():
            line = sorted(line, key=lambda d: d.get("x0",0))
            text = "".join(d.get("text","") for d in line).strip()
            if not text: continue
            sizes = [d.get("size",0) for d in line]
            score = max(sizes)*10 + (sum(sizes)/len(sizes) if sizes else 0)*2 + (len(text)**0.5)
            cands.append((score, -y, text))
        return cands[0][2].strip(" -\u00a0") if cands else None
    except Exception:
        return None

def extract_title(pdf: pdfplumber.PDF) -> str:
    try:
        p = pdf.pages[0]
        t = pick_top_title_from_chars(p)
        if t: return t
        txt = (p.extract_text() or "").strip()
        for line in txt.splitlines():
            if line.strip(): return line.strip()
    except Exception:
        pass
    return ""

# -------------------- 본문/조항 파싱 --------------------
def parse_articles(full_text: str) -> List[Tuple[str,str,str]]:
    text = re.sub(r"\r", "\n", full_text)
    text = re.sub(r"[ \t]+", " ", text)
    m = list(ARTICLE_HDR.finditer(text))
    results = []
    if not m: return results

    def line_bounds(idx: int):
        s = text.rfind("\n", 0, idx) + 1
        e = text.find("\n", idx)
        return (s, len(text)) if e == -1 else (s, e)

    for i, mm in enumerate(m):
        num, inline = mm.group(1), (mm.group(2) or "").strip()
        start = mm.end()
        end   = m[i+1].start() if i+1 < len(m) else len(text)

        name = inline
        body_start = start
        if not name:
            ln_s, ln_e = line_bounds(start)
            nxt = text[ln_s:ln_e].strip()
            if nxt and not nxt.startswith("제") and len(nxt) <= 40:
                name = nxt; body_start = ln_e + 1

        body = re.sub(r"\n{3,}", "\n\n", text[body_start:end].strip())

        # '부칙/시행' 등 행정문구 제거(이후 라인 전부 drop)
        lines, out = body.split("\n"), []
        for L in lines:
            S = L.strip()
            if (S.startswith("부칙") or S.startswith("부 칙") or
                ("이 약관은" in S and "시행" in S) or
                S.startswith("본 특약은")):
                break
            out.append(L)
        body = "\n".join(out).strip()
        if body: results.append((num, name, body))
    return results

# -------------------- 표 감지/매핑 --------------------
def find_article_headers_with_positions(page, pidx: int):
    items = []
    try:
        chars = [c for c in page.chars if c.get("text","").strip()]
        if not chars: return items
        from collections import defaultdict
        lines = defaultdict(list)
        for c in chars: lines[round(c.get("top",0),1)].append(c)
        for y, line in lines.items():
            line = sorted(line, key=lambda d: d.get("x0",0))
            text = "".join(d.get("text","") for d in line)
            m = re.match(r"^\s*제\s*(\d+)\s*조\s*(.*)$", text)
            if m: items.append({"page": pidx, "y": y, "num": m.group(1), "raw": text.strip()})
    except Exception:
        pass
    return sorted(items, key=lambda d: d["y"])

def extract_tables_with_positions(page):
    tables = []
    try:
        if hasattr(page, "find_tables"):
            settings = [
                {},
                {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                {"vertical_strategy": "text", "horizontal_strategy": "text"},
                {"vertical_strategy": "lines_strict", "horizontal_strategy": "lines_strict"},
            ]
            for st in settings:
                try:
                    for t in page.find_tables(**st):
                        data = t.extract()
                        if data and any(any(str(c).strip() for c in r) for r in data):
                            # 중복 bbox 제거
                            dup = False
                            if t.bbox:
                                x0,y0,x1,y1 = t.bbox
                                for ex in tables:
                                    if ex["bbox"]:
                                        ex0,ey0,ex1,ey1 = ex["bbox"]
                                        if (abs(x0-ex0)<10 and abs(y0-ey0)<10 and
                                            abs(x1-ex1)<10 and abs(y1-ey1)<10):
                                            dup=True; break
                            if not dup:
                                tables.append({"bbox": t.bbox, "data": data})
                except Exception:
                    continue
        if not tables:
            data_list = page.extract_tables() or []
            for data in data_list:
                if data and any(any(str(c).strip() for c in r) for r in data):
                    tables.append({"bbox": None, "data": data})
    except Exception:
        pass
    return tables

def map_tables_to_articles(pdf: pdfplumber.PDF):
    headers_by_page, tables_meta = {}, []
    for pidx, page in enumerate(pdf.pages):
        headers_by_page[pidx] = find_article_headers_with_positions(page, pidx)
        for t in extract_tables_with_positions(page):
            ymid=None
            if t["bbox"] is not None:
                _, top, _, bot = t["bbox"]; ymid=(top+bot)/2.0
            tables_meta.append({"page": pidx, "ymid": ymid, "data": t["data"]})

    mapping, last_seen = {}, None
    for tm in tables_meta:
        pidx, ymid = tm["page"], tm["ymid"]
        cand = [h for h in headers_by_page.get(pidx, []) if (ymid is None or h["y"]<=ymid)]
        chosen = sorted(cand, key=lambda h: h["y"])[-1] if cand else None
        if not chosen:
            for back in range(pidx-1, -1, -1):
                prev = headers_by_page.get(back, [])
                if prev: chosen = prev[-1]; break
        if chosen: last_seen = chosen["num"]
        art_num = chosen["num"] if chosen else (last_seen or "0")

        raw = tm["data"]
        header = raw[0] if raw else []
        data   = raw[1:] if len(raw)>1 else []
        if header and sum(1 for h in header if h and str(h).strip()) >= max(1, len(header)//2):
            df = pd.DataFrame(data, columns=[(str(h).strip() if h else "") for h in header])
        else:
            df = pd.DataFrame(raw)
        df.columns = [re.sub(r"\s+"," ",str(c)).strip() for c in df.columns]
        if not df.empty and df.shape[1]>0:
            mapping.setdefault(art_num, []).append(df)
    return mapping

# -------------------- 표 → 텍스트(KV) --------------------
BULLET_CHARS = ("-", "•", "·")

def _split_lines(s: Any) -> List[str]:
    if s is None:
        return []
    s = str(s)
    return [p.strip() for p in s.split("\n") if p.strip() and str(p).strip()!="nan"]

def _is_bullet(s: str) -> bool:
    return s.lstrip().startswith(BULLET_CHARS)

def _clean_bullet(s: str) -> str:
    return s.lstrip().lstrip("".join(BULLET_CHARS)).strip()

def df_to_kv_text(df: pd.DataFrame) -> str:
    """
    OCR 친화적 KV 텍스트 생성:
    - 1~N 컬럼 모두 고려하되, 좌→우로 '첫 비어있지 않은 셀'을 key, 나머지를 value
    - 병합셀/공백은 위쪽 값으로 forward-fill (키/값 모두)
    - 값이 완전히 동일해 시각적으로 한 덩어리면, 직전 key의 value로 이어붙임
    - 불릿행은 하위 항목으로 처리
    """
    if df.empty: return ""

    # 공백/NaN 정리 + 문자열화
    df = df.copy()
    def clean_cell(x):
        if x is None:
            return ""
        try:
            s = str(x).strip()
            return "" if s == "nan" else s
        except:
            return ""
    
    df = df.applymap(clean_cell)

    # 전열 forward-fill (OCR 병합 셀 보정)
    df = df.replace("", pd.NA).ffill().fillna("")

    cols = list(df.columns)
    out: List[str] = []

    # 헤더 한 줄(앞 2개 컬럼까지만 노출)
    if len(cols)>=2:
        out.append(f"{cols[0]}: {cols[1]}:")
    elif len(cols)==1:
        out.append(f"{cols[0]}:")

    prev_key = None
    prev_val_sig = None  # 값 시그니처(동일 값 반복 시 병합)

    for _, row in df.iterrows():
        # 왼→오 스캔: 최초 비어있지 않은 것을 key, 나머지 합쳐 value
        row_vals = [row[c] for c in cols if str(row[c]).strip()]
        if not row_vals: continue
        key_raw = row_vals[0]
        vals = row_vals[1:]

        # 불릿/하위 항목 판단
        is_sub = _is_bullet(key_raw)
        key = _clean_bullet(key_raw) if is_sub else key_raw

        # value 구성 (여러 줄 합치기)
        val_text = " ".join(
            " ".join(_split_lines(v)) for v in vals if v is not None and str(v).strip() != "nan"
        ).strip()

        # 값 시그니처로 동일 여부 판단(완전 동일 텍스트)
        val_sig = val_text if val_text else None

        if not val_text:
            # 키만 있는 줄
            line = f"- {key}:" if is_sub else f"{key}:"
            out.append(line)
            prev_key, prev_val_sig = key, None
            continue

        # 이전 값과 완전 동일하면 이전 key에 붙임(시각적 병합 대응)
        if prev_key and prev_val_sig and val_sig == prev_val_sig and key == prev_key:
            # 같은 키가 반복되며 값이 동일 → 스킵(이미 기록됨)
            continue

        # 일반 기록
        line = f"- {key}:" if is_sub else f"{key}:"
        out.append(line)
        out.append(val_text)

        prev_key, prev_val_sig = key, val_sig

    return "\n".join(out)

# 표 삽입 위치 탐지
def should_insert_table_after_line(line: str) -> bool:
    s = line.strip()
    if not s: return False
    triggers = [
        "기본실적", "실적 인정조건", "면제조건", "면제대상 수수료 및 면제횟수",
        "면제 대상 수수료", "면제횟수"
    ]
    return any(t in s for t in triggers)

def insert_tables_in_body(body_text: str, table_texts: List[str]) -> str:
    if not table_texts or not body_text: return body_text
    lines = body_text.split("\n")
    out, inserted = [], False
    for ln in lines:
        out.append(ln)
        if not inserted and should_insert_table_after_line(ln):
            for tt in table_texts: out.append(tt)
            inserted = True
    if not inserted:
        for tt in table_texts: out.append(tt)
    return "\n".join(out)

# -------------------- OCR 텍스트 --------------------
def pdf_text_with_ocr_fallback(pdf_path: Path, use_ocr: bool, lang: str, dpi: int = 300) -> str:
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for p in pdf.pages: pages.append(p.extract_text() or "")
    except Exception: pages=[]
    joined = "\n".join(pages).strip()
    if (not joined or len(joined)<30) and use_ocr:
        if convert_from_path is None or pytesseract is None:
            return joined
        try:
            imgs = convert_from_path(str(pdf_path), dpi=dpi)
            ocrs=[]
            for img in imgs:
                conf = f"-l {lang}" if lang else ""
                ocrs.append(pytesseract.image_to_string(img, config=conf).strip())
            return "\n".join(ocrs)
        except Exception:
            return joined
    return joined

# -------------------- 메인 파이프라인 --------------------
def process_pdf(pdf_path: Path, out_dir: Path, exclude_description: bool, use_ocr: bool, ocr_lang: str, base_input_dir: Path):
    stem = pdf_path.stem
    with pdfplumber.open(pdf_path) as pdf:
        title = extract_title(pdf).strip() or stem

        # "상품설명서" 제외
        if exclude_description and "상품설명서" in title:
            return None
        full_text = pdf_text_with_ocr_fallback(pdf_path, use_ocr, ocr_lang)
        if exclude_description and "상품설명서" in full_text:
            return None

        bank  = infer_bank(title)
        ptype = infer_product_type(title)
        base  = sanitize_filename(title)

        # 출력 폴더(입력 하위 구조 보존)
        relative = pdf_path.relative_to(base_input_dir)
        out_sub  = out_dir / relative.parent
        out_sub.mkdir(parents=True, exist_ok=True)

        # 표→조항 매핑
        tables_by_article = map_tables_to_articles(pdf)

        # 본문→조항 파싱
        articles = parse_articles(full_text)

        rows=[]
        if not articles:
            body = full_text or ""
            if tables_by_article:
                ttxt=[]
                for dfs in tables_by_article.values():
                    for df in dfs:
                        txt = df_to_kv_text(df)
                        if txt.strip(): ttxt.append(txt)
                if ttxt:
                    body = insert_tables_in_body(body, ttxt)
            rows.append({"은행":bank,"예/적금 또는 대출":ptype,"상품이름":title,"조항":"","조항이름":"","조항내용":body})
        else:
            for (num, name, body) in articles:
                body_text = (body or "").strip()
                if num in tables_by_article and tables_by_article[num]:
                    ttxt=[]
                    for df in tables_by_article[num]:
                        txt = df_to_kv_text(df)
                        if txt.strip(): ttxt.append(txt)
                    if ttxt:
                        body_text = insert_tables_in_body(body_text, ttxt)
                rows.append({"은행":bank,"예/적금 또는 대출":ptype,"상품이름":title,"조항":str(num),"조항이름":name,"조항내용":body_text})

        df = pd.DataFrame(rows, columns=["은행","예/적금 또는 대출","상품이름","조항","조항이름","조항내용"])
        out_csv = out_sub / f"{base}.csv"
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        return out_csv

def main():
    ap = argparse.ArgumentParser(description="KB 특약 OCR 파서(상품설명서 제외, 조항별 표→KV 텍스트 삽입, CSV만 저장)")
    ap.add_argument("--in-dir", type=str, default=".", help="PDF 루트 폴더(하위 폴더 재귀 검색)")
    ap.add_argument("--out-dir", type=str, default="./parsed_csv", help="CSV 출력 폴더")
    ap.add_argument("--exclude-description", type=int, default=1, help="'상품설명서' 포함 PDF 제외(1/0)")
    ap.add_argument("--use-ocr", type=int, default=1, help="텍스트 없을 때 OCR 폴백(1/0)")
    ap.add_argument("--ocr-lang", type=str, default="kor", help="Tesseract 언어 코드")
    args = ap.parse_args()

    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    excl, ocr_on, ocr_lang = bool(args.exclude_description), bool(args.use_ocr), args.ocr_lang

    pdfs = sorted(in_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"[INFO] No PDFs found in {in_dir}")
        return

    cnt=0
    for p in pdfs:
        res = process_pdf(p, out_dir, excl, ocr_on, ocr_lang, in_dir)
        if res:
            print(f"[OK] {p} -> {res.relative_to(out_dir)}")
            cnt+=1
        else:
            print(f"[SKIP] {p}")
    print(f"[DONE] {cnt} file(s) processed. Output: {out_dir.resolve()}")

if __name__ == "__main__":
    main()
