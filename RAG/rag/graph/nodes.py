"""LangGraph 노드 함수들"""

from typing import Dict, Any
from jinja2 import Environment

from RAG.core.logger import get_logger
from RAG.rag.retriever import BankRetriever
from RAG.llm.openai_chat import OpenAIChatModel


logger = get_logger(__name__)


class GraphNodes:
    """
    LangGraph 파이프라인의 노드 함수들
    
    각 노드는 상태를 입력받아 처리하고 업데이트된 상태를 반환합니다.
    """
    
    def __init__(
        self,
        retriever: BankRetriever,
        llm: OpenAIChatModel,
        jinja_env: Environment
    ):
        """
        Initialize graph nodes.
        
        Args:
            retriever: Document retriever
            llm: Language model for generation
            jinja_env: Jinja2 environment for templates
        """
        self.retriever = retriever
        self.llm = llm
        self.jinja_env = jinja_env
        logger.info("GraphNodes initialized")

    
    def normalize_query(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        질의 정규화 노드
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with normalized query
        """
        query = state["query"].strip()
        logger.info(f"Normalized query: {query[:100]}...")
        
        return {
            **state,
            "query": query
        }

    
    def route_metadata(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        메타데이터 라우팅 노드
        
        질의에서 은행명과 상품종류를 자동으로 추출합니다.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with extracted metadata
        """
        query = state["query"]
        
        # Extract bank name (if not already provided)
        bank_name = state.get("bank_name")
        if not bank_name:
            if "우리은행" in query or "우리" in query:
                bank_name = "우리은행"
            elif "국민은행" in query or "국민" in query or "KB" in query:
                bank_name = "국민은행"
        
        # Extract product type (if not already provided)
        product_type = state.get("product_type")
        if not product_type:
            if "대출" in query:
                product_type = "대출"
            elif "예금" in query or "적금" in query or "예적금" in query:
                # 우선 "예적금"으로 검색 (국민은행), 없으면 retriever가 "예금"(우리은행)도 검색
                product_type = "예적금"
        
        logger.info(f"Routed metadata - bank: {bank_name}, product: {product_type}")
        
        return {
            **state,
            "bank_name": bank_name,
            "product_type": product_type
        }

    
    def vector_search(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        벡터 검색 노드
        
        메타데이터 필터를 사용하여 관련 문서를 검색합니다.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with retrieved documents
        """
        query = state["query"]
        top_k = state.get("top_k", 8)
        bank_name = state.get("bank_name")
        product_type = state.get("product_type")
        
        logger.info(f"Searching with top_k={top_k}, bank={bank_name}, product={product_type}")
        
        try:
            documents = self.retriever.retrieve(
                query=query,
                top_k=top_k,
                bank_name=bank_name,
                product_type=product_type
            )
            
            logger.info(f"Found {len(documents)} documents")
            
            return {
                **state,
                "documents": documents
            }
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return {
                **state,
                "documents": [],
                "error": str(e)
            }

    
    def generate_answer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM 답변 생성 노드
        
        검색된 문서를 기반으로 LLM을 사용하여 답변을 생성합니다.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with generated answer
        """
        query = state["query"]
        documents = state.get("documents", [])
        
        # Handle empty results
        if not documents:
            logger.warning("No documents found for query")
            return {
                **state,
                "answer": "죄송합니다. 관련된 정보를 찾을 수 없습니다. 질문을 다시 확인해주세요."
            }
        
        try:
            # Load template
            template = self.jinja_env.get_template("answer.j2")
            prompt = template.render(query=query, documents=documents)
            
            # Generate answer
            system_prompt = "당신은 은행 상품 전문가입니다. 제공된 문서를 기반으로 정확하게 답변하세요."
            answer = self.llm.generate(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=0.7
            )
            
            logger.info("Answer generated successfully")
            
            return {
                **state,
                "answer": answer
            }
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return {
                **state,
                "answer": f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {str(e)}",
                "error": str(e)
            }

    
    def format_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        응답 포맷팅 노드
        
        출처 정보를 추출하고 포맷팅합니다.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with formatted sources
        """
        documents = state.get("documents", [])
        
        sources = []
        for i, doc in enumerate(documents):
            source = {
                "index": i + 1,
                "bank_name": doc.metadata.get("은행명", ""),
                "product_name": doc.metadata.get("상품이름", ""),
                "clause": doc.metadata.get("조항", ""),
                "clause_name": doc.metadata.get("조항이름", ""),
                "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            }
            sources.append(source)
        
        logger.info(f"Formatted {len(sources)} sources")
        
        return {
            **state,
            "sources": sources
        }
