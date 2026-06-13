from __future__ import annotations

import json
from typing import Any
from ..state import UnifiedChatState

async def response_composer_node(state: UnifiedChatState) -> dict[str, Any]:
    response_sections = []
    text_parts = []
    
    # Asset Selection Context
    asset_ctx = state.get("asset_selection_context", {})
    asset_ids = asset_ctx.get("asset_ids", [])
    
    evidence = state.get("evidence", [])
    rag_evidence = [e for e in evidence if e.get("type") == "rag"]
    
    if asset_ids:
        reason = asset_ctx.get("selection_reason", "relevant")
        rtype = asset_ctx.get("report_type", "document").replace("_", " ")
        
        if rag_evidence:
            msg = f"Your {reason} {rtype} was located.\nRetrieved Findings:"
            for e in rag_evidence:
                msg += f"\n* {e.get('content')}"
        else:
            msg = f"Your {reason} {rtype} was located.\nSelected documents:"
            for aid in asset_ids:
                msg += f"\n* {rtype.title()} ({aid})"
                
        response_sections.append({"type": "asset_selection", "content": msg})
        text_parts.append(msg)
        
    # Appointment Context
    app_ctx = state.get("appointment_context", {})
    if app_ctx:
        action = app_ctx.get("action", "processing")
        msg = f"Appointment status: {action}."
        response_sections.append({"type": "appointment", "content": msg})
        text_parts.append(msg)
        
    # Consultation Context
    cons_ctx = state.get("consultation_context", [])
    if cons_ctx:
        msg = f"Previous consultation notes indicate {len(cons_ctx)} past records."
        response_sections.append({"type": "consultation", "content": msg})
        text_parts.append(msg)
        
    # Medical History Context
    hist_ctx = state.get("patient_history_context", [])
    if hist_ctx:
        msg = f"Medical history shows {len(hist_ctx)} active conditions or records."
        response_sections.append({"type": "patient_history", "content": msg})
        text_parts.append(msg)
        
    # Memory Context
    mem_ctx = state.get("memory_context", [])
    if mem_ctx:
        msg = f"I recalled {len(mem_ctx)} memories from our previous conversations."
        response_sections.append({"type": "memory", "content": msg})
        text_parts.append(msg)
        
    if not text_parts:
        text_parts.append("I am processing your request using general knowledge.")
        response_sections.append({"type": "general", "content": text_parts[-1]})
        
    shadow_response = "\n\n".join(text_parts)
    
    return {
        "response_sections": response_sections,
        "shadow_response": shadow_response,
        "shadow_execution_completed": True
    }
