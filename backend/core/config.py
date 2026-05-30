from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv
from pydantic.v1 import BaseSettings, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Settings(BaseSettings):
    jwt_secret: str = Field(
        default="doc-talk-dev-secret",
        env=["JWT_SECRET", "JWT_SECRET_KEY", "SESSION_SECRET_KEY"],
    )
    database_url: str = Field(default="", env="DATABASE_URL")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_chat_model: str = Field(default="qwen2.5:7b-instruct", env="OLLAMA_CHAT_MODEL")
    ollama_vision_model: str = Field(default="llama3.2-vision", env="OLLAMA_VISION_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", env="OLLAMA_EMBED_MODEL")
    ai_request_timeout_seconds: float = Field(default=45.0, env=["AI_REQUEST_TIMEOUT_SECONDS", "OLLAMA_TIMEOUT_SECONDS"])
    rag_embedding_dimension: int = Field(default=384, env="RAG_EMBEDDING_DIMENSION")
    rag_embedding_cache_size: int = Field(default=128, env="RAG_EMBEDDING_CACHE_SIZE")
    rag_max_memory_age_days: int = Field(default=365, env="RAG_MAX_MEMORY_AGE_DAYS")

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

DATA_ROOT = Path(os.getenv("DATA_ROOT") or (PROJECT_ROOT / "data")).resolve()
