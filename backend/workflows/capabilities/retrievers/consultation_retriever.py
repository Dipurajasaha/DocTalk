from __future__ import annotations

from typing import Any

from backend.core.database import prisma


async def retrieve_consultations(
    *,
    patient_id: str | None,
    doctor_id: str | None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    where_clause: dict[str, Any] = {}
    if patient_id:
        where_clause["patientUsername"] = patient_id
    if doctor_id:
        where_clause["doctorId"] = doctor_id

    if not where_clause:
        return []

    consultations = await prisma.consultation.find_many(
        where=where_clause,
        include={"messages": {"take": 5, "orderBy": {"timestamp": "desc"}}, "appointment": {"include": {"doctor": True}}},
        order={"createdAt": "desc"},
        take=limit,
    )

    results: list[dict[str, Any]] = []
    for c in consultations:
        doctor_name = "Unknown Doctor"
        status = "UNKNOWN"
        if getattr(c, "appointment", None):
            status = str(c.appointment.status)
            if getattr(c.appointment, "doctor", None):
                doctor_name = str(getattr(c.appointment.doctor, "name", "Unknown Doctor"))
        elif getattr(c, "doctorId", None):
            doctor_name = str(c.doctorId)

        recent_messages: list[dict[str, Any]] = []
        messages = getattr(c, "messages", [])
        if messages:
            # Reverse them to return in chronological order
            for m in reversed(messages):
                recent_messages.append({
                    "role": str(m.senderRole),
                    "content": str(m.message),
                    "timestamp": m.timestamp,
                })

        results.append({
            "consultation_id": c.id,
            "created_at": c.createdAt,
            "doctor_name": doctor_name,
            "status": status,
            "recent_messages": recent_messages,
        })

    return results
