from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.auth import profile_router, router as auth_router
from .api.compat import router as compat_router
from .api.chat import router as chat_router
from .api.appointments import router as appointments_router
from .api.medical_assets import router as assets_router
from .api.hospital import router as hospital_router, public_router as hospital_public_router
from .api.users import doctor_router as user_doctor_router, router as users_router
from .api.image_analysis import router as image_analysis_router
from .core.database import connect_prisma, disconnect_prisma, ensure_connected, ping_database


logger = logging.getLogger(__name__)


app = FastAPI(title="DocTalk Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def db_connect_middleware(request: Request, call_next):
    """Ensure the database is connected before each request.

    This runs BEFORE any route handler so that services never hit
    ClientNotConnectedError even if the startup DB connect failed.
    """
    try:
        await ensure_connected()
    except Exception as exc:
        logger.error("DB connection unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable, please try again later."},
        )
    return await call_next(request)


@app.on_event("startup")
async def startup_event() -> None:
    try:
        await connect_prisma()
        logger.info("DocTalk backend started; database connected successfully")
    except Exception as exc:
        logger.error("DocTalk backend started but database connection FAILED: %s", exc)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await disconnect_prisma()


app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(profile_router, prefix="/api", tags=["auth"])
app.include_router(compat_router, prefix="/api", tags=["compat"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(user_doctor_router, prefix="/api/doctor", tags=["users"])
app.include_router(appointments_router, prefix="/api/appointments", tags=["appointments"])
app.include_router(assets_router, prefix="/api/assets", tags=["assets"])
app.include_router(hospital_router, prefix="/api/hospital", tags=["hospital"])
app.include_router(hospital_public_router, prefix="/api/hospital/public", tags=["hospital"])
app.include_router(image_analysis_router, prefix="/api", tags=["images"])


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": "DocTalk Backend", "version": "1.0.0"}


@app.get("/health/db", tags=["system"])
async def health_db() -> dict:
    """Ping the database and return its status."""
    return await ping_database()
