from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from langgraph.graph import END, START, StateGraph

from ..core.database import prisma
from .nodes.doctor_nodes import doctor_answer, retrieve_doctor_context
from .nodes.patient_nodes import patient_answer, patient_general_response, patient_safety_guardrail, retrieve_patient_context, triage_patient_message
from .nodes.routing import classify_intent
from .state import UnifiedChatState


def _flatten_reply(reply: Any) -> str:
    if isinstance(reply, str):
        return reply.strip()
    if not isinstance(reply, dict):
        return str(reply or "").strip()

    parts: list[str] = []
    summary = str(reply.get("summary") or reply.get("patient_summary") or "").strip()
    if summary:
        parts.append(summary)
    for label, key in (
        ("Key Findings", "key_findings"),
        ("Observations", "observations"),
        ("Risks", "risks"),
        ("Recommendations", "recommendations"),
        ("Notes", "notes"),
    ):
        values = reply.get(key) or []
        if isinstance(values, list) and values:
            text = ", ".join(str(item).strip() for item in values if str(item).strip())
            if text:
                parts.append(f"{label}: {text}")
        elif isinstance(values, str) and values.strip():
            parts.append(f"{label}: {values.strip()}")
    if not parts:
        parts.append(str(reply))
    return "\n\n".join(parts).strip()


async def state_persister(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    consultation_id = str(state.get("consultation_id") or payload.get("consultation_id") or "").strip()
    messages = list(state.get("messages") or [])
    reply = dict(payload.get("reply") or {})
    assistant_text = _flatten_reply(reply)
    if not consultation_id or not assistant_text:
        return {"context_payload": {**payload, "persisted_message": {"skipped": True}}}

    consultation = await prisma.consultation.find_unique(where={"id": consultation_id})
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")

    persisted_at = datetime.now(timezone.utc)
    saved_message = await prisma.message.create(
        data={
            "consultationId": consultation_id,
            "senderId": "doctalk-ai",
            "senderRole": "doctor",
            "message": assistant_text,
            "timestamp": persisted_at,
        }
    )
    await prisma.consultation.update(
        where={"id": consultation_id},
        data={"lastMessageAt": persisted_at},
    )

    if messages:
        last_message = dict(messages[-1])
        last_message.update(
            {
                "id": str(getattr(saved_message, "id", "") or ""),
                "sender_role": "doctor",
                "sender_id": "doctalk-ai",
                "message": assistant_text,
                "timestamp": persisted_at,
                "persisted": True,
            }
        )
        messages[-1] = last_message

    return {
        "messages": messages,
        "context_payload": {
            **payload,
            "persisted_message": {
                "id": str(getattr(saved_message, "id", "") or ""),
                "consultation_id": consultation_id,
                "sender_id": "doctalk-ai",
                "sender_role": "doctor",
                "message": assistant_text,
                "timestamp": persisted_at.isoformat(),
            },
        },
    }


class UnifiedChatGraph:
    def __init__(self) -> None:
        self._graph = self._build_graph().compile()

    def _build_graph(self) -> StateGraph[UnifiedChatState]:
        graph: StateGraph[UnifiedChatState] = StateGraph(UnifiedChatState)
        graph.add_node("patient_general", patient_general_response)
        graph.add_node("patient_retrieve", retrieve_patient_context)
        graph.add_node("patient_triage", triage_patient_message)
        graph.add_node("patient_safety", patient_safety_guardrail)
        graph.add_node("patient_answer", patient_answer)
        graph.add_node("doctor_retrieve", retrieve_doctor_context)
        graph.add_node("doctor_answer", doctor_answer)
        graph.add_node("state_persister", state_persister)

        graph.add_conditional_edges(
            START,
            classify_intent,
            {
                "patient_general": "patient_general",
                "patient_rag": "patient_retrieve",
                "doctor_rag": "doctor_retrieve",
                "emergency": "patient_retrieve",
            },
        )
        graph.add_edge("patient_general", "state_persister")
        graph.add_edge("patient_retrieve", "patient_triage")
        graph.add_edge("patient_triage", "patient_safety")
        graph.add_edge("patient_safety", "patient_answer")
        graph.add_edge("patient_answer", "state_persister")
        graph.add_edge("doctor_retrieve", "doctor_answer")
        graph.add_edge("doctor_answer", "state_persister")
        graph.add_edge("state_persister", END)
        return graph

    async def ainvoke(self, state: UnifiedChatState) -> dict[str, Any]:
        result = await self._graph.ainvoke(state)
        return result if isinstance(result, dict) else dict(state)


unified_chat_graph = UnifiedChatGraph()
