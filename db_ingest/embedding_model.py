"""문서 로딩 및 임베딩 관련 유틸리티."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Sequence

import pandas as pd
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.base import BaseLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

# data/final_dataset_woo.csv 구성에 맞춘 기본 설정 값들
DEFAULT_CONTENT_COLUMNS: Sequence[str] = (
    "은행명",
    "상품종류",
    "상품이름",
    "조항",
    "조항이름",
    "조항내용",
)
DEFAULT_METADATA_COLUMNS: Sequence[str] = (
    "chunk_id",
    "doc_id",
    "은행명",
    "상품종류",
    "상품이름",
    "조항",
    "조항이름",
)
DEFAULT_COLUMN_LABELS: Mapping[str, str] = {
    "은행명": "은행명",
    "상품종류": "상품종류",
    "상품이름": "상품명",
    "조항": "조항",
    "조항이름": "조항 이름",
    "조항내용": "조항 내용",
}
EN_METADATA_KEYS: Mapping[str, str] = {
    "bank": "은행명",
    "product_type": "상품종류",
    "product_name": "상품이름",
    "clause_number": "조항",
    "clause_title": "조항이름",
}


@dataclass
class CSVLoaderConfig:
    """CSV 로더 설정."""

    file_path: str
    content_columns: Sequence[str] = DEFAULT_CONTENT_COLUMNS
    metadata_columns: Sequence[str] = DEFAULT_METADATA_COLUMNS
    sep: str = ","
    encoding: str = "utf-8-sig"
    na_fill: str = ""
    column_labels: Mapping[str, str] = field(default_factory=lambda: DEFAULT_COLUMN_LABELS.copy())


class CustomCSVLoader(BaseLoader):
    """final_dataset_woo.csv를 LangChain Document로 변환하는 전용 로더."""

    def __init__(self, config: CSVLoaderConfig) -> None:
        self.file_path = config.file_path
        self.content_columns = config.content_columns
        self.metadata_columns = config.metadata_columns
        self.sep = config.sep
        self.encoding = config.encoding
        self.na_fill = config.na_fill
        self.column_labels = dict(config.column_labels)

    def load(self) -> List[Document]:
        df = (
            pd.read_csv(self.file_path, sep=self.sep, encoding=self.encoding)
            .fillna(self.na_fill)
        )
        documents: List[Document] = []
        for record in df.to_dict("records"):
            page_content = self._build_page_content(record)
            metadata = self._build_metadata(record)
            documents.append(Document(page_content=page_content, metadata=metadata))
        return documents

    def _build_page_content(self, record: Mapping[str, object]) -> str:
        parts: List[str] = []
        for column in self.content_columns:
            if column not in record:
                continue
            raw_value = record[column]
            value = str(raw_value).strip()
            if not value or value == "nan":
                continue
            label = self.column_labels.get(column, column)
            parts.append(f"{label}: {value}")
        return "\n".join(parts)

    def _build_metadata(self, record: Mapping[str, object]) -> Dict[str, object]:
        metadata: Dict[str, object] = {
            column: record[column]
            for column in self.metadata_columns
            if column in record
        }
        for meta_key, source_column in EN_METADATA_KEYS.items():
            if source_column in record:
                metadata[meta_key] = record[source_column]
        metadata["source"] = self.file_path
        return metadata


def load_documents(
    file_path: str,
    *,
    splitter: RecursiveCharacterTextSplitter | None = None,
) -> List[Document]:
    """
    final_dataset_woo.csv 기반으로 문서를 불러온다.

    상품명을 검색하면 해당 상품의 조항이, 조항 내 키워드를 검색하면 상품명을
    쉽게 확인할 수 있도록 page_content와 metadata를 구성한다.
    """
    loader = CustomCSVLoader(CSVLoaderConfig(file_path=file_path))
    documents = loader.load()
    if splitter is None:
        return documents
    return splitter.split_documents(documents)


def create_text_splitter(
    chunk_size: int = 600,
    chunk_overlap: int = 100,
) -> RecursiveCharacterTextSplitter:
    """조항 본문이 길 때를 대비한 텍스트 분할기."""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )


def split_documents(
    splitter: RecursiveCharacterTextSplitter, documents: Iterable[Document]
) -> List[Document]:
    """문서를 겹치는 청크로 분할한다."""
    return splitter.split_documents(list(documents))


def create_embeddings(model: str = "text-embedding-3-small") -> OpenAIEmbeddings:
    """OpenAI 임베딩 모델 인스턴스를 생성한다."""
    return OpenAIEmbeddings(model=model)
