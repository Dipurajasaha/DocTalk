from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.prescription_signing import (
    sign_prescription,
    verify_prescription,
    get_public_key_b64,
    CURRENT_SIGNING_KEY_ID,
)
from .prescription_pdf_service import render_prescription_pdf
from .prescription_pdf_storage import save_prescription_pdf


class PrescriptionService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    # ---------- issuing ----------

    async def issue(self, doctor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        patient_username = str(data.get("patientUsername") or "").strip()
        medicines = data.get("medicines") or []
        sick_note = data.get("sickNote")
        consultation_id = data.get("consultationId")
        doctor_notes = str(data.get("doctorNotes") or "").strip() or None

        if not patient_username:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="patientUsername is required")
        if not medicines and not sick_note:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide at least one medicine or a sick note")

        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        if not getattr(doctor, "signatureImageBase64", None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Save your signature before issuing prescriptions (Doctor settings > Signature)",
            )

        patient = await self.client.patient.find_unique(where={"username": patient_username})
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        cleaned_medicines = [self._clean_medicine(m) for m in medicines]
        cleaned_sick_note = self._clean_sick_note(sick_note) if sick_note else None

        prescription_number = await self._next_prescription_number()
        issued_at = datetime.now(timezone.utc)

        signed = sign_prescription(
            prescription_number=prescription_number,
            doctor_id=doctor_id,
            patient_username=patient_username,
            medicines=cleaned_medicines,
            sick_note=cleaned_sick_note,
            issued_at=issued_at,
        )

        created = await self.client.prescription.create(
            data={
                "id": str(uuid4()),
                "prescriptionNumber": prescription_number,
                "doctorId": doctor_id,
                "patientUsername": patient_username,
                "consultationId": consultation_id,
                "medicines": cleaned_medicines,
                "sickNote": cleaned_sick_note,
                "doctorNotes": doctor_notes,
                "status": "ACTIVE",
                "contentHash": signed.content_hash,
                "signature": signed.signature_b64,
                "signingKeyId": signed.signing_key_id,
                "issuedAt": issued_at,
                "qrToken": str(uuid4()),
            },
            include={"doctor": True, "patient": True},
        )

        pdf_bytes = render_prescription_pdf(self._serialize(created, include_verification=True), doctor, patient)
        await save_prescription_pdf(created.id, pdf_bytes, client=self.client)

        return self._serialize(created, include_verification=True)

    async def supersede(self, doctor_id: str, prescription_id: str, data: dict[str, Any]) -> dict[str, Any]:
        old = await self.client.prescription.find_unique(where={"id": prescription_id})
        if old is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found")
        if old.doctorId != doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this prescription")
        if old.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an active prescription can be superseded")

        data = {**data, "patientUsername": old.patientUsername, "consultationId": old.consultationId}
        new_record = await self.issue(doctor_id, data)

        await self.client.prescription.update(
            where={"id": prescription_id},
            data={"status": "SUPERSEDED", "supersededById": new_record["id"]},
        )
        await self.client.prescription.update(
            where={"id": new_record["id"]},
            data={"supersedesId": prescription_id},
        )
        return await self.get(new_record["id"], requester_type="doctor", requester_id=doctor_id)

    async def revoke(self, doctor_id: str, prescription_id: str, reason: str) -> dict[str, Any]:
        reason = str(reason or "").strip()
        if not reason:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="revokedReason is required")

        record = await self.client.prescription.find_unique(where={"id": prescription_id})
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found")
        if record.doctorId != doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this prescription")
        if record.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an active prescription can be revoked")

        updated = await self.client.prescription.update(
            where={"id": prescription_id},
            data={"status": "REVOKED", "revokedAt": datetime.now(timezone.utc), "revokedReason": reason},
            include={"doctor": True, "patient": True},
        )
        return self._serialize(updated, include_verification=True)

    async def get_pdf_bytes(self, prescription_id: str, *, requester_type: str, requester_id: str) -> bytes:
        # Reuses get() for the exact same access-control rules as viewing the record.
        await self.get(prescription_id, requester_type=requester_type, requester_id=requester_id)
        from .prescription_pdf_storage import load_decrypted_prescription_pdf
        return await load_decrypted_prescription_pdf(prescription_id, client=self.client)

    # ---------- reading ----------

    async def get(self, prescription_id: str, *, requester_type: str, requester_id: str) -> dict[str, Any]:
        record = await self.client.prescription.find_unique(
            where={"id": prescription_id}, include={"doctor": True, "patient": True}
        )
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found")
        if requester_type == "doctor" and record.doctorId != requester_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this prescription")
        if requester_type == "patient" and record.patientUsername != requester_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this prescription")
        return self._serialize(record, include_verification=True)

    async def list_for_patient_self(self, patient_username: str) -> list[dict[str, Any]]:
        records = await self.client.prescription.find_many(
            where={"patientUsername": patient_username},
            include={"doctor": True, "patient": True},
            order={"issuedAt": "desc"},
        )
        return [self._serialize(r) for r in records]

    async def list_for_doctor(self, doctor_id: str, patient_username: str | None = None) -> list[dict[str, Any]]:
        where: dict[str, Any] = {"doctorId": doctor_id}
        if patient_username:
            where["patientUsername"] = patient_username
        records = await self.client.prescription.find_many(
            where=where, include={"doctor": True, "patient": True}, order={"issuedAt": "desc"}
        )
        return [self._serialize(r) for r in records]

    # ---------- public verification ----------

    async def verify_by_qr_token(self, qr_token: str) -> dict[str, Any]:
        record = await self.client.prescription.find_unique(
            where={"qrToken": qr_token}, include={"doctor": True, "patient": True}
        )
        if record is None:
            return {"found": False}

        valid = verify_prescription(
            prescription_number=record.prescriptionNumber,
            doctor_id=record.doctorId,
            patient_username=record.patientUsername,
            medicines=record.medicines or [],
            sick_note=record.sickNote,
            issued_at=record.issuedAt,
            expected_content_hash=record.contentHash,
            signature_b64=record.signature,
        )
        patient_name = record.patient.name if record.patient else ""
        return {
            "found": True,
            "valid_signature": valid,
            "status": record.status,
            "prescription_number": record.prescriptionNumber,
            "doctor_name": record.doctor.name if record.doctor else "",
            "patient_name_masked": self._mask_name(patient_name),
            "issued_at": record.issuedAt.isoformat(),
            "medicines_count": len(record.medicines or []),
            "revoked": record.status == "REVOKED",
            "revoked_reason": record.revokedReason if record.status == "REVOKED" else None,
        }

    async def get_public_key(self) -> dict[str, str]:
        return {"public_key": get_public_key_b64(), "key_id": CURRENT_SIGNING_KEY_ID, "algorithm": "Ed25519"}

    # ---------- doctor signature ----------

    async def save_signature(self, doctor_id: str, signature_image_base64: str) -> dict[str, Any]:
        signature_image_base64 = str(signature_image_base64 or "").strip()
        if not signature_image_base64:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="signatureImageBase64 is required")
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        updated = await self.client.doctor.update(
            where={"doctorId": doctor_id},
            data={"signatureImageBase64": signature_image_base64, "signatureUpdatedAt": datetime.now(timezone.utc)},
        )
        return {"saved": True, "signatureUpdatedAt": updated.signatureUpdatedAt.isoformat()}

    async def get_signature_status(self, doctor_id: str) -> dict[str, Any]:
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        has_signature = bool(getattr(doctor, "signatureImageBase64", None))
        return {
            "hasSignature": has_signature,
            "signatureImageBase64": doctor.signatureImageBase64 if has_signature else None,
            "signatureUpdatedAt": doctor.signatureUpdatedAt.isoformat() if doctor.signatureUpdatedAt else None,
        }

    # ---------- helpers ----------

    def _clean_medicine(self, m: dict[str, Any]) -> dict[str, Any]:
        name = str(m.get("name") or "").strip()
        dosage = str(m.get("dosage") or "").strip()
        if not name or not dosage:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Each medicine needs a name and dosage")
        return {
            "name": name,
            "dosage": dosage,
            "frequency": str(m.get("frequency") or "").strip(),
            "duration": str(m.get("duration") or "").strip(),
            "notes": str(m.get("notes") or "").strip(),
        }

    def _clean_sick_note(self, s: dict[str, Any]) -> dict[str, Any]:
        reason = str(s.get("reason") or "").strip()
        start_date = str(s.get("startDate") or s.get("start_date") or "").strip()
        end_date = str(s.get("endDate") or s.get("end_date") or "").strip()
        if not reason or not start_date or not end_date:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sick note needs reason, startDate, and endDate")
        return {"reason": reason, "startDate": start_date, "endDate": end_date}

    def _mask_name(self, name: str) -> str:
        parts = name.strip().split()
        return " ".join((p[0] + "***") if p else "" for p in parts) or "Unknown"

    async def _next_prescription_number(self) -> str:
        year = datetime.now(timezone.utc).year
        count = await self.client.prescription.count()
        return f"DT-{year}-{count + 1:06d}"

    def _serialize(self, record: Any, include_verification: bool = False) -> dict[str, Any]:
        out = {
            "id": record.id,
            "prescriptionNumber": record.prescriptionNumber,
            "doctorId": record.doctorId,
            "doctorName": record.doctor.name if getattr(record, "doctor", None) else None,
            "patientUsername": record.patientUsername,
            "patientName": record.patient.name if getattr(record, "patient", None) else None,
            "consultationId": record.consultationId,
            "medicines": record.medicines,
            "sickNote": record.sickNote,
            "doctorNotes": record.doctorNotes,
            "status": record.status,
            "supersedesId": record.supersedesId,
            "supersededById": record.supersededById,
            "issuedAt": record.issuedAt.isoformat() if record.issuedAt else None,
            "revokedAt": record.revokedAt.isoformat() if record.revokedAt else None,
            "revokedReason": record.revokedReason,
            "qrToken": record.qrToken,
        }
        if include_verification:
            out["contentHash"] = record.contentHash
        return out
