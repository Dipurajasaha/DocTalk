from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from backend.services.appointment_service import AppointmentService
from backend.services.user_service import UserService


user_service = UserService()
appointment_service = AppointmentService()


@tool("search_available_doctors_tool")
async def search_available_doctors_tool(specialization: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    """Search for available doctors by specialization or category."""
    return await user_service.list_doctors(specialization=specialization, category=category)


@tool("search_available_slots_tool")
async def search_available_slots_tool(doctor_id: str) -> list[dict[str, Any]]:
    """Search for available appointment slots for a specific doctor."""
    return await appointment_service.get_available_slots(doctor_id=doctor_id)


@tool("book_appointment_tool")
async def book_appointment_tool(patient_id: str, slot_id: str, reason: str, note: str | None = None) -> dict[str, Any]:
    """Book a new appointment."""
    payload = {"slotId": slot_id, "reason": reason, "note": note}
    return await appointment_service.create_appointment(patient_id=patient_id, payload=payload)


@tool("reschedule_appointment_tool")
async def reschedule_appointment_tool(appointment_id: str, new_slot_id: str, actor_role: str, actor_id: str) -> dict[str, Any]:
    """Reschedule an existing appointment."""
    payload = {"slot_id": new_slot_id}
    return await appointment_service.update_appointment(
        appointment_id=appointment_id,
        payload=payload,
        actor_role=actor_role,
        actor_id=actor_id,
    )


@tool("cancel_appointment_tool")
async def cancel_appointment_tool(appointment_id: str, actor_role: str, actor_id: str) -> dict[str, Any]:
    """Cancel an existing appointment."""
    return await appointment_service.cancel_appointment(
        actor_role=actor_role,
        actor_id=actor_id,
        appointment_id=appointment_id,
    )


@tool("list_upcoming_appointments_tool")
async def list_upcoming_appointments_tool(role: str, user_id: str) -> list[dict[str, Any]]:
    """List upcoming appointments for the user."""
    return await appointment_service.list_appointments(role=role, user_id=user_id)
