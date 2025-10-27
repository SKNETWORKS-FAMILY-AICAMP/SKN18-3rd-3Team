"""Abstract embedding provider interface"""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    
    This interface allows for easy swapping of embedding models
    (e.g., OpenAI, HuggingFace, Cohere, etc.)
    
    Note: This is a custom interface. For LangChain compatibility,
    implementations should also inherit from langchain_core.embeddings.Embeddings
    """
    
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of documents into vectors (LangChain standard).
        
        Args:
            texts: List of text strings to embed
        
        Returns:
            List of embedding vectors
        """
        pass
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts (backward compatibility).
        
        Args:
            texts: List of text strings to embed
        
        Returns:
            List of embedding vectors
        """
        return self.embed_documents(texts)
    
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query text into a vector.
        
        Args:
            text: Query text to embed
        
        Returns:
            Embedding vector
        """
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """
        Get the dimension of the embedding vectors.
        
        Returns:
            Embedding dimension
        """
        pass
