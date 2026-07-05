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

    
    evidence = state.get("evidence") or []
    
    context_str = ""
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
    
    import time
    from ...utils.logger import log_section, log_key_value, log_trace, format_duration
    
    log_section("COMPOSER")
    log_key_value("Response Mode", "patient_general_llm")
    log_trace("Prompts", [{"type": getattr(m, "type", ""), "content": m.content} for m in messages])
    
    start_time = time.time()
    response = await llm.ainvoke(messages)
    comp_time = (time.time() - start_time) * 1000
    
    timing = state.get("timing_metrics", {})
    timing["composer"] = timing.get("composer", 0) + comp_time
    
    response_text = message_content_text(response) or "I am here to help with your health question."
    
    log_section("FINAL RESPONSE")
    print(f"{response_text}\n")

    return {
        "messages": [response],
        "final_response": response_text,
        "timing_metrics": timing,
        "context_payload": {
            **dict(state.get("context_payload") or {}),
            "route": "patient_general_llm",
            "assistant_mode": "general_health_assistant",
        },
    }

async def patient_knowledge_llm(state: UnifiedChatState) -> dict[str, Any]:
    sys_content = (
        "You are a knowledgeable, empathetic medical assistant. "
        "Provide educational, general medical information about the user's query in plain, patient-friendly language. "
        "Do not diagnose the user or provide personalized medical advice. "
        "Explain medical terms clearly."
    )
        
    all_messages = list(state.get("messages") or [])
    
    messages = [
        SystemMessage(content=sys_content),
        *all_messages,
    ]
    
    import time
    from ...utils.logger import log_section, log_key_value, log_trace, format_duration
    
    log_section("COMPOSER")
    log_key_value("Response Mode", "patient_knowledge_llm")
    log_trace("Prompts", [{"type": getattr(m, "type", ""), "content": m.content} for m in messages])
    
    start_time = time.time()
    response = await llm.ainvoke(messages)
    comp_time = (time.time() - start_time) * 1000
    
    timing = state.get("timing_metrics", {})
    timing["composer"] = timing.get("composer", 0) + comp_time
    
    response_text = message_content_text(response) or "I am here to help with your health question."
    
    log_section("FINAL RESPONSE")
    print(f"{response_text}\n")

    return {
        "messages": [response],
        "final_response": response_text,
        "timing_metrics": timing,
        "context_payload": {
            **dict(state.get("context_payload") or {}),
            "route": "patient_knowledge_llm",
            "assistant_mode": "medical_knowledge_assistant",
        },
    }



async def patient_assistant_llm(state: UnifiedChatState) -> dict[str, Any]:
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
    
    ai_message_count = sum(1 for m in messages_list if getattr(m, "type", "") == "ai")
    if context_str and context_str != '""' and context_str != "{}" and context_str != "[]" and context_str != "null" and messages_list:
        chat_messages = [messages_list[-1]]
    else:
        chat_messages = messages_list
        
    messages = [sys_msg] + chat_messages
    
    import time
    from ...utils.logger import log_section, log_key_value, log_trace, format_duration
    
    log_section("COMPOSER")
    log_key_value("Response Mode", "patient_assistant_llm")
    log_trace("Prompts", [{"type": getattr(m, "type", ""), "content": m.content} for m in messages])
    
    start_time = time.time()
    response = await llm.ainvoke(messages)
    comp_time = (time.time() - start_time) * 1000
    
    timing = state.get("timing_metrics", {})
    timing["composer"] = timing.get("composer", 0) + comp_time
    
    response_text = message_content_text(response) or "I am here to help with your health question."
    
    log_section("FINAL RESPONSE")
    print(f"{response_text}\n")

    return {
        "messages": [response],
        "final_response": response_text,
        "timing_metrics": timing,
        "context_payload": {
            **dict(state.get("context_payload") or {}),
            "route": "patient_assistant_llm",
            "assistant_mode": "empathetic_health_assistant",
        },
    }
