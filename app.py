"""
은행상품 검색 LLM - Streamlit App

Multi-Agent RAG 시스템을 사용한 은행 상품 질의응답 서비스
"""

import streamlit as st
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.graph.build import create_rag_system
from rag.llm.get_llm import get_llm_model
from rag.vectorstore.pgvector_store import PgVectorStore
from rag.embeddings.openai_embed import OpenAIEmbeddings
from rag.db.connection import DatabaseConnection
from rag.core.config import get_config


# 페이지 설정
st.set_page_config(
    page_title="은행상품 검색 LLM",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #1f77b4;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left: 4px solid #4caf50;
    }
    .info-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_system():
    """RAG 시스템 초기화 (캐싱)"""
    try:
        # 설정 로드
        config = get_config()
        
        # LLM 초기화
        llm = get_llm_model()
        
        # DB 연결
        db = DatabaseConnection(config.DB_URL)
        
        # Embeddings 초기화
        embeddings = OpenAIEmbeddings(
            model=config.EMBED_MODEL,
            api_key=config.OPENAI_API_KEY
        )
        
        # VectorStore 초기화
        vectorstore = PgVectorStore(
            connection=db,
            embeddings=embeddings
        )
        
        # RAG 시스템 생성
        graph = create_rag_system(
            llm=llm,
            vectorstore=vectorstore,
            top_k=8,
            relevance_threshold=35.0,
            enable_langsmith=False
        )
        
        return graph, config
    
    except Exception as e:
        st.error(f"시스템 초기화 실패: {e}")
        return None, None


def main():
    """메인 앱"""
    
    # 헤더
    st.markdown('<div class="main-header">🏦 은행상품 검색 LLM</div>', unsafe_allow_html=True)
    
    # 사이드바
    with st.sidebar:
        st.header("⚙️ 설정")
        
        # 시스템 정보
        st.subheader("시스템 정보")
        st.info("""
        **Multi-Agent RAG 시스템**
        - 생성 LLM: gpt-4o-mini
        - 평가 LLM: gpt-4o
        - 검색: SQL + VectorDB + Web
        """)
        
        # 검색 설정
        st.subheader("검색 설정")
        top_k = st.slider("검색 청크 수", 4, 16, 8)
        threshold = st.slider("관련성 임계값", 0.0, 100.0, 35.0, 5.0)
        
        # 고급 설정
        with st.expander("고급 설정"):
            enable_langsmith = st.checkbox("LangSmith 추적", value=False)
            show_debug = st.checkbox("디버그 정보 표시", value=False)
        
        # 초기화 버튼
        if st.button("🔄 시스템 재시작"):
            st.cache_resource.clear()
            st.rerun()
        
        # 도움말
        with st.expander("💡 사용 팁"):
            st.markdown("""
            **질문 예시:**
            - 우리은행 전세자금대출 금리는?
            - 국민은행 신용대출 조건 알려줘
            - 전문직 대상 대출 상품 추천해줘
            - KB국민은행 주택담보대출 한도는?
            
            **검색 범위:**
            - 우리은행, 국민은행
            - 대출, 예금, 적금 상품
            """)
    
    # 시스템 초기화
    with st.spinner("시스템 초기화 중..."):
        graph, config = initialize_system()
    
    if graph is None:
        st.error("시스템을 초기화할 수 없습니다. 환경 설정을 확인해주세요.")
        return
    
    st.success("✅ 시스템 준비 완료")
    
    # 세션 상태 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # 채팅 기록 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # 디버그 정보 표시
            if show_debug and "debug" in message:
                with st.expander("🔍 디버그 정보"):
                    st.json(message["debug"])
    
    # 채팅 입력
    if prompt := st.chat_input("은행 상품에 대해 질문하세요..."):
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # AI 응답 생성
        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                try:
                    # RAG 시스템 실행
                    result = graph.invoke({"question": prompt})
                    
                    # 답변 추출
                    answer = result.get("answer", "답변을 생성할 수 없습니다.")
                    
                    # 답변 표시
                    st.markdown(answer)
                    
                    # 메타 정보 표시
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        sql_count = len(result.get("sql_results", []))
                        st.metric("SQL 검색", f"{sql_count}개 상품")
                    
                    with col2:
                        vector_count = result.get("vector_chunks_count", 0)
                        st.metric("Vector 검색", f"{vector_count}개 청크")
                    
                    with col3:
                        relevant_count = result.get("relevant_chunks_count", 0)
                        st.metric("관련 청크", f"{relevant_count}개")
                    
                    # 디버그 정보
                    debug_info = {
                        "intent": result.get("intent"),
                        "bank_name": result.get("bank_name"),
                        "product_name": result.get("product_name"),
                        "product_type": result.get("product_type"),
                        "confidence": result.get("confidence", 0.0),
                        "sql_results_count": sql_count,
                        "vector_chunks_count": vector_count,
                        "relevant_chunks_count": relevant_count,
                    }
                    
                    # 세션에 저장
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "debug": debug_info
                    })
                    
                except Exception as e:
                    error_msg = f"오류가 발생했습니다: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
    
    # 하단 정보
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption("🏦 우리은행 · 국민은행")
    
    with col2:
        st.caption("💡 대출 · 예금 · 적금")
    
    with col3:
        st.caption("🤖 Multi-Agent RAG")


if __name__ == "__main__":
    main()
