from __future__ import annotations

import json
from typing import Any
from fastapi.encoders import jsonable_encoder

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field, model_validator

from ...graph.common import get_workflow_model, latest_message_text, message_content_text
from ...graph.state import UnifiedChatState
from ...capabilities.tools.rag_tools import patient_rag_tool


class TriageEvaluation(BaseModel):
    is_emergency: bool = Field(
        default=False,
        description="True when the last message contains severe emergency symptoms.",
    )
    rationale: str = Field(default="", description="Short explanation of the triage decision.")

    @model_validator(mode='before')
    @classmethod
    def parse_flexible_fields(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        
        data = dict(values)
        if "is_emergency" not in data:
            is_emer = False
            for k, v in data.items():
                k_lower = k.lower()
                if "emergency" in k_lower or "severity" in k_lower or "triage" in k_lower:
                    if isinstance(v, bool):
                        is_emer = v
                        break
                    elif isinstance(v, str):
                        v_lower = v.lower()
                        if "non" in v_lower or "false" in v_lower or "no" in v_lower or "low" in v_lower:
                            is_emer = False
                            break
                        elif "emergency" in v_lower or "true" in v_lower or "yes" in v_lower or "high" in v_lower:
                            is_emer = True
                            break
            data["is_emergency"] = is_emer
            
        if "rationale" not in data:
            rat = ""
            for k, v in data.items():
                if "rationale" in k.lower() or "reason" in k.lower() or "explain" in k.lower():
                    rat = str(v)
                    break
            data["rationale"] = rat
            
        return data


TRIAGE_SYSTEM_PROMPT = (
    "You are a clinical triage safety classifier. Read only the last patient message and decide whether it contains "
    "severe emergency symptoms such as chest pain, trouble breathing, stroke symptoms, severe bleeding, seizure, "
    "unconsciousness, blue lips, or other immediately life-threatening signs. Reply with a strict structured decision."
)

llm = get_workflow_model(temperature=0.1)


async def triage_evaluator(state: UnifiedChatState) -> dict[str, Any]:
    latest_message = latest_message_text(state.get("messages"))
    if not latest_message:
        return {}

    model = get_workflow_model()
    evaluator = model.with_structured_output(TriageEvaluation)
    evaluation = await evaluator.ainvoke(
        [
            {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
            {"role": "human", "content": latest_message},
        ]
    )

    is_emergency = bool(getattr(evaluation, "is_emergency", False))
    rationale = str(getattr(evaluation, "rationale", "") or "").strip()
    payload = dict(state.get("context_payload") or {})

    updated_state: dict[str, Any] = {
        "context_payload": {
            **payload,
            "triage_evaluation": {
                "is_emergency": is_emergency,
                "rationale": rationale,
                "last_message": latest_message,
            },
        },
    }
    if is_emergency:
        updated_state["triage_level"] = "emergency"
    return updated_state


async def patient_general_llm(state: UnifiedChatState) -> dict[str, Any]:
    print("[DEBUG][LLM_STATE_KEYS]", state.keys())
    print("[DEBUG][LLM_STATE_RAW]", {
        "patient_history_context": state.get("patient_history_context"),
        "consultation_context": state.get("consultation_context"),
        "memory_context": state.get("memory_context")
    })
    
    patient_history_context = state.get("patient_history_context") or []
    consultation_context = state.get("consultation_context") or []
    memory_context = state.get("memory_context") or []
    appointment_context = state.get("appointment_context") or {}
    evidence = state.get("evidence") or []
    
    context_str = ""
    if patient_history_context:
        context_str += f"Patient History:\n{json.dumps(jsonable_encoder(patient_history_context))}\n\n"
    if consultation_context:
        context_str += f"Consultations:\n{json.dumps(jsonable_encoder(consultation_context))}\n\n"
    if memory_context:
        context_str += f"Memory:\n{json.dumps(jsonable_encoder(memory_context))}\n\n"
    if appointment_context:
        context_str += f"Appointments:\n{json.dumps(jsonable_encoder(appointment_context))}\n\n"
    if evidence:
        context_str += f"Evidence:\n{json.dumps(jsonable_encoder(evidence))}\n\n"
        
    sys_content = (
        "You are a helpful, empathetic medical assistant. "
        "Answer the user's question in plain, patient-friendly language. "
        "Do not attempt to diagnose or provide definitive medical advice. "
        "Use ONLY retrieved context data. If a field is missing, explicitly state that it is unavailable. "
        "Never infer doctor names, dates, locations, clinics, or appointment details."
    )
    if context_str:
        sys_content += f"\n\nYou have access to the following retrieved context. Summarize and use it to answer the user's query:\n{context_str}"
        
    all_messages = list(state.get("messages") or [])
    ai_message_count = sum(1 for m in all_messages if getattr(m, "type", "") == "ai")
    
    if context_str and all_messages:
        chat_messages = [all_messages[-1]]
    else:
        chat_messages = all_messages
        
    messages = [
        SystemMessage(content=sys_content),
        *chat_messages,
    ]
    
    print("[DEBUG][MESSAGE_COUNT]", len(messages))
    print("[DEBUG][PREVIOUS_AI_MESSAGES]", ai_message_count)
    
    print("[DEBUG][STATE_BEFORE_LLM]", {
        "patient_history_context": len(patient_history_context),
        "consultation_context": len(consultation_context),
        "memory_context": len(memory_context),
        "evidence": len(evidence),
    })
    print("[DEBUG][LLM_PROMPT_CONTEXT_INJECTED]", bool(context_str))
    print("[DEBUG][PATIENT_HISTORY_LEN]", len(patient_history_context))
    print("[DEBUG][APPOINTMENT_LEN]", len(appointment_context.get("appointments", [])) if isinstance(appointment_context, dict) else 0)
    print("[DEBUG][APPOINTMENT_PROMPT]", sys_content)
    print("[DEBUG][LLM] prompt =", messages)
    
    response = await llm.ainvoke(messages)
    
    print("=================== DEBUG LOGGING LLM RESPONSE ===================")
    print(f"1. type(response): {type(response)}")
    print(f"2. repr(response): {repr(response)}")
    print(f"3. response.content: {getattr(response, 'content', 'NOT_AVAILABLE')}")
    print(f"4. response.additional_kwargs: {getattr(response, 'additional_kwargs', 'NOT_AVAILABLE')}")
    print(f"5. response.response_metadata: {getattr(response, 'response_metadata', 'NOT_AVAILABLE')}")
    print(f"6. message_content_text(response): {repr(message_content_text(response))}")
    print("==================================================================")
    
    response_text = message_content_text(response) or "I am here to help with your health question."

    return {
        "messages": [response],
        "final_response": response_text,
        "context_payload": {
            **dict(state.get("context_payload") or {}),
            "route": "patient_general_llm",
            "assistant_mode": "general_health_assistant",
        },
    }


async def patient_assistant_llm(state: UnifiedChatState) -> dict[str, Any]:
    messages_list = list(state.get("messages") or [])
    last_message = messages_list[-1] if messages_list else None
    query = message_content_text(last_message) if last_message else latest_message_text(messages_list)
    context = await patient_rag_tool.ainvoke({"query": query, "state": state})
    
    # Strip unnecessary metadata to save token budget
    clean_items = []
    for item in context.get("items", []):
        if isinstance(item, dict) and "content" in item:
            clean_items.append({"content": item["content"]})
    
    clean_context = {"items": clean_items} if clean_items else {}
    context_str = json.dumps(clean_context, default=str) if clean_context else ""
    
    sys_msg = SystemMessage(
        content=(
            "You are a medical AI. Answer the user's query using ONLY this retrieved data: "
            f"{context_str}. If empty, say no records exist."
        )
    )
    
    ai_message_count = sum(1 for m in messages_list if getattr(m, "type", "") == "ai")
    if context_str and context_str != '""' and context_str != "{}" and context_str != "[]" and context_str != "null" and messages_list:
        chat_messages = [messages_list[-1]]
    else:
        chat_messages = messages_list
        
    messages = [sys_msg] + chat_messages
    
    print("[DEBUG][MESSAGE_COUNT]", len(messages))
    print("[DEBUG][PREVIOUS_AI_MESSAGES]", ai_message_count)
    print("[DEBUG][LLM] patient_history_context =", state.get("patient_history_context"))
    print("[DEBUG][LLM] consultation_context =", state.get("consultation_context"))
    print("[DEBUG][LLM] memory_context =", state.get("memory_context"))
    print("[DEBUG][LLM] evidence =", state.get("evidence"))
    print("[DEBUG][LLM] prompt =", messages)
    
    response = await llm.ainvoke(messages)
    
    response_text = message_content_text(response) or "I am here to help with your health question."

    return {
        "messages": [response],
        "final_response": response_text,
        "context_payload": {
            **dict(state.get("context_payload") or {}),
            "route": "patient_assistant_llm",
            "assistant_mode": "empathetic_health_assistant",
        },
    }
