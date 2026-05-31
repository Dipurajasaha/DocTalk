from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.auth import profile_router, router as auth_router
from .api.chat import router as chat_router
from .api.appointments import router as appointments_router
from .api.medical_assets import router as assets_router
from .api.users import doctor_router as user_doctor_router, router as users_router
from .core.database import connect_prisma, disconnect_prisma

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
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(user_doctor_router, prefix="/api/doctor", tags=["users"])
app.include_router(appointments_router, prefix="/api/appointments", tags=["appointments"])
app.include_router(assets_router, prefix="/api/assets", tags=["assets"])


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": "DocTalk Backend", "version": "1.0.0"}
