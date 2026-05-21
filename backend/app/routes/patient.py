from datetime import datetime

from fastapi import APIRouter, Depends, Request

from ..schemas import AppointmentCreate, AppointmentRecord, ProfileUpdate
from ..repositories.patient_repository import PatientRepository
from ..repositories.doctor_repository import DoctorRepository
from ..services.patient_service import PatientService


router = APIRouter()


def _get_patient_service(request: Request) -> PatientService:
    store = request.app.state.store
    patient_repo = PatientRepository(store)
    doctor_repo = DoctorRepository(store)
    return PatientService(patient_repo, doctor_repo)


@router.get("/{username}/profile")
async def get_profile(username: str, patient_svc: PatientService = Depends(_get_patient_service)) -> dict:
    profile = await patient_svc.get_profile(username)
    if not profile:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Patient not found")
    return profile


@router.put("/{username}/profile")
async def update_profile(username: str, payload: ProfileUpdate, patient_svc: PatientService = Depends(_get_patient_service)) -> dict:
    return await patient_svc.update_profile(username, payload.model_dump())


@router.get("/{username}/appointments")
async def get_appointments(username: str, patient_svc: PatientService = Depends(_get_patient_service)) -> list[dict]:
    return await patient_svc.get_appointments(username)


@router.post("/appointments", response_model=AppointmentRecord)
async def create_appointment(payload: AppointmentCreate, patient_svc: PatientService = Depends(_get_patient_service)) -> AppointmentRecord:
    saved = await patient_svc.create_appointment(payload.model_dump())

    return AppointmentRecord(
        id=saved["id"],
        patient=saved["patient"],
        doctor_id=saved["doctor_id"],
        date=saved["date"],
        time=saved["time"],
        reason=saved["reason"],
        status=saved["status"],
        created_at=datetime.fromisoformat(saved["created_at"]),
    )
