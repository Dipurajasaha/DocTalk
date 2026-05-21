from fastapi import APIRouter, Depends

from ..schemas import ProfileUpdate
from ..repositories.doctor_repository import DoctorRepository
from ..services.doctor_service import DoctorService
from fastapi import Request


router = APIRouter()


def _get_doctor_service(request: Request) -> DoctorService:
    store = request.app.state.store
    repo = DoctorRepository(store)
    return DoctorService(repo)


@router.get("/list")
async def list_doctors(doctor_svc: DoctorService = Depends(_get_doctor_service)) -> list[dict]:
    return await doctor_svc.list_doctors()


@router.get("/{doctor_id}/profile")
async def get_profile(doctor_id: str, doctor_svc: DoctorService = Depends(_get_doctor_service)) -> dict:
    profile = await doctor_svc.get_profile(doctor_id)
    if not profile:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Doctor not found")
    return profile


@router.put("/{doctor_id}/profile")
async def update_profile(doctor_id: str, payload: ProfileUpdate, doctor_svc: DoctorService = Depends(_get_doctor_service)) -> dict:
    return await doctor_svc.update_profile(doctor_id, payload.model_dump())


@router.get("/{doctor_id}/requests")
async def get_requests(doctor_id: str, doctor_svc: DoctorService = Depends(_get_doctor_service)) -> list[dict]:
    return await doctor_svc.get_requests(doctor_id)
