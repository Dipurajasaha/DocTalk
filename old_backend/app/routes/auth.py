from fastapi import APIRouter, HTTPException, Request, Depends

from ..schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)
from ..repositories.auth_repository import AuthRepository
from ..services.auth.auth_service import AuthService


router = APIRouter()


def _get_auth_service(request: Request) -> AuthService:
    store = request.app.state.store
    repo = AuthRepository(store)
    return AuthService(repo)


@router.post("/register", response_model=RegisterResponse)
async def register(
    payload: RegisterRequest, auth_svc: AuthService = Depends(_get_auth_service)
) -> RegisterResponse:
    username = payload.username.strip()

    common_profile = {
        "name": payload.name.strip(),
        "email": payload.email,
        "phone": payload.phone,
        "password": payload.password,
    }

    if payload.role == "patient":
        created = await auth_svc.register_patient(username, common_profile)
    else:
        doctor_profile = {
            **common_profile,
            "specialization": payload.specialization,
            "bio": payload.bio,
        }
        created = await auth_svc.register_doctor(username, doctor_profile)

    if not created:
        raise HTTPException(status_code=409, detail="User already exists")

    return RegisterResponse(
        success=True,
        role=payload.role,
        username=username,
        message="Registration successful",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_svc: AuthService = Depends(_get_auth_service),
) -> LoginResponse:
    ok = await auth_svc.authenticate(payload.role, payload.username, payload.password)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    request.session["user"] = payload.username
    request.session["category"] = payload.role
    request.session["role"] = payload.role

    return LoginResponse(
        success=True,
        role=payload.role,
        username=payload.username,
    )
