from __future__ import annotations

from typing import Any

from backend.core.database import prisma


async def retrieve_conversation_memory(*, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
    if not session_id:
        return []

    messages = await prisma.aichatmessage.find_many(
        where={"sessionId": session_id},
        order={"createdAt": "desc"},
        take=limit,
    )

    results: list[dict[str, Any]] = []
    for msg in messages:
        results.append({
            "role": str(msg.role or ""),
            "content": str(msg.content or ""),
            "created_at": msg.createdAt,
        })

    return results
