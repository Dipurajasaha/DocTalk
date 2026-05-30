from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..copilot.patient_overview_service import patient_overview_service
from ..copilot.timeline_service import timeline_service
from .common import AuthRole, WorkflowState, append_log, create_workflow_state, mark_status, run_step


class DoctorCopilotWorkflow:
    def __init__(self) -> None:
        self._graph = self._build_graph().compile()

    async def run(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        consultation_id: str | None = None,
        query: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        state = create_workflow_state(
            workflow_name="doctor_copilot_workflow",
            request_id=request_id,
            patient_id=patient_id,
            role=role,
            consultation_id=consultation_id,
            query=str(query or "doctor copilot overview"),
            source_type="consultation",
            metadata={"requester_id": requester_id, "source": "doctor_copilot"},
        )
        mark_status(state, "running")
        append_log(state, "workflow started", node="start")

        result = await self._graph.ainvoke(state)
        result_state: WorkflowState = result if isinstance(result, dict) else state
        if result_state.get("workflow_status") in {"queued", "running", None}:
            mark_status(result_state, "completed")
        payload = dict(result_state.get("copilot_payload") or {})
        payload.setdefault("patient_summary", {"text": "", "evidence": []})
        payload.setdefault("recent_consultations", [])
        payload.setdefault("recurring_symptoms", {})
        payload.setdefault("medication_history", {})
        payload.setdefault("recent_reports", [])
        payload.setdefault("key_findings", [])
        payload.setdefault("timeline", {})
        payload.setdefault("risk_highlights", {})
        payload.setdefault("explainability", {"source_summaries": [], "retrieved_evidence": []})
        payload.setdefault("warnings", ["Doctor copilot output is informational support only."])
        payload.setdefault("metadata", {})
        workflow_status = result_state.get("workflow_status")
        if not str(payload.get("patient_summary", {}).get("text") or "").strip() and workflow_status == "completed":
            workflow_status = "partial"
        payload["metadata"]["workflow_status"] = workflow_status
        payload["metadata"]["workflow_logs"] = list(result_state.get("workflow_logs") or [])[-25:]
        payload["metadata"]["workflow_timings"] = dict(result_state.get("node_timings") or {})
        payload["metadata"]["workflow_retries"] = dict(result_state.get("retry_counts") or {})
        payload["metadata"]["workflow_errors"] = list(result_state.get("errors") or [])
        return payload

    def _build_graph(self) -> StateGraph[WorkflowState]:
        graph: StateGraph[WorkflowState] = StateGraph(WorkflowState)
        graph.add_node("overview", self._overview)
        graph.add_node("timeline_refresh", self._timeline_refresh)
        graph.add_edge(START, "overview")
        graph.add_edge("overview", "timeline_refresh")
        graph.add_edge("timeline_refresh", END)
        return graph

    async def _overview(self, state: WorkflowState) -> dict[str, Any]:
        async def operation() -> dict[str, Any]:
            return await patient_overview_service.generate_overview(
                requester_id=str(state.get("metadata", {}).get("requester_id") or ""),
                role=str(state.get("role") or "doctor"),
                patient_id=str(state.get("patient_id") or ""),
                consultation_id=state.get("consultation_id"),
                query=str(state.get("query") or "doctor copilot overview"),
            )

        payload = await run_step(state, "overview", operation, max_attempts=1, fallback={})
        return {"copilot_payload": payload}

    async def _timeline_refresh(self, state: WorkflowState) -> dict[str, Any]:
        async def operation() -> dict[str, Any]:
            return await timeline_service.build_timeline(
                requester_id=str(state.get("metadata", {}).get("requester_id") or ""),
                role=str(state.get("role") or "doctor"),
                patient_id=str(state.get("patient_id") or ""),
                consultation_id=state.get("consultation_id"),
                limit=60,
            )

        refreshed = await run_step(state, "timeline_refresh", operation, max_attempts=1, fallback={})
        payload = dict(state.get("copilot_payload") or {})
        if refreshed:
            payload["timeline"] = refreshed
        return {"copilot_payload": payload}


doctor_copilot_workflow = DoctorCopilotWorkflow()
