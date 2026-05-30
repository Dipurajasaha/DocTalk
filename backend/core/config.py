from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
