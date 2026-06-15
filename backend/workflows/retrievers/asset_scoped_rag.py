from typing import Any

from ...ai.vectorstore.pgvector_service import pgvector_service

async def retrieve_asset_scoped_context(
    query: str,
    asset_ids: list[str],
    patient_id: str
) -> dict[str, Any]:
    return await pgvector_service.search_documents_by_assets(
        patient_id=patient_id,
        query=query,
        asset_ids=asset_ids
    )
