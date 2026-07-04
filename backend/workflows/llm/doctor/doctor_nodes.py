from __future__ import annotations

import json
from typing import Any
from fastapi.encoders import jsonable_encoder

from langchain_core.messages import SystemMessage

from ...graph.common import get_workflow_model, latest_message_text, message_content_text
from ...graph.state import UnifiedChatState
from ...capabilities.tools.rag_tools import doctor_rag_tool


DOCTOR_SYSTEM_PROMPT = (
    "You are a highly technical clinical reasoning copilot. Use medical terminology, reason with precision, and "
    "focus on differential considerations, red-flag assessment, and next-step clinical thinking. Be concise but detailed."
)

llm = get_workflow_model(temperature=0.1)


async def doctor_general_llm(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    latest_message = latest_message_text(state.get("messages"))
    if latest_message:
        payload.setdefault("latest_request", latest_message)

    messages = [
        SystemMessage(content=DOCTOR_SYSTEM_PROMPT),
        *list(state.get("messages") or []),
    ]
    
    evidence = state.get("evidence") or []
    if evidence:
        context_str = f"Evidence:\n{json.dumps(jsonable_encoder(evidence))}\n\n"
        messages.insert(1, SystemMessage(content=f"You have access to the following retrieved context:\n{context_str}"))
    
    print("[DEBUG][LLM] evidence =", state.get("evidence"))
    print("[DEBUG][LLM] prompt =", messages)
    
    response = await llm.ainvoke(messages)
    response_text = message_content_text(response) or "Clinical reasoning guidance is unavailable at the moment."

    return {
        "messages": [response],
        "final_response": response_text,
        "context_payload": {
            **payload,
            "route": "doctor_general_llm",
            "assistant_mode": "clinical_reasoning_copilot",
        },
    }


async def doctor_scoped_llm(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    target_patient_id = str(state.get("target_patient_id") or "").strip()
    latest_message = latest_message_text(state.get("messages"))
    if latest_message:
        payload.setdefault("latest_request", latest_message)

    messages_list = list(state.get("messages") or [])
    last_message = messages_list[-1] if messages_list else None
    evidence = state.get("evidence") or []
    context_str = json.dumps(jsonable_encoder(evidence), default=str) if evidence else ""
    sys_msg = SystemMessage(
        content=(
            "You are a medical AI. Answer the user's query using ONLY this retrieved data: "
            f"{context_str}. If empty, say no records exist."
        )
    )
    
    messages = [sys_msg] + messages_list
    print("[DEBUG][LLM] evidence =", state.get("evidence"))
    print("[DEBUG][LLM] prompt =", messages)
    
    response = await llm.ainvoke(messages)
    response_text = message_content_text(response) or "Clinical reasoning guidance is unavailable at the moment."

    return {
        "messages": [response],
        "final_response": response_text,
        "context_payload": {
            **payload,
            "route": "doctor_scoped_llm",
            "assistant_mode": "clinical_reasoning_copilot",
            "target_patient_id": target_patient_id,
        },
    }


doctor_copilot_llm = doctor_general_llm
