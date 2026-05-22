"""Auth-specific schema aliases to preserve backward compatibility.

This module re-exports the login/register Pydantic models from
`app.schemas` under an auth-focused module name to avoid creating a
`schemas` package that would conflict with the existing `schemas.py` module.
"""
from .schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RegisterResponse",
]
