from __future__ import annotations

from typing import Any

from ..state import UnifiedChatState


async def response_composer_node(state: UnifiedChatState) -> dict[str, Any]:
    # Skeleton implementation
    # Pass through the final response
    return {
        "final_response": state.get("final_response", "")
    }
