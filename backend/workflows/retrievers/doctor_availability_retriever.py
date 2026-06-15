from __future__ import annotations

import logging
from datetime import datetime, timezone
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo
from typing import Any

from ...core.database import prisma, ensure_connected

logger = logging.getLogger(__name__)


async def retrieve_doctor_availability(
    specialization: str | None = None, doctor_name: str | None = None
) -> list[dict[str, Any]]:
    """Fetch doctor availability slots from the database.
    
    Returns real records from the DoctorSlot table where isBooked is False.
    """
    await ensure_connected()
    
    print(f"[DEBUG][RETRIEVER_DOCTOR_NAME] {doctor_name}")
    
    where_clause: dict[str, Any] = {}
    
    if doctor_name:
        where_clause["name"] = {"contains": doctor_name, "mode": "insensitive"}
    if specialization:
        where_clause["specialization"] = {"contains": specialization, "mode": "insensitive"}
        
    print(f"[DEBUG][DOCTOR_AVAILABILITY_QUERY] {where_clause}")
    
    try:
        # Include slots that are in the future, active, and NOT booked.
        current_time = datetime.now(timezone.utc)
        rows = await prisma.doctor.find_many(
            where=where_clause,
            include={
                "doctorSlots": {
                    "where": {
                        "isBooked": False,
                        "isActive": True,
                        "startTime": {"gt": current_time}
                    },
                    "orderBy": {"startTime": "asc"}
                }
            }
        )
    except Exception as exc:
        logger.error("Doctor availability DB query failed: %s", exc)
        print(f"[DEBUG][DOCTOR_AVAILABILITY_DB_RESULT] ERROR: {exc}")
        print("[DEBUG][DOCTOR_AVAILABILITY_FALLBACK_USED] False")
        return [{"error": "Failed to fetch availability. Please try again."}]
        
    print(f"[DEBUG][DOCTOR_AVAILABILITY_DB_RESULT] {len(rows)}")
    print("[DEBUG][DOCTOR_AVAILABILITY_FALLBACK_USED] False")
    
    if not rows:
        target = doctor_name or specialization or "requested"
        return [{"message": f"No availability information found for doctor {target}."}]
        
    results: list[dict[str, Any]] = []
    
    for doctor in rows:
        # Prisma returns relation lists
        slots = getattr(doctor, "doctorSlots", [])
        if not slots:
            results.append({
                "message": f"No availability information found for doctor {doctor.name}.",
                "doctor_id": doctor.doctorId,
                "doctor_name": doctor.name
            })
            continue
            
        # Localize to Asia/Kolkata for LLM context
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        available_slot_times = [s.startTime.astimezone(tz).strftime('%B %d, %Y at %I:%M %p') for s in slots]
        
        results.append({
            "doctor_id": doctor.doctorId,
            "doctor_name": doctor.name,
            "specialization": getattr(doctor, "specialization", None),
            "hospital_name": getattr(doctor, "hospitalName", None),
            "available_slots": available_slot_times
        })
        
    return results
