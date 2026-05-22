from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..services.medical_image_service import MedicalImageService
from ..services.rag_service import rag_service
from ..services.response_formatter import medical_response_formatter
from ..services.safety_service import medical_safety_service
from ..services.summary_service import medical_summary_service
from ..services.xray_analysis_service import xray_analysis_service
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


class XRayWorkflow:
	def __init__(self, medical_image_service: MedicalImageService | None = None) -> None:
		self.medical_image_service = medical_image_service or MedicalImageService()
		self._graph = self._build_graph().compile()

	async def run(
		self,
		*,
		requester_id: str,
		role: AuthRole,
		medical_image_id: str,
		language: str = "en",
		request_id: str | None = None,
	) -> WorkflowState:
		state = create_workflow_state(
			workflow_name="xray_workflow",
			request_id=request_id,
			patient_id="",
			role=role,  # type: ignore[arg-type]
			language=language,
			source_type="xray",
			metadata={"requester_id": requester_id, "medical_image_id": medical_image_id},
		)
		mark_status(state, "running")
		append_log(state, "workflow started", node="start")
		result = await self._graph.ainvoke(
			{
				**state,
				"requester_id": requester_id,
				"medical_image_id": medical_image_id,
			}
		)
		result_state: WorkflowState = result if isinstance(result, dict) else state
		if result_state.get("workflow_status") not in {"failed"}:
			mark_status(result_state, "completed")
		return result_state

	def _build_graph(self) -> StateGraph[WorkflowState]:
		graph: StateGraph[WorkflowState] = StateGraph(WorkflowState)
		graph.add_node("load_image", self._load_image)
		graph.add_node("analyze", self._analyze)
		graph.add_node("summarize", self._summarize)
		graph.add_node("safety", self._safety)
		graph.add_node("format", self._format)
		graph.add_node("persist", self._persist)
		graph.add_edge(START, "load_image")
		graph.add_edge("load_image", "analyze")
		graph.add_edge("analyze", "summarize")
		graph.add_edge("summarize", "safety")
		graph.add_edge("safety", "format")
		graph.add_edge("format", "persist")
		graph.add_edge("persist", END)
		return graph

	async def _load_image(self, state: WorkflowState) -> dict[str, Any]:
		requester_id = str(state.get("metadata", {}).get("requester_id") or "")
		medical_image_id = str(state.get("metadata", {}).get("medical_image_id") or "")
		role = state.get("role") or "patient"

		async def operation() -> dict[str, Any]:
			asset = await self.medical_image_service.get_asset(requester_id, role, medical_image_id)
			file_path, original_name, mime_type = await self.medical_image_service.get_asset_file_path(requester_id, role, medical_image_id)
			return {
				"patient_id": str(asset.get("patient_id") or ""),
				"consultation_id": asset.get("consultation_id"),
				"source_path": str(file_path),
				"original_name": original_name,
				"mime_type": mime_type,
				"asset": asset,
			}

		loaded = await run_step(state, "load_image", operation, max_attempts=2, fallback={})
		if loaded:
			state["patient_id"] = str(loaded.get("patient_id") or state.get("patient_id") or "")
			state["consultation_id"] = loaded.get("consultation_id")
		return dict(loaded or {})

	async def _analyze(self, state: WorkflowState) -> dict[str, Any]:
		path = str(state.get("source_path") or "")
		requester_id = str(state.get("metadata", {}).get("requester_id") or "")
		role = state.get("role") or "patient"

		async def operation() -> dict[str, Any]:
			return await xray_analysis_service.analyze_image(
				path,
				language=str(state.get("language") or "en"),
				requester_id=requester_id,
				role=role,
				patient_id=str(state.get("patient_id") or ""),
				consultation_id=state.get("consultation_id"),
			)

		analysis = await run_step(state, "analyze", operation, max_attempts=2, fallback={})
		return {"ai_result": analysis or {}}

	async def _summarize(self, state: WorkflowState) -> dict[str, Any]:
		analysis = dict(state.get("ai_result") or {})
		findings = list(analysis.get("findings") or [])
		recommendations = list(analysis.get("recommendations") or [])
		source_text = "\n".join(findings) if findings else str(analysis.get("summary") or "").strip()
		metadata = dict(state.get("metadata") or {})
		metadata.update(
			{
				"workflow_name": state.get("workflow_name"),
				"request_id": state.get("request_id"),
				"source": "xray_workflow",
				"medical_image_id": metadata.get("medical_image_id"),
			}
		)

		async def operation() -> Any:
			return await medical_summary_service.build_summary(
				"xray",
				source_text,
				summary=str(analysis.get("summary") or "").strip() or None,
				findings=findings,
				recommendations=recommendations,
				metadata=metadata,
			)

		summary_payload = await run_step(state, "summarize", operation, max_attempts=2, fallback=None)
		if summary_payload is None:
			return build_summary_payload(analysis)
		return {
			"summary_payload": {
				"source_type": summary_payload.source_type,
				"content": summary_payload.content,
				"summary": summary_payload.summary,
				"findings": list(summary_payload.findings),
				"recommendations": list(summary_payload.recommendations),
				"warnings": list(analysis.get("warnings") or []),
				"metadata": dict(summary_payload.metadata),
				"success": bool(analysis.get("success", True)),
			},
			"findings": list(summary_payload.findings),
			"recommendations": list(summary_payload.recommendations),
			"warnings": list(analysis.get("warnings") or []),
		}

	async def _safety(self, state: WorkflowState) -> dict[str, Any]:
		payload = dict(state.get("summary_payload") or {})

		async def operation() -> dict[str, Any]:
			return medical_safety_service.guard_output(
				{
					"success": bool(payload.get("success", True)),
					"summary": str(payload.get("summary") or "").strip(),
					"findings": list(payload.get("findings") or []),
					"recommendations": list(payload.get("recommendations") or []),
					"warnings": list(payload.get("warnings") or []),
					"metadata": dict(payload.get("metadata") or {}),
				},
				fallback=payload or {},
				prompt_type="xray",
			)

		validated = await run_step(state, "safety", operation, max_attempts=1, fallback=payload)
		return {
			"summary_payload": {
				**payload,
				**dict(validated or {}),
				"warnings": list((validated or {}).get("warnings") or payload.get("warnings") or []),
			}
		}

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

		summary_payload = dict(state.get("summary_payload") or {})

		async def operation() -> dict[str, Any]:
			return await rag_service.ingest_processing_result(
				patient_id=str(state.get("patient_id") or ""),
				consultation_id=state.get("consultation_id"),
				source_type="xray",
				content=str(summary_payload.get("content") or "").strip() or str(state.get("source_path") or ""),
				summary=str(formatted.get("summary") or summary_payload.get("summary") or "").strip(),
				findings=list(formatted.get("findings") or summary_payload.get("findings") or []),
				recommendations=list(formatted.get("recommendations") or summary_payload.get("recommendations") or []),
				metadata={
					**dict(state.get("metadata") or {}),
					"workflow_name": state.get("workflow_name"),
					"request_id": state.get("request_id"),
					"source": "xray_workflow",
				},
			)

		persistence_result = await run_step(state, "persist", operation, max_attempts=2, fallback={"skipped": True})
		return {"persistence_result": persistence_result}


xray_workflow = XRayWorkflow()

