# 상위 디렉토리를 모듈 탐색 경로에 추가
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import json
import re
from typing import List, Dict, Any
from LangGraph.llm import get_llm_model
from langchain.prompts import PromptTemplate

# --- 내부 유틸 ---
def _extract_json_block(text: str) -> str:
    """
    응답 내에서 첫 번째 JSON 오브젝트 블록만 추출.
    예: '...```json { ... } ``` ...' 같은 경우에도 동작.
    """
    if not text:
        return ""
    # 코드펜스 제거
    text = re.sub(r"```(?:json)?\s*|\s*```", "", text, flags=re.IGNORECASE)
    # 첫 번째 { ... } 캡처
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return m.group(0) if m else text  # 그래도 없으면 원문 반환(파싱 시도)

def _safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        # 여전히 실패하면 공백/제어문자 정리 후 재시도
        try:
            return json.loads(text.strip())
        except Exception:
            return {}

def _normalize_eval(parsed: Dict[str, Any]) -> Dict[str, Any]:
    # 기본값
    eval_results = str(parsed.get("eval_results", "NO")).upper()
    eval_score = parsed.get("eval_score", 0.0)
    eval_reasoning = parsed.get("eval_reasoning", "")

    # 결과 표준화
    if eval_results not in ("YES", "NO"):
        eval_results = "NO"
    try:
        eval_score = float(eval_score)
    except Exception:
        eval_score = 0.0
    # 0~100 클램프
    if eval_score < 0: eval_score = 0.0
    if eval_score > 100: eval_score = 100.0

    return {
        "eval_results": eval_results,
        "eval_score": eval_score,
        "eval_reasoning": str(eval_reasoning),
    }

# --> 벡터DB 데이터를 평가하는 노드 (개선 프롬프트)
def __get_prompt_for_eval():
    system_template = """
You are a strict evaluator. Return ONLY valid JSON.

Evaluate how well the retrieved VectorDB contents support answering the user's question.
Be conservative: if the contents do not directly support the question, return "NO" with a low score.

Output JSON schema (no extra keys, no explanations outside JSON):
{{
  "eval_results": "YES" or "NO",
  "eval_score": number,   // 0 to 100
  "eval_reasoning": "short explanation in Korean"
}}

UserQuestion:
{question}

VectorDBContents:
{contents}
""".strip()
    return PromptTemplate.from_template(template=system_template)

def eval_node(state, deps: Any = None):
    """벡터 검색 결과가 질문에 답하기 충분한지 LLM으로 평가한다."""
    chain = __get_prompt_for_eval() | get_llm_model()  # LLM 인스턴스 재사용

    # contents 정규화
    contents_value = state.get("contents", [])
    if isinstance(contents_value, str):
        contents_sequence: List[str] = [contents_value]
    elif isinstance(contents_value, list):
        contents_sequence = [str(x) for x in contents_value]
    else:
        contents_sequence = [str(contents_value)]

    # 빈 근거 처리: 검색 근거가 전혀 없으면 바로 NO
    if len(contents_sequence) == 0 or all(len(c.strip()) == 0 for c in contents_sequence):
        state.update({
            "eval_results": "NO",
            "eval_score": 0.0,
            "eval_reasoning": "검색된 근거가 없어 질문을 지지할 수 없습니다."
        })
        return state

    contents_joined = "\n\n---\n\n".join(contents_sequence)

    # LLM 호출
    result = chain.invoke({
        "question": state.get("question", ""),
        "contents": contents_joined
    })

    # 응답 정규화 (list/chunk/string)
    raw_content = getattr(result, "content", result)
    if isinstance(raw_content, list):
        # OpenAI류 chunk 포맷 대응
        try:
            raw_content = "".join(
                (part.get("text", "") if isinstance(part, dict) else str(part))
                for part in raw_content
            )
        except Exception:
            raw_content = "".join(map(str, raw_content))
    else:
        raw_content = str(raw_content)

    # JSON 추출 및 파싱
    json_str = _extract_json_block(raw_content)
    parsed = _safe_json_loads(json_str)

    # 파싱 실패 시 안전 기본값
    if not parsed:
        parsed = {
            "eval_results": "NO",
            "eval_score": 0.0,
            "eval_reasoning": "LLM 응답을 JSON으로 파싱하지 못했습니다."
        }

    normalized = _normalize_eval(parsed)

    # state 업데이트
    state.update({
        "eval_results": normalized["eval_results"],
        "eval_score": normalized["eval_score"],
        "eval_reasoning": normalized["eval_reasoning"],
    })
    return state
