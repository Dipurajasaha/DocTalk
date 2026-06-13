from __future__ import annotations

import json
from typing import Any
from ..state import UnifiedChatState

async def response_composer_node(state: UnifiedChatState) -> dict[str, Any]:
    return {
        "shadow_response": json.dumps({
            "execution_plan": state.get("execution_plan", []),
            "evidence_count": len(state.get("evidence", [])),
            "memory_count": len(state.get("memory_context", [])),
            "consultation_count": len(state.get("consultation_context", []))
        }),
        "shadow_execution_completed": True
    }
