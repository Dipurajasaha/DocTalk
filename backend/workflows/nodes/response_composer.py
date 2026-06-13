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
            "consultation_count": len(state.get("consultation_context", [])),
            "execution_iteration": state.get("execution_iteration", 0),
            "need_more_actions": state.get("need_more_actions", False)
        }),
        "shadow_execution_completed": True
    }
