import re
import csv
from pathlib import Path
from typing import List, Tuple, Optional
import pdfplumber

# ===== 기본 설정 =====
BANK_NAME = "우리은행"
BASE_DIR = Path(__file__).parent
DATA_ROOT = BASE_DIR / "data" / "wo_bank"
TARGET_DIRS = ["우리대출약관", "우리예금약관", "우리적금약관"]
DIR_TO_TYPE = {
    "우리대출약관": "대출",
    "우리예금약관": "예금",
    "우리적금약관": "적금",
}

# ===== 조항 패턴 =====
ARTICLE_START_RE = re.compile(
    r"(?:(?<=^)|(?<=\n)|(?<=\r)|(?<=\f))(제\s*\d+\s*조)(?=\s|[\(\[]|$)([^\n\r]*)",
    flags=re.UNICODE,
)
ARTICLE_NUMBER_RE = re.compile(r"제\s*\d+\s*조", flags=re.UNICODE)

# ===== 유틸 =====
def normalize_lines(text: str) -> List[str]:
    """여러 공백을 1칸으로 정리하고 빈 줄 제거"""
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln]

# ===== 제목(상품이름) 추출 =====
def _merge_words_in_line(words: List[dict], min_gap: float = 3.0, gap_factor: float = 0.4) -> str:
    """단어 간 간격을 보고 자연스러운 공백만 유지하면서 문자열 합치기"""
    parts: List[str] = []
    prev_x1: Optional[float] = None
    prev_size: Optional[float] = None
    for word in words:
        text = word.get("text")
        if not text:
            continue
        x0 = word.get("x0")
        x1 = word.get("x1", x0)
        if x0 is not None and prev_x1 is not None:
            size = word.get("size") or prev_size or 0
            gap = x0 - prev_x1
            tol = max(min_gap, size * gap_factor)
            if gap > tol:
                parts.append(" ")
        parts.append(text)
        prev_x1 = x1 if x1 is not None else x0
        prev_size = word.get("size", prev_size)
    return "".join(parts).strip()

def _extract_title_from_text(text: str, max_lines: int = 3) -> str:
    """extract_text 결과에서 상단 연속 줄을 묶어 제목 후보 생성"""
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ""
    candidate: List[str] = []
    for ln in lines:
        if ARTICLE_NUMBER_RE.search(ln):
            break
        candidate.append(ln)
        if len(candidate) >= max_lines or len(" ".join(candidate)) >= 80:
            break
    return " ".join(candidate).strip()

def _needs_text_fallback(word_title: str, text_title: str) -> bool:
    """단어 기반 추출 결과가 흐트러졌다면 텍스트 기반 제목으로 대체"""
    if not text_title:
        return False
    if not word_title:
        return True
    norm_word = re.sub(r"\s+", "", word_title)
    if not norm_word:
        return True
    dup = sum(1 for i in range(1, len(norm_word)) if norm_word[i] == norm_word[i - 1])
    if len(norm_word) > 1 and (dup / (len(norm_word) - 1)) >= 0.05:
        return True
    tokens = word_title.split()
    if tokens:
        single_chars = sum(1 for t in tokens if len(t) == 1)
        if single_chars >= max(2, len(tokens) // 2):
            return True
    return False

def extract_title_from_first_page(pdf_path: Path, size_tol: float = 1.5) -> str:
    """
    1페이지에서 폰트 크기/좌표를 이용해 다줄 제목을 합쳐 추출.
    실패 시 빈 문자열 반환.
    """
    with pdfplumber.open(str(pdf_path)) as pdf:
        if not pdf.pages:
            return ""
        page = pdf.pages[0]

        text_based_title = _extract_title_from_text(page.extract_text() or "")

        words = page.extract_words(
            use_text_flow=True,
            keep_blank_chars=False,
            extra_attrs=["size", "x0", "x1", "top", "bottom"],
        )
        if not words:
            return text_based_title[:200]

        sizes = [w.get("size", 0) for w in words if w.get("size")]
        max_size = max(sizes) if sizes else 0
        if max_size == 0:
            t = (page.extract_text() or "").splitlines()
            return next((ln.strip() for ln in t if ln.strip()), "")

        title_words = [w for w in words if abs(w.get("size", 0) - max_size) <= size_tol]
        if not title_words:
            sizes_sorted = sorted(sizes, reverse=True)
            idx = max(0, len(sizes_sorted) // 10 - 1)
            threshold = sizes_sorted[idx]
            title_words = [w for w in words if w.get("size", 0) >= threshold]

        title_words.sort(key=lambda w: (w["top"], w["x0"]))
        lines = []
        cur_line = []
        last_top = None
        line_gap_tol = max(8.0, max_size * 1.5)

        for w in title_words:
            if last_top is None or abs(w["top"] - last_top) <= line_gap_tol:
                cur_line.append(w)
                last_top = w["top"] if last_top is None else max(last_top, w["top"])
            else:
                if cur_line:
                    lines.append(cur_line)
                cur_line = [w]
                last_top = w["top"]
        if cur_line:
            lines.append(cur_line)

        line_texts: List[str] = []
        for line in lines:
            line.sort(key=lambda w: w["x0"])
            line_texts.append(_merge_words_in_line(line))

        title = " ".join(lt for lt in line_texts if lt).strip()

        if _needs_text_fallback(title, text_based_title):
            return text_based_title[:200]

        return (title or text_based_title)[:200]

def extract_product_name(full_text: str, pdf_path: Path) -> str:
    title = extract_title_from_first_page(pdf_path)
    if title:
        return title
    for ln in full_text.splitlines():
        if ln.strip():
            return ln.strip()
    return pdf_path.stem

# ===== 표 + 본문 텍스트 추출 =====
def _mask_article_markers_in_text(txt: str) -> str:
    """
    표에서 나오는 '제1조' 등이 본문 파서에 걸리지 않도록 마스킹.
    ex) '제1조' -> '제1조(표내)'
    정규식 경계를 깨서 ARTICLE_NUMBER_RE가 매칭되지 않게 함.
    """
    return re.sub(r"(제\s*\d+\s*조)", r"\1(표내)", txt)

def _should_join_without_space(prev_line: str, next_line: str) -> bool:
    """
    줄을 공백 없이 이어 붙일지 판단.
    - 이전 줄 마지막 글자와 다음 줄 첫 글자가 모두 한글이면서
      둘 중 하나라도 한 글자라면 공백 없이 붙임 (줄바꿈으로 단어가 쪼개진 상황 방지)
    """
    if not prev_line or not next_line:
        return False
    prev_trimmed = prev_line.rstrip()
    next_trimmed = next_line.lstrip()
    if not prev_trimmed or not next_trimmed:
        return False

    prev_last = prev_trimmed[-1]
    next_first = next_trimmed[0]
    hangul_re = r"[\uAC00-\uD7A3]"

    if re.match(hangul_re, prev_last) and re.match(hangul_re, next_first):
        prev_token = prev_trimmed.split()[-1]
        next_token = next_trimmed.split()[0]
        if len(prev_token) <= 1 or len(next_token) <= 1:
            return True
    return False

def _normalize_article_content(text: str) -> str:
    """
    불필요한 개행을 공백으로 정리해 문장이 끊기지 않도록 변환.
    - 마침표/물음표/느낌표/콜론/세미콜론으로 끝나는 줄은 개행 유지
    - 다음 줄이 리스트/번호/특수기호로 시작하면 개행 유지
    """
    if not text:
        return text

    def is_list_line(line: str) -> bool:
        stripped = line.lstrip()
        return bool(re.match(r"(?:(?:\d+|[가-하]|[A-Za-z])[\).\s]|[①-⑳]|[-•◦]|[※＊])", stripped))

    lines = text.splitlines()
    result: List[str] = []
    buffer = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buffer:
                result.append(buffer.strip())
                buffer = ""
            result.append("")
            continue

        if not buffer:
            buffer = stripped
            continue

        last_char = buffer.rstrip()[-1] if buffer.rstrip() else ""
        if last_char in ".?!:;" or is_list_line(line):
            result.append(buffer.strip())
            buffer = stripped
        else:
            if _should_join_without_space(buffer, stripped):
                buffer = f"{buffer.rstrip()}{stripped}"
            else:
                buffer = f"{buffer.rstrip()} {stripped}"

    if buffer:
        result.append(buffer.strip())

    return "\n".join(result)

def _is_two_col_table(table: List[List[Optional[str]]]) -> bool:
    """
    표가 실질적으로 2열인지 판단.
    - 비어 있지 않은 컬럼(Index 기준)이 2개를 초과하면 False
    """
    nonempty_cols = set()
    for row in table or []:
        if not row:
            continue
        for idx, cell in enumerate(row):
            text = cell.strip() if isinstance(cell, str) else cell
            if text:
                nonempty_cols.add(idx)
                if len(nonempty_cols) > 2:
                    return False
    return True

def _has_change_heading_above_table(bbox: Tuple[float, float, float, float], words: List[dict], margin: float = 4.0) -> bool:
    """
    테이블 상단 좌표보다 위쪽에 '변경사항' 텍스트가 존재하는지 확인.
    - margin: 경계값 보정 (폰트 크기 등에 따라 약간 겹치는 경우 대응)
    """
    table_top = bbox[1]
    for word in words or []:
        text = word.get("text")
        if not text or "변경사항" not in text:
            continue
        top = word.get("top")
        bottom = word.get("bottom")
        if top is None and bottom is None:
            continue
        # word 좌표가 table_top보다 충분히 위에 있으면 True
        if bottom is not None and bottom <= table_top + margin:
            return True
        if top is not None and top <= table_top + margin:
            return True
    return False

def extract_text_with_tables(pdf_path: Path) -> str:
    """
    각 페이지:
      - 본문 텍스트
      - **2열 표만** 'key: value' 줄로 변환하여 본문 뒤에 덧붙임
      - 3열 이상 표는 **무시**
      - 표 내부의 '제n조'는 '(표내)' 마스킹으로 조항 파서에서 제외
    """
    parts: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                parts.append(page_text)

            words = page.extract_words(
                use_text_flow=True,
                keep_blank_chars=False,
                extra_attrs=["top", "bottom"],
            )

            try:
                raw_tables = page.find_tables()
            except Exception:
                raw_tables = []

            for raw_table in raw_tables or []:
                table = raw_table.extract(x_tolerance=3, y_tolerance=3)
                if not table or not _is_two_col_table(table):
                    # 3열 이상 표는 버림
                    continue
                if _has_change_heading_above_table(raw_table.bbox, words):
                    # '변경사항' 제목 아래 표는 무시
                    continue

                lines = []
                for row in table:
                    if not row:
                        continue
                    cells = [(c.strip() if isinstance(c, str) else "") for c in row]
                    # 위 필터로 실질 2열만 남으므로 앞 2칸만 사용
                    left = cells[0] if len(cells) > 0 else ""
                    right = cells[1] if len(cells) > 1 else ""
                    if left or right:
                        pair = f"{left}: {right}".strip()
                        lines.append(_mask_article_markers_in_text(pair))

                if lines:
                    parts.append("\n".join(lines))

    return "\n\n".join(p for p in parts if p).strip()

# ===== 서문/조항 분리 & 파싱 =====
def split_preamble_and_body(full_text: str, product_name: str) -> Tuple[str, str]:
    first_article = ARTICLE_START_RE.search(full_text)
    if first_article:
        preamble = full_text[: first_article.start()].strip()
        pre_lines = normalize_lines(preamble)
        if pre_lines and pre_lines[0] == product_name:
            preamble = "\n".join(pre_lines[1:]).strip()
        body = full_text[first_article.start() :].strip()
    else:
        lines = normalize_lines(full_text)
        preamble = "\n".join(lines[1:]).strip() if lines else ""
        body = ""
    return preamble, body

def parse_articles(body_text: str) -> List[Tuple[str, Optional[str], str]]:
    if not body_text:
        return []
    out: List[Tuple[str, Optional[str], str]] = []
    matches = list(ARTICLE_START_RE.finditer(body_text))
    for i, m in enumerate(matches):
        art_num = re.search(ARTICLE_NUMBER_RE, m.group(0)).group(0) if m else ""
        art_name = " ".join((m.group(2) or "").split()) if m else ""
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body_text)
        content_raw = body_text[start:end]

        if not art_name:
            after = content_raw.lstrip()
            first_line = after.splitlines()[0].strip() if after else ""
            if 0 < len(first_line) <= 30:
                art_name = " ".join(first_line.split())
                content_raw = after[len(first_line):]

        content = _normalize_article_content(content_raw.strip())
        out.append((art_num, art_name, content))
    return out

# ===== 개별 PDF 처리 =====
def process_pdf(pdf_path: Path, product_type: str) -> List[dict]:
    full_text = extract_text_with_tables(pdf_path)
    product_name = extract_product_name(full_text, pdf_path)
    preamble, body = split_preamble_and_body(full_text, product_name)

    rows: List[dict] = []

    for art_num, art_name, art_body in parse_articles(body):
        rows.append({
            "은행명": BANK_NAME,
            "상품종류": product_type,
            "상품이름": product_name,
            "조항": art_num,
            "조항이름": art_name,
            "조항내용": art_body,
        })

    if not rows and full_text:
        rows.append({
            "은행명": BANK_NAME,
            "상품종류": product_type,
            "상품이름": product_name or pdf_path.stem,
            "조항": "",
            "조항이름": "",
            "조항내용": full_text,
        })

    return rows

# ===== 폴더 단위 CSV 출력 =====
def write_folder_csv(dir_path: Path, product_type: str) -> None:
    rows: List[dict] = []
    for pdf_path in sorted(dir_path.rglob("*.pdf")):
        try:
            rows.extend(process_pdf(pdf_path, product_type))
            print(f"[OK] {pdf_path}")
        except Exception as e:
            print(f"[ERR] {pdf_path} -> {e}")

    if not rows:
        print(f"[SKIP] {dir_path} (추출된 행 없음)")
        return

    out_csv = dir_path / f"{dir_path.name}_추출.csv"
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["은행명", "상품종류", "상품이름", "조항", "조항이름", "조항내용"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"[DONE] {out_csv} (총 {len(rows)}행)")

# ===== 메인 =====
def main():
    for dir_name in TARGET_DIRS:
        dir_path = DATA_ROOT / dir_name
        if not dir_path.exists():
            print(f"[WARN] 경로 없음: {dir_path}")
            continue
        product_type = DIR_TO_TYPE.get(dir_name, dir_name)
        write_folder_csv(dir_path, product_type)

if __name__ == "__main__":
    main()
