from __future__ import annotations

from typing import Any
from ..graph.state import UnifiedChatState
from ..models.composed_response import ComposedResponse

async def response_composer_node(state: UnifiedChatState) -> dict[str, Any]:
    response = ComposedResponse(
        evidence=state.get("evidence", [])
    )
    
    print("[DEBUG][COMPOSER] state keys =", list(state.keys()))
    print("[DEBUG][COMPOSER] sections =", response.to_dict().get("response_sections"))
    
    return response.to_dict()
