"""
Multi-Agent RAG 시스템 테스트 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.graph.build import create_rag_system
from rag.llm.get_llm import get_llm_model
from rag.vectorstore.pgvector_store import PgVectorStore
from rag.embeddings.openai_embed import OpenAIEmbeddings
from rag.db.connection import DatabaseConnection
from rag.core.config import get_config
import json


def print_section(title: str):
    """섹션 구분선 출력"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_rag(question: str):
    """RAG 시스템 테스트"""
    print_section("Multi-Agent RAG 시스템 테스트")
    
    # 설정 로드
    print("설정 로드 중...")
    config = get_config()
    print("✓ 설정 로드 완료")
    
    # LLM 초기화
    print("\n생성용 LLM 초기화 중...")
    llm = get_llm_model()
    print("✓ 생성용 LLM 초기화 완료 (gpt-5-nano, temperature=1.0)")
    
    # VectorStore 초기화
    print("\nVectorStore 초기화 중...")
    
    # DB 연결 초기화
    db_connection = DatabaseConnection(db_url=config.DB_URL)
    print("✓ DB 연결 초기화 완료")
    
    # Embeddings 초기화
    embeddings = OpenAIEmbeddings(
        model=config.EMBED_MODEL,
        api_key=config.OPENAI_API_KEY
    )
    print(f"✓ Embeddings 초기화 완료: {config.EMBED_MODEL}")
    
    # VectorStore 초기화
    vectorstore = PgVectorStore(
        connection=db_connection,
        embeddings=embeddings
    )
    print("✓ VectorStore 초기화 완료")
    
    # RAG 시스템 생성 (build.py 사용)
    print("\nRAG 그래프 생성 중...")
    print("  - 평가용 LLM은 EvaluationAgent 내부에서 자동 생성됩니다 (gpt-5-mini, temperature=0.0)")
    print("  - 청크 관련성 임계값: 35.0 (완화됨)")
    print("  - 조건부 라우팅: 비활성화 (순차 실행)")
    print("  - LangSmith 추적: 비활성화")
    graph = create_rag_system(
        llm=llm,
        vectorstore=vectorstore,
        top_k=8,
        relevance_threshold=35.0,  # 60.0 -> 35.0으로 완화
        enable_routing=False,
        enable_langsmith=False
    )
    print("✓ RAG 그래프 생성 완료")
    
    # 질문 실행
    print_section(f"질문: {question}")
    result = graph.invoke({"question": question})
    
    # 결과 출력
    print_section("1. Classification 결과")
    print(f"Intent: {result.get('intent')}")
    print(f"은행명: {result.get('bank_name')}")
    print(f"상품명: {result.get('product_name')}")
    print(f"상품종류: {result.get('product_type')}")
    print(f"대출종류: {result.get('loan_type')}")
    print(f"대출대상: {result.get('loan_target')}")
    print(f"Confidence: {result.get('confidence', 0.0):.2f}")
    print(f"Reasoning: {result.get('reasoning')}")
    
    print_section("2. SQL 검색 결과")
    sql_results = result.get('sql_results', [])
    print(f"검색된 상품 수: {len(sql_results)}")
    for idx, product in enumerate(sql_results, 1):
        print(f"\n[상품 {idx}]")
        print(f"  은행: {product.get('bank_name')}")
        print(f"  상품명: {product.get('product_name')}")
        print(f"  종류: {product.get('product_category')} > {product.get('product_detail_category')}")
        print(f"  대출대상: {product.get('loan_target')}")
        print(f"  대출기간: {product.get('loan_period')}")
        print(f"  대출한도: {product.get('loan_limit')}")
    
    print_section("3. Vector DB 검색 결과")
    vector_chunks = result.get('vector_chunks', [])
    print(f"검색된 청크 수: {len(vector_chunks)}")
    for idx, chunk in enumerate(vector_chunks[:3], 1):  # 처음 3개만
        print(f"\n[청크 {idx}]")
        print(f"  은행: {chunk.get('bank_name')}")
        print(f"  문서: {chunk.get('document_name')}")
        print(f"  상품: {chunk.get('product_name')}")
        print(f"  조항: {chunk.get('clause')} - {chunk.get('clause_name')}")
        print(f"  유사도: {chunk.get('similarity_score', 0.0):.4f}")
        print(f"  내용: {chunk.get('content', '')[:100]}...")
    
    print_section("4. Evaluation 결과")
    relevant_chunks = result.get('relevant_chunks', [])
    print(f"관련성 있는 청크 수: {len(relevant_chunks)}")
    for idx, chunk in enumerate(relevant_chunks[:3], 1):  # 처음 3개만
        print(f"\n[관련 청크 {idx}]")
        print(f"  은행: {chunk.get('bank_name')}")
        print(f"  문서: {chunk.get('document_name')}")
        print(f"  조항: {chunk.get('clause')} - {chunk.get('clause_name')}")
        
        eval_result = chunk.get('eval_result', {})
        if eval_result:
            print(f"  관련성 점수: {eval_result.get('relevance_score', 0.0):.2f}")
            print(f"  평가 이유: {eval_result.get('reason', '')}")
    
    print_section("5. 최종 답변")
    answer = result.get('answer', '')
    print(answer)
    
    # 디버그 정보 (선택적)
    if result.get('debug'):
        print_section("디버그 정보")
        print(json.dumps(result['debug'], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # 테스트 질문들
    test_questions = [
        "전문직 대상 대출 상품 추천해줘"
    ]
    
    # 첫 번째 질문으로 테스트
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = test_questions[0]
    
    test_rag(question)

