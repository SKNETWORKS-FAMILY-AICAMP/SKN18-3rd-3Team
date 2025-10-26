# -*- coding: utf-8 -*-
"""Streamlit UI for Bank RAG Q&A Service"""

import streamlit as st
from rag.engine import RAGEngine
from rag.core.logger import get_logger

# Page config
st.set_page_config(
    page_title="은행 Q&A 서비스",
    page_icon="🏦",
    layout="wide"
)

# Initialize logger
logger = get_logger(__name__)

def process_query_with_context(current_question: str, chat_history: list) -> str:
    """
    대화 컨텍스트를 고려하여 질문을 전처리합니다.
    
    Args:
        current_question: 현재 사용자 질문
        chat_history: 이전 대화 기록
    
    Returns:
        컨텍스트가 포함된 처리된 질문
    """
    # 후속 질문 패턴들
    followup_patterns = [
        "응", "응해줘", "응알려줘", "더 알려줘", "더 자세히", "자세히 알려줘",
        "그거", "그것", "그 상품", "그 조항", "그것에 대해", "그거에 대해",
        "어떻게", "뭐야", "뭔가", "뭐지", "뭐하는", "뭐하는거야",
        "알려줘", "말해줘", "설명해줘", "상세히", "자세히", "더",
        "약관", "조항", "상품약관", "주의사항", "조건"
    ]
    
    # 단순한 후속 질문인지 확인 (예: "응", "알려줘" 등)
    simple_followup_patterns = ["응", "응해줘", "응알려줘", "더 알려줘", "더 자세히", "자세히 알려줘", "그거", "그것", "그 상품", "그 조항", "그것에 대해", "그거에 대해", "어떻게", "뭐야", "뭔가", "뭐지", "뭐하는", "뭐하는거야", "알려줘", "말해줘", "설명해줘", "상세히", "자세히", "더"]
    
    cleaned_question = current_question.replace(" ", "").lower()
    is_simple_followup = any(pattern.replace(" ", "") in cleaned_question for pattern in simple_followup_patterns)
    
    # 단순한 후속 질문이면 원본 질문을 그대로 반환 (gen_agent.py에서 처리하도록)
    if is_simple_followup:
        return current_question
    
    # 현재 질문이 후속 질문인지 확인 (공백 제거 후 확인)
    is_followup = any(pattern.replace(" ", "") in cleaned_question for pattern in followup_patterns)
    
    if not is_followup or len(chat_history) == 0:
        return current_question
    
    # 이전 대화에서 마지막 어시스턴트 답변 찾기
    last_assistant_message = None
    for msg in reversed(chat_history):
        if msg["role"] == "assistant":
            last_assistant_message = msg["content"]
            break
    
    if not last_assistant_message:
        return current_question
    
    # 컨텍스트가 포함된 질문 생성
    context_question = f"""
이전 대화 내용:
{last_assistant_message}

현재 질문: {current_question}

위 이전 대화 내용을 참고하여 현재 질문에 답변해주세요.
특히 이전에 여러 상품이 추천되었고 현재 질문에서 특정 상품을 지정하지 않은 경우, 
"다섯 상품의 약관 내용을 자세히 안내해 드릴 수 있습니다. 어떤 상품의 약관을 자세히 알고 싶으신가요?"라고 답변하고 상품 목록을 제시하세요.
"""
    
    return context_question.strip()

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
    
    # Initialize session state for chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "current_context" not in st.session_state:
        st.session_state.current_context = {
            "recommended_products": [],
            "last_intent": None,
            "waiting_for_product_selection": False
        }
    
    # Sidebar - Settings
    with st.sidebar:
        st.header("⚙️ 설정")
        
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
        
        st.divider()
        
        # Clear chat history
        if st.button("🗑️ 대화 기록 삭제"):
            st.session_state.messages = []
            st.session_state.current_context = {
                "recommended_products": [],
                "last_intent": None,
                "waiting_for_product_selection": False
            }
            st.rerun()
    
    # Chat interface
    st.subheader("💬 상담사와 대화하기")
    
    # Example questions
    with st.expander("💡 질문 예시"):
        st.markdown("""
        **상품 추천:**
        - 전문직 대상 대출 상품 추천해줘
        - 전세자금대출 상품 알려줘
        - 우리은행 대출 상품 추천해줘
        
        **조항 질문:**
        - 중도상환수수료는 얼마인가요?
        - 대출 금리는 어떻게 되나요?
        - 우대 조건은 무엇인가요?
        """)
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show product details if it's a product recommendation
            if message["role"] == "assistant" and message.get("products"):
                st.markdown("**추천 상품:**")
                for product in message["products"]:
                    with st.expander(f"🏦 {product['bank_name']} - {product['product_name']}"):
                        # 6개 항목으로 통일된 형식
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**🏦 은행:** {product.get('bank_name', 'N/A')}")
                            st.write(f"**📋 분류:** {product.get('product_category', 'N/A')}")
                            st.write(f"**👥 대상:** {product.get('loan_target', 'N/A')}")
                        with col2:
                            st.write(f"**⏰ 기간:** {product.get('loan_period', 'N/A')}")
                            st.write(f"**💰 한도:** {product.get('loan_limit', 'N/A')}")
                            
                            # 금리 정보 표시 (6번째 항목)
                            interest_rates = product.get('interest_rates', [])
                            if interest_rates:
                                # 첫 번째 금리 정보 표시
                                first_rate = interest_rates[0]
                                rate_type = first_rate.get('rate_type', '기본')
                                rate_condition = first_rate.get('rate_condition', '')
                                interest_rate = first_rate.get('interest_rate', 'N/A')
                                
                                if rate_condition:
                                    st.write(f"**📊 금리:** {interest_rate}% ({rate_type}, {rate_condition})")
                                else:
                                    st.write(f"**📊 금리:** {interest_rate}% ({rate_type})")
                            else:
                                st.write(f"**📊 금리:** 정보 없음")
    
    # Chat input
    if prompt := st.chat_input("질문을 입력하세요..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                try:
                    # Process query with conversation context
                    processed_question = process_query_with_context(prompt, st.session_state.messages)
                    
                    # Process query through RAG engine
                    result = rag_engine.query(question=processed_question)
                    
                    # Extract information
                    answer = result["answer"]
                    sql_sources = [s for s in result.get("sources", []) if s.get("source_type") == "sql"]
                    vector_sources = [s for s in result.get("sources", []) if s.get("source_type") == "vector"]
                    
                    # Display answer
                    st.markdown(answer)
                    
                    # Update context based on intent
                    debug_info = result.get("debug", {})
                    intent = debug_info.get("intent", "")
                    
                    # Determine if this is a product recommendation or clause question
                    # 상품 추천: SQL 결과가 있고 상품 관련 질문인 경우
                    is_product_recommendation = len(sql_sources) > 0 and any(keyword in processed_question.lower() for keyword in [
                        "추천", "상품", "대출", "예금", "적금", "어떤", "무엇", "좋은", "추천해"
                    ])
                    
                    # 조항 질문: Vector 결과가 있거나 조항 관련 질문인 경우
                    is_clause_question = len(vector_sources) > 0 or any(keyword in processed_question.lower() for keyword in [
                        "약관", "조항", "금리", "수수료", "조건", "주의", "제1조", "제2조", "제3조"
                    ])
                    
                    if is_product_recommendation:
                        # Product recommendation case - show products in expandable format
                        st.session_state.current_context["recommended_products"] = sql_sources
                        st.session_state.current_context["last_intent"] = intent
                        st.session_state.current_context["waiting_for_product_selection"] = True
                        
                        # Show products in a clean format
                        st.markdown("**🏦 추천 상품 정보:**")
                        for i, product in enumerate(sql_sources):
                            with st.expander(f"📄 {product.get('bank_name', 'N/A')} - {product.get('product_name', 'N/A')}", expanded=False):
                                # 6개 항목으로 통일된 형식
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**🏦 은행:** {product.get('bank_name', 'N/A')}")
                                    st.write(f"**📋 분류:** {product.get('product_category', 'N/A')}")
                                    st.write(f"**👥 대상:** {product.get('loan_target', 'N/A')}")
                                with col2:
                                    st.write(f"**⏰ 기간:** {product.get('loan_period', 'N/A')}")
                                    st.write(f"**💰 한도:** {product.get('loan_limit', 'N/A')}")
                                    
                                    # 금리 정보 표시 (6번째 항목)
                                    interest_rates = product.get('interest_rates', [])
                                    if interest_rates:
                                        st.write(f"**📊 금리:** {interest_rates[0].get('interest_rate', 'N/A')}")
                                    else:
                                        st.write(f"**📊 금리:** N/A")
                                
                                # 금리 상세 정보가 있으면 별도 섹션으로 표시
                                interest_rates = product.get('interest_rates', [])
                                if interest_rates and len(interest_rates) > 1:
                                    st.write("**📈 금리 상세:**")
                                    for j, rate in enumerate(interest_rates[:3]):  # 최대 3개만 표시
                                        rate_type = rate.get('rate_type', '')
                                        rate_condition = rate.get('rate_condition', '')
                                        interest_rate = rate.get('interest_rate', '')
                                        st.write(f"  {j+1}. {interest_rate} ({rate_type})")
                                        if rate_condition:
                                            st.write(f"     조건: {rate_condition}")
                        
                        # Add assistant message
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": answer,
                            "products": sql_sources
                        })
                    else:
                        # General question or clause question case
                        st.session_state.current_context["waiting_for_product_selection"] = False
                        
                        # Add assistant message
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": answer
                        })
                        
                        # Show additional sources if available (only for clause questions)
                        if is_clause_question and vector_sources:
                            st.markdown("**📚 관련 약관 정보:**")
                            for source in vector_sources[:2]:  # Show first 2 only
                                with st.expander(f"📄 {source.get('clause', '')} - {source.get('clause_name', '')}"):
                                    st.markdown(source["content_preview"])
                        
                        # 특정 상품을 지정한 조항 질문인 경우 상품 정보도 표시
                        if is_clause_question and sql_sources:
                            st.markdown("**🏦 상품 정보:**")
                            for product in sql_sources:
                                with st.expander(f"📄 {product.get('bank_name', 'N/A')} - {product.get('product_name', 'N/A')}", expanded=False):
                                    # 6개 항목으로 통일된 형식
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**🏦 은행:** {product.get('bank_name', 'N/A')}")
                                        st.write(f"**📋 분류:** {product.get('product_category', 'N/A')}")
                                        st.write(f"**👥 대상:** {product.get('loan_target', 'N/A')}")
                                    with col2:
                                        st.write(f"**⏰ 기간:** {product.get('loan_period', 'N/A')}")
                                        st.write(f"**💰 한도:** {product.get('loan_limit', 'N/A')}")
                                        
                                        # 금리 정보 표시 (6번째 항목)
                                        interest_rates = product.get('interest_rates', [])
                                        if interest_rates:
                                            # 첫 번째 금리 정보 표시
                                            first_rate = interest_rates[0]
                                            rate_type = first_rate.get('rate_type', '기본')
                                            rate_condition = first_rate.get('rate_condition', '')
                                            interest_rate = first_rate.get('interest_rate', 'N/A')
                                            
                                            if rate_condition:
                                                st.write(f"**📊 금리:** {interest_rate}% ({rate_type}, {rate_condition})")
                                            else:
                                                st.write(f"**📊 금리:** {interest_rate}% ({rate_type})")
                                        else:
                                            st.write(f"**📊 금리:** 정보 없음")
                
                except Exception as e:
                    error_msg = f"❌ 오류가 발생했습니다: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": error_msg
                    })
    
    # Footer
    st.divider()
    st.caption("🤖 Powered by OpenAI GPT + pgvector | 우리은행 + 국민은행 대출 및 예적금 Q&A")


if __name__ == "__main__":
    main()
