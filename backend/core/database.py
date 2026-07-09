from __future__ import annotations

import asyncio
import logging
from typing import Any

from prisma import Prisma

from .config import settings

logger = logging.getLogger(__name__)

prisma = Prisma(auto_register=False)
_is_connected = False


async def connect_prisma() -> None:
    global _is_connected
    if _is_connected:
        return

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    connect_timeout_seconds = 15.0
    try:
        await asyncio.wait_for(prisma.connect(), timeout=connect_timeout_seconds)
        _is_connected = True
        logger.info(
            "Supabase PostgreSQL database connected",
            extra={"component": "database"},
        )
    except Exception as exc:
        _is_connected = False
        logger.warning(
            "Database connect failed",
            extra={"component": "database", "error": str(exc)},
        )
        raise exc


async def disconnect_prisma() -> None:
    global _is_connected
    if not _is_connected:
        return

    await prisma.disconnect()
    _is_connected = False
    logger.info("Database client disconnected", extra={"component": "database"})


async def ensure_connected() -> None:
    if not _is_connected:
        await connect_prisma()


async def get_prisma() -> Prisma:
    await ensure_connected()
    return prisma


async def ping_database() -> dict[str, Any]:
    try:
        await ensure_connected()
        result = await prisma.query_raw("SELECT 1 AS ok")
    except Exception:
        logger.warning(
            "Database ping failed, retrying reconnect",
            extra={"component": "database"},
        )
        await disconnect_prisma()
        await connect_prisma()
        result = await prisma.query_raw("SELECT 1 AS ok")

    first_row = result[0] if result else {"ok": 1}
    return {"status": "ok", "database": "connected", "result": first_row}
