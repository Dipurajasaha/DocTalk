from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from ..core.security import CurrentUser, get_current_user
from ..services.prescription_service import PrescriptionService

router = APIRouter()


def get_prescription_service() -> PrescriptionService:
    return PrescriptionService()


def _require_doctor(current_user: CurrentUser) -> None:
    if current_user.role != "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can perform this action")


def _require_patient(current_user: CurrentUser) -> None:
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can perform this action")


@router.post("")
async def issue_prescription(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    _require_doctor(current_user)
    data = await request.json()
    return await service.issue(current_user.user_id, data)


@router.get("/mine")
async def list_my_prescriptions(
    current_user: CurrentUser = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    _require_patient(current_user)
    return await service.list_for_patient_self(current_user.user_id)


@router.get("/issued")
async def list_issued_prescriptions(
    patient_username: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    _require_doctor(current_user)
    return await service.list_for_doctor(current_user.user_id, patient_username)


@router.get("/public-key")
async def get_signing_public_key(
    service: PrescriptionService = Depends(get_prescription_service),
):
    return await service.get_public_key()


@router.get("/signature/status")
async def get_signature_status(
    current_user: CurrentUser = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    _require_doctor(current_user)
    return await service.get_signature_status(current_user.user_id)


@router.post("/signature")
async def save_signature(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    _require_doctor(current_user)
    data = await request.json()
    return await service.save_signature(current_user.user_id, data.get("signatureImageBase64", ""))


@router.get("/verify/{qr_token}")
async def verify_prescription_by_qr(
    qr_token: str,
    service: PrescriptionService = Depends(get_prescription_service),
):
    return await service.verify_by_qr_token(qr_token)


@router.get("/{prescription_id}")
async def get_prescription(
    prescription_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    return await service.get(prescription_id, requester_type=current_user.role, requester_id=current_user.user_id)


@router.get("/{prescription_id}/pdf")
async def download_prescription_pdf(
    prescription_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    pdf_bytes = await service.get_pdf_bytes(
        prescription_id, requester_type=current_user.role, requester_id=current_user.user_id
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="prescription-{prescription_id}.pdf"'},
    )


@router.post("/{prescription_id}/revoke")
async def revoke_prescription(
    prescription_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    _require_doctor(current_user)
    data = await request.json()
    return await service.revoke(current_user.user_id, prescription_id, data.get("revokedReason", ""))


@router.post("/{prescription_id}/supersede")
async def supersede_prescription(
    prescription_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    _require_doctor(current_user)
    data = await request.json()
    return await service.supersede(current_user.user_id, prescription_id, data)
