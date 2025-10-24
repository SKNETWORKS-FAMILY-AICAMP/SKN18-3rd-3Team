
from typing import List, Dict, Any, Optional, Tuple
import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from langchain.vectorstores.base import VectorStore
from langchain_core.documents import Document
from psycopg2.extras import Json
load_dotenv(override=True)

try:
    from db_ingest.embedding_model import load_documents, create_text_splitter, create_embeddings
except ImportError:
    from embedding_model import load_documents, create_text_splitter, create_embeddings

DEFAULT_DATASET_PATH = Path("data/final_embedding_data_v4.csv")
DEFAULT_TABLE_NAME = "rag.bank_clauses"
DEFAULT_CHUNK_SIZE = 300
DEFAULT_CHUNK_OVERLAP = 100


def load_config() -> Dict[str, Optional[str]]:
    """환경 변수에서 데이터베이스 연결 정보를 불러온다."""
    return {
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_PORT": os.getenv("DB_PORT"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
    }


def build_connection_string(config: Dict[str, Optional[str]]) -> str:
    """설정 값으로 PostgreSQL 연결 문자열을 만든다."""
    return (
        f"postgresql://{config['DB_USER']}:{config['DB_PASSWORD']}"
        f"@{config['DB_HOST']}:{config['DB_PORT']}/{config['DB_NAME']}"
    )


def resolve_dataset_path(path: Optional[str] = None) -> Path:
    """CSV 경로를 검증하고 Path 객체로 반환한다."""
    dataset_path = Path(path) if path else DEFAULT_DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    return dataset_path


def load_clause_documents(
    dataset_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Document]:
    """은행 상품 조항 CSV를 불러와 임베딩용 문서로 변환한다."""
    splitter = create_text_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return load_documents(str(dataset_path), splitter=splitter)


def create_vector_store(conn_str: str, embedding_fn, table: str = DEFAULT_TABLE_NAME) -> "CustomPGVector":
    """벡터 스토어 인스턴스를 생성한다."""
    return CustomPGVector(conn_str=conn_str, embedding_fn=embedding_fn, table=table)


def ingest_documents(vector_store, documents: List[Document]) -> None:
    """문서 청크를 벡터 스토어에 저장한다."""
    vector_store.add_documents(documents)


# VectorStore의 싱글톤 패턴 구현
class Singleton(type(VectorStore)):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class CustomPGVector(VectorStore, metaclass=Singleton):
    """init.sql로 생성한 PGVector 테이블에 맞춘 CustomPGVector 클래스 정의"""

    def __init__(self, conn_str: str, embedding_fn, table: str = DEFAULT_TABLE_NAME):
        self.conn = psycopg2.connect(conn_str)
        self.embedding_fn = embedding_fn
        self.table = table

    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding_fn,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        conn_str: str = None,
        table: str = DEFAULT_TABLE_NAME,
        **kwargs,
    ):
        store = cls(conn_str=conn_str, embedding_fn=embedding_fn, table=table)
        store.add_texts(texts, metadatas=metadatas)
        return store

    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]] = None):
        metadatas = metadatas or [{} for _ in texts]
        embeddings = self.embedding_fn.embed_documents(texts)
        doc_chunk_counters: Dict[str, int] = {}
        embedding_model_name = (
            getattr(self.embedding_fn, "model", None)
            or getattr(self.embedding_fn, "model_name", None)
            or "unknown"
        )

        with self.conn.cursor() as cur:
            for text, emb, meta in zip(texts, embeddings, metadatas):
                meta = dict(meta or {})

                raw_doc_id = meta.get("doc_id") or meta.get("chunk_id") or "UNKNOWN_DOC"
                doc_id = str(raw_doc_id)

                raw_chunk_index = meta.get("chunk_index")
                try:
                    chunk_index = int(raw_chunk_index)
                except (TypeError, ValueError):
                    chunk_index = None

                if chunk_index is None:
                    chunk_index = doc_chunk_counters.get(doc_id, 0)

                doc_chunk_counters[doc_id] = chunk_index + 1

                raw_chunk_id = meta.get("chunk_id")
                chunk_id = str(raw_chunk_id) if raw_chunk_id is not None else f"{doc_id}-chunk-{chunk_index}"

                source_file = str(meta.get("source") or meta.get("source_file") or "unknown")

                bank_name = meta.get("은행명") or meta.get("bank") or meta.get("bank_name")
                product_type = meta.get("상품종류") or meta.get("product_type")
                product_name = meta.get("상품이름") or meta.get("product_name")
                clause_number = meta.get("조항") or meta.get("clause_number")
                clause_title = meta.get("조항이름") or meta.get("clause_title")

                def _norm(value):
                    return str(value).strip() if value is not None else None

                bank_name = _norm(bank_name)
                product_type = _norm(product_type)
                product_name = _norm(product_name)
                clause_number = _norm(clause_number)
                clause_title = _norm(clause_title)

                meta.update(
                    {
                        "doc_id": doc_id,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "source_file": source_file,
                        "embedding_model": embedding_model_name,
                        "bank_name": bank_name,
                        "product_type": product_type,
                        "product_name": product_name,
                        "clause_number": clause_number,
                        "clause_title": clause_title,
                    }
                )

                cur.execute(
                    f"""
                    INSERT INTO {self.table} (
                        chunk_id,
                        doc_id,
                        chunk_index,
                        bank_name,
                        product_type,
                        product_name,
                        clause_number,
                        clause_title,
                        content,
                        embedding,
                        metadata,
                        source_file,
                        embedding_model
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id)
                    DO UPDATE SET
                        doc_id = EXCLUDED.doc_id,
                        chunk_index = EXCLUDED.chunk_index,
                        bank_name = EXCLUDED.bank_name,
                        product_type = EXCLUDED.product_type,
                        product_name = EXCLUDED.product_name,
                        clause_number = EXCLUDED.clause_number,
                        clause_title = EXCLUDED.clause_title,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        source_file = EXCLUDED.source_file,
                        embedding_model = EXCLUDED.embedding_model,
                        updated_at = NOW()
                    """,
                    (
                        chunk_id,
                        doc_id,
                        chunk_index,
                        bank_name,
                        product_type,
                        product_name,
                        clause_number,
                        clause_title,
                        text,
                        emb,
                        Json(meta),
                        source_file,
                        embedding_model_name,
                    ),
                )
        self.conn.commit()

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:

        query_emb = self.embedding_fn.embed_query(query)

        # 쿼리 매개변수 리스트 초기화. 필터 매개변수가 있다면 여기에 먼저 추가됩니다.
        params = []

        # SQL 쿼리 기본 구조 설정
        sql_query_template = f"""
            SELECT content, metadata
            FROM {self.table}
        """

        # WHERE 절을 위한 리스트
        where_clauses = []

        if filter:
            # 1. 필터 딕셔너리를 JSON 문자열로 변환합니다.
            filter_json = json.dumps(filter)

            # 2. WHERE 절에 'metadata @> %s::jsonb' 조건을 추가합니다.
            where_clauses.append("metadata @> %s::jsonb")

            # 3. 필터 JSON 문자열을 params 리스트에 먼저 추가합니다.
            #    이것이 SQL 쿼리에서 가장 먼저 나오는 %s에 바인딩됩니다.
            params.append(filter_json)

        if where_clauses:
            sql_query_template += " WHERE 1=1 AND " + " AND ".join(where_clauses)

        # ORDER BY 및 LIMIT 절 추가
        # ORDER BY에는 임베딩 비교가 들어가며, 이는 필터가 있든 없든 항상 두 번째 (혹은 첫 번째) %s가 됩니다.
        sql_query_template += """
            ORDER BY embedding <-> %s::vector
            LIMIT %s
        """

        # 4. 임베딩 벡터를 params에 추가합니다.
        #    이는 ORDER BY의 %s에 바인딩됩니다.
        params.append(query_emb)

        # 5. LIMIT 값 (k)을 params에 마지막으로 추가합니다.
        #    이는 LIMIT의 %s에 바인딩됩니다.
        params.append(k)

        # 최종 SQL 쿼리: (필터가 있을 경우) WHERE [조건] ORDER BY [임베딩] LIMIT [k]

        with self.conn.cursor() as cur:
            # 쿼리와 매개변수를 실행
            # 매개변수의 순서는 SQL 쿼리에 나타나는 %s의 순서와 정확히 일치해야 합니다.
            cur.execute(sql_query_template, tuple(params))
            rows = self.__get_unique_documents(cur.fetchall())

        return [Document(page_content=row[0], metadata=row[1]) for row in rows]

    def similarity_search_with_score(
        self, query: str, k: int = 4
    ) -> List[Tuple[Document, float]]:
        """쿼리와 유사도 점수를 함께 반환"""
        query_emb = self.embedding_fn.embed_query(query)

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT content, metadata, (embedding <-> %s::vector) AS score
                FROM {self.table}
                ORDER BY score
                LIMIT %s
                """,
                (query_emb, k),
            )
            rows = self.__get_unique_documents(cur.fetchall())

        return [
            (Document(page_content=row[0], metadata=row[1]), float(row[2]))
            for row in rows
        ]

    def __get_unique_documents(self, rows):
        # 중복 제거를 위한 후처리
        unique_contents = set()
        unique_documents = []

        for row in rows:
            content = row[0]

            if content not in unique_contents:
                unique_contents.add(content)
                unique_documents.append(row)  # 중복이 아닐 때 원본 튜플을 저장

        return unique_documents  # 중복 제거된 리스트 반환


if __name__ == "__main__":
    # 전체 파이프라인 실행: 문서 로드 → 분할 → 임베딩 → 벡터 저장.
    config = load_config()
    dataset = resolve_dataset_path()
    documents = load_clause_documents(dataset)
    embeddings = create_embeddings()
    str_connection_info = build_connection_string(config)
    vector_store = create_vector_store(str_connection_info, embeddings)
    ingest_documents(vector_store, documents)
    print(f"벡터 DB 생성 완료: {dataset}")
