"""Simple, import-safe settings helper.

This module exposes a lightweight Settings dataclass reading from environment
variables. It avoids heavy dependencies so imports remain safe during refactor.
"""
from dataclasses import dataclass
import os
from typing import Optional


@dataclass
class Settings:
    SESSION_SECRET_KEY: str
    DATA_ROOT: str
    CORS_ORIGINS: Optional[str]
    GOOGLE_API_KEY: Optional[str]


def get_settings() -> Settings:
    return Settings(
        SESSION_SECRET_KEY=os.getenv("SESSION_SECRET_KEY", "your_secret_key"),
        DATA_ROOT=os.getenv("HEALTHCARE_DATA_ROOT", os.path.join(os.path.dirname(__file__), "..", "..", "data")),
        CORS_ORIGINS=os.getenv("CORS_ORIGINS"),
        GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
    )


settings = get_settings()
