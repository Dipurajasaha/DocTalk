from __future__ import annotations

from typing import Any
from ..state import UnifiedChatState
from ..models.composed_response import ComposedResponse

async def response_composer_node(state: UnifiedChatState) -> dict[str, Any]:
    response = ComposedResponse(
        memory_context=state.get("memory_context", []),
        consultation_context=state.get("consultation_context", []),
        patient_history_context=state.get("patient_history_context", []),
        doctor_availability_context=state.get("doctor_availability_context", []),
        appointment_context=state.get("appointment_context", {}),
        asset_selection_context=state.get("asset_selection_context", {}),
        rag_scope=state.get("rag_scope", {}),
        evidence=state.get("evidence", [])
    )
    
    print("[DEBUG][COMPOSER] state keys =", list(state.keys()))
    print("[DEBUG][COMPOSER] sections =", response.to_dict().get("response_sections"))
    
    return response.to_dict()
