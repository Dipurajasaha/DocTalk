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

    admin_login_max_attempts: int = Field(default=5, env="ADMIN_LOGIN_MAX_ATTEMPTS")
    admin_login_window_seconds: int = Field(default=300, env="ADMIN_LOGIN_WINDOW_SECONDS")
    admin_login_lockout_seconds: int = Field(default=900, env="ADMIN_LOGIN_LOCKOUT_SECONDS")
    admin_invite_token_bytes: int = Field(default=24, env="ADMIN_INVITE_TOKEN_BYTES")
    admin_mfa_issuer: str = Field(default="DocTalk", env="ADMIN_MFA_ISSUER")

    # Supabase / PostgreSQL (Prisma)
    database_url: str = Field(default="", env="DATABASE_URL")
    direct_url: str = Field(default="", env="DIRECT_URL")
    shadow_database_url: str = Field(default="", env="SHADOW_DATABASE_URL")

    # Supabase project credentials
    supabase_url: str = Field(default="", env="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", env="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(default="", env="SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_secret: str = Field(default="", env="SUPABASE_JWT_SECRET")

    # --- Gemini (embeddings + vision) ---
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    gemini_model: str = Field(default="", env="GEMINI_MODEL")
    gemini_embed_model: str = Field(default="", env="GEMINI_EMBED_MODEL")
    gemini_base_url: str = Field(default="", env="GEMINI_BASE_URL")

    # --- OpenAI-compatible LLM (text models) ---
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="", env="OPENAI_MODEL")
    openai_base_url: str = Field(default="", env="OPENAI_BASE_URL")

    # --- Vision endpoint selection ---
    vision_endpoint: str = Field(default="gemini", env="VISION_ENDPOINT")

    # --- Imagga ---
    imgaga_api_key: str = Field(default="", env="IMGAGA_API_KEY")
    imgaga_api_url: str = Field(default="", env="IMGAGA_API_URL")

    # --- External News API (landing page health news) ---
    news_api_key: str = Field(default="", env="NEWS_API_KEY")
    news_api_url: str = Field(
        default="https://newsapi.org/v2/top-headlines?category=health&language=en&pageSize=6",
        env="NEWS_API_URL",
    )

    ai_request_timeout_seconds: float = Field(default=45.0, env="AI_REQUEST_TIMEOUT_SECONDS")
    xray_analysis_timeout_seconds: float = Field(default=300.0, env="XRAY_ANALYSIS_TIMEOUT_SECONDS")
    rag_embedding_timeout_seconds: float = Field(default=120.0, env="RAG_EMBEDDING_TIMEOUT_SECONDS")
    rag_embedding_dimension: int = Field(default=768, env="RAG_EMBEDDING_DIMENSION")
    rag_embedding_cache_size: int = Field(default=128, env="RAG_EMBEDDING_CACHE_SIZE")
    rag_max_memory_age_days: int = Field(default=365, env="RAG_MAX_MEMORY_AGE_DAYS")

    frontend_base_url: str = Field(default="http://localhost:5173", env="FRONTEND_BASE_URL")

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