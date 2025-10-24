import re
import pandas as pd
from sqlalchemy import create_engine, text

# ============================================================
# 1️⃣ DB 연결 설정
# ============================================================
DB_USER = "admin"
DB_PASSWORD = "admin123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "multiagent_db"

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ============================================================
# 2️⃣ 유니크 키워드 사전 생성 (캐시)
# ============================================================
_cached_keywords = None


def load_unique_keywords(force_reload=False):
    """
    DB에서 상세종류/대출대상 유니크 값 불러오기 (캐시 적용 + 복합어 분리)
    """
    global _cached_keywords
    if _cached_keywords and not force_reload:
        return _cached_keywords

    query = "SELECT DISTINCT 상세종류, 대출대상 FROM merged_table;"
    df = pd.read_sql(query, engine)

    def normalize(x):
        return re.sub(r"\s+", "", str(x))

    kinds_raw = df["상세종류"].dropna().map(normalize).unique().tolist()
    targets_raw = df["대출대상"].dropna().map(normalize).unique().tolist()

    # ------------------------------------------------------------
    # ✅ 복합어 확장 로직 (예: '담보대출' → ['담보대출', '담보', '대출'])
    # + 너무 짧거나 일반적인 단어는 제거 (‘대출’, ‘상품’ 등)
    # ------------------------------------------------------------
    def expand_keywords(lst):
        expanded = set()
        for word in lst:
            expanded.add(word)
            parts = re.split(r"(대출|상품|자금|용자)", word)
            for p in parts:
                p = p.strip()
                if len(p) > 1:
                    expanded.add(p)
        # ✅ 불필요한 일반 단어 제거
        stopwords = {"대출", "상품", "자금", "용자"}
        expanded = {w for w in expanded if w not in stopwords}
        return list(expanded)

    kinds = expand_keywords(kinds_raw)
    targets = expand_keywords(targets_raw)

    _cached_keywords = (kinds, targets)
    return kinds, targets


# ============================================================
# 3️⃣ 사용자 질의로부터 키워드 탐지 (정확도 향상 버전)
# ============================================================
def detect_keywords(user_query: str, use_frequency=False):
    """
    사용자 입력에서 상세종류/대출대상 키워드 탐지 (정확도 향상 버전)
    - 정확 일치 > 긴 키워드 > 빈도 기반 우선 탐지
    """
    unique_kinds, unique_targets = load_unique_keywords()
    normalized_query = re.sub(r"\s+", "", user_query)

    kind_freq = {}
    target_freq = {}
    if use_frequency:
        try:
            freq_df = pd.read_sql("""
                SELECT 상세종류, COUNT(*) as cnt FROM merged_table GROUP BY 상세종류
            """, engine)
            kind_freq = dict(zip(freq_df["상세종류"].map(lambda x: re.sub(r"\s+", "", str(x))), freq_df["cnt"]))

            freq_df = pd.read_sql("""
                SELECT 대출대상, COUNT(*) as cnt FROM merged_table GROUP BY 대출대상
            """, engine)
            target_freq = dict(zip(freq_df["대출대상"].map(lambda x: re.sub(r"\s+", "", str(x))), freq_df["cnt"]))
        except Exception as e:
            print(f"[경고] 빈도 기반 우선순위 로드 실패: {e}")
            use_frequency = False

    # ------------------------------------------------------------
    # 정렬: 긴 단어 > 빈도 > 알파벳순
    # ------------------------------------------------------------
    def sort_by_priority(lst, freq_dict):
        return sorted(
            lst,
            key=lambda x: (
                -len(x),                    # 긴 단어 우선
                -freq_dict.get(x, 0) if use_frequency else 0,  # 빈도 우선 (옵션)
                x                           # 알파벳순 tie-break
            )
        )

    unique_kinds = sort_by_priority(unique_kinds, kind_freq)
    unique_targets = sort_by_priority(unique_targets, target_freq)

    # ------------------------------------------------------------
    # ✅ 정확 일치 탐지
    # ------------------------------------------------------------
    exact_kind = next((k for k in unique_kinds if k == normalized_query), None)
    exact_target = next((t for t in unique_targets if t == normalized_query), None)

    if exact_kind or exact_target:
        print(f"[디버그] 정확 일치 탐지 → 상세종류: {exact_kind}, 대출대상: {exact_target}")
        return exact_kind, exact_target

    # ------------------------------------------------------------
    # ✅ 부분 포함 탐지: "가장 긴 일치 단어" 선택
    # ------------------------------------------------------------
    def find_best_match(candidates, text):
        matches = [w for w in candidates if w in text]
        if not matches:
            return None
        return max(matches, key=len)  # 가장 긴 단어 반환

    detected_kind = find_best_match(unique_kinds, normalized_query)
    detected_target = find_best_match(unique_targets, normalized_query)

    # ------------------------------------------------------------
    # 교차 검증 (한쪽이 다른 쪽을 포함하면 긴 쪽 우선)
    # ------------------------------------------------------------
    if detected_kind and detected_target:
        if detected_kind in detected_target:
            detected_kind = detected_target
        elif detected_target in detected_kind:
            detected_target = detected_kind

    return detected_kind, detected_target


# ============================================================
# 4️⃣ SQL Query 생성 로직
# ============================================================
def generate_sql(user_query: str):
    detected_kind, detected_target = detect_keywords(user_query, use_frequency=False)

    if detected_kind and detected_target:
        sql = text("""
            SELECT * FROM merged_table
            WHERE REPLACE(상세종류, ' ', '') LIKE :kind
              AND REPLACE(대출대상, ' ', '') LIKE :target
        """)
        if detected_target == "개인" and "사업" in user_query:
            params = {"kind": f"%{detected_kind}%", "target": f"개인사업자"}
        elif "근로자" in user_query:
            params = {"kind": f"%{detected_kind}%", "target": f"근로소득자"}
        elif "주택건설업" in user_query.replace(" ", ""):
            params = {"kind": f"%{detected_kind}%", "target": f"주택건설등록업자"}
        else:
            params = {"kind": f"%{detected_kind}%", "target": f"%{detected_target}%"}

    elif detected_kind:
        sql = text("""
            SELECT * FROM merged_table
            WHERE REPLACE(상세종류, ' ', '') LIKE :kind
        """)
        params = {"kind": f"%{detected_kind}%"}

    elif detected_target:
        sql = text("""
            SELECT * FROM merged_table
            WHERE REPLACE(대출대상, ' ', '') LIKE :target
        """)
        params = {"target": f"%{detected_target}%"}

    else:
        # 상세종류/대출대상 모두 탐지 실패 시 대출조건 기준 검색
        sql = text("""
            SELECT * FROM merged_table
            WHERE REPLACE(대출조건, ' ', '') LIKE :query
            LIMIT 5
        """)
        params = {"query": f"%{user_query.replace(' ', '')}%"}

    return sql, params


# ============================================================
# 5️⃣ 질의 수행 및 결과 반환
# ============================================================
def query_agent(user_query: str):
    sql, params = generate_sql(user_query)
    print(sql, params)
    df = pd.read_sql(sql, engine, params=params)

    if df.empty:
        return "❌ 조건에 맞는 대출상품을 찾을 수 없습니다."
    else:
        return df


# ============================================================
# 6️⃣ 실행 테스트 (CLI)
# ============================================================
"""
<질문 예시>
- 개인 사업자의 기업 대출상품 설명
- 군인을 대상으로 하는 담보대출 상품
- 개인을 대상으로 하는 대출 상품
- 개인사업자를 대상 대출상품
- 부동산 개인관련 상품
- 부동산 개인 사업자관련 상품
- 개인적으로 사업을 하는데, 신용대출 상품설명
- 개인사업 대상으로 신용대출 상품설명
- 분양계약자 신용대출 상품 설명
- 신용 대출 분양자 관련 상품
- 부부 신용대출 관련 상품
- 근로 소득자 신용 대출 상품
- 신용대출 상품 중에서 근로 소득자 대상
- 분양 계약자 부동산 대출 상품 설명
- 분양자 부동산관련 대출상품
- 근로소득자 신용대출 상품
- 근로자 신용대출 상품
- 담보 대출 군인 상품
- 담보 대출 근로자 상품
- 담보 대출 주택 건설 등록업자 상품
- 담보대출 주택 건설업 상품
- 폐업한 사람의 정책자금관련 대출상품
- 담보대출 상품
"""
if __name__ == "__main__":
    print("💬 대출상품 SQL Agent 실행 중...\n")
    user_query = input("질문: ")
    result = query_agent(user_query)
    if isinstance(result, str):
        print(result)
    else:
        print("\n[조회 결과]")
        print(result[["상품명", "상세종류", "대출대상", "대출조건"]])
        print("\n" + "=" * 50 + "\n")
        print(result[["대출기간", "대출한도"]])
        print("\n" + "=" * 50 + "\n")
