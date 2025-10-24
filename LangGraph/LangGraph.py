# 상위 디렉토리를 모듈 탐색 경로에 추가
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from typing import Any, Dict, List, Optional

from IPython.display import Image, display
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from LangGraph.State import State
from LangGraph.nodes.intent_question_node import intent_question_node
from LangGraph.nodes.search_vectordb_node import search_vectordb_node
from LangGraph.nodes.sql_retrieval_node import sql_retrieval_node
from LangGraph.nodes.eval_node import eval_node
from LangGraph.nodes.generate_node import generate_node
from LangGraph.nodes.search_web_node import search_web_node
from LangGraph.nodes.clarify_node import clarify_node
from LangGraph.route.route_after_eval import route_after_eval

from db_ingest.create_vectordb import CustomPGVector, load_config, build_connection_string
from db_ingest.embedding_model import create_embeddings
from langchain_tavily import TavilySearch

# --- 싱글턴 의존성 --------------------------------------------------------
_deps_singleton: Optional["Deps"] = None


class VectorSearcher:
    """CustomPGVector를 LangGraph 노드에서 쓰기 편하게 감싼 검색기."""

    def __init__(self) -> None:
        config = load_config()
        conn_str = build_connection_string(config)
        embeddings = create_embeddings()
        # CustomPGVector 내부도 싱글턴 메타클래스를 사용하므로 인스턴스는 한 번만 생성된다.
        self._store = CustomPGVector(conn_str=conn_str, embedding_fn=embeddings)

    def search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """질문과 필터를 이용해 벡터 DB에서 문서를 찾는다."""
        if not query:
            return []

        results = self._store.similarity_search_with_score(query, k=top_k)

        hits: List[Dict[str, Any]] = []
        for doc, distance in results:
            metadata = doc.metadata or {}

            if filters and any(metadata.get(key) != value for key, value in filters.items()):
                continue

            score = 1.0 / (1.0 + float(distance))
            hits.append(
                {
                    "text": doc.page_content,
                    "meta": metadata,
                    "score": score,
                }
            )

        return hits


class TavilyWrapper:
    """LangChain Tavily 도구를 search() 인터페이스로 감싼 래퍼."""

    def __init__(self, **kwargs) -> None:
        self._init_error: Optional[Exception] = None
        try:
            self._tool = TavilySearch(**kwargs)
        except Exception as exc:  # API 키 누락 등 초기화 실패
            self._tool = None
            self._init_error = exc

    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Tavily API를 호출해 검색 결과를 반환한다."""
        if self._tool is None:
            raise RuntimeError(f"Tavily 검색 도구 초기화 실패: {self._init_error}")
        if not query:
            return []

        original_max = self._tool.max_results
        if max_results is not None:
            self._tool.max_results = max_results
        try:
            result = self._tool.invoke(query)
        finally:
            self._tool.max_results = original_max

        # LangChain Tool은 (results, raw) 튜플을 반환할 수 있으므로 안전하게 분리한다.
        if isinstance(result, tuple):
            hits = result[0]
        else:
            hits = result

        if not hits:
            return []
        if isinstance(hits, list):
            return hits
        # 예외적인 응답 형태(문자열 등)는 리스트로 감싸 후속 단계가 안전하게 처리하도록 한다.
        return [ {"title": "", "url": "", "content": str(hits)} ]


class Deps:
    """그래프 전역에서 공유할 외부 의존성 묶음."""

    def __init__(self) -> None:
        self.vector = VectorSearcher()
        self.tavily = TavilyWrapper(
            max_results=5,
            search_depth="advanced",
            include_answers=True,
            include_raw_content=True,
            include_images=False,
        )


def _get_deps() -> Deps:
    """필요할 때만 초기화하여 재사용하는 싱글턴 의존성."""
    global _deps_singleton
    if _deps_singleton is None:
        _deps_singleton = Deps()
    return _deps_singleton


def _wrap_with_deps(node_fn):
    """deps 주입이 필요한 노드를 LangGraph 규약에 맞게 감싼다."""

    def _wrapped(state: State) -> State:
        return node_fn(state, _get_deps())

    return _wrapped


def _route_node(state: State) -> State:
    """분기 결과를 상태에 기록하고 그대로 반환한다."""
    decision = route_after_eval(state)
    state["_next_node"] = decision
    return state


def _select_route(state: State) -> str:
    """route_after_eval에서 기록한 다음 노드 이름을 꺼낸다."""
    return state.pop("_next_node", "clarify_node")


# --- LangGraph 구성 -------------------------------------------------------
def _genereate_langgraph() -> StateGraph:
    """LangGraph 생성"""
    workflow = StateGraph(State)
    return workflow


def _add_nodes(workflow: StateGraph) -> StateGraph:
    """노드 추가"""
    workflow.add_node("intent_question_node", _wrap_with_deps(intent_question_node))
    workflow.add_node("search_vectordb_node", _wrap_with_deps(search_vectordb_node))
    workflow.add_node("sql_retrieval_node", _wrap_with_deps(sql_retrieval_node))
    workflow.add_node("eval_node", _wrap_with_deps(eval_node))
    workflow.add_node("route_after_eval", _route_node)
    workflow.add_node("generate_node", _wrap_with_deps(generate_node))
    workflow.add_node("search_web_node", _wrap_with_deps(search_web_node))
    workflow.add_node("clarify_node", _wrap_with_deps(clarify_node))
    return workflow


def _add_edges(workflow: StateGraph, START, END) -> StateGraph:
    """엣지 추가(노드 연결)"""
    workflow.add_edge(START, "intent_question_node")
    workflow.add_edge("intent_question_node", "search_vectordb_node")
    workflow.add_edge("search_vectordb_node", "sql_retrieval_node")
    workflow.add_edge("sql_retrieval_node", "eval_node")
    workflow.add_edge("eval_node", "route_after_eval")

    workflow.add_conditional_edges(
        "route_after_eval",
        _select_route,
        {
            "clarify_node": "clarify_node",
            "generate_node": "generate_node",
            "search_web_node": "search_web_node",
        },
    )

    workflow.add_edge("search_web_node", "generate_node")
    workflow.add_edge("clarify_node", END)
    workflow.add_edge("generate_node", END)

    return workflow


def compile_langgraph():
    """워크플로우 컴파일(옵션:메모리추가)"""
    workflow = _genereate_langgraph()
    workflow = _add_nodes(workflow)
    workflow = _add_edges(workflow, START, END)

    graph = workflow.compile(checkpointer=MemorySaver())
    return graph


def display_langgraph(graph):
    """LangGraph 시각화"""
    display(Image(graph.graph.get_graph().draw_mermaid_png(path="langgraph.png")))


if __name__ == "__main__":
    graph = compile_langgraph()
    display_langgraph(graph)
