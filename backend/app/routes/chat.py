from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..schemas import ChatRequest
from ..services.ai.chat_service import AIChatService
from ..services.ai.chat_workflow_service import ChatWorkflowService
from ..services.ai.gemini_service import GeminiService
from ..services.ai.memory_service import MemoryService
from ..services.ai.summarizer import Summarizer


router = APIRouter()


def _require_patient(request: Request) -> str:
	session = dict(request.session)
	user = str(session.get("user") or "").strip()
	if not user or session.get("category") != "patient":
		raise HTTPException(status_code=401, detail="Unauthorized")
	return user


def _get_chat_workflow(request: Request) -> ChatWorkflowService:
	store = request.app.state.store
	data_root = str(getattr(store, "data_root", "data"))
	ai_service = AIChatService(data_root)
	memory_service = MemoryService(data_root)
	summarizer = Summarizer(data_root)
	gemini_service = GeminiService(data_root)
	return ChatWorkflowService(ai_service, memory_service, summarizer, gemini_service)


def _normalize_messages(payload: ChatRequest) -> list[dict[str, str]]:
	messages: list[dict[str, str]] = []
	if payload.messages:
		for message in payload.messages:
			messages.append({"role": message.role, "content": message.content})
	if payload.message:
		messages.append({"role": "user", "content": payload.message})
	return messages


@router.get("/chat_sessions")
async def chat_sessions(
	request: Request,
	chat_workflow: ChatWorkflowService = Depends(_get_chat_workflow),
):
	username = _require_patient(request)
	sessions = await chat_workflow.list_sessions(username)
	return JSONResponse({"success": True, "sessions": sessions})


@router.post("/chat")
async def chat(
	payload: ChatRequest,
	request: Request,
	chat_workflow: ChatWorkflowService = Depends(_get_chat_workflow),
):
	username = _require_patient(request)
	messages = _normalize_messages(payload)
	if not messages:
		return JSONResponse(
			{"success": False, "error": "No chat message provided", "language": payload.language or "en", "session_id": payload.session_id},
			status_code=400,
		)

	result = await chat_workflow.send_message(
		username=username,
		messages=messages,
		language=payload.language or "en",
		session_id=payload.session_id,
	)

	if result.get("success"):
		return JSONResponse(result)

	return JSONResponse(result, status_code=200)
