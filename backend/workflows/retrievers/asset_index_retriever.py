from __future__ import annotations

from typing import Any

from backend.core.database import prisma


async def get_latest_document(patient_id: str) -> dict[str, Any] | None:
    docs = await prisma.assetindex.find_many(
        where={"patientId": patient_id},
        order={"documentDate": "desc"},
        take=1
    )
    if not docs:
        return None
    return dict(docs[0])


async def get_documents_by_type(patient_id: str, doc_type: str, limit: int = 5) -> list[dict[str, Any]]:
    docs = await prisma.assetindex.find_many(
        where={
            "patientId": patient_id,
            "documentType": doc_type
        },
        order={"documentDate": "desc"},
        take=limit
    )
    return [dict(d) for d in docs]


async def get_recent_documents(patient_id: str, limit: int = 5) -> list[dict[str, Any]]:
    docs = await prisma.assetindex.find_many(
        where={"patientId": patient_id},
        order={"documentDate": "desc"},
        take=limit
    )
    return [dict(d) for d in docs]


async def get_document_by_asset_id(asset_id: str) -> dict[str, Any] | None:
    doc = await prisma.assetindex.find_unique(
        where={"assetId": asset_id}
    )
    if not doc:
        return None
    return dict(doc)


async def get_reports_by_report_type(patient_id: str, report_type: str, limit: int = 5) -> list[dict[str, Any]]:
    docs = await prisma.assetindex.find_many(
        where={
            "patientId": patient_id,
            "reportType": report_type
        },
        order={"documentDate": "desc"},
        take=limit
    )
    return [dict(d) for d in docs]


async def get_latest_report_by_type(patient_id: str, report_type: str) -> dict[str, Any] | None:
    docs = await prisma.assetindex.find_many(
        where={
            "patientId": patient_id,
            "reportType": report_type
        },
        order={"documentDate": "desc"},
        take=1
    )
    if not docs:
        return None
    return dict(docs[0])


async def get_documents_by_keyword(patient_id: str, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    import json
    kw_json = json.dumps([keyword])
    
    rows = await prisma.query_raw(
        '''
        SELECT id FROM asset_indexes 
        WHERE "patientId" = $1 
        AND keywords @> $2::jsonb
        ORDER BY "documentDate" DESC 
        LIMIT $3
        ''',
        patient_id,
        kw_json,
        limit
    )
    
    if not rows:
        return []
        
    ids = [r["id"] for r in rows]
    docs = await prisma.assetindex.find_many(
        where={
            "id": {"in": ids}
        },
        order={"documentDate": "desc"}
    )
    return [dict(d) for d in docs]
