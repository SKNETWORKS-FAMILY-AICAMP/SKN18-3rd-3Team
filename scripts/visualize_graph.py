"""
LangGraph 시각화 스크립트

RAG 파이프라인의 그래프 구조를 시각화합니다.
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


def visualize_graph():
    """
    RAG 그래프 시각화 (순차 실행)
    """
    print("RAG 그래프 생성 중 (Sequential Mode)...")
    
    # 설정 로드
    config = get_config()
    
    # LLM 초기화
    llm = get_llm_model()
    
    # VectorStore 초기화
    db_connection = DatabaseConnection(db_url=config.DB_URL)
    embeddings = OpenAIEmbeddings(
        model=config.EMBED_MODEL,
        api_key=config.OPENAI_API_KEY
    )
    vectorstore = PgVectorStore(
        connection=db_connection,
        embeddings=embeddings
    )
    
    # RAG 시스템 생성
    graph = create_rag_system(
        llm=llm,
        vectorstore=vectorstore,
        enable_routing=False,
        enable_langsmith=False
    )
    
    print("✓ 그래프 생성 완료\n")
    
    # 그래프 구조 출력
    print("=" * 80)
    print("  Multi-Agent RAG Pipeline (Sequential Mode)")
    print("=" * 80)
    print()
    
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│                         START                                   │")
    print("└────────────────────────┬────────────────────────────────────────┘")
    print("                         │")
    print("                         ▼")
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│  1. CLASSIFY NODE                                               │")
    print("│     - Intent 분류 (gpt-4o-mini)                                 │")
    print("│     - 은행명, 상품명, 상품종류 추출                             │")
    print("└────────────────────────┬────────────────────────────────────────┘")
    print("                         │")
    print("                         ▼")
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│  2. SQL NODE                                                    │")
    print("│     - RDB 조회 (SQLRetrievalAgent)                              │")
    print("│     - 상품 정보 검색                                            │")
    print("└────────────────────────┬────────────────────────────────────────┘")
    print("                         │")
    print("                         ▼")
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│  3. VECTOR NODE                                                 │")
    print("│     - Vector DB 조회 (Top-K=8)                                  │")
    print("│     - 관련 청크 검색                                            │")
    print("└────────────────────────┬────────────────────────────────────────┘")
    print("                         │")
    print("                         ▼")
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│  4. EVAL NODE                                                   │")
    print("│     - 청크 관련성 평가 (gpt-4o, temperature=0.0)                │")
    print("│     - 관련성 높은 청크만 필터링                                 │")
    print("└────────────────────────┬────────────────────────────────────────┘")
    print("                         │")
    print("                         ▼")
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│  5. GENERATE NODE                                               │")
    print("│     - 최종 답변 생성 (gpt-4o-mini, temperature=1.0)             │")
    print("│     - SQL 결과 + 관련 청크 기반                                 │")
    print("└────────────────────────┬────────────────────────────────────────┘")
    print("                         │")
    print("                         ▼")
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│                          END                                    │")
    print("└─────────────────────────────────────────────────────────────────┘")
    
    print()
    print("=" * 80)
    print("  Key Features")
    print("=" * 80)
    print()
    print("✓ Multi-Agent Architecture")
    print("  - Classification Agent: Intent 분류 및 엔티티 추출")
    print("  - SQL Agent: RDB에서 상품 정보 조회")
    print("  - Vector Search: Vector DB에서 관련 청크 조회")
    print("  - Evaluation Agent: LLM 기반 청크 관련성 평가")
    print("  - Generation Agent: 최종 답변 생성")
    print()
    print("✓ Dual LLM Strategy")
    print("  - Generation LLM: gpt-4o-mini (temperature=1.0) - 창의적 답변")
    print("  - Evaluation LLM: gpt-4o (temperature=0.0) - 일관된 평가")
    print()
    print("✓ Sequential Execution")
    print("  - 모든 노드를 순차적으로 실행")
    print("  - 안정적이고 예측 가능한 플로우")
    print("  - 디버깅 및 모니터링 용이")
    print()


if __name__ == "__main__":
    visualize_graph()
    
    print()
    print("=" * 80)
    print("  Usage")
    print("=" * 80)
    print()
    print("# 그래프 시각화")
    print("python scripts/visualize_graph.py")
    print()

