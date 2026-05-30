from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.auth import profile_router, router as auth_router
from .api.appointments import compat_router as appointments_compat_router, router as appointments_router
from .api.users import doctor_router as user_doctor_router, router as users_router
from .core.database import connect_prisma, disconnect_prisma
from .api import medical_assets



app = FastAPI(title="DocTalk Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    await connect_prisma()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await disconnect_prisma()


app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(profile_router, prefix="/api", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(user_doctor_router, prefix="/api/doctor", tags=["users"])
app.include_router(appointments_router, prefix="/api/appointments", tags=["appointments"])
app.include_router(appointments_compat_router, prefix="/api", tags=["appointments"])

# Medical assets router (mounted at /api for compatibility and /api/assets as requested)
app.include_router(medical_assets.router, prefix="/api", tags=["assets"])
app.include_router(medical_assets.router, prefix="/api/assets", tags=["assets"])


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": "DocTalk Backend", "version": "1.0.0"}
