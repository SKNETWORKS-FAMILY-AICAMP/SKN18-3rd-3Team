"""Configuration management using environment variables."""

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    # OpenAI settings
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    EMBED_MODEL: str = Field(
        default="text-embedding-3-large",
        description="OpenAI embedding model",
    )
    LLM_MODEL: str = Field(
        default="gpt-4",
        description="OpenAI LLM model for generation",
    )
    OPENAI_TIMEOUT: int = Field(
        default=30,
        description="Timeout for OpenAI API calls in seconds",
    )

    # Database settings
    DB_URL: str = Field(..., description="PostgreSQL connection URL")
    PGVECTOR_INDEX: str = Field(
        default="ivfflat",
        description="Vector index type (ivfflat or hnsw)",
    )

    # RAG settings
    TOP_K: int = Field(
        default=8,
        description="Number of documents to retrieve",
    )

    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level",
    )

    # pydantic-settings v2 configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        env_ignore_empty=True,
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("PGVECTOR_INDEX")
    @classmethod
    def validate_index_type(cls, value: str) -> str:
        """Ensure PGVECTOR_INDEX uses a supported backend."""
        if value not in {"ivfflat", "hnsw"}:
            raise ValueError("PGVECTOR_INDEX must be 'ivfflat' or 'hnsw'")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Ensure LOG_LEVEL is one of the supported logging levels."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_value = value.upper()
        if upper_value not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(valid_levels)}")
        return upper_value

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
