from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from ...middleware.auth_middleware import CurrentUser, require_doctor
from ...services.doctor_service import DoctorService
from ...workflows.doctor_copilot_workflow import doctor_copilot_workflow
from ..schemas import DoctorProfileResponse, DoctorProfileUpdate


router = APIRouter()


def get_doctor_service() -> DoctorService:
    return DoctorService()


class DoctorCopilotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_summary: dict[str, Any]
    recent_consultations: list[dict[str, Any]] = Field(default_factory=list)
    recurring_symptoms: dict[str, Any] = Field(default_factory=dict)
    medication_history: dict[str, Any] = Field(default_factory=dict)
    recent_reports: list[dict[str, Any]] = Field(default_factory=list)
    key_findings: list[dict[str, Any]] = Field(default_factory=list)
    timeline: dict[str, Any] = Field(default_factory=dict)
    risk_highlights: dict[str, Any] = Field(default_factory=dict)
    explainability: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/me", response_model=DoctorProfileResponse)
async def get_my_profile(
    current_user: CurrentUser = Depends(require_doctor),
    doctor_service: DoctorService = Depends(get_doctor_service),
) -> DoctorProfileResponse:
    return DoctorProfileResponse.model_validate(await doctor_service.get_profile(current_user.user_id))


@router.put("/me", response_model=DoctorProfileResponse)
async def update_my_profile(
    payload: DoctorProfileUpdate,
    current_user: CurrentUser = Depends(require_doctor),
    doctor_service: DoctorService = Depends(get_doctor_service),
) -> DoctorProfileResponse:
    return DoctorProfileResponse.model_validate(
        await doctor_service.update_profile(current_user.user_id, payload.model_dump(exclude_unset=True))
    )


@router.get("/list", response_model=list[DoctorProfileResponse])
async def list_doctors(
    _: CurrentUser = Depends(require_doctor),
    specialization: str | None = Query(default=None),
    category: str | None = Query(default=None),
    doctor_service: DoctorService = Depends(get_doctor_service),
) -> list[DoctorProfileResponse]:
    doctors = await doctor_service.list_doctors(specialization=specialization, category=category)
    return [DoctorProfileResponse.model_validate(item) for item in doctors]


@router.get("/copilot/consultations/{consultation_id}", response_model=DoctorCopilotResponse)
async def doctor_copilot_for_consultation(
    consultation_id: str,
    query: str | None = Query(default=None, min_length=1),
    current_user: CurrentUser = Depends(require_doctor),
) -> DoctorCopilotResponse:
    from ...core.database import prisma

    consultation = await prisma.consultation.find_unique(where={"id": consultation_id})
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    if str(getattr(consultation, "doctorId", "")) != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this consultation")
    payload = await doctor_copilot_workflow.run(
        requester_id=current_user.user_id,
        role="doctor",
        patient_id=str(getattr(consultation, "patientUsername", "")),
        consultation_id=consultation_id,
        query=query,
    )
    return DoctorCopilotResponse.model_validate(payload)


@router.get("/copilot/patients/{patient_id}", response_model=DoctorCopilotResponse)
async def doctor_copilot_for_patient(
    patient_id: str,
    consultation_id: str | None = Query(default=None),
    query: str | None = Query(default=None, min_length=1),
    current_user: CurrentUser = Depends(require_doctor),
) -> DoctorCopilotResponse:
    from ...core.database import prisma

    if consultation_id:
        consultation = await prisma.consultation.find_unique(where={"id": consultation_id})
        if consultation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
        if str(getattr(consultation, "doctorId", "")) != current_user.user_id or str(getattr(consultation, "patientUsername", "")) != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this patient's consultation")
    else:
        permitted = await prisma.consultation.find_first(where={"doctorId": current_user.user_id, "patientUsername": patient_id})
        if permitted is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this patient's overview")

    payload = await doctor_copilot_workflow.run(
        requester_id=current_user.user_id,
        role="doctor",
        patient_id=patient_id,
        consultation_id=consultation_id,
        query=query,
    )
    return DoctorCopilotResponse.model_validate(payload)
