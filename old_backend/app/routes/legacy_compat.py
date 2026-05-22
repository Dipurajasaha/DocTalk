"""Compatibility route layer.

Maps old /api/* paths to modular services for frontend compatibility.
Business logic is in services/repositories; this layer only handles routing.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Any

router = APIRouter(tags=["legacy-compat"])


def _get_store(request: Request) -> Any:
    """Extract store from request app state."""
    return request.app.state.store


@router.post("/api/login")
async def login_compat(request: Request):
    """Map /api/login to auth service."""
    from ..services.auth.auth_service import AuthService
    from ..repositories.auth_repository import AuthRepository
    
    form = await request.form()
    category = str(form.get("category") or "").strip().lower()
    username = str(form.get("username") or "").strip()
    password = str(form.get("password") or "")

    store = _get_store(request)
    repo = AuthRepository(store)
    svc = AuthService(repo)

    # Debug: log incoming auth attempt and result to server logs for troubleshooting
    try:
        ok = await svc.authenticate(category, username, password)
    except Exception as exc:
        print(f"[auth-debug] authentication raised: role={category!r} user={username!r} exc={exc}")
        raise
    print(f"[auth-debug] login attempt: role={category!r} user={username!r} result={ok}")
    if not ok:
        return JSONResponse({"success": False, "error": "Invalid credentials"}, status_code=401)

    request.session["user"] = username
    request.session["category"] = category
    return JSONResponse({"success": True})


@router.post("/api/register")
async def register_compat(request: Request):
    """Map /api/register to auth service."""
    from ..services.auth.auth_service import AuthService
    from ..repositories.auth_repository import AuthRepository
    
    form = await request.form()
    # Normalize category and username
    category = str(form.get("category") or "").strip().lower()
    username = str(form.get("username") or "").strip()

    # Debug: show incoming registration payload keys (do not log passwords in production)
    try:
        _debug_payload = {k: ("<redacted>" if k.lower() == "password" else v) for k, v in dict(form).items()}
    except Exception:
        _debug_payload = {"_form_repr": str(form)}
    print(f"[auth-debug] register attempt: role={category!r} user={username!r} payload={_debug_payload}")

    if category not in ("patient", "doctor"):
        return JSONResponse({"success": False, "error": "Invalid category"}, status_code=400)
    if not username:
        return JSONResponse({"success": False, "error": "Username required"}, status_code=400)

    store = _get_store(request)
    repo = AuthRepository(store)
    svc = AuthService(repo)

    profile = dict(form)
    if category == "patient":
        ok = await svc.register_patient(username, profile)
    else:
        ok = await svc.register_doctor(username, profile)

    print(f"[auth-debug] register result: role={category!r} user={username!r} created={ok}")

    if not ok:
        return JSONResponse({"success": False, "error": "User already exists"}, status_code=409)
    return JSONResponse({"success": True})


@router.post("/api/logout")
async def logout_compat(request: Request):
    """Map /api/logout to session clear."""
    request.session.clear()
    return JSONResponse({"success": True})


@router.get("/api/patient_session")
async def patient_session_compat(request: Request):
    """Map /api/patient_session to file repo."""
    from ..repositories.file_repository import FileRepository
    
    username = request.session.get("user")
    if not username:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)
    store = _get_store(request)
    frepo = FileRepository(store)
    profile = await frepo.get_profile(username) or {}
    display_name = profile.get("display_name") or profile.get("name") or username
    return JSONResponse({
        "success": True,
        "username": username,
        "display_name": display_name,
        "name": display_name,
        "profile_pic": profile.get("profile_pic") or ""
    })


@router.get("/api/doctor_session")
async def doctor_session_compat(request: Request):
    """Map /api/doctor_session to doctor repo."""
    from ..repositories.doctor_repository import DoctorRepository
    
    username = request.session.get("user")
    if not username:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)
    store = _get_store(request)
    drepo = DoctorRepository(store)
    doc = await drepo.get_profile(username) or {}
    return JSONResponse({
        "success": True,
        "username": username,
        "display_name": doc.get("name", username),
        "profile_pic": doc.get("profile_pic") or ""
    })


@router.get("/api/doctors")
async def doctors_compat(request: Request):
    """Map /api/doctors to doctor repo."""
    from ..repositories.doctor_repository import DoctorRepository
    
    store = _get_store(request)
    drepo = DoctorRepository(store)
    docs = await drepo.list_doctors()
    simplified = [{
        "id": d.get("id"),
        "name": d.get("name"),
        "gender": d.get("gender", "male"),
        "category": d.get("category") or d.get("specialization") or "General Medicine",
        "location": d.get("location") or d.get("hospital_location") or "",
        "address": d.get("address") or d.get("hospital_location") or "",
    } for d in docs]
    return JSONResponse({"success": True, "doctors": simplified})


@router.get("/api/chat_sessions")
async def chat_sessions_compat(request: Request):
    """Map /api/chat_sessions to file repo."""
    from ..repositories.file_repository import FileRepository
    
    username = request.session.get("user")
    if not username:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)
    store = _get_store(request)
    frepo = FileRepository(store)
    profile = await frepo.get_profile(username) or {}
    return JSONResponse({"success": True, "sessions": profile.get("chat_sessions", [])})


@router.post("/api/appointment_request")
async def appointment_request_compat(request: Request):
    """Map /api/appointment_request to patient/doctor repos."""
    from ..repositories.patient_repository import PatientRepository
    from ..repositories.doctor_repository import DoctorRepository
    
    username = request.session.get("user")
    if not username:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)
    
    try:
        data = await request.json()
    except Exception:
        data = {}
    
    doctor_id = data.get("doctor_id")
    if not doctor_id:
        return JSONResponse({"success": False, "error": "doctor_id required"}, status_code=400)

    store = _get_store(request)
    drepo = DoctorRepository(store)
    doc = await drepo.get_profile(doctor_id)
    if not doc:
        return JSONResponse({"success": False, "error": "Doctor not found"}, status_code=404)

    prepo = PatientRepository(store)
    appt = {"patient": username, "doctor_id": doctor_id, "status": "requested"}
    await prepo.create_appointment(appt)
    return JSONResponse({"success": True, "appointment": appt})


@router.get("/api/get_prescriptions")
async def get_prescriptions_compat(request: Request):
    """Map /api/get_prescriptions to file repo."""
    from ..repositories.file_repository import FileRepository
    
    username = request.session.get("user")
    if not username:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)
    store = _get_store(request)
    frepo = FileRepository(store)
    profile = await frepo.get_profile(username) or {}
    return JSONResponse({"success": True, "prescriptions": profile.get("prescriptions", [])})


@router.get("/api/file/{file_id}")
async def file_download_compat(file_id: str, request: Request):
    """Map /api/file/{file_id} downloads."""
    from ..services.file_service import FileService
    from ..repositories.file_repository import FileRepository
    from fastapi import HTTPException, Response
    
    username = request.session.get("user")
    if not username:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)
    
    store = _get_store(request)
    repo = FileRepository(store)
    fsvc = FileService(repo)
    
    try:
        file_bytes, content_type = await fsvc.download_file(username, file_id)
        return Response(content=file_bytes, media_type=content_type)
    except HTTPException as exc:
        return JSONResponse({"success": False, "error": exc.detail}, status_code=exc.status_code)
