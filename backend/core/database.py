from __future__ import annotations

from typing import Any
import asyncio

from prisma import Prisma

from .config import settings
from .logger import get_logger


logger = get_logger(__name__)
prisma = Prisma()
_is_connected = False


async def connect_prisma() -> None:
    global _is_connected
    if _is_connected:
        return

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            await prisma.connect()
            _is_connected = True
            logger.info("Prisma connected", extra={"component": "database", "attempt": attempt})
            return
        except Exception as exc:
            last_error = exc
            logger.warning("Prisma connect attempt failed", extra={"component": "database", "attempt": attempt, "error": str(exc)})
            await asyncio.sleep(min(0.25 * attempt, 1.0))

    _is_connected = False
    raise last_error or RuntimeError("Unable to connect to Prisma")


async def disconnect_prisma() -> None:
    global _is_connected
    if not _is_connected:
        return

    await prisma.disconnect()
    _is_connected = False
    logger.info("Prisma disconnected", extra={"component": "database"})


async def ping_database() -> dict[str, Any]:
    try:
        await connect_prisma()
        result = await prisma.query_raw(settings.database_ready_sql)
    except Exception:
        logger.warning("Prisma ping failed, retrying reconnect", extra={"component": "database"})
        await disconnect_prisma()
        await connect_prisma()
        result = await prisma.query_raw(settings.database_ready_sql)
    first_row = result[0] if result else {"ok": 1}
    return {
        "status": "ok",
        "database": "connected",
        "result": first_row,
    }
