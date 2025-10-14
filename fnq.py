import os
import sys
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# ---------------------------
# 0. 라이브러리 임포트
# ---------------------------

# Langchain Groq
from langchain_groq import ChatGroq
from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

# .env 파일에서 환경 변수 로드
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---------------------------
# 1. 파이프라인 설정
# ---------------------------

# 설정 변수
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "bge-m3"  # Ollama에서 구동
LLM_MODEL = "llama-3.1-8b-instant"  # Groq 모델
PERSIST_DIR = os.path.join(os.getcwd(), f"coupang_faq_chroma_db_{EMBEDDING_MODEL.replace(':', '_')}")
CSV_FILE = "coupang_faq.csv"

# ---------------------------
# 2. RAG 체인 구축 함수
# ---------------------------

@st.cache_resource
def setup_rag_pipeline():
    """RAG 파이프라인 (데이터 로드, DB 구축, 리트리버 및 체인) 설정"""
    
    # 2-1. CSV 데이터 로드
    csv_path = os.path.join(os.getcwd(), CSV_FILE)
    
    if not os.path.exists(csv_path):
        st.error(f"에러: {CSV_FILE} 파일이 루트 폴더에 없습니다. 파일을 추가해주세요.")
        sys.exit(1)
    
    try:
        # CSV 파일 로드 (질문과 답변 컬럼 확인)
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        
        # 컬럼명 확인 및 표준화
        if '질문' not in df.columns or '답변' not in df.columns:
            st.error(f"에러: CSV 파일에 '질문'과 '답변' 컬럼이 필요합니다. 현재 컬럼: {list(df.columns)}")
            sys.exit(1)
        
        # Document 형식으로 변환 (질문 + 답변을 하나의 문서로)
        from langchain.schema import Document
        documents = []
        
        for idx, row in df.iterrows():
            # 카테고리가 있으면 포함
            content = ""
            if '카테고리' in df.columns:
                content += f"[카테고리: {row['카테고리']}]\n"
            content += f"질문: {row['질문']}\n답변: {row['답변']}"
            
            doc = Document(
                page_content=content,
                metadata={
                    "번호": row.get('번호', idx+1),
                    "카테고리": row.get('카테고리', ''),
                    "질문": row['질문']
                }
            )
            documents.append(doc)
        
        st.info(f"CSV 파일에서 총 {len(documents)}개의 FAQ 문서를 로드했습니다.")
        
    except Exception as e:
        st.error(f"CSV 로드 중 오류: {e}")
        sys.exit(1)

    # 2-2. 문서 분할 (Chunking) - FAQ는 이미 단위가 작으므로 크게 나눌 필요 없음
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    splits = text_splitter.split_documents(documents)
    
    st.info(f"총 {len(splits)}개 청크로 분할 완료. 벡터 DB 구축 중...")

    # 2-3. 벡터 DB 구축 및 로드
    try:
        # 기존 DB 로드 시도
        embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
        vectorstore = Chroma(persist_directory=PERSIST_DIR, embedding_function=embeddings)
        print("기존 벡터 DB 로드 성공")
        
    except Exception:
        # DB 없거나 에러 시 새로 구축
        print("벡터 DB 새로 구축 중...")
        embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=PERSIST_DIR,
        )
        print("벡터 DB 새로 구축 완료")

    # 2-4. 하이브리드 리트리버 + RAG 체인 구성
    
    # BM25 키워드 검색
    bm25_retriever = BM25Retriever.from_documents(splits)
    bm25_retriever.k = 5

    # 의미 기반 벡터 검색
    chroma_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    # 두 검색 방법 결합 (Ensemble)
    retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, chroma_retriever],
        weights=[0.3, 0.7],
    )

    # LLM 설정: Groq 사용
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model_name=LLM_MODEL,
        temperature=0.1,  # FAQ는 정확성이 중요
    )

    # 쿠팡 FAQ 답변용 프롬프트
    prompt_template = PromptTemplate.from_template(
        """당신은 쿠팡 고객센터의 전문 상담원입니다. 제공된 컨텍스트를 기반으로 정확하고 친절하게 답변하세요.

규칙:
- 컨텍스트에 있는 정보만 사용하여 답변하세요.
- 컨텍스트에 없는 내용은 절대 추측하지 말고, "제공된 정보에서 찾을 수 없습니다"라고 답변하세요.
- 답변은 친절하고 이해하기 쉬운 한국어로 작성하세요.
- 관련된 카테고리 정보가 있으면 함께 제공하세요.
- 질문과 가장 관련성 높은 답변을 우선적으로 제시하세요.
- 복잡한 내용은 단계별로 설명하세요.

컨텍스트:
{context}

고객 질문: {question}

친절한 답변:"""
    )

    # RAG 체인 구성
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt_template
        | llm
        | StrOutputParser()
    )

    return rag_chain

# ---------------------------
# 3. Streamlit 앱 메인 함수
# ---------------------------

def streamlit_main():
    """Streamlit 앱 UI 및 로직"""
    
    st.set_page_config(
        page_title="쿠팡 F&Q 검색",
        layout="wide"
    )
    
    # 헤더
    st.title("쿠팡 F&Q 검색 시스템")
    st.markdown("쿠팡 관련 궁금한 점을 질문하시면 AI가 답변해드립니다.")
    st.markdown("---")

    # 1. Groq API 키 확인
    if not GROQ_API_KEY:
        st.error("에러: `.env` 파일에 `GROQ_API_KEY`가 설정되어 있지 않습니다.")
        st.info(" `.env` 파일을 생성하고 `GROQ_API_KEY=your_api_key`를 추가하세요.")
        return

    # 2. RAG 체인 로드
    with st.spinner(" RAG 시스템 로드 중... (Ollama 서버"):
        try:
            rag_chain = setup_rag_pipeline()
            st.success(" RAG 시스템 준비 완료!")
            st.info(f"**사용 모델:** Groq ({LLM_MODEL}) + Ollama ({EMBEDDING_MODEL})")
        except Exception as e:
            st.error(f"RAG 시스템 로드 실패: {e}")
            return

    st.markdown("---")
    
    # 3. 사용자 질문 입력
    st.header("질문하기")
    
    # 예시 질문 버튼
    st.markdown("**빠른 질문 예시:**")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("배송은 언제 되나요?"):
            st.session_state.user_question = "주문한 상품은 언제 배송되나요?"
    
    with col2:
        if st.button("반품하고 싶어요"):
            st.session_state.user_question = "상품을 반품하고 싶어요"
    
    with col3:
        if st.button("와우 멤버십 해지"):
            st.session_state.user_question = "와우 멤버십을 해지하고 싶어요"
    
    with col4:
        if st.button("test김창현이 핫도그 먹고 싶어 하나요?"):
            st.session_state.user_question = "김창현이 핫도그 먹고 싶어 하나요?"       
    
    # 질문 입력창
    user_question = st.text_area(
        "궁금한 내용을 입력하세요:",
        value=st.session_state.get('user_question', ''),
        height=100,
        placeholder="예: 배송 조회는 어떻게 하나요?\n예: 현금영수증은 어디서 받을 수 있나요?"
    )
    
    # 검색 버튼
    search_button = st.button(" 답변 받기", type="primary", use_container_width=True)

    # 4. 질문 처리 및 RAG 실행
    if search_button or user_question != st.session_state.get('last_question', ''):
        if not user_question.strip():
            st.warning("질문을 입력해주세요.")
            return
        
        # 마지막 질문 저장 (중복 실행 방지)
        st.session_state.last_question = user_question
        
        try:
            st.markdown("---")
            st.subheader("답변")
            
            with st.spinner("답변을 찾고 있습니다..."):
                # RAG 체인 호출
                response = rag_chain.invoke(user_question)
            
            # 5. 결과 출력
            st.success("답변이 완료되었습니다.")
            
            # 답변 표시 (박스 형태로)
            st.markdown(
                f"""
                <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; margin: 10px 0;">
                    {response}
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # 추가 안내
            st.info("더 궁금한 점이 있으시면 새로운 질문을 입력해주세요!")
            
        except Exception as e:
            st.error(f" 답변 생성 중 오류가 발생했습니다: {e}")
            st.info("Ollama 서버가 실행 중인지 확인하세요: `ollama serve`")

    # 푸터
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666; font-size: 0.9em;">
            <p>AI 기반 자동 답변(래그+streamlit)</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------------------
# 4. 스크립트 실행
# ---------------------------
if __name__ == "__main__":
    # Groq API 키 및 Ollama 서버가 필요합니다.
    #Groq API 키는 개인꺼 넣어서 실행해야함(무료 많이 써서 없음)
    streamlit_main()
