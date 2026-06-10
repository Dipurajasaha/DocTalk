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
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # Supabase / PostgreSQL (Prisma)
    database_url: str = Field(default="", env="DATABASE_URL")
    direct_url: str = Field(default="", env="DIRECT_URL")
    shadow_database_url: str = Field(default="", env="SHADOW_DATABASE_URL")

    # Supabase project credentials
    supabase_url: str = Field(default="", env="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", env="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(default="", env="SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_secret: str = Field(default="", env="SUPABASE_JWT_SECRET")

    # Gemini AI
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    gemini_model: str = Field(default="", env="GEMINI_MODEL")
    gemini_embed_model: str = Field(default="", env="GEMINI_EMBED_MODEL")
    gemini_base_url: str = Field(default="", env="GEMINI_BASE_URL")

    # --- Provider selection ---
    # Values: gemini | openai | nvidia | longchat
    ai_provider: str = Field(default="", env="AI_PROVIDER")

    # --- OpenAI ---
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="", env="OPENAI_MODEL")
    openai_base_url: str = Field(default="", env="OPENAI_BASE_URL")

    # --- NVIDIA ---
    nvidia_api_key: str = Field(default="", env="NVIDIA_API_KEY")
    nvidia_model: str = Field(default="", env="NVIDIA_MODEL")
    nvidia_base_url: str = Field(default="", env="NVIDIA_BASE_URL")

    # --- LongChat ---
    longchat_api_key: str = Field(default="", env="LONGCHAT_API_KEY")
    longchat_model: str = Field(default="", env="LONGCHAT_MODEL")
    longchat_base_url: str = Field(default="", env="LONGCHAT_BASE_URL")

    # --- Imagga ---
    imgaga_api_key: str = Field(default="", env="IMGAGA_API_KEY")
    imgaga_api_url: str = Field(default="", env="IMGAGA_API_URL")

    # --- Fallback ---
    ai_fallback_enabled: bool = Field(default=True, env="AI_FALLBACK_ENABLED")
    ai_fallback_chain: str = Field(default="", env="AI_FALLBACK_CHAIN")

    ai_request_timeout_seconds: float = Field(default=45.0, env="AI_REQUEST_TIMEOUT_SECONDS")
    xray_analysis_timeout_seconds: float = Field(default=300.0, env="XRAY_ANALYSIS_TIMEOUT_SECONDS")
    rag_embedding_timeout_seconds: float = Field(default=120.0, env="RAG_EMBEDDING_TIMEOUT_SECONDS")
    rag_embedding_dimension: int = Field(default=768, env="RAG_EMBEDDING_DIMENSION")
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