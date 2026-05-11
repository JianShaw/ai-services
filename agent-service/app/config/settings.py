from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Customer Service Agent"
    debug: bool = True
    version: str = "0.1.0"

    database_url: str = "sqlite+aiosqlite:///./data/database.db"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str = "knowledge_chunks"

    redis_url: str = "redis://localhost:6379"

    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.deepseek.com"
    anthropic_api_key: Optional[str] = None
    model_name: str = "deepseek-v4-flash"
    ai_request_timeout: float = 8.0

    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimension: int = 1536
    knowledge_score_threshold: float = 0.35
    knowledge_top_k: int = 5

    max_conversation_history: int = 10
    default_confidence_threshold: float = 0.7

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"dev", "development"}:
                return True
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
