"""Configuration management using environment variables"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Config(BaseSettings):
    """Application configuration loaded from environment variables"""
    
    # OpenAI settings
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    EMBED_MODEL: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model"
    )
    
    # LLM Models
    GEN_LLM_MODEL: str = Field(
        default="gpt-5-nano",
        description="생성용 LLM 모델 (답변 생성, 분류 등)"
    )
    GEN_LLM_TEMPERATURE: float = Field(
        default=1.0,
        description="생성용 LLM Temperature (창의성)"
    )
    EVAL_LLM_MODEL: str = Field(
        default="gpt-4o",
        description="평가용 LLM 모델 (청크 관련성 평가)"
    )
    EVAL_LLM_TEMPERATURE: float = Field(
        default=0.0,
        description="평가용 LLM Temperature (일관성)"
    )
    
    # Legacy LLM Model (호환성 유지)
    LLM_MODEL: str = Field(
        default="gpt-4",
        description="OpenAI LLM model for generation (legacy)"
    )
    
    OPENAI_TIMEOUT: int = Field(
        default=30,
        description="Timeout for OpenAI API calls in seconds"
    )
    
    # Database settings
    DB_URL: str = Field(..., description="PostgreSQL connection URL")
    PGVECTOR_INDEX: str = Field(
        default="ivfflat",
        description="Vector index type (ivfflat or hnsw)"
    )
    
    # RAG settings
    TOP_K: int = Field(
        default=8,
        description="Number of documents to retrieve"
    )
    
    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # LangSmith settings (optional)
    LANGCHAIN_TRACING_V2: Optional[str] = Field(
        default=None,
        description="Enable LangSmith tracing"
    )
    LANGCHAIN_ENDPOINT: Optional[str] = Field(
        default=None,
        description="LangSmith API endpoint"
    )
    LANGCHAIN_API_KEY: Optional[str] = Field(
        default=None,
        description="LangSmith API key"
    )
    LANGCHAIN_PROJECT: Optional[str] = Field(
        default=None,
        description="LangSmith project name"
    )
    
    @validator("PGVECTOR_INDEX")
    def validate_index_type(cls, v):
        """Validate vector index type"""
        if v not in ["ivfflat", "hnsw"]:
            raise ValueError("PGVECTOR_INDEX must be 'ivfflat' or 'hnsw'")
        return v

    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # 정의되지 않은 환경 변수 무시
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        return cls()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global config instance"""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
