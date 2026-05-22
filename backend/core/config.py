from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv

from .constants import DEFAULT_CORS_ORIGINS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DATA_ROOT = PROJECT_ROOT / "data"
PRISMA_SCHEMA_PATH = PROJECT_ROOT / "prisma" / "schema.prisma"
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE, override=False)


def _split_csv(value: str | None, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return fallback
    values = tuple(item.strip() for item in value.split(",") if item.strip())
    return values or fallback


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "DocTalk Backend")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    environment: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    port: int = int(os.getenv("BACKEND_PORT", "8000"))
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    direct_url: str = os.getenv("DIRECT_URL", "")
    shadow_database_url: str = os.getenv("SHADOW_DATABASE_URL", "")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY") or os.getenv("SESSION_SECRET_KEY", "dev-jwt-secret")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    postgres_user: str = os.getenv("POSTGRES_USER", "doctalk")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "doctalk")
    postgres_db: str = os.getenv("POSTGRES_DB", "doctalk")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    pgadmin_email: str = os.getenv("PGADMIN_DEFAULT_EMAIL", "admin@local")
    pgadmin_password: str = os.getenv("PGADMIN_DEFAULT_PASSWORD", "admin")

    @property
    def cors_origins(self) -> tuple[str, ...]:
        return _split_csv(self.cors_origins_raw, DEFAULT_CORS_ORIGINS)

    @property
    def data_root(self) -> Path:
        root = os.getenv("DATA_ROOT")
        return Path(root).resolve() if root else DATA_ROOT

    @property
    def database_ready_sql(self) -> str:
        return "SELECT 1 AS ok"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
