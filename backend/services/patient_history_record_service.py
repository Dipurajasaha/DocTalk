from typing import Any
from ..core.database import prisma
from ..schemas.patient_history import CreatePatientHistoryRecord, UpdatePatientHistoryRecord


class PatientHistoryRecordService:
    async def get_latest(self, patient_id: str) -> dict[str, Any] | None:
        record = await prisma.patienthistoryrecord.find_first(
            where={"patientId": patient_id},
            order={"recordDate": "desc", "createdAt": "desc"},
        )
        return dict(record) if record else None

    async def list_history(self, patient_id: str) -> list[dict[str, Any]]:
        records = await prisma.patienthistoryrecord.find_many(
            where={"patientId": patient_id},
            order={"recordDate": "desc", "createdAt": "desc"},
        )
        return [dict(r) for r in records]

    async def create_record(
        self, patient_id: str, payload: CreatePatientHistoryRecord
    ) -> dict[str, Any]:
        data = payload.model_dump(exclude_none=True)
        data["patientId"] = patient_id
        record = await prisma.patienthistoryrecord.create(data=data)
        return dict(record)

    async def update_record(
        self,
        patient_id: str,
        record_id: str,
        payload: UpdatePatientHistoryRecord,
    ) -> dict[str, Any]:
        existing = await prisma.patienthistoryrecord.find_first(
            where={"id": record_id, "patientId": patient_id}
        )
        if not existing:
            raise ValueError("Record not found")

        data = payload.model_dump(exclude_none=True)
        if not data:
            return dict(existing)

        record = await prisma.patienthistoryrecord.update(
            where={"id": record_id},
            data=data,
        )
        return dict(record)


patient_history_record_service = PatientHistoryRecordService()
