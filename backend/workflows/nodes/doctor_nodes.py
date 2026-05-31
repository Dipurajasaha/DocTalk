from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..common import get_ollama_chat_model, latest_message_text, message_content_text
from ..state import UnifiedChatState


DOCTOR_SYSTEM_PROMPT = (
    "You are a highly technical clinical reasoning copilot. Use medical terminology, reason with precision, and "
    "focus on differential considerations, red-flag assessment, and next-step clinical thinking. Be concise but detailed. "
    "Retrieved context: {context_summary}"
)


async def doctor_copilot_llm(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    context_summary = str(
        payload.get("retrieved_context_text")
        or payload.get("context_text")
        or payload.get("prompt_frame")
        or "No additional patient context was retrieved."
    ).strip()
    latest_message = latest_message_text(state.get("messages"))
    if latest_message:
        payload.setdefault("latest_request", latest_message)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", DOCTOR_SYSTEM_PROMPT),
            MessagesPlaceholder("messages"),
        ]
    )
    response = await (prompt | get_ollama_chat_model()).ainvoke(
        {
            "messages": list(state.get("messages") or []),
            "context_summary": context_summary,
        }
    )
    response_text = message_content_text(response) or "Clinical reasoning guidance is unavailable at the moment."

    return {
        "messages": list(state.get("messages") or []) + [AIMessage(content=response_text)],
        "final_response": response_text,
        "context_payload": {
            **payload,
            "route": "doctor_copilot_llm",
            "assistant_mode": "clinical_reasoning_copilot",
        },
    }
