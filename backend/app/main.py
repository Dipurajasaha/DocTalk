from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config.settings import settings
from .data_store import JsonHealthCareStore
from .routes.chat import router as chat_router
from .routes.auth import router as auth_router
from .routes.doctor import router as doctor_router
from .routes.file import router as file_router
from .routes.patient import router as patient_router
from .routes.legacy_compat import router as compat_router


app = FastAPI(title="HealthCare API", version="1.1.0")
store = JsonHealthCareStore()

app.state.store = store

_origins = []
if settings.CORS_ORIGINS:
    _origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if not _origins:
    # Default to common local dev origins used by Vite
    _origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(compat_router)
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(patient_router, prefix="/api/patient", tags=["patient"])
app.include_router(doctor_router, prefix="/api/doctor", tags=["doctor"])
app.include_router(file_router, prefix="/api", tags=["file"])

frontend_root = Path(__file__).resolve().parents[2] / "frontend"
frontend_dist = frontend_root / "dist"
frontend_assets = frontend_dist / "assets"

if frontend_assets.exists():
    app.mount("/assets", StaticFiles(directory=frontend_assets), name="assets")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def home() -> Response:
    dist_index = frontend_dist / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index)

    return JSONResponse(
        status_code=503,
        content={
            "message": "Frontend is now React and has not been built yet. Run npm install and npm run build inside frontend/."
        },
    )
