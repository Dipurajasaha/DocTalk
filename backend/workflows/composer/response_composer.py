from __future__ import annotations

from typing import Any
from ..graph.state import UnifiedChatState
from ..models.composed_response import ComposedResponse
from ..utils.sanitizer import sanitize_for_llm

ACTION_CAPABILITIES = {"APPOINTMENT_BOOK", "APPOINTMENT_CANCEL", "APPOINTMENT_RESCHEDULE"}

async def response_composer_node(state: UnifiedChatState) -> dict[str, Any]:
    evidence = list(state.get("evidence", []))
    
    for ev in evidence:
        if ev.get("type") == "consultation":
            c_ctx = state.get("consultation_context")
            if c_ctx:
                import json
                ev["content"] += f"\n\nDetails:\n{json.dumps(sanitize_for_llm(c_ctx), default=str)}"
        elif ev.get("type") == "patient_history":
            h_ctx = state.get("patient_history_context")
            if h_ctx:
                import json
                ev["content"] += f"\n\nDetails:\n{json.dumps(sanitize_for_llm(h_ctx), default=str)}"

    response = ComposedResponse(
        evidence=evidence
    )
    
    result_dict: dict[str, Any] = {
        **response.to_dict(),
        "evidence": evidence
    }

    # Action capabilities generate user-facing confirmation directly
    action_ev = next((ev for ev in evidence if ev.get("source") in ACTION_CAPABILITIES), None)
    if action_ev:
        cap_source = action_ev.get("source")
        raw_msg = action_ev.get("content", "")
        
        if cap_source == "APPOINTMENT_BOOK":
            if "booked successfully" in raw_msg.lower():
                if not raw_msg.lower().startswith("your appointment has been booked"):
                    formatted_msg = raw_msg.replace("Appointment booked successfully.", "Your appointment has been booked successfully.")
                else:
                    formatted_msg = raw_msg
                result_dict["final_response"] = formatted_msg
        else:
            result_dict["final_response"] = raw_msg

    return result_dict

