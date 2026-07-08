"""Public stats endpoint for the landing page."""
from __future__ import annotations

from fastapi import APIRouter

from ..core.database import prisma


router = APIRouter()


@router.get("/stats", tags=["public"])
async def public_stats() -> dict[str, int]:
    """Return real aggregate counts for the landing page stats band."""
    patients = await prisma.patient.count()
    doctors = await prisma.doctor.count()
    admins = await prisma.admin.count()

    return {
        "patients": patients,
        "doctors": doctors,
        "admins": admins,
        "hospitals": 0,
    }