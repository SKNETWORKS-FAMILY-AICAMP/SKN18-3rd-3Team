# 질문 정규화 및 키워드 추출 에이전트

from __future__ import annotations
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

###################################################
# 고정 라벨
###################################################

# 질문 목적
ALLOWED_INTENTS = {"rate_fee_lookup", "clause_lookup", "compare", "definition", "other"}
ALLOWED_TAGS = {"rate", "fee", "early_close", "preferential", "eligibility"}

# 상품 유형
PRODUCT_TYPES = {"예금", "적금", "대출"}

LOAN_TYPES = {
    "부동산대출", "기업대출", "주택도시기금대출", "전세자금대출", "담보대출", "신용대출", "정책자금대출"
}

TARGET_SET = {
    "개인","세대주","전문직","임차인","기업","장애인","근로소득자","임직원","부부",
    "개인사업자","공무원","주택매매","분양계약자","담보","군인","소상공인","주택건설등록업자",
    "분양","주택소유","폐업"
}

###################################################
# 키워드 후보
###################################################

BANK_ALIASES: Dict[str, str] = {
    "우리": "우리은행",
    "국민": "국민은행",
    "우리 은행": "우리은행",
    "국민 은행": "국민은행",
    "KB국민은행": "국민은행",
    "woori bank": "우리은행",
    "kb bank": "국민은행",
    "woori": "우리은행",
    "kb": "국민은행",
}

TARGET_SYNONYM: Dict[str, str] = {
    "의사": "전문직",
    "변호사": "전문직",
    "판사": "전문직",
    "전문자격증": "전문직",
    "doctor": "전문직",
    "lawyer": "전문직",
    "임대차": "임차인",
    "세입자": "임차인",
    "자영업자": "개인사업자",
    "프리랜서": "개인사업자",  # 상황에 따라 수정
    "state-employee": "공무원",
    "군복무자": "군인"
}

###################################################
# LLM 정규화 이전 간단한 정규화 진행
###################################################

def norm_key(s: str) -> str:
    """간단 정규화: 소문자, 공백/특수문자 제거"""
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"[\s\-\_\.\·/]+", "", s)
    return s

def _dedup(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _tokenize_keywords(*texts: Optional[str]) -> List[str]:
    tokens: List[str] = []
    for text in texts:
        if not text:
            continue
        tokens.extend(re.findall(r"[가-힣A-Za-z0-9]+", text))
    # 한 글자 토큰은 노이즈가 커서 제거
    return [tok for tok in tokens if len(tok) > 1]

def extract_topk_candidates(question: str, K: int = 6) -> Tuple[List[str], List[str]]:
    """질문에서 은행 후보만 뽑고, 상품 후보는 LLM에 전적으로 맡깁니다."""
    nk_q = norm_key(question)

    # 은행 후보만 유지
    banks: List[Tuple[str,int]] = []
    for alias, canonical in BANK_ALIASES.items():
        score = 0
        aka = norm_key(alias)
        if alias in question: score += 2
        if aka in nk_q: score += 2
        if len(alias) >= 2 and any(tok and tok in alias for tok in re.findall(r"[가-힣A-Za-z0-9]+", question)):
            score += 1
        if score:
            banks.append((canonical, score))
    banks = [b for b,_ in sorted(banks, key=lambda x: -x[1])][:K]
    banks = _dedup(banks)

    # 상품 후보는 제공하지 않음
    prods: List[str] = []

    return banks, prods


###################################################
# LLM 실패 시 룰베이스 보조 함수
###################################################

def infer_product_type(question: str) -> Optional[str]:
    if re.search(r"대출", question):
        return "대출"
    if re.search(r"적금", question):
        return "적금"
    if re.search(r"예금|금리", question):
        return "예금"
    return None

def normalize_loan_type(text: Optional[str], question: str) -> Optional[str]:
    if not text and not question:
        return None
    cand = text or ""
    src = f"{cand} {question}"

    # 직접 매칭
    for lt in LOAN_TYPES:
        if lt in src:
            return lt
    return None

def normalize_loan_target(text: Optional[str], question: str) -> Optional[str]:
    if not text and not question:
        return None
    cand = text or ""
    src = f"{cand} {question}"
    for k, v in TARGET_SYNONYM.items():
        if k in src:
            return v
    for t in TARGET_SET:
        if t in src:
            return t
    return None

def rule_based_guess(question: str) -> Dict[str, Any]:
    """LLM 실패 시 최소한의 구조화 결과를 제공합니다."""
    ptype = infer_product_type(question)
    loan_type = normalize_loan_type(None, question) if ptype == "대출" else None
    loan_target = normalize_loan_target(None, question) if ptype == "대출" else None
    tags = []
    if re.search(r"금리|이자|우대", question):
        tags.append("rate")
        if "우대" in question:
            tags.append("preferential")
    if re.search(r"수수료|수수", question):
        tags.append("fee")
    if re.search(r"중도해지|중도 상환|중도상환", question):
        tags.append("early_close")

    return {
        "intent": "rate_fee_lookup" if ("금리" in question or "수수료" in question) else "other",
        "bank_name": None,
        "product_name": None,
        "product_type": ptype,
        "loan_type": loan_type,
        "loan_target": loan_target,
        "clause_keywords": _dedup([t for t in tags if t in ALLOWED_TAGS]),
        "applicability_hint": None,
        "raw_keywords": [],
        "confidence": 0.35,
        "reasoning": "규칙 기반 최소 추정",
    }

###################################################
# LLM 프롬프트
###################################################

SYSTEM_PROMPT = (
    "당신은 한국 금융상품 Q&A의 의도/개체 추출기입니다.\n"
    "반드시 JSON만 출력하세요. 허용된 라벨만 사용하세요.\n"
    "intent: [rate_fee_lookup, clause_lookup, compare, definition, other]\n"
    "clause_keywords: [rate, fee, early_close, preferential, eligibility] 중 필요한 것만.\n"
    'product_type: ["예금","적금","대출"] 중 하나 또는 null.\n'
    "만약 product_type가 '대출'이면, loan_type은 "
    "[부동산대출, 기업대출, 주택도시기금대출, 전세자금대출, 담보대출, 신용대출, 정책자금대출] 중 하나 또는 null.\n"
    "loan_target은 아래 후보 중 하나 또는 null입니다.\n"
    "후보: 개인, 세대주, 전문직, 임차인, 기업, 장애인, 근로소득자, 임직원, 부부, 개인사업자, 공무원, "
    "주택매매, 분양계약자, 담보, 군인, 소상공인, 주택건설등록업자, 분양, 주택소유, 폐업\n"
    "허용된 값 외의 새 태그/용어를 만들지 마세요.\n"
    "가능하면 confidence(0.0~1.0)와 reasoning(1~2문장)을 포함하세요.\n"
)

def build_user_prompt(question: str, bank_cands: List[str], prod_cands: List[str]) -> str:
    lines = [f'질문: "{question}"', ""]
    if bank_cands:
        lines.append("은행 후보:")
        for b in bank_cands:
            lines.append(f"- {b}")
        lines.append("")
    if prod_cands:
        lines.append("상품 후보:")
        for p in prod_cands:
            lines.append(f"- {p}")
        lines.append("")
    lines.append(
        "반드시 다음 키를 포함한 JSON으로만 답하세요: "
        "intent, bank_name, product_name, product_type, loan_type, loan_target, "
        "clause_keywords, applicability_hint, raw_keywords, confidence, reasoning"
    )
    lines.append("")
    lines.append('예시: {"intent":"rate_fee_lookup","bank_name":null,"product_name":null,'
                 '"product_type":"대출","loan_type":"전세자금대출","loan_target":"임차인",'
                 '"clause_keywords":["rate"],"applicability_hint":null,"raw_keywords":["금리"],'
                 '"confidence":0.75,"reasoning":"전세자금대출 금리 문의"}')
    return "\n".join(lines)

def safe_json_loads(text: str) -> Dict[str, Any]:
    t = text.strip()
    # 코드블록 안전 처리
    if t.startswith("```"):
        t = t.strip("`")
        # optional leading language marker
        t = re.sub(r"^json", "", t, flags=re.IGNORECASE).strip()
    try:
        return json.loads(t)
    except Exception:
        # best-effort 추출: 중괄호 가장 바깥 블럭만 파싱 시도
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}

###################################################
# Agent 실행 함수
###################################################
def make_llm_fn(model):
    def llm_fn(system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        resp = model.invoke(messages)
        if hasattr(resp, "content"):
            return resp.content
        return str(resp)
    return llm_fn


def run_intent_agent(
    question: str,
    llm: Optional[Any] = None,
    confidence_threshold: float = 0.55,
    topk: int = 6,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Parameters
    ----------
    question : str
        사용자 질문 원문(한국어 기준).
    llm : Any | None
        LLM 모델 객체. (예: get_llm_model() 결과)
        내부에서 make_llm_fn(llm)을 호출해 (system,user)→str 어댑터를 만듭니다.
    confidence_threshold : float
        LLM 결과 채택 임계값.
    topk : int
        후보 목록 길이.
    debug : bool
        디버그 정보를 함께 반환할지 여부.

    Returns
    -------
    Dict[str, Any]
        위 스키마의 결과 딕셔너리 + (debug가 True면 "debug" 키 추가)
    """
    bank_cands, prod_cands = extract_topk_candidates(question, K=topk)

    # llm_fn 준비
    llm_fn = make_llm_fn(llm) if llm is not None else None

    # LLM 경로
    if llm_fn is not None:
        sys_prompt = SYSTEM_PROMPT
        user_prompt = build_user_prompt(question, bank_cands, prod_cands)
        model_text = llm_fn(sys_prompt, user_prompt)  # <- 사용자가 주입하는 함수
        model_out = safe_json_loads(model_text)

        # 스키마 정리/검증
        intent = model_out.get("intent")
        if intent not in ALLOWED_INTENTS:
            intent = "other"

        product_type = model_out.get("product_type")
        if product_type not in PRODUCT_TYPES and product_type is not None:
            # 보정
            product_type = infer_product_type(question)

        # 대출 관련 필드 정리
        loan_type = model_out.get("loan_type")
        loan_target = model_out.get("loan_target")
        if product_type == "대출":
            loan_type = normalize_loan_type(loan_type, question)
            loan_target = normalize_loan_target(loan_target, question)
            if loan_type not in LOAN_TYPES and loan_type is not None:
                loan_type = normalize_loan_type(None, question)
            if loan_target not in TARGET_SET and loan_target is not None:
                loan_target = normalize_loan_target(None, question)
        else:
            loan_type = None
            loan_target = None

        # 태그 필터
        clause = [t for t in (model_out.get("clause_keywords") or []) if t in ALLOWED_TAGS]

        confidence = float(model_out.get("confidence") or 0.0)
        result = {
            "intent": intent,
            "bank_name": model_out.get("bank_name"),
            "product_name": model_out.get("product_name"),
            "product_type": product_type,
            "loan_type": loan_type,
            "loan_target": loan_target,
            "clause_keywords": _dedup(clause),
            "applicability_hint": model_out.get("applicability_hint"),
            "raw_keywords": model_out.get("raw_keywords") or [],
            "confidence": confidence,
            "reasoning": model_out.get("reasoning") or "",
        }

        # 질문/상품명에서 추가 키워드를 추출해 raw_keywords에 보강
        extra_tokens = _tokenize_keywords(result.get("product_name"), question)
        if result.get("bank_name"):
            extra_tokens.extend(_tokenize_keywords(result.get("bank_name")))
        if extra_tokens:
            merged = result["raw_keywords"] + extra_tokens
            result["raw_keywords"] = _dedup([tok for tok in merged if tok])

        # 임계값 미만이면 폴백
        if not result["intent"] or confidence < confidence_threshold:
            rb = rule_based_guess(question)
            if debug:
                rb = {**rb, "debug": {"fallback": True, "llm_raw": model_out}}
            return rb

        if debug:
            result["debug"] = {
                "llm_text": model_text,
                "bank_candidates": bank_cands,
                "product_candidates": prod_cands,
            }
        return result

    # 규칙 기반만 사용하는 경로
    rb = rule_based_guess(question)
    if debug:
        rb["debug"] = {"fallback": True, "llm_raw": None}
    return rb


if __name__ == "__main__":
    # Agent 테스트
    # 상위 디렉토리를 모듈 탐색 경로에 추가
    from pathlib import Path
    import sys

    PROJECT_ROOT = Path(__file__).resolve().parents[3]  # 두 단계 위
    sys.path.insert(0, str(PROJECT_ROOT))

    # LLM 호출
    from rag.llm.llm import get_llm_model

    model = get_llm_model()

    q = "우리은행 전세자금대출 금리 알려줘"
    res = run_intent_agent(q, llm=model, debug=True)
    print(json.dumps(res, ensure_ascii=False, indent=2))
