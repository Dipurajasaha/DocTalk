from __future__ import annotations

import json
from typing import Any

from backend.core.database import prisma


class AssetIndexService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def create_index(self, data: dict[str, Any]) -> Any:
        # Prisma JSON serialization patch
        if "keywords" in data and isinstance(data["keywords"], list):
            data["keywords"] = json.dumps(data["keywords"])
            
        return await self.client.assetindex.create(data=data)

    async def update_index(self, asset_id: str, data: dict[str, Any]) -> Any:
        return await self.client.assetindex.update(
            where={"assetId": asset_id},
            data=data
        )

    async def delete_index(self, asset_id: str) -> Any:
        return await self.client.assetindex.delete(
            where={"assetId": asset_id}
        )

    async def get_index(self, asset_id: str) -> Any:
        return await self.client.assetindex.find_unique(
            where={"assetId": asset_id}
        )

    async def get_by_asset_id(self, asset_id: str) -> Any:
        return await self.get_index(asset_id)

    async def delete_by_asset_id(self, asset_id: str) -> Any:
        return await self.delete_index(asset_id)

    async def list_indexes(self, patient_id: str, limit: int = 10) -> list[Any]:
        return await self.client.assetindex.find_many(
            where={"patientId": patient_id},
            order={"createdAt": "desc"},
            take=limit
        )
