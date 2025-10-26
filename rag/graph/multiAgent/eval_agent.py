"""
Evaluation Agent

검색된 청크가 쿼리와 문맥상 관련성이 있는지 LLM으로 평가하는 에이전트
"""

from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional
from rag.core.logger import get_logger
from rag.llm.get_llm import get_eval_llm_model

logger = get_logger(__name__)


###################################################
# 내부 유틸 함수
###################################################

def _extract_json_block(text: str) -> str:
    """
    응답 내에서 첫 번째 JSON 블록만 추출.
    예: '...```json { ... } ``` ...' 같은 경우에도 동작.
    """
    if not text:
        return ""
    # 코드펜스 제거
    text = re.sub(r"```(?:json)?\s*|\s*```", "", text, flags=re.IGNORECASE)
    # 첫 번째 { ... } 또는 [ ... ] 캡처
    m = re.search(r"[\{\[].*[\}\]]", text, flags=re.DOTALL)
    return m.group(0) if m else text


def _safe_json_loads(text: str) -> List[Dict[str, Any]]:
    """안전한 JSON 파싱 (배열 반환)"""
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]
        return []
    except Exception:
        try:
            result = json.loads(text.strip())
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                return [result]
            return []
        except Exception:
            return []


def _normalize_eval(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """평가 결과 정규화"""
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
    if eval_score < 0:
        eval_score = 0.0
    if eval_score > 100:
        eval_score = 100.0

    return {
        "eval_results": eval_results,
        "eval_score": eval_score,
        "eval_reasoning": str(eval_reasoning),
    }


###################################################
# LLM 프롬프트
###################################################

EVAL_SYSTEM_PROMPT = """
You are a strict evaluator for banking product Q&A system. Return ONLY valid JSON array.

Evaluate EACH chunk individually to determine if it helps answer the user's question about banking products.

**Evaluation Criteria:**
- Direct Relevance (80-100): Chunk directly answers the question with specific information
- Indirect Relevance (50-79): Chunk provides related background or supporting information
- Low Relevance (20-49): Same product but different aspect
- Not Relevant (0-19): Completely unrelated content

**Consider for each chunk:**
- Does bank name and product name match the question?
- Does the clause title align with the question intent?
- Does the content contain key information to answer the question?
- Is the content actually usable for generating an answer?

**Important - Source Priority:**
- If there are conflicting information between Vector DB chunks and web search results, ALWAYS prioritize Vector DB information.
- Vector DB contains official banking product data and should be considered more reliable.
- When evaluating chunks, give higher relevance scores to Vector DB sources over web search sources if both address the same topic.

Output JSON array with one object per chunk:
[
  {{
    "chunk_id": "chunk ID",
    "is_relevant": true or false,
    "relevance_score": number,  // 0 to 100
    "reasoning": "short explanation in Korean (1-2 sentences)"
  }},
  ...
]

Be conservative: only mark as relevant if the chunk directly supports answering the question.
""".strip()


def build_eval_prompt(question: str, chunks: List[Dict[str, Any]]) -> str:
    """
    평가 프롬프트 생성
    
    Parameters
    ----------
    question : str
        사용자 질문
    chunks : List[Dict[str, Any]]
        평가할 청크 리스트
        
    Returns
    -------
    str
        포맷된 프롬프트
    """
    lines = [
        "=" * 80,
        "User Question:",
        "=" * 80,
        f'"{question}"',
        "",
        "=" * 80,
        "Retrieved Chunks (Vector DB + Web Search):",
        "=" * 80,
        ""
    ]
    
    for idx, chunk in enumerate(chunks, 1):
        chunk_id = chunk.get("chunk_id", f"chunk_{idx}")
        content = chunk.get("content", "")
        bank = chunk.get("bank_name", "")
        doc_name = chunk.get("document_name", "")
        product_name = chunk.get("product_name", "")
        clause = chunk.get("clause", "")
        clause_name = chunk.get("clause_name", "")
        similarity_score = chunk.get("similarity_score", 0.0)
        source = chunk.get("source", "vector_db")  # 기본값은 vector_db
        
        # 내용 길이 제한
        if len(content) > 400:
            content_preview = content[:400] + "... (truncated)"
        else:
            content_preview = content
        
        # 소스 표시
        source_label = "Vector DB" if source != "web_search" else "Web Search"
        
        lines.append(f"[Chunk {idx}] ID: {chunk_id} (Source: {source_label})")
        lines.append(f"Bank: {bank}")
        lines.append(f"Document: {doc_name}")
        lines.append(f"Product: {product_name}")
        lines.append(f"Clause: {clause} - {clause_name}")
        lines.append(f"Similarity Score: {similarity_score:.4f}")
        lines.append(f"Content: {content_preview}")
        lines.append("")
    
    lines.extend([
        "=" * 80,
        "",
        "Evaluate if these chunks collectively provide sufficient information to answer the question.",
        "Return JSON with eval_results (YES/NO), eval_score (0-100), and eval_reasoning."
    ])
    
    return "\n".join(lines)


###################################################
# Agent 실행 클래스
###################################################

class EvaluationAgent:
    """청크 관련성 평가 에이전트 (gpt-4o, temperature=0.0)"""
    
    def __init__(
        self,
        relevance_threshold: float = 35.0
    ):
        """
        Parameters
        ----------
        relevance_threshold : float
            관련성 임계값 (0-100, 기본값: 35.0)
        """
        # 항상 평가용 LLM 자동 생성
        logger.info("Creating eval LLM (gpt-4o, temperature=0.0)")
        self.llm = get_eval_llm_model()
        
        self.relevance_threshold = relevance_threshold
        logger.info(f"EvaluationAgent initialized with threshold={relevance_threshold}")
    
    def evaluate_chunks(
        self,
        question: str,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        청크 관련성 평가
        
        Parameters
        ----------
        question : str
            사용자 질문
        chunks : List[Dict[str, Any]]
            평가할 청크 리스트
            
        Returns
        -------
        List[Dict[str, Any]]
            관련성이 있다고 판단된 청크 리스트
        """
        if not chunks:
            logger.warning("No chunks to evaluate")
            return []
        
        # LLM 체크 (초기화 시 자동 생성되므로 이제 항상 존재)
        if not self.llm:
            logger.error("No LLM available for evaluation")
            return chunks
        
        logger.info(f"Evaluating {len(chunks)} chunks with eval LLM (gpt-4o, temperature=0.0)...")
        
        try:
            # 프롬프트 생성
            system_prompt = EVAL_SYSTEM_PROMPT
            user_prompt = build_eval_prompt(question, chunks)
            
            # LLM 호출
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            logger.debug(f"Sending evaluation request to LLM (prompt length: {len(user_prompt)} chars)")
            response = self.llm.invoke(messages)
            
            # 응답 정규화
            raw_content = getattr(response, "content", response)
            if isinstance(raw_content, list):
                try:
                    raw_content = "".join(
                        (part.get("text", "") if isinstance(part, dict) else str(part))
                        for part in raw_content
                    )
                except Exception:
                    raw_content = "".join(map(str, raw_content))
            else:
                raw_content = str(raw_content)
            
            logger.debug(f"Received LLM response (length: {len(raw_content)} chars)")
            
            # JSON 추출 및 파싱 (배열)
            json_str = _extract_json_block(raw_content)
            evaluations = _safe_json_loads(json_str)
            
            # 파싱 실패 시 모든 청크 반환
            if not evaluations:
                logger.warning("Failed to parse LLM evaluation response, returning all chunks")
                return chunks
            
            logger.info(f"Successfully parsed {len(evaluations)} chunk evaluations")
            
            # 청크 ID로 매핑
            eval_map = {}
            for eval_item in evaluations:
                chunk_id = eval_item.get("chunk_id", "")
                if chunk_id:
                    eval_map[chunk_id] = eval_item
            
            # 각 청크를 개별적으로 평가
            relevant_chunks = []
            filtered_out = []
            
            for chunk in chunks:
                chunk_id = chunk.get("chunk_id", "")
                eval_result = eval_map.get(chunk_id)
                
                if not eval_result:
                    # 평가 결과가 없으면 유사도 점수로 판단
                    similarity = chunk.get("similarity_score", 0.0)
                    if similarity >= (self.relevance_threshold / 100.0):
                        logger.warning(f"No eval for chunk {chunk_id}, using similarity {similarity:.2f}")
                        chunk["eval_result"] = {
                            "is_relevant": True,
                            "relevance_score": similarity,
                            "reason": "LLM 평가 없음, 유사도 점수 기반 선택"
                        }
                        relevant_chunks.append(chunk)
                    continue
                
                is_relevant = eval_result.get("is_relevant", False)
                relevance_score = float(eval_result.get("relevance_score", 0.0))
                reasoning = eval_result.get("reasoning", "")
                
                # 임계값 체크
                if is_relevant and relevance_score >= self.relevance_threshold:
                    chunk["eval_result"] = {
                        "is_relevant": True,
                        "relevance_score": relevance_score / 100.0,  # 0-1 스케일로 변환
                        "reason": reasoning
                    }
                    relevant_chunks.append(chunk)
                    logger.debug(f"✓ Chunk {chunk_id}: relevant (score={relevance_score:.1f}/100)")
                else:
                    filtered_out.append({
                        "chunk_id": chunk_id,
                        "score": relevance_score,
                        "reason": reasoning
                    })
                    logger.debug(f"✗ Chunk {chunk_id}: filtered out (score={relevance_score:.1f}/100)")
            
            logger.info(f"Evaluation complete: {len(relevant_chunks)}/{len(chunks)} chunks are relevant")
            
            if filtered_out:
                logger.info(f"Filtered out {len(filtered_out)} chunks:")
                for item in filtered_out[:3]:  # 처음 3개만 로깅
                    logger.info(f"  - {item['chunk_id']}: {item['score']:.1f}/100 - {item['reason'][:50]}...")
            
            return relevant_chunks
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            logger.warning("Returning all chunks due to evaluation error")
            return chunks
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node에서 호출하기 위한 헬퍼
        
        Parameters
        ----------
        state : Dict[str, Any]
            현재 상태 (question, vector_chunks 포함)
            
        Returns
        -------
        Dict[str, Any]
            relevant_chunks가 추가된 상태
        """
        question = state.get("question", "")
        vector_chunks = state.get("vector_chunks", [])
        
        # 청크 평가
        relevant_chunks = self.evaluate_chunks(question, vector_chunks)
        
        # 상태 업데이트
        state["relevant_chunks"] = relevant_chunks
        state["relevant_chunks_count"] = len(relevant_chunks)
        
        # 디버그 정보
        debug = state.get("debug", {})
        debug["eval"] = {
            "input_chunks": len(vector_chunks),
            "relevant_chunks": len(relevant_chunks),
            "threshold": self.relevance_threshold
        }
        state["debug"] = debug
        
        return state


###################################################
# Export
###################################################

__all__ = ["EvaluationAgent"]
