"""Backward-compatible re-exports for chat schemas.

This module used to define chat schemas inline. It now re-exports the
canonical models from `app.schemas` to avoid duplication while preserving
existing import paths. Keep this file until callers are fully migrated.

TODO: Remove this compatibility shim after all call sites import from
`app.schemas` directly.
"""
from ..schemas import Message, ChatRequest, ChatReply

__all__ = ["Message", "ChatRequest", "ChatReply"]
