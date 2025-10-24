from __future__ import annotations

import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Dict, List, Any

import streamlit as st

# ---- 경로 설정 -----------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from LangGraph.LangGraph import compile_langgraph


# ---- LangGraph 초기화 (세션 전체에서 재사용) -----------------------------
@st.cache_resource(show_spinner=False)
def get_graph():
    """LangGraph 그래프를 싱글턴처럼 캐시."""
    return compile_langgraph()


# ---- Streamlit 레이아웃 -------------------------------------------------
st.set_page_config(page_title="은행 약관 챗봇", page_icon="🏦")
st.title("🏦 은행 약관 챗봇")
st.caption("은행 상품/약관 관련 질문을 입력하면 LangGraph 파이프라인이 답변을 생성합니다.")

if "history" not in st.session_state:
    st.session_state.history: List[Dict[str, Any]] = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"streamlit-{uuid.uuid4().hex}"

graph = get_graph()


def render_sources(sources: List[Dict[str, Any]] | None) -> None:
    """근거 문서 메타데이터를 표 형태로 렌더링."""
    if not sources:
        st.write("근거 데이터가 없습니다.")
        return
    for idx, meta in enumerate(sources, start=1):
        with st.expander(f"근거 {idx}", expanded=False):
            for key, value in meta.items():
                st.markdown(f"- **{key}**: {value}")


# 기존 대화 표시
for message in st.session_state.history:
    role = message["role"]
    with st.chat_message("assistant" if role == "assistant" else "user"):
        st.markdown(message["content"])
        if role == "assistant" and message.get("sources"):
            render_sources(message["sources"])


# ---- 사용자 입력 처리 ---------------------------------------------------
prompt = st.chat_input("은행 상품이나 약관 관련 질문을 입력해 주세요.")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("생각 중입니다… ⏳")

        try:
            result = graph.invoke(
                {"question": prompt},
                config={"configurable": {"thread_id": st.session_state.thread_id}},
            )

            answer = result.get("final_answer") or result.get("followup_question")
            if not answer:
                answer = "죄송하지만 답변을 생성하지 못했습니다. 질문을 다시 확인해 주세요."

            strategy = result.get("generation_strategy", "unknown")
            eval_results = result.get("eval_results")
            eval_score = result.get("eval_score")
            sources = result.get("sources") or []

            markdown_lines = [answer]
            markdown_lines.append(f"\n_응답 전략_: **{strategy}**")
            if eval_results is not None:
                markdown_lines.append(f"_VectorDB 평가_: {eval_results} ({eval_score})")
            if error := result.get("web_error"):
                markdown_lines.append(f"_웹 검색 오류_: {error}")

            placeholder.markdown("\n\n".join(markdown_lines))
            if sources:
                render_sources(sources)

            st.session_state.history.append(
                {
                    "role": "assistant",
                    "content": "\n\n".join(markdown_lines),
                    "sources": sources,
                }
            )
        except Exception as exc:
            error_message = "그래프 실행 중 오류가 발생했습니다. 로그를 확인해 주세요."
            placeholder.error(error_message)
            st.exception(exc)
            st.session_state.history.append(
                {
                    "role": "assistant",
                    "content": f"{error_message}\n\n```\n{traceback.format_exc()}\n```",
                }
            )

    st.rerun()
