from functools import lru_cache
from typing import Optional

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
    ai_request_timeout: float = 30.0

    embedding_model: str = "text-embedding-ada-002"
    embedding_dimension: int = 1536

    max_conversation_history: int = 10
    default_confidence_threshold: float = 0.7

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
