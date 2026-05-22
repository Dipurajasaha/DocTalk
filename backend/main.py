from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.doctor import router as doctor_router
from .api.patient import router as patient_router
from .api.reports import router as reports_router
from .api.ai import router as ai_router
from .core.config import settings
from .core.constants import APP_NAME, APP_VERSION, DB_HEALTH_PATH, HEALTH_PATH
from .core.database import connect_prisma, disconnect_prisma, ping_database
from .core.logger import configure_logging, get_logger


configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
	logger.info("Starting application", extra={"component": "lifecycle"})
	await connect_prisma()
	try:
		yield
	finally:
		await disconnect_prisma()
		logger.info("Stopping application", extra={"component": "lifecycle"})


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=list(settings.cors_origins),
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(patient_router)
app.include_router(doctor_router)
app.include_router(chat_router)
app.include_router(reports_router)
app.include_router(ai_router)


@app.get(HEALTH_PATH, tags=["system"])
async def health_check() -> dict[str, str]:
	return {"status": "ok", "app": APP_NAME, "version": APP_VERSION}


@app.get(DB_HEALTH_PATH, tags=["system"])
async def database_health_check() -> dict[str, object]:
	try:
		return await ping_database()
	except Exception as exc:  # pragma: no cover - surfaced in validation
		logger.exception("Database health check failed", extra={"component": "database"})
		raise HTTPException(status_code=503, detail="database unavailable") from exc

