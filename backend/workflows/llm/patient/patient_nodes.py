from __future__ import annotations

import json
from typing import Any
from fastapi.encoders import jsonable_encoder

from langchain_core.messages import SystemMessage, AIMessage
from pydantic import BaseModel, Field, model_validator

from ...graph.common import get_workflow_model, latest_message_text, message_content_text
from ...graph.state import UnifiedChatState
from ...capabilities.tools.rag_tools import patient_rag_tool
from ...utils.sanitizer import sanitize_for_llm
from ....ai.prompts.templates import medical_prompt_service


def _language_instruction(state: UnifiedChatState) -> str:
    language = str(state.get("language") or "en").strip().lower() or "en"
    return medical_prompt_service._language_hint(language)


def _dedupe_messages(messages: Any) -> list:
    """Remove exact (type, content) duplicates while preserving order.

    The websocket reloads the full DB history each turn and the LangGraph
    in-memory checkpointer also accumulates it, so a resumed conversation can
    contain the same turns twice. Collapsing them keeps the prompt clean.
    """
    seen = set()
    deduped: list = []
    for m in (messages or []):
        key = (getattr(m, "type", ""), str(getattr(m, "content", "") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)
    return deduped


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
        sanitized = sanitize_for_llm(evidence)
        context_str += f"Evidence:\n{json.dumps(jsonable_encoder(sanitized))}\n\n"
        
    sys_content = (
        "You are a helpful, empathetic medical assistant. "
        "Answer the user's question in plain, patient-friendly language. "
        "Do not attempt to diagnose or provide definitive medical advice. "
        "Use ONLY retrieved context data. If a field is missing, explicitly state that it is unavailable. "
        "Never invent or guess doctor names, dates, locations, or clinics. "
        "HOWEVER, if the provided context explicitly contains 'care_recommendation' with suggested doctors, "
        "you MUST seamlessly suggest these specific doctors to the user as next steps on the platform."
    )
    if context_str:
        sys_content += f"\n\nYou have access to the following retrieved context. Summarize and use it to answer the user's query:\n{context_str}"

    sys_content += f"\n\n{_language_instruction(state)}"
    
    active_wf_dict = state.get("planner_metadata", {}).get("active_workflow", {})
    if active_wf_dict and active_wf_dict.get("status") == "waiting_confirmation":
        sys_content += "\n\nCRITICAL INSTRUCTION: The user has requested to book an appointment and a candidate slot has been found. You must explicitly ask the user to confirm if they would like to book this exact slot. Do NOT say you cannot book it directly."

    all_messages = _dedupe_messages(state.get("messages") or [])
    all_messages = list(state.get("messages") or [])
    latest_text = latest_message_text(all_messages).lower()
    payment_failed = bool(
        state.get("payment_failed")
        or (state.get("context_payload") or {}).get("payment_failed")
        or "payment not successful" in latest_text
        or "payment failed" in latest_text
        or "payment cancelled" in latest_text
    )
    if payment_failed:
        sys_content += (
            "\n\nIMPORTANT: The payment did not go through. "
            "Do NOT search for a new slot or start a new booking. "
            "Acknowledge the failed payment and ask the user whether they want to retry the payment."
        )

    ai_message_count = sum(1 for m in all_messages if getattr(m, "type", "") == "ai")

    # Always keep the full conversation so the assistant can reference prior
    # turns. Retrieved context (evidence) is still surfaced via the system
    # prompt above; truncating history here would make the model "forget"
    # everything said earlier in the session.
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
    
    response_text = ""
    from langchain_core.callbacks.manager import adispatch_custom_event
    async for chunk in llm.astream(messages):
        content = getattr(chunk, "content", "")
        if content:
            response_text += content
            await adispatch_custom_event("llm_stream_chunk", content)
            
    response = AIMessage(content=response_text)
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

    sys_content += f"\n\n{_language_instruction(state)}"

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
    
    response_text = ""
    from langchain_core.callbacks.manager import adispatch_custom_event
    async for chunk in llm.astream(messages):
        content = getattr(chunk, "content", "")
        if content:
            response_text += content
            await adispatch_custom_event("llm_stream_chunk", content)
            
    response = AIMessage(content=response_text)
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
    if evidence:
        sanitized = sanitize_for_llm(evidence)
        context_str = json.dumps(jsonable_encoder(sanitized), default=str)
    else:
        context_str = ""
    
    sys_msg = SystemMessage(
        content=(
            "You are a helpful medical assistant. Answer the user's query using ONLY this retrieved data: "
            f"{context_str}. If empty, say no records exist.\n\n"
            "REQUIREMENTS:\n"
            "1. NEVER diagnose a condition unless the diagnosis is explicitly written in the uploaded report.\n"
            "   - Do NOT write: 'This means you have diabetes', 'This confirms diabetes', 'This indicates anemia', 'This suggests fatty liver', 'This means kidney disease'.\n"
            "   - Instead, explain the laboratory value and state whether it is above, below, or within the reference range.\n"
            "2. NEVER prescribe treatment or management. Do NOT recommend medications, dosage changes, diet plans, exercise plans, weight loss, follow-up investigations, or lifestyle modifications.\n"
            "3. If the report itself contains physician remarks or impressions, clearly attribute them under a heading exactly named '### Physician Remarks' and state they come directly from the uploaded report. Never rewrite them as your own medical opinion.\n"
            "4. Avoid speculative statements ('likely', 'probably', 'suggests because of', 'may indicate') unless those exact words appear in the report.\n"
            "5. For every abnormal value in a lab report, you MUST use exactly this structure:\n"
            "   [Parameter Name]\n"
            "   Your Value: [Measured Value]\n"
            "   Reference: [Reference Range]\n"
            "   Status: [High/Low/Normal]\n"
            "   What this measures: [Brief explanation of what the parameter measures]\n"
            "   Why doctors order this test: [Brief explanation of why doctors commonly order this test]\n"
            "6. If a 'care_recommendation' block is provided in the retrieved data, you MUST copy its content EXACTLY at the very end of your response.\n"
            "7. ONLY IF you are interpreting a clinical medical report (e.g. lab results, imaging), you MUST conclude your response with EXACTLY this sentence:\n"
            "   'Please discuss these findings with your healthcare provider, who can interpret them together with your symptoms, medical history, physical examination, and any additional investigations.'\n"
            "   DO NOT include this sentence for general inquiries, past consultation history, or administrative queries (like appointments)."
        )
    )

    sys_msg = SystemMessage(content=sys_msg.content + f"\n\n{_language_instruction(state)}")
    
    ai_message_count = sum(1 for m in messages_list if getattr(m, "type", "") == "ai")
    # Keep the entire conversation history (de-duplicated) so the assistant can
    # refer back to earlier turns instead of only the latest message.
    chat_messages = _dedupe_messages(messages_list)

    messages = [sys_msg] + chat_messages
    
    import time
    from ...utils.logger import log_section, log_key_value, log_trace, format_duration
    
    log_section("COMPOSER")
    log_key_value("Response Mode", "patient_assistant_llm")
    log_trace("Prompts", [{"type": getattr(m, "type", ""), "content": m.content} for m in messages])
    
    start_time = time.time()
    
    response_text = ""
    from langchain_core.callbacks.manager import adispatch_custom_event
    async for chunk in llm.astream(messages):
        content = getattr(chunk, "content", "")
        if content:
            response_text += content
            await adispatch_custom_event("llm_stream_chunk", content)
            
    response = AIMessage(content=response_text)
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
