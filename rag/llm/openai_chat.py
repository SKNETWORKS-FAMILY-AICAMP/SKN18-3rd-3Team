"""OpenAI chat model implementation"""

from typing import Optional, List, Dict, Any
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from RAG.core.logger import get_logger


logger = get_logger(__name__)


class OpenAIChatModel:
    """
    OpenAI chat model wrapper with retry logic.
    
    Supports models like gpt-4, gpt-3.5-turbo, etc.
    """
    
    def __init__(
        self,
        model: str,
        api_key: str,
        timeout: int = 30,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ):
        """
        Initialize OpenAI chat model.
        
        Args:
            model: OpenAI model name
            api_key: OpenAI API key
            timeout: Request timeout in seconds
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
        """
        self.model = model
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        # gpt-5-nano는 temperature=1만 지원하므로 기본값을 1로 설정
        self.temperature = 1.0 if "gpt-5" in model else temperature
        self.max_tokens = max_tokens
        
        logger.info(f"Initialized OpenAI chat model: {model} (temperature={self.temperature})")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a response using the chat model.
        
        Args:
            system_prompt: System message (instructions)
            user_prompt: User message (query)
            temperature: Override default temperature
            max_tokens: Override default max_tokens
        
        Returns:
            Generated response text
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            logger.debug(f"Generating response for query: {user_prompt[:100]}...")
            
            # gpt-5-nano는 model과 messages만 지원 (최소 파라미터)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            
            answer = response.choices[0].message.content
            logger.debug(f"Generated response: {answer[:100]}...")
            
            return answer
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise

    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a response with custom message history.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max_tokens
        
        Returns:
            Generated response text
        """
        try:
            logger.debug(f"Generating response with {len(messages)} messages")
            
            # gpt-5-nano는 model과 messages만 지원 (최소 파라미터)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            
            answer = response.choices[0].message.content
            logger.debug("Generated response successfully")
            
            return answer
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise
