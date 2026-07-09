from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core.security import CurrentUser, get_current_user
from ..schemas.hospital_schemas import (
    HospitalDashboardResponse,
    HospitalLoginRequest,
    HospitalNewsCreate,
    HospitalNewsResponse,
    HospitalProfileUpdate,
    HospitalProfileResponse,
    HospitalRegisterRequest,
    HospitalTokenResponse,
    SymptomReportCreate,
    SymptomReportListResponse,
    SymptomReportResponse,
    HospitalPatientRegisterRequest,
    HospitalPatientResponse,
    SymptomReportStatusUpdate,
)
from ..services.hospital_service import HospitalService


router = APIRouter()
public_router = APIRouter()


def get_hospital_service() -> HospitalService:
    return HospitalService()


# ──────────────────────────────── AUTH ────────────────────────────────


@router.post("/auth/login", response_model=HospitalTokenResponse)
async def hospital_login(
    payload: HospitalLoginRequest,
    service: HospitalService = Depends(get_hospital_service),
) -> HospitalTokenResponse:
    return await service.login(payload.hospital_id, payload.password)


@router.post("/auth/signup", response_model=HospitalTokenResponse)
async def hospital_signup(
    payload: HospitalRegisterRequest,
    service: HospitalService = Depends(get_hospital_service),
) -> HospitalTokenResponse:
    return await service.register(
        payload.hospital_id,
        payload.name,
        payload.password,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        registration_number=payload.registration_number,
        phone=payload.phone,
        email=payload.email,
        website=payload.website,
    )


# ───────────────────────── SYMPTOM REPORTS ─────────────────────────


@router.post("/reports", response_model=SymptomReportResponse)
async def create_report(
    payload: SymptomReportCreate,
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can submit reports")
    return await service.create_symptom_report(current_user.user_id, payload.model_dump())


@router.get("/reports", response_model=SymptomReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    disease: str | None = Query(None),
    severity: str | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can view their reports")
    return await service.get_hospital_reports(
        current_user.user_id, page=page, per_page=per_page, disease=disease, severity=severity,
    )


@router.get("/reports/{report_id}", response_model=SymptomReportResponse)
async def get_report(
    report_id: str,
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    return await service.get_report_by_id(report_id)


@router.get("/reports/patient/{patient_username}")
async def get_patient_reports(
    patient_username: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    """Get all symptom reports for a specific registered patient."""
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can view patient reports")
    return await service.get_hospital_reports(
        current_user.user_id, patient_username=patient_username
    )


@router.get("/detailed-analysis")
async def detailed_analysis(
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    """Comprehensive disease analysis with mortality stats, trends, patient demographics."""
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can access detailed analysis")
    return await service.get_detailed_analysis(hospital_id=current_user.user_id)


@public_router.get("/detailed-analysis/global")
async def global_detailed_analysis(
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    """Public endpoint for global detailed disease analysis."""
    return await service.get_detailed_analysis(hospital_id=None)


@router.get("/patients/{patient_username}/medical-history")
async def patient_medical_history(
    patient_username: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    """Get full medical history for a registered patient."""
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can view patient medical history")
    return await service.get_patient_full_medical_history(current_user.user_id, patient_username)


# ─────────────────────── HOSPITAL NEWS ───────────────────────


@router.post("/news", response_model=HospitalNewsResponse)
async def create_news(
    payload: HospitalNewsCreate,
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can create news")
    return await service.create_news(current_user.user_id, payload.model_dump())


@router.get("/news", response_model=list[HospitalNewsResponse])
async def list_news(
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> list[dict]:
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can view their news")
    return await service.get_hospital_news(current_user.user_id)


# ─────────────────────── GLOBAL / PUBLIC ENDPOINTS ───────────────────────


@public_router.get("/news/global", response_model=list[HospitalNewsResponse])
async def global_news(
    limit: int = Query(10, ge=1, le=50),
    service: HospitalService = Depends(get_hospital_service),
) -> list[dict]:
    """Public endpoint to fetch global news for sidebar display."""
    return await service.get_latest_news_all(limit=limit)


@public_router.get("/reports/global", response_model=SymptomReportListResponse)
async def global_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    disease: str | None = Query(None),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    """Public endpoint to view aggregated symptom data for analysis."""
    return await service.get_all_reports_global(page=page, per_page=per_page, disease=disease)


@public_router.get("/disease-summary")
async def disease_summary(
    service: HospitalService = Depends(get_hospital_service),
) -> list[dict]:
    """Public endpoint to get aggregated disease counts."""
    return await service.get_disease_summary()




# ─────────────────────── HOSPITAL PROFILE ───────────────────────


@router.put("/profile", response_model=HospitalProfileResponse)
async def update_hospital_profile(
    payload: HospitalProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can update their profile")
    return await service.update_hospital_profile(current_user.user_id, payload.model_dump(exclude_none=True))


@router.get("/profile", response_model=HospitalProfileResponse)
async def get_hospital_profile(
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    """Get the hospital's own profile."""
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can view their profile")
    hospital = await service._get_hospital(current_user.user_id)
    return service._format_hospital_profile(hospital)


# ─────────────────────── DASHBOARD ───────────────────────


@router.get("/dashboard", response_model=HospitalDashboardResponse)
async def dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can access dashboard")
    return await service.get_dashboard(current_user.user_id)


@router.post("/register-patient", response_model=HospitalPatientResponse)
async def register_patient(
    payload: HospitalPatientRegisterRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can register patients")
    return await service.register_patient(current_user.user_id, payload.model_dump())


@router.get("/patients", response_model=list[HospitalPatientResponse])
async def get_registered_patients(
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> list[dict]:
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can view their patients")
    return await service.get_registered_patients(current_user.user_id)


@router.put("/reports/{report_id}/status", response_model=SymptomReportResponse)
async def update_report_status(
    report_id: str,
    payload: SymptomReportStatusUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    if current_user.role != "hospital":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only hospitals can update report status")
    return await service.update_report_status(current_user.user_id, report_id, payload.status)