"""Streamlit UI for Bank RAG Q&A Service"""

import streamlit as st
from RAG.rag.engine import RAGEngine
from RAG.core.logger import get_logger

# Page config
st.set_page_config(
    page_title="은행 Q&A 서비스",
    page_icon="🏦",
    layout="wide"
)

# Initialize logger
logger = get_logger(__name__)

# Initialize RAG engine (cached)
@st.cache_resource
def get_rag_engine():
    """Initialize and cache RAG engine"""
    try:
        # Create progress indicators
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🔧 RAG 엔진 초기화 중... (0%)")
        progress_bar.progress(10)
        
        logger.info("Initializing RAG Engine...")
        
        status_text.text("📊 설정 로드 중... (20%)")
        progress_bar.progress(20)
        
        status_text.text("🗄️ 데이터베이스 연결 중... (40%)")
        progress_bar.progress(40)
        
        status_text.text("🤖 AI 모델 초기화 중... (60%)")
        progress_bar.progress(60)
        
        engine = RAGEngine()
        
        status_text.text("✅ 초기화 완료! (100%)")
        progress_bar.progress(100)
        
        logger.info("RAG Engine initialized successfully")
        
        # Clear progress indicators
        import time
        time.sleep(0.5)
        progress_bar.empty()
        status_text.empty()
        
        return engine
    except Exception as e:
        logger.error(f"Failed to initialize RAG Engine: {e}")
        st.error(f"시스템 초기화 실패: {str(e)}")
        return None

# Main UI
def main():
    st.title("🏦 우리은행 + 국민은행 Q&A 서비스")
    st.markdown("대출 및 예적금 상품에 대해 질문하세요!")
    
    # Initialize engine
    rag_engine = get_rag_engine()
    
    if rag_engine is None:
        st.error("⚠️ RAG 엔진을 초기화할 수 없습니다. 환경 설정을 확인해주세요.")
        return
    
    # Sidebar - Filters
    with st.sidebar:
        st.header("🔍 검색 옵션")
        
        bank_name = st.selectbox(
            "은행 선택",
            ["자동 감지", "우리은행", "국민은행"],
            index=0
        )
        
        product_type = st.selectbox(
            "상품 종류",
            ["자동 감지", "대출", "예적금"],
            index=0
        )
        
        top_k = st.slider(
            "검색 문서 수",
            min_value=3,
            max_value=15,
            value=8,
            help="더 많은 문서를 검색하면 더 정확한 답변을 얻을 수 있지만, 시간이 더 걸립니다."
        )
        
        st.divider()
        
        # Health check
        if st.button("🏥 시스템 상태 확인"):
            with st.spinner("상태 확인 중..."):
                health = rag_engine.health_check()
                if health["status"] == "healthy":
                    st.success("✅ 시스템 정상")
                    st.json(health["components"])
                else:
                    st.error("❌ 시스템 이상")
                    st.json(health)
    
    # Main content
    st.divider()
    
    # Example questions
    with st.expander("💡 질문 예시"):
        st.markdown("""
        - 국민은행 대출 금리는 어떻게 되나요?
        - 우리은행 예금 상품에는 어떤 것이 있나요?
        - 중도상환수수료는 얼마인가요?
        - 대출 한도는 어떻게 결정되나요?
        - 금리 우대 조건은 무엇인가요?
        """)
    
    # Query input
    question = st.text_area(
        "질문을 입력하세요:",
        height=100,
        placeholder="예: 국민은행 대출 금리는 어떻게 되나요?"
    )
    
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        search_button = st.button("🔍 검색", type="primary", use_container_width=True)
    with col2:
        clear_button = st.button("🗑️ 초기화", use_container_width=True)
    
    if clear_button:
        st.rerun()
    
    # Process query
    if search_button and question:
        with st.spinner("답변 생성 중..."):
            try:
                # Prepare filters
                bank_filter = None if bank_name == "자동 감지" else bank_name
                product_filter = None if product_type == "자동 감지" else product_type
                
                # Query RAG engine
                result = rag_engine.query(
                    question=question,
                    top_k=top_k,
                    bank_name=bank_filter,
                    product_type=product_filter
                )
                
                # Display answer
                st.divider()
                st.subheader("💬 답변")
                st.markdown(result["answer"])
                
                # Display filters used
                if result.get("filters"):
                    filters = result["filters"]
                    filter_text = []
                    if filters.get("bank_name"):
                        filter_text.append(f"🏦 {filters['bank_name']}")
                    if filters.get("product_type"):
                        filter_text.append(f"📊 {filters['product_type']}")
                    if filter_text:
                        st.caption(f"적용된 필터: {' | '.join(filter_text)}")
                
                # Display sources
                if result.get("sources"):
                    st.divider()
                    st.subheader(f"📚 참고 문서 ({result['num_sources']}개)")
                    
                    for source in result["sources"]:
                        with st.expander(
                            f"📄 {source['bank_name']} - {source['product_name']} "
                            f"({source['clause']} {source['clause_name']})"
                        ):
                            st.markdown(source["content_preview"])
                
            except Exception as e:
                logger.error(f"Query failed: {e}")
                st.error(f"❌ 오류가 발생했습니다: {str(e)}")
    
    elif search_button and not question:
        st.warning("⚠️ 질문을 입력해주세요.")
    
    # Footer
    st.divider()
    st.caption("🤖 Powered by OpenAI GPT + pgvector | 우리은행 + 국민은행 대출 및 예적금 Q&A")


if __name__ == "__main__":
    main()
