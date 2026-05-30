from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..agents import doctor_assistant_agent, summarizer_agent, triage_agent
from ..services.ai_service import ai_service
from ..services.context_builder_service import context_builder_service
from ..services.rag_service import rag_service
from ..services.response_formatter import medical_response_formatter
from ..services.safety_service import medical_safety_service
from .common import (
    AuthRole,
    WorkflowState,
    append_log,
    build_formatted_output,
    build_retrieval_result,
    create_workflow_state,
    mark_status,
    run_step,
)


class PatientChatWorkflow:
    def __init__(self) -> None:
        self._graph = self._build_graph().compile()

    async def run(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        conversation_text: str,
        language: str = "en",
        consultation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> WorkflowState:
        state = create_workflow_state(
            workflow_name="patient_chat_workflow",
            request_id=request_id,
            patient_id=patient_id,
            role=role,
            consultation_id=consultation_id,
            language=language,
            query=conversation_text,
            source_type="consultation",
            metadata=metadata,
        )
        state["metadata"]["requester_id"] = requester_id
        mark_status(state, "running")
        append_log(state, "workflow started", node="start")

        result = await self._graph.ainvoke(
            {
                **state,
                "requester_id": requester_id,
                "conversation_text": conversation_text,
            }
        )
        result_state: WorkflowState = result if isinstance(result, dict) else state
        if result_state.get("workflow_status") not in {"failed"}:
            mark_status(result_state, "completed")
        return result_state

    def _build_graph(self) -> StateGraph[WorkflowState]:
        graph: StateGraph[WorkflowState] = StateGraph(WorkflowState)
        graph.add_node("retrieve_context", self._retrieve_context)
        graph.add_node("build_context", self._build_context)
        graph.add_node("triage", self._triage)
        graph.add_node("doctor_assistant", self._doctor_assistant)
        graph.add_node("reason", self._reason)
        graph.add_node("safety", self._safety)
        graph.add_node("summarize", self._summarize)
        graph.add_node("format", self._format)
        graph.add_node("persist", self._persist)
        graph.add_edge(START, "retrieve_context")
        graph.add_edge("retrieve_context", "build_context")
        graph.add_edge("build_context", "triage")
        graph.add_edge("triage", "doctor_assistant")
        graph.add_edge("doctor_assistant", "reason")
        graph.add_edge("reason", "safety")
        graph.add_edge("safety", "summarize")
        graph.add_edge("summarize", "format")
        graph.add_edge("format", "persist")
        graph.add_edge("persist", END)
        return graph

    async def _retrieve_context(self, state: WorkflowState) -> dict[str, Any]:
        async def operation() -> Any:
            return await context_builder_service.build_context(
                requester_id=str(state.get("metadata", {}).get("requester_id") or state.get("patient_id") or ""),
                role=state.get("role") or "patient",
                patient_id=str(state.get("patient_id") or ""),
                query=str(state.get("query") or state.get("conversation_text") or ""),
                consultation_id=state.get("consultation_id"),
                focus="consultation",
            )

        bundle = await run_step(state, "retrieve_context", operation, max_attempts=2, fallback=None)
        return build_retrieval_result(bundle)

    async def _build_context(self, state: WorkflowState) -> dict[str, Any]:
        async def operation() -> str:
            return str(state.get("retrieved_context_text") or "").strip()

        prompt_context = await run_step(state, "build_context", operation, max_attempts=1, fallback="")
        return {"prompt_context": prompt_context}

    async def _triage(self, state: WorkflowState) -> dict[str, Any]:
        async def operation() -> dict[str, Any]:
            return await triage_agent.assess(
                str(state.get("conversation_text") or state.get("query") or ""),
                context_text=str(state.get("prompt_context") or "") or None,
                metadata={
                    **dict(state.get("metadata") or {}),
                    "workflow_name": state.get("workflow_name"),
                    "request_id": state.get("request_id"),
                    "source": "patient_chat_workflow",
                },
            )

        triage_result = await run_step(state, "triage", operation, max_attempts=1, fallback={})
        warnings = list(triage_result.get("warnings") or [])
        return {"triage_result": triage_result or {}, "warnings": warnings}

    async def _doctor_assistant(self, state: WorkflowState) -> dict[str, Any]:
        if str(state.get("role") or "patient") != "doctor":
            return {}

        async def operation() -> dict[str, Any]:
            return await doctor_assistant_agent.build_overview(
                requester_id=str(state.get("metadata", {}).get("requester_id") or state.get("patient_id") or ""),
                role=str(state.get("role") or "doctor"),
                patient_id=str(state.get("patient_id") or ""),
                query=str(state.get("conversation_text") or state.get("query") or ""),
                consultation_id=state.get("consultation_id"),
                context_text=str(state.get("prompt_context") or "") or None,
                metadata={
                    **dict(state.get("metadata") or {}),
                    "workflow_name": state.get("workflow_name"),
                    "request_id": state.get("request_id"),
                    "source": "patient_chat_workflow",
                },
            )

        doctor_briefing = await run_step(state, "doctor_assistant", operation, max_attempts=1, fallback={})
        return {"doctor_briefing": doctor_briefing or {}}

    async def _reason(self, state: WorkflowState) -> dict[str, Any]:
        metadata = dict(state.get("metadata") or {})
        triage_result = dict(state.get("triage_result") or {})
        doctor_briefing = dict(state.get("doctor_briefing") or {})
        context_parts = [str(state.get("prompt_context") or "").strip()]
        if triage_result.get("triage_note"):
            context_parts.append(f"Triage: {triage_result.get('triage_note')}")
        if doctor_briefing.get("doctor_briefing_text"):
            context_parts.append(str(doctor_briefing.get("doctor_briefing_text") or "").strip())
        metadata.update(
            {
                "workflow_name": state.get("workflow_name"),
                "request_id": state.get("request_id"),
                "patient_id": state.get("patient_id"),
                "consultation_id": state.get("consultation_id"),
                "triage_result": triage_result,
                "doctor_briefing": doctor_briefing,
                "source": "patient_chat_workflow",
            }
        )

        async def operation() -> dict[str, Any]:
            return await ai_service.analyze_consultation_text(
                str(state.get("conversation_text") or state.get("query") or ""),
                language=str(state.get("language") or "en"),
                metadata=metadata,
                context_text="\n\n".join(part for part in context_parts if part).strip() or None,
            )

        ai_result = await run_step(state, "reason", operation, max_attempts=2, fallback={})
        return {"ai_result": ai_result or {}}

    async def _safety(self, state: WorkflowState) -> dict[str, Any]:
        fallback = dict(state.get("ai_result") or {})

        async def operation() -> dict[str, Any]:
            return medical_safety_service.guard_output(fallback, fallback=fallback, prompt_type="consultation")

        validated = await run_step(state, "safety", operation, max_attempts=1, fallback=fallback)
        warnings = list(state.get("warnings") or [])
        warnings.extend(list(validated.get("warnings") or []))
        return {"ai_result": validated, "warnings": self._unique_items(warnings)}

    async def _summarize(self, state: WorkflowState) -> dict[str, Any]:
        ai_result = dict(state.get("ai_result") or {})

        async def operation() -> dict[str, Any]:
            return await summarizer_agent.summarize_consultation(
                content=str(state.get("conversation_text") or state.get("query") or ""),
                summary=str(ai_result.get("summary") or "").strip() or None,
                findings=list(ai_result.get("findings") or []),
                recommendations=list(ai_result.get("recommendations") or []),
                metadata={
                    **dict(state.get("metadata") or {}),
                    "workflow_name": state.get("workflow_name"),
                    "request_id": state.get("request_id"),
                    "patient_id": state.get("patient_id"),
                    "consultation_id": state.get("consultation_id"),
                    "source": "patient_chat_workflow",
                },
                context_text=str(state.get("prompt_context") or "") or None,
            )

        agent_summary = await run_step(state, "summarize", operation, max_attempts=1, fallback={})
        warnings = list(state.get("warnings") or [])
        warnings.extend(list(agent_summary.get("warnings") or []))
        return {"agent_summary": agent_summary or {}, "warnings": warnings}

    async def _format(self, state: WorkflowState) -> dict[str, Any]:
        ai_result = dict(state.get("agent_summary") or state.get("ai_result") or {})

        async def operation() -> dict[str, Any]:
            return medical_response_formatter.format_output(
                success=bool(ai_result.get("success", False)),
                summary=str(ai_result.get("summary") or "").strip(),
                findings=list(ai_result.get("findings") or []),
                recommendations=list(ai_result.get("recommendations") or []),
                warnings=list(ai_result.get("warnings") or []),
                metadata=dict(ai_result.get("metadata") or {}),
            )

        formatted = await run_step(state, "format", operation, max_attempts=1, fallback={})
        return build_formatted_output(formatted or {})

    async def _persist(self, state: WorkflowState) -> dict[str, Any]:
        formatted = dict(state.get("formatted_result") or {})
        if not formatted:
            return {"persistence_result": {"skipped": True}}

        patient_id = str(state.get("patient_id") or "").strip()
        requester_id = str(state.get("metadata", {}).get("requester_id") or "").strip()
        if not patient_id or not requester_id:
            append_log(state, "missing ownership metadata; stopping persistence", level="error", node="persist")
            mark_status(state, "failed")
            return {"workflow_status": "failed", "persistence_result": {"skipped": True, "reason": "missing_ownership"}}

        content = "\n\n".join(
            part
            for part in [
                str(state.get("conversation_text") or state.get("query") or "").strip(),
                str(dict(state.get("agent_summary") or {}).get("content") or formatted.get("summary") or "").strip(),
            ]
            if part
        )

        async def operation() -> dict[str, Any]:
            return await rag_service.ingest_consultation_summary(
                patient_id=patient_id,
                consultation_id=state.get("consultation_id") or "",
                content=content,
                summary=str(formatted.get("summary") or "").strip(),
                metadata={
                    **dict(state.get("metadata") or {}),
                    "workflow_name": state.get("workflow_name"),
                    "request_id": state.get("request_id"),
                    "source": "patient_chat_workflow",
                },
            )

        if not state.get("consultation_id"):
            return {"persistence_result": {"skipped": True, "reason": "missing consultation_id"}}

        persistence_result = await run_step(state, "persist", operation, max_attempts=2, fallback={"skipped": True})
        return {"persistence_result": persistence_result}

    @staticmethod
    def _unique_items(items: list[str]) -> list[str]:
        unique: list[str] = []
        for item in items:
            value = str(item or "").strip()
            if value and value not in unique:
                unique.append(value)
        return unique


patient_chat_workflow = PatientChatWorkflow()
