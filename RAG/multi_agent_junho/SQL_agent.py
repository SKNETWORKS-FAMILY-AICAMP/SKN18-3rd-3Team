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

        # 은행명
        bank_found = None
        for bank in self.bank_list:
            if bank.replace(" ", "") in q_nospace:
                detected.append("은행명")
                info["은행명"] = bank
                bank_found = bank
                break

        # 조항
        clause_match = re.search(r"(?:제\s*)?([0-9]+)\s*(?:조|조항)", query)
        if clause_match:
            detected.append("조항")
            info["조항"] = f"제{clause_match.group(1)}조"

        # 상품명 fuzzy 탐지
        q_nobank = q_nospace
        if bank_found:
            q_nobank = q_nobank.replace(bank_found.replace(" ", ""), "")

        best_prod, best_sim = None, 0
        for prod in self.product_list:
            sim = max(
                fuzz.token_sort_ratio(q_nobank, prod.replace(" ", "")),
                fuzz.partial_ratio(q_nobank, prod.replace(" ", ""))
            )
            if sim > best_sim:
                best_prod, best_sim = prod, sim

        if best_sim >= self.sim_threshold:
            detected.append("상품이름")
            info["상품이름"] = best_prod

        # 후보 text 추가
        info.setdefault("text_candidate_tokens", []).append(query)
        if best_prod is None:
            info.setdefault("product_candidate_tokens", []).append(q_nobank)

        return detected, info

# -----------------------
# 2️⃣ DB 상품명 fuzzy/partial match
# -----------------------
def match_product_from_db_fuzzy(token: str, col_name="상품이름", limit=200, sim_threshold=70):
    pat = f"%{token.replace(' ', '')}%"
    sql = text(f"SELECT DISTINCT {col_name} FROM {TABLE} WHERE {col_name} ILIKE :pat LIMIT :limit")
    
    with engine.connect() as conn:
        rows = conn.execute(sql, {"pat": pat, "limit": limit}).fetchall()
    
    candidates = [r[0] for r in rows if r[0] is not None]
    if not candidates:
        return None, 0
    
    for c in candidates:
        if c.replace(" ", "") == token.replace(" ", ""):
            return c, 100
    
    best = process.extractOne(token, candidates, scorer=fuzz.token_sort_ratio)
    if best and best[1] >= sim_threshold:
        return best[0], int(best[1])
    
    return None, 0

# -----------------------
# 3️⃣ CoordinatorAgent 통합
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

        # 1️⃣ DB fuzzy 매칭으로 상품 후보
        if "상품이름" not in info and info.get("product_candidate_tokens"):
            for tok in info["product_candidate_tokens"]:
                matched_prod, score = match_product_from_db_fuzzy(tok, col_name=self.field_map["상품이름"])
                print("DB fuzzy 후보:", matched_prod, score)
                if matched_prod and score >= 70:
                    info["상품이름"] = matched_prod
                    if "상품이름" not in fields:
                        fields.append("상품이름")
                    break

        # 2️⃣ WHERE 절 구성
        where_clauses = []
        params = {}
        for f in fields:
            db_col = self.field_map.get(f)
            if not db_col:
                continue
            if f == "조항":
                num = re.search(r"\d+", info["조항"])
                if num:
                    where_clauses.append(f"{db_col}::text ILIKE :clause")
                    params["clause"] = f"%{num.group()}%"
            elif f == "상품이름":
                where_clauses.append(f"{db_col} ILIKE :prod_pat")
                params["prod_pat"] = f"%{info[f].replace(' ', '')}%"
            else:
                where_clauses.append(f"{db_col} = :{f}")
                params[f] = info[f]

        base = f"SELECT * FROM {TABLE}"
        sql_query = base
        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)
        sql_query += " LIMIT 50"

        print("📘 생성된 SQL:", sql_query)
        print("📘 파라미터:", params)

        with self.engine.connect() as conn:
            df = pd.read_sql(text(sql_query), con=conn, params=params)

        # 3️⃣ 조건 불일치 시 semantic search + 상품명 + 조항 필터링
        if df.empty:
            print("⚠️ 조건 일치 없음 → 의미검색으로 대체합니다.")
            sem_rows = self.semantic_search(user_query, top_k=10, max_rows=1000)

            # 상품명 필터링
            prod_pat = info.get("상품이름", "")
            # 조항 숫자 추출
            clause_num = ""
            if info.get("조항"):
                m = re.search(r"\d+", info["조항"])
                if m:
                    clause_num = m.group()

            filtered_rows = []
            for r in sem_rows:
                # 상품명 포함 여부
                if prod_pat.replace(" ", "") in str(r.get("상품이름", "")).replace(" ", ""):
                    # 조항 숫자 비교
                    if clause_num == ''.join(j for j in str(r.get("조항", "")) if j in "0123456789"):
                        r["상품이름_matched"] = r["상품이름"]
                        r["조항_matched"] = f"제{clause_num}조"
                        filtered_rows.append(r)
            sem_rows = filtered_rows

            return {"mode": "semantic", "rows": sem_rows}

        return {"mode": "match", "rows": df}

    def semantic_search(self, query, top_k=3, max_rows=1000):
        if "text" not in self.field_map:
            return []
        sql = text(f"SELECT text, 은행명, {self.field_map.get('상품이름','상품명')}, 조항 FROM {TABLE} WHERE text IS NOT NULL LIMIT :max_rows")
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
                "상품이름": df.iloc[i].get(self.field_map.get("상품이름","상품명")),
                "조항": df.iloc[i].get("조항")
            })
        return results

# -----------------------
# 4️⃣ 실행 예시
# -----------------------
if __name__ == "__main__":
    banks = ["우리은행", "신한은행", "하나은행", "국민은행"]
    products = ["청년희망적금", "예금거래기본약관", "우리 FLEX 정기예금", "KB 스타 건강적금"]

    agent = CoordinatorAgent(engine, banks, products)

    queries = [
        "국민은행 KB스타 건강적금 6조항에 대해 알려줘.",
        "우리은행 상품별 금리를 알려줘.",
        "우리은행 예금거래 기본약관 제5조에 대해 설명해줘."
    ]

    for q in queries:
        out = agent.query_database(q)
        print("모드:", out["mode"])
        if out["mode"] == "match":
            print(out["rows"].head(5))
        else:
            for r in out["rows"]:
                print(r)
