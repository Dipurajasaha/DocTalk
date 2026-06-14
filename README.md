# DocTalk

DocTalk is a healthcare consultation platform with a FastAPI backend and a Vite + React frontend. AI features (chat, document analysis, X-ray review, and RAG search) run through the **Google Gemini API** — no local LLM runtime is required.

## Project Structure

```
DocTalk/
├── backend/                 # FastAPI backend, Prisma schema, Python deps
│   ├── main.py
│   ├── api/
│   ├── ai/
│   ├── prisma/schema.prisma
│   └── requirements.txt
├── frontend/                # Vite + React SPA
├── data/                    # Uploaded assets and local storage
├── docker-compose.yml       # PostgreSQL + pgvector
├── .env.example             # Environment template
└── start_dev.bat            # Windows dev bootstrap
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop (for PostgreSQL)
- A [Gemini API key](https://aistudio.google.com/apikey)

## Quick Start

### 1. Environment

```powershell
copy .env.example .env
```

Edit `.env` and set at minimum:

- `GEMINI_API_KEY` — required for AI features
- `JWT_SECRET_KEY` — any long random string for dev
- `DATABASE_URL` — defaults to `postgresql://doctalk:doctalk@localhost:5432/doctalk`

### 2. Database

```powershell
docker compose up -d postgres
```

### 3. Backend

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
python -m prisma generate --schema=backend/prisma/schema.prisma
cd ..
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The Vite dev server proxies `/api`, `/health`, and `/static` to the backend on port 8000.

### One-command Windows bootstrap

```powershell
start_dev.bat
```

## Gemini Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `GEMINI_API_KEY` | — | Required for chat, vision, JSON analysis, embeddings |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Chat and structured analysis |
| `GEMINI_EMBED_MODEL` | `text-embedding-004` | RAG vector embeddings |
| `RAG_EMBEDDING_DIMENSION` | `768` | pgvector column size |

Without `GEMINI_API_KEY`, the API still starts but AI endpoints return graceful fallbacks (OCR-only document reads, hash-based embedding fallback for RAG).

## API Overview

| Area | Prefix |
|------|--------|
| Auth | `/api/auth/*`, `/api/me` |
| Users | `/api/users/*`, `/api/doctor/list` |
| Appointments | `/api/appointments/*` |
| Assets | `/api/assets/*` |
| Chat | `/api/chat/*` (REST + WebSockets) |
| Legacy AI | `/api/analyze_document`, `/api/analyze_xray`, `/api/explain_report` |
| Health | `/health` |

Interactive docs: `http://127.0.0.1:8000/docs`

## Frontend Routes

| Path | Page |
|------|------|
| `/` | Home |
| `/login` | Login / signup |
| `/patient/dashboard` | Patient portal |
| `/doctor/dashboard` | Doctor portal |
| `/reports/:id` | Report viewer |
| `/prescriptions/:id` | Prescription viewer |

## Production Build

```powershell
cd frontend
npm run build
```

FastAPI can serve `frontend/dist` when built. During development, run backend and frontend separately.

## Notes

- Prisma schema lives at `backend/prisma/schema.prisma`.
- Backend dependencies are in `backend/requirements.txt`.
- RAG uses PostgreSQL pgvector; changing `RAG_EMBEDDING_DIMENSION` after data exists may require re-ingesting documents.
