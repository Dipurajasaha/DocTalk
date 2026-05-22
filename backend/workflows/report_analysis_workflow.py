from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..services.ai_service import ai_service
from ..services.ocr_service import ocr_service
from ..services.rag_service import rag_service
from ..services.report_service import ReportService
from ..services.response_formatter import medical_response_formatter
from ..services.safety_service import medical_safety_service
from .common import (
    AuthRole,
    WorkflowState,
    append_log,
    build_formatted_output,
    build_summary_payload,
    create_workflow_state,
    mark_status,
    run_step,
)


class ReportAnalysisWorkflow:
    def __init__(self, report_service: ReportService | None = None) -> None:
        self.report_service = report_service or ReportService()
        self._graph = self._build_graph().compile()

    async def run(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        report_id: str,
        language: str = "en",
        request_id: str | None = None,
    ) -> WorkflowState:
        state = create_workflow_state(
            workflow_name="report_analysis_workflow",
            request_id=request_id,
            patient_id="",
            role=role,  # type: ignore[arg-type]
            language=language,
            source_type="ocr",
            metadata={"requester_id": requester_id, "report_id": report_id},
        )
        mark_status(state, "running")
        append_log(state, "workflow started", node="start")
        result = await self._graph.ainvoke(
            {
                **state,
                "requester_id": requester_id,
                "report_id": report_id,
            }
        )
        result_state: WorkflowState = result if isinstance(result, dict) else state
        if result_state.get("workflow_status") not in {"failed"}:
            mark_status(result_state, "completed")
        return result_state

    def _build_graph(self) -> StateGraph[WorkflowState]:
        graph: StateGraph[WorkflowState] = StateGraph(WorkflowState)
        graph.add_node("load_report", self._load_report)
        graph.add_node("extract_text", self._extract_text)
        graph.add_node("summarize", self._summarize)
        graph.add_node("safety", self._safety)
        graph.add_node("format", self._format)
        graph.add_node("persist", self._persist)
        graph.add_edge(START, "load_report")
        graph.add_edge("load_report", "extract_text")
        graph.add_edge("extract_text", "summarize")
        graph.add_edge("summarize", "safety")
        graph.add_edge("safety", "format")
        graph.add_edge("format", "persist")
        graph.add_edge("persist", END)
        return graph

    async def _load_report(self, state: WorkflowState) -> dict[str, Any]:
        requester_id = str(state.get("metadata", {}).get("requester_id") or "")
        report_id = str(state.get("metadata", {}).get("report_id") or "")
        role = state.get("role") or "patient"

        async def operation() -> dict[str, Any]:
            asset = await self.report_service.get_asset(requester_id, role, report_id)
            file_path, original_name, mime_type = await self.report_service.get_asset_file_path(requester_id, role, report_id)
            return {
                "patient_id": str(asset.get("patient_id") or ""),
                "consultation_id": asset.get("consultation_id"),
                "source_path": str(file_path),
                "original_name": original_name,
                "mime_type": mime_type,
                "asset": asset,
            }

        loaded = await run_step(state, "load_report", operation, max_attempts=2, fallback={})
        if loaded:
            state["patient_id"] = str(loaded.get("patient_id") or state.get("patient_id") or "")
            state["consultation_id"] = loaded.get("consultation_id")
        return dict(loaded or {})

    async def _extract_text(self, state: WorkflowState) -> dict[str, Any]:
        path = str(state.get("source_path") or "")
        mime_type = str(state.get("mime_type") or "")
        requester_id = str(state.get("metadata", {}).get("requester_id") or "")
        role = state.get("role") or "patient"

        async def operation() -> dict[str, Any]:
            return await ocr_service.extract_text_from_file(
                path,
                mime_type=mime_type or None,
                language=str(state.get("language") or "en"),
                requester_id=requester_id,
                role=role,
                patient_id=str(state.get("patient_id") or ""),
                consultation_id=state.get("consultation_id"),
            )

        extracted = await run_step(state, "extract_text", operation, max_attempts=2, fallback={"success": False, "extracted_text": "", "warnings": ["OCR unavailable"]})
        return {
            "extracted_text": str(extracted.get("extracted_text") or "").strip(),
            "warnings": list(extracted.get("warnings") or []),
        }

    async def _summarize(self, state: WorkflowState) -> dict[str, Any]:
        extracted_text = str(state.get("extracted_text") or "").strip()
        metadata = dict(state.get("metadata") or {})
        metadata.update(
            {
                "workflow_name": state.get("workflow_name"),
                "request_id": state.get("request_id"),
                "source": "report_analysis_workflow",
                "report_id": metadata.get("report_id"),
            }
        )

        async def operation() -> dict[str, Any]:
            return await ai_service.summarize_medical_text(
                extracted_text,
                language=str(state.get("language") or "en"),
                metadata=metadata,
            )

        summary = await run_step(state, "summarize", operation, max_attempts=2, fallback={})
        return build_summary_payload(summary or {})

    async def _safety(self, state: WorkflowState) -> dict[str, Any]:
        fallback = dict(state.get("summary_payload") or {})
        summary_text = str(fallback.get("summary") or "").strip()

        async def operation() -> dict[str, Any]:
            validated = medical_safety_service.guard_output(
                {
                    "success": bool(fallback.get("success", True)),
                    "summary": summary_text,
                    "findings": list(fallback.get("findings") or []),
                    "recommendations": list(fallback.get("recommendations") or []),
                    "warnings": list(fallback.get("warnings") or []),
                    "metadata": dict(fallback.get("metadata") or {}),
                },
                fallback={
                    "success": bool(fallback.get("success", False)),
                    "summary": summary_text,
                    "findings": list(fallback.get("findings") or []),
                    "recommendations": list(fallback.get("recommendations") or []),
                    "warnings": list(fallback.get("warnings") or []),
                    "metadata": dict(fallback.get("metadata") or {}),
                },
                prompt_type="summary",
            )
            return validated

        validated = await run_step(state, "safety", operation, max_attempts=1, fallback=fallback)
        return build_summary_payload(validated or fallback)

    async def _format(self, state: WorkflowState) -> dict[str, Any]:
        payload = dict(state.get("summary_payload") or {})

        async def operation() -> dict[str, Any]:
            return medical_response_formatter.format_output(
                success=bool(payload.get("success", True)),
                summary=str(payload.get("summary") or "").strip(),
                findings=list(payload.get("findings") or []),
                recommendations=list(payload.get("recommendations") or []),
                warnings=list(payload.get("warnings") or []),
                metadata=dict(payload.get("metadata") or {}),
            )

        formatted = await run_step(state, "format", operation, max_attempts=1, fallback={})
        return build_formatted_output(formatted or {})

    async def _persist(self, state: WorkflowState) -> dict[str, Any]:
        formatted = dict(state.get("formatted_result") or {})
        if not formatted:
            return {"persistence_result": {"skipped": True}}

        async def operation() -> dict[str, Any]:
            return await rag_service.ingest_processing_result(
                patient_id=str(state.get("patient_id") or ""),
                consultation_id=state.get("consultation_id"),
                source_type="ocr",
                content=str(state.get("extracted_text") or "").strip(),
                summary=str(formatted.get("summary") or "").strip(),
                findings=list(formatted.get("findings") or []),
                recommendations=list(formatted.get("recommendations") or []),
                metadata={
                    **dict(state.get("metadata") or {}),
                    "workflow_name": state.get("workflow_name"),
                    "request_id": state.get("request_id"),
                    "source": "report_analysis_workflow",
                },
            )

        persistence_result = await run_step(state, "persist", operation, max_attempts=2, fallback={"skipped": True})
        return {"persistence_result": persistence_result}


report_analysis_workflow = ReportAnalysisWorkflow()
