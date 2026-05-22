from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

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
        graph.add_node("reason", self._reason)
        graph.add_node("safety", self._safety)
        graph.add_node("format", self._format)
        graph.add_node("persist", self._persist)
        graph.add_edge(START, "retrieve_context")
        graph.add_edge("retrieve_context", "build_context")
        graph.add_edge("build_context", "reason")
        graph.add_edge("reason", "safety")
        graph.add_edge("safety", "format")
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

    async def _reason(self, state: WorkflowState) -> dict[str, Any]:
        metadata = dict(state.get("metadata") or {})
        metadata.update(
            {
                "workflow_name": state.get("workflow_name"),
                "request_id": state.get("request_id"),
                "patient_id": state.get("patient_id"),
                "consultation_id": state.get("consultation_id"),
                "source": "patient_chat_workflow",
            }
        )

        async def operation() -> dict[str, Any]:
            return await ai_service.analyze_consultation_text(
                str(state.get("conversation_text") or state.get("query") or ""),
                language=str(state.get("language") or "en"),
                metadata=metadata,
                context_text=str(state.get("prompt_context") or "") or None,
            )

        ai_result = await run_step(state, "reason", operation, max_attempts=2, fallback={})
        return {"ai_result": ai_result or {}}

    async def _safety(self, state: WorkflowState) -> dict[str, Any]:
        fallback = dict(state.get("ai_result") or {})

        async def operation() -> dict[str, Any]:
            return medical_safety_service.guard_output(fallback, fallback=fallback, prompt_type="consultation")

        validated = await run_step(state, "safety", operation, max_attempts=1, fallback=fallback)
        return {"ai_result": validated, "warnings": list(validated.get("warnings") or [])}

    async def _format(self, state: WorkflowState) -> dict[str, Any]:
        ai_result = dict(state.get("ai_result") or {})

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

        content = "\n\n".join(
            part
            for part in [
                str(state.get("conversation_text") or state.get("query") or "").strip(),
                str(formatted.get("summary") or "").strip(),
            ]
            if part
        )

        async def operation() -> dict[str, Any]:
            return await rag_service.ingest_consultation_summary(
                patient_id=str(state.get("patient_id") or ""),
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


patient_chat_workflow = PatientChatWorkflow()
