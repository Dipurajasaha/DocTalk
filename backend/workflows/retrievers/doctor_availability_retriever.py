from typing import Any

async def retrieve_doctor_availability(specialization: str | None = None, doctor_name: str | None = None) -> list[dict[str, Any]]:
    # Placeholder/mock data for now
    return [
        {
            "doctor_id": "mock_doctor_1",
            "doctor_name": doctor_name or "Dr. Smith",
            "specialization": specialization or "Cardiologist",
            "available_slots": ["2026-06-20T10:00:00Z", "2026-06-20T14:30:00Z"]
        }
    ]
