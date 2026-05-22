from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Awaitable, Callable, Literal, TypedDict
from uuid import uuid4

from ..core.logger import get_logger


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]
WorkflowStatus = Literal["queued", "running", "partial", "completed", "failed"]


class WorkflowState(TypedDict, total=False):
    request_id: str
    workflow_name: str
    workflow_status: WorkflowStatus
    role: AuthRole
    patient_id: str
    consultation_id: str | None
    language: str
    query: str
    source_type: str
    source_path: str
    extracted_text: str
    retrieved_context: dict[str, Any] | None
    retrieved_context_text: str
    prompt_context: str
    ai_result: dict[str, Any] | None
    triage_result: dict[str, Any] | None
    doctor_briefing: dict[str, Any] | None
    agent_summary: dict[str, Any] | None
    summary_payload: dict[str, Any] | None
    formatted_result: dict[str, Any] | None
    persistence_result: dict[str, Any] | None
    findings: list[str]
    recommendations: list[str]
    warnings: list[str]
    errors: list[str]
    workflow_logs: list[str]
    node_timings: dict[str, float]
    retry_counts: dict[str, int]
    metadata: dict[str, Any]


def create_workflow_state(
    *,
    workflow_name: str,
    patient_id: str,
    role: AuthRole | None = None,
    consultation_id: str | None = None,
    language: str = "en",
    query: str = "",
    source_type: str = "consultation",
    source_path: str = "",
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> WorkflowState:
    return WorkflowState(
        request_id=str(request_id or uuid4()),
        workflow_name=workflow_name,
        workflow_status="queued",
        role=role,
        patient_id=str(patient_id or "").strip(),
        consultation_id=consultation_id,
        language=language,
        query=str(query or "").strip(),
        source_type=source_type,
        source_path=str(source_path or "").strip(),
        extracted_text="",
        retrieved_context=None,
        retrieved_context_text="",
        prompt_context="",
        ai_result=None,
        triage_result=None,
        doctor_briefing=None,
        agent_summary=None,
        summary_payload=None,
        formatted_result=None,
        persistence_result=None,
        findings=[],
        recommendations=[],
        warnings=[],
        errors=[],
        workflow_logs=[],
        node_timings={},
        retry_counts={},
        metadata=dict(metadata or {}),
    )


def context_bundle_to_payload(bundle: Any) -> dict[str, Any]:
    if bundle is None:
        return {}
    if hasattr(bundle, "to_metadata"):
        payload = asdict(bundle)
        payload["retrieved_source_ids"] = list(getattr(bundle, "retrieved_source_ids", []))
        payload["retrieval_scores"] = list(getattr(bundle, "retrieval_scores", []))
        return payload
    if hasattr(bundle, "model_dump"):
        return dict(bundle.model_dump())
    if isinstance(bundle, dict):
        return dict(bundle)
    return {"value": bundle}


def append_log(state: WorkflowState, message: str, *, level: str = "info", node: str | None = None) -> None:
    entry = f"{datetime.now(timezone.utc).isoformat()} | {level.upper()} | {node or state.get('workflow_name')} | {message}"
    state.setdefault("workflow_logs", []).append(entry)
    log_payload = {
        "component": "workflow",
        "request_id": state.get("request_id"),
        "workflow_name": state.get("workflow_name"),
    }
    if node:
        log_payload["node"] = node
    logger.info(message, extra=log_payload)


def append_error(state: WorkflowState, message: str, *, node: str | None = None) -> None:
    state.setdefault("errors", []).append(f"{node or state.get('workflow_name')}: {message}")
    append_log(state, message, level="error", node=node)


def mark_status(state: WorkflowState, status: WorkflowStatus) -> None:
    state["workflow_status"] = status


async def run_step(
    state: WorkflowState,
    node_name: str,
    operation: Callable[[], Awaitable[Any]],
    *,
    max_attempts: int = 2,
    fallback: Any = None,
) -> Any:
    attempts = max(1, int(max_attempts))
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        started_at = perf_counter()
        append_log(state, f"starting attempt {attempt}", node=node_name)
        try:
            result = await operation()
            duration = round(perf_counter() - started_at, 4)
            state.setdefault("node_timings", {})[node_name] = duration
            state.setdefault("retry_counts", {})[node_name] = attempt - 1
            append_log(state, f"completed in {duration:.4f}s", node=node_name)
            return result
        except Exception as exc:
            last_error = exc
            duration = round(perf_counter() - started_at, 4)
            state.setdefault("node_timings", {})[node_name] = duration
            state.setdefault("retry_counts", {})[node_name] = attempt - 1
            append_log(state, f"attempt {attempt} failed after {duration:.4f}s: {exc}", level="warning", node=node_name)
            if attempt < attempts:
                continue

    if last_error is not None:
        append_error(state, str(last_error), node=node_name)
        if fallback is not None:
            mark_status(state, "partial")
            return fallback
        mark_status(state, "failed")
    return fallback


def build_retrieval_result(bundle: Any) -> dict[str, Any]:
    payload = context_bundle_to_payload(bundle)
    return {
        "retrieved_context": payload,
        "retrieved_context_text": str(payload.get("context_text") or "").strip(),
        "prompt_context": str(payload.get("context_text") or "").strip(),
    }


def build_summary_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary_payload": dict(result),
        "extracted_text": str(result.get("extracted_text") or result.get("content") or "").strip(),
        "findings": list(result.get("findings") or []),
        "recommendations": list(result.get("recommendations") or []),
        "warnings": list(result.get("warnings") or []),
    }


def build_formatted_output(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "formatted_result": dict(result),
        "summary": str(result.get("summary") or "").strip(),
        "findings": list(result.get("findings") or []),
        "recommendations": list(result.get("recommendations") or []),
        "warnings": list(result.get("warnings") or []),
    }
