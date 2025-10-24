"""OpenAI embedding implementation"""

from typing import List
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from RAG.embeddings.provider import EmbeddingProvider
from RAG.core.logger import get_logger


logger = get_logger(__name__)


class OpenAIEmbeddings(EmbeddingProvider):
    """
    OpenAI embedding provider with retry logic.
    
    Supports models like text-embedding-3-large (3072 dimensions)
    """
    
    # Model dimensions mapping
    MODEL_DIMENSIONS = {
        "text-embedding-3-large": 3072,
        "text-embedding-3-small": 1536,
        "text-embedding-ada-002": 1536
    }
    
    def __init__(self, model: str, api_key: str, timeout: int = 30):
        """
        Initialize OpenAI embeddings.
        
        Args:
            model: OpenAI embedding model name
            api_key: OpenAI API key
            timeout: Request timeout in seconds
        """
        self.model = model
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self._dimension = self.MODEL_DIMENSIONS.get(model, 1536)
        
        logger.info(f"Initialized OpenAI embeddings with model: {model}")
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension"""
        return self._dimension
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts with retry logic.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors
        """
        try:
            logger.debug(f"Embedding {len(texts)} texts")
            
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            logger.debug(f"Successfully embedded {len(embeddings)} texts")
            
            return embeddings
        except Exception as e:
            logger.error(f"Failed to embed texts: {e}")
            raise

    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query text with retry logic.
        
        Args:
            text: Query text to embed
        
        Returns:
            Embedding vector
        """
        try:
            logger.debug(f"Embedding query: {text[:100]}...")
            
            response = self.client.embeddings.create(
                model=self.model,
                input=[text]
            )
            
            embedding = response.data[0].embedding
            logger.debug("Successfully embedded query")
            
            return embedding
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise
