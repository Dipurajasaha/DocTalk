from typing import Any
from ..core.database import prisma
from ..schemas.patient_history import CreatePatientHistory, UpdatePatientHistory

class PatientHistoryService:
    async def create_entry(self, data: CreatePatientHistory) -> dict[str, Any]:
        print("[DEBUG][HISTORY_CREATE_ATTEMPT]", data.model_dump(exclude_none=True))
        try:
            # Deduplication: check if a record with the same type and title exists for the patient
            existing = await prisma.patientmedicalhistory.find_first(
                where={
                    "patientId": data.patientId,
                    "historyType": data.historyType,
                    "title": data.title
                }
            )
            if existing:
                doc = await prisma.patientmedicalhistory.update(
                    where={"id": existing.id},
                    data={
                        "value": data.value,
                        "source": data.source,
                        "sourceId": data.sourceId,
                        "recordDate": data.recordDate
                    }
                )
            else:
                doc = await prisma.patientmedicalhistory.create(data=data.model_dump(exclude_none=True))
            
            print("[DEBUG][HISTORY_CREATE_SUCCESS]", dict(doc) if doc else None)
            return dict(doc) if doc else {}
        except Exception as e:
            print("[DEBUG][HISTORY_CREATE_FAILURE]", str(e))
            raise

    async def update_entry(self, entry_id: str, data: UpdatePatientHistory) -> dict[str, Any]:
        doc = await prisma.patientmedicalhistory.update(
            where={"id": entry_id},
            data=data.model_dump(exclude_none=True)
        )
        return dict(doc) if doc else {}

    async def delete_entry(self, entry_id: str) -> bool:
        doc = await prisma.patientmedicalhistory.delete(where={"id": entry_id})
        return bool(doc)

    async def delete_by_source_id(self, source: str, source_id: str) -> int:
        doc = await prisma.patientmedicalhistory.delete_many(
            where={"source": source, "sourceId": source_id}
        )
        return doc.count if hasattr(doc, "count") else 0

    async def list_entries(self, patient_id: str, limit: int = 50) -> list[dict[str, Any]]:
        docs = await prisma.patientmedicalhistory.find_many(
            where={"patientId": patient_id},
            order={"createdAt": "desc"},
            take=limit
        )
        print("[DEBUG][HISTORY_DB_RECORDS]", len(docs))
        return [dict(d) for d in docs]

    async def get_entries_by_type(self, patient_id: str, history_type: str, limit: int = 50) -> list[dict[str, Any]]:
        docs = await prisma.patientmedicalhistory.find_many(
            where={"patientId": patient_id, "historyType": history_type},
            order={"createdAt": "desc"},
            take=limit
        )
        return [dict(d) for d in docs]

patient_history_service = PatientHistoryService()
