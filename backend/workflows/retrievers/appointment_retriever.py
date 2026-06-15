from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ...core.database import prisma, ensure_connected

logger = logging.getLogger(__name__)


async def retrieve_appointments(
    patient_id: str | None = None,
    doctor_id: str | None = None,
    upcoming_only: bool = False
) -> list[dict[str, Any]]:
    """Fetch real appointments from the database.

    Returns an empty list when no rows match — never injects mock data.
    """
    await ensure_connected()

    where: dict[str, Any] = {}
    if patient_id:
        where["patientUsername"] = patient_id
    if doctor_id:
        where["doctorId"] = doctor_id

    if not where:
        print("[DEBUG][APPOINTMENT_DB_QUERY] No patient_id or doctor_id provided, skipping DB query")
        return []

    print(f"[DEBUG][APPOINTMENT_DB_QUERY] where={where}")

    try:
        rows = await prisma.appointment.find_many(
            where=where,
            include={"doctor": True, "slot": True},
            order={"requestedAt": "desc"},
        )
    except Exception as exc:
        logger.error("Appointment DB query failed: %s", exc)
        print(f"[DEBUG][APPOINTMENT_DB_RESULT] ERROR: {exc}")
        print("[DEBUG][APPOINTMENT_FALLBACK_USED] False — returning empty list on error")
        return []

    print(f"[DEBUG][APPOINTMENT_DB_RESULT] row_count={len(rows)}")

    results: list[dict[str, Any]] = []
    for row in rows:
        doctor = getattr(row, "doctor", None)
        slot = getattr(row, "slot", None)

        appt: dict[str, Any] = {
            "id": row.id,
            "patientUsername": row.patientUsername,
            "doctorId": row.doctorId,
            "doctorName": getattr(doctor, "name", None) if doctor else None,
            "specialization": getattr(doctor, "specialization", None) if doctor else None,
            "hospitalName": getattr(doctor, "hospitalName", None) if doctor else None,
            "appointmentDate": str(row.appointmentDate) if row.appointmentDate else None,
            "scheduledTime": str(row.scheduledTime) if row.scheduledTime else None,
            "date": row.date,
            "time": row.time,
            "reason": row.reason,
            "note": row.note,
            "doctorMessage": row.doctorMessage,
            "status": row.status,
            "requestedAt": str(row.requestedAt) if row.requestedAt else None,
        }

        if slot:
            appt["slotStart"] = str(slot.startTime) if slot.startTime else None
            appt["slotEnd"] = str(slot.endTime) if slot.endTime else None

        # Filter upcoming appointments
        if upcoming_only:
            current_time = datetime.now(timezone.utc)
            appointment_time = row.appointmentDate
            if appointment_time is None:
                continue
                
            # If naive, make timezone aware
            if appointment_time.tzinfo is None:
                appointment_time = appointment_time.replace(tzinfo=timezone.utc)
                
            is_upcoming = appointment_time > current_time
            print(f"[DEBUG][CURRENT_TIME] {current_time}")
            print(f"[DEBUG][APPOINTMENT_TIME] {appointment_time}")
            print(f"[DEBUG][IS_UPCOMING] {is_upcoming}")
            
            if not is_upcoming:
                continue

        results.append(appt)
        print(
            f"[DEBUG][APPOINTMENT_ROW] id={row.id} doctor={appt['doctorName']} "
            f"date={appt['appointmentDate'] or appt['date']} status={row.status}"
        )

    print(f"[DEBUG][APPOINTMENT_FALLBACK_USED] False — {len(results)} real rows returned")
    return results
