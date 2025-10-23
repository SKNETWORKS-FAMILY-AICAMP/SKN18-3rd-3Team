import re
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from rapidfuzz import fuzz, process
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


# -----------------------
# 0️⃣ DB 연결 및 임베딩 모델
# -----------------------
DB_URI = "postgresql+psycopg2://admin:admin123@localhost:5432/multiagent_db"
TABLE = "merged_table"
engine = create_engine(DB_URI, future=True)
embed_model = SentenceTransformer("intfloat/multilingual-e5-base")


# -----------------------
# 🔧 유틸 함수: 텍스트 정규화
# -----------------------
def normalize_text(s: str) -> str:
    """문자 + 숫자만 남기고, 공백 및 특수문자 제거 + 로마 숫자(Ⅰ~Ⅹ, I~X) 변환"""
    if not s:
        return ""

    # ① 유니코드 로마 숫자 → 아라비아 숫자
    roman_map = {
        "Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5",
        "Ⅵ": "6", "Ⅶ": "7", "Ⅷ": "8", "Ⅸ": "9", "Ⅹ": "10"
    }
    for r, a in roman_map.items():
        s = s.replace(r, a)

    # ② ASCII 로마 숫자 (긴 패턴부터 변환)
    ascii_roman_map = [
        ("X", "10"), ("IX", "9"), ("VIII", "8"), ("VII", "7"),
        ("VI", "6"), ("V", "5"), ("IV", "4"), ("III", "3"),
        ("II", "2"), ("I", "1")
    ]
    for r, a in ascii_roman_map:
        s = re.sub(rf"\b{r}\b", a, s, flags=re.IGNORECASE)

    # ③ 문자 + 숫자만 남기기
    return re.sub(r"[^가-힣A-Za-z0-9]", "", s)


# -----------------------
# 1️⃣ KeywordAnalyzer
# -----------------------
class KeywordAnalyzer:
    def __init__(self, bank_list, product_list, sim_threshold=78):
        self.bank_list = bank_list
        self.product_list = product_list
        self.sim_threshold = sim_threshold

    def detect_fields(self, query):
        detected = []
        info = {}
        q_nospace = query.replace(" ", "")

        # ① 은행명 감지
        bank_found = None
        for bank in self.bank_list:
            if bank.replace(" ", "") in q_nospace:
                detected.append("은행명")
                info["은행명"] = bank
                bank_found = bank
                break

        # ② 조항 감지
        clause_match = re.search(r"(?:제\s*)?([0-9]+)\s*(?:조|조항)?", query)
        if clause_match:
            detected.append("조항")
            info["조항"] = f"제{clause_match.group(1)}조"

        # ③ 상품명 fuzzy 탐지
        q_nobank = q_nospace
        if bank_found:
            q_nobank = q_nobank.replace(bank_found.replace(" ", ""), "")

        best_prod, best_sim = None, 0
        for prod in self.product_list:
            prod_norm = normalize_text(prod)
            sim = max(
                fuzz.token_sort_ratio(normalize_text(q_nobank), prod_norm),
                fuzz.partial_ratio(normalize_text(q_nobank), prod_norm)
            )
            if sim > best_sim:
                best_prod, best_sim = prod, sim

        # ✅ 상품명 인식 강화
        if best_sim >= self.sim_threshold:
            detected.append("상품이름")
            info["상품이름"] = best_prod
        else:
            info.setdefault("product_candidate_tokens", []).append(q_nobank)

        # 후보 텍스트
        info.setdefault("text_candidate_tokens", []).append(query)

        return detected, info


# -----------------------
# 2️⃣ DB 상품 fuzzy match
# -----------------------
def match_product_from_db_fuzzy(token: str, col_name="상품이름", limit=200, sim_threshold=70):
    pat = f"%{token.replace(' ', '')}%"
    sql = text(f"SELECT DISTINCT {col_name} FROM {TABLE} WHERE {col_name} ILIKE :pat LIMIT :limit")

    with engine.connect() as conn:
        rows = conn.execute(sql, {"pat": pat, "limit": limit}).fetchall()

    candidates = [r[0] for r in rows if r[0] is not None]
    if not candidates:
        return None, 0

    # 완전 일치 우선
    for c in candidates:
        if normalize_text(c) == normalize_text(token):
            return c, 100

    # fuzzy 매칭
    best = process.extractOne(token, candidates, scorer=fuzz.token_sort_ratio)
    if best and best[1] >= sim_threshold:
        return best[0], int(best[1])

    return None, 0


# -----------------------
# 3️⃣ CoordinatorAgent (Ⅲ→3 변환 포함)
# -----------------------
class CoordinatorAgent:
    def __init__(self, db_engine, bank_list, product_list):
        self.engine = db_engine
        self.analyzer = KeywordAnalyzer(bank_list, product_list)
        self.embed_model = embed_model

        inspector = inspect(self.engine)
        cols = [col['name'] for col in inspector.get_columns(TABLE)]
        self.field_map = {}
        if "은행명" in cols:
            self.field_map["은행명"] = "은행명"
        if "상품명" in cols:
            self.field_map["상품이름"] = "상품명"
        elif "상품이름" in cols:
            self.field_map["상품이름"] = "상품이름"
        if "조항" in cols:
            self.field_map["조항"] = "조항"
        if "text" in cols:
            self.field_map["text"] = "text"

    def query_database(self, user_query):
        fields, info = self.analyzer.detect_fields(user_query)
        print("👉 감지된 필드:", fields)
        print("👉 초기 매칭정보:", info)

        # DB fuzzy 매칭
        if "상품이름" not in info and info.get("product_candidate_tokens"):
            for tok in info["product_candidate_tokens"]:
                matched_prod, score = match_product_from_db_fuzzy(tok, col_name=self.field_map["상품이름"])
                print("DB fuzzy 후보:", matched_prod, score)
                if matched_prod and score >= 70:
                    info["상품이름"] = matched_prod
                    if "상품이름" not in fields:
                        fields.append("상품이름")
                    break

        # WHERE 절 구성
        where_clauses = []
        params = {}

        for f in fields:
            db_col = self.field_map.get(f)
            if not db_col:
                continue

            if f == "조항":
                num_match = re.search(r"\d+", info["조항"])
                if num_match:
                    clause_num = num_match.group(0)
                    where_clauses.append(
                        f"regexp_replace({db_col}::text, '[^0-9]', '', 'g') ILIKE :clause_num"
                    )
                    params["clause_num"] = f"%{clause_num}%"

            elif f == "상품이름":
                prod_norm = normalize_text(info[f])
                # ✅ 유니코드 로마자(Ⅰ~Ⅹ) → 숫자로 변환 후 정규화 검색
                where_clauses.append(
                    f"""
                    regexp_replace(
                        translate({db_col},
                            'ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ',
                            '1234567890'
                        ),
                        '[^가-힣A-Za-z0-9]', '', 'g'
                    ) ILIKE :prod_norm
                    """
                )
                params["prod_norm"] = f"%{prod_norm}%"

            else:
                where_clauses.append(f"{db_col} = :{f}")
                params[f] = info[f]

        sql_query = f"SELECT * FROM {TABLE}"
        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)
        sql_query += " LIMIT 50"

        print("📘 생성된 SQL:", sql_query)
        print("📘 파라미터:", params)

        with self.engine.connect() as conn:
            df = pd.read_sql(text(sql_query), con=conn, params=params)

        if df.empty or not fields:
            return {"mode": "no_match", "message": "⚠️ 조건 일치 없음", "rows": None}

        return {"mode": "match", "message": "✅ 결과 반환 성공", "rows": df}

    def semantic_search(self, query, top_k=3, max_rows=1000):
        if "text" not in self.field_map:
            return []
        sql = text(
            f"SELECT text, 은행명, {self.field_map.get('상품이름','상품명')}, 조항 FROM {TABLE} "
            "WHERE text IS NOT NULL LIMIT :max_rows"
        )
        with self.engine.connect() as conn:
            df = pd.read_sql(sql, con=conn, params={"max_rows": max_rows})

        if df.empty:
            return []

        texts = df["text"].astype(str).tolist()
        q_emb = self.embed_model.encode([query])
        text_embs = self.embed_model.encode(texts)
        sims = cosine_similarity(q_emb, text_embs)[0]
        idxs = np.argsort(sims)[::-1][:top_k]

        results = []
        for i in idxs:
            results.append({
                "text": texts[i],
                "score": float(sims[i]),
                "은행명": df.iloc[i].get("은행명"),
                "상품이름": df.iloc[i].get(self.field_map.get("상품이름", "상품명")),
                "조항": df.iloc[i].get("조항")
            })
        return results


# -----------------------
# 4️⃣ 실행 (테스트 질의 반영)
# -----------------------
if __name__ == "__main__":
    with engine.connect() as conn:
        bank_query = text(f"SELECT DISTINCT 은행명 FROM {TABLE} WHERE 은행명 IS NOT NULL;")
        bank_rows = conn.execute(bank_query).fetchall()
        banks = [r[0] for r in bank_rows if r[0]]

        inspector = inspect(engine)
        cols = [col['name'] for col in inspector.get_columns(TABLE)]
        product_col = "상품이름" if "상품이름" in cols else "상품명"
        prod_query = text(f"SELECT DISTINCT {product_col} FROM {TABLE} WHERE {product_col} IS NOT NULL;")
        prod_rows = conn.execute(prod_query).fetchall()
        products = [r[0] for r in prod_rows if r[0]]

    print(f"✅ 불러온 은행 목록 ({len(banks)}개):", banks)
    print(f"✅ 불러온 상품 목록 ({len(products)}개):", products)

    agent = CoordinatorAgent(engine, banks, products)

    queries = [
            "국민은행 KB스타 건강적금 6조항에 대해 알려줘.",
            "국민 은행 KB스타 건강 적금에 대해 알려줘.",
            "우리은행 상품별 금리를 알려줘.",
            "우리 은행 예금거래 기본약관 제5조에 대해 설명해줘.",
            "우리은행 예금 거래 기본 약관에 대해 설명",
            "국민은행 KB 올인원급여통장에 대해 설명해줘.",
            "fsdljksfd",
            "KB 스타적금에 대해 설명",
            "KB 스타 건강적금 7조항 정보",
            "KB 스타적금III의 제2조",
            "KB스타적금Ⅲ 조항 3",
            "KB 스타플러스통장 적용범위",  # ✅ 상품이름 + 조항이름
            "위비 모바일 통장 제한사항에 대해 알려줘.",  # ✅ 상품이름 + 조항이름
            "우리은행에서 위비 모바일통장 제한사항 상세 설명."  # ✅ 은행명 + 상품이름 + 조항이름
        ]

    for q in queries:
            print("\n===============================")
            print("💬 사용자 질의:", q)
            out = agent.query_database(q)

            if out["mode"] == "match":
                print(out["message"])
                print(out["rows"].head(3))
            else:
                print(out["message"])