"""Embedding providers for text vectorization"""

from .provider import EmbeddingProvider
from .openai_embed import OpenAIEmbeddings

__all__ = ["EmbeddingProvider", "OpenAIEmbeddings"]
