"""Data types for vector store operations"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SearchResult:
    """
    Search result from vector store.
    
    Attributes:
        content: Document text content
        metadata: Document metadata (bank_name, product_type, etc.)
        score: Similarity score (0-1, higher is more similar)
        doc_id: Document identifier
        chunk_id: Chunk identifier
    """
    content: str
    metadata: Dict[str, Any]
    score: float
    doc_id: str
    chunk_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "content": self.content,
            "metadata": self.metadata,
            "score": self.score,
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id
        }
