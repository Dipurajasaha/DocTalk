from __future__ import annotations

from typing import Any, Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from backend.ai.vectorstore.pgvector_service import pgvector_service
from ...graph.state import UnifiedChatState


def _normalized_scope_id(value: str | None) -> str:
    return str(value or "").strip()


@tool("patient_rag_tool")
async def patient_rag_tool(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.30,
    state: Annotated[UnifiedChatState, InjectedState] | None = None,
) -> dict[str, Any]:
    """Retrieve patient-scoped RAG context for the authenticated user only."""
    user_id = _normalized_scope_id((state or {}).get("user_id"))
    if not user_id:
        return {
            "scope": "patient",
            "items": [],
            "top_k": max(1, min(int(top_k), 20)),
            "similarity_threshold": max(0.0, min(float(similarity_threshold), 1.0)),
            "fallback_used": False,
        }

    rag_scope = (state or {}).get("rag_scope") or {}
    print("[DEBUG][RAG_INPUT]", {"query": query, "rag_scope": rag_scope})
    asset_ids = rag_scope.get("asset_ids")
    
    if asset_ids:
        result = await pgvector_service.search_documents_by_assets(
            patient_id=user_id,
            metadata_user_id=user_id,
            query=query,
            asset_ids=asset_ids,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )
    else:
        result = await pgvector_service.search_documents(
            patient_id=user_id,
            metadata_user_id=user_id,
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )
        
    return {
        "scope": "patient",
        "user_id": user_id,
        "asset_scoped": bool(asset_ids),
        **result,
    }


@tool("doctor_rag_tool")
async def doctor_rag_tool(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.30,
    state: Annotated[UnifiedChatState, InjectedState] | None = None,
) -> dict[str, Any]:
    """Retrieve doctor-scoped RAG context for the selected target patient only."""
    target_patient_id = _normalized_scope_id((state or {}).get("target_patient_id"))
    if not target_patient_id:
        return {
            "scope": "doctor",
            "items": [],
            "top_k": max(1, min(int(top_k), 20)),
            "similarity_threshold": max(0.0, min(float(similarity_threshold), 1.0)),
            "fallback_used": False,
            "target_patient_id": None,
            "skipped": True,
        }

    rag_scope = (state or {}).get("rag_scope") or {}
    print("[DEBUG][RAG_INPUT]", {"query": query, "rag_scope": rag_scope})
    asset_ids = rag_scope.get("asset_ids")

    if asset_ids:
        result = await pgvector_service.search_documents_by_assets(
            patient_id=target_patient_id,
            metadata_user_id=target_patient_id,
            query=query,
            asset_ids=asset_ids,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )
    else:
        result = await pgvector_service.search_documents(
            patient_id=target_patient_id,
            metadata_user_id=target_patient_id,
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )
        
    return {
        "scope": "doctor",
        "target_patient_id": target_patient_id,
        "asset_scoped": bool(asset_ids),
        **result,
    }
