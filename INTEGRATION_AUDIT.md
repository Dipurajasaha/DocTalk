# Backend & Frontend Integration Audit

**Last updated:** 2026-06-06  
**Status:** Ready for runtime testing with `GEMINI_API_KEY` and PostgreSQL

---

## Executive Summary

| Area | Status |
|------|--------|
| Backend architecture | Sound |
| Frontend ↔ backend routes | Aligned for all active UI flows |
| LLM provider | **Gemini API only** (chat, vision, JSON, embeddings) |
| Local Ollama | Removed — no longer required |
| Build/import errors | None detected |
| Runtime blockers | `GEMINI_API_KEY` (AI), PostgreSQL credentials (DB endpoints) |

---

## LLM Provider Migration

All AI workloads now use the Google Gemini API via `backend/ai/core_services/gemini.py`:

| Feature | Implementation |
|---------|----------------|
| Patient/doctor chat (LangGraph) | `GeminiChatModel` / `gemini_complete_text` |
| Document classification | `gemini_complete_json` |
| X-ray analysis | `gemini_complete_image_json` |
| RAG embeddings | `gemini_embed_text` (`text-embedding-004`) |

Hash-based embedding fallback remains when `GEMINI_API_KEY` is unset.

---

## Backend Route Inventory

### System
| Method | Path | Status |
|--------|------|--------|
| GET | `/health` | ✅ |

### Auth (`/api/auth`, `/api`)
| Method | Path | Status |
|--------|------|--------|
| POST | `/api/auth/patient/login` | ✅ |
| POST | `/api/auth/patient/signup` | ✅ |
| POST | `/api/auth/doctor/login` | ✅ |
| POST | `/api/auth/doctor/signup` | ✅ |
| GET | `/api/me` | ✅ |

### Users & Doctors
| Method | Path | Status |
|--------|------|--------|
| GET/PUT | `/api/users/me` | ✅ |
| GET | `/api/doctor/list` | ✅ |

### Appointments
| Method | Path | Status |
|--------|------|--------|
| GET | `/api/appointments` | ✅ |
| POST | `/api/appointments/slots` | ✅ |
| GET | `/api/appointments/slots/{doctor_id}` | ✅ |
| POST | `/api/appointments/book/direct` | ✅ |
| POST | `/api/appointments/book/open` | ✅ |
| PUT | `/api/appointments/{id}/action` | ✅ |
| PATCH | `/api/appointments/{id}/cancel` | ✅ |

### Assets
| Method | Path | Status |
|--------|------|--------|
| GET/POST | `/api/assets`, `/api/assets/upload` | ✅ |
| GET/PATCH/DELETE | `/api/assets/{id}` | ✅ |
| GET | `/api/assets/{id}/download` | ✅ |

### Chat
| Method | Path | Status |
|--------|------|--------|
| GET/POST | `/api/chat/consultations/*` | ✅ |
| POST | `/api/chat/` | ✅ (LangGraph via `process_chat_message`) |
| GET | `/api/chat/ai/history` | ✅ |
| WS | `/api/chat/ai/patient/ws` | ✅ |
| WS | `/api/chat/ai/doctor/ws` | ✅ |
| WS | `/api/chat/consultations/{id}/messages` | ✅ |

### Legacy compat
| Method | Path | Status |
|--------|------|--------|
| POST | `/api/update_patient_profile` | ✅ |
| POST | `/api/explain_report` | ✅ |
| POST | `/api/analyze_document` | ✅ |
| POST | `/api/analyze_xray` | ✅ |

---

## Frontend ↔ Backend Alignment

### Active UI flows (all matched)

| Frontend call | Backend route |
|---------------|---------------|
| `authApi.me` → `/api/me` | ✅ |
| Appointments CRUD | `/api/appointments/*` ✅ |
| Assets CRUD + download | `/api/assets/*` ✅ |
| Consultations + messages | `/api/chat/consultations/*` ✅ |
| AI WebSockets | `/api/chat/ai/*/ws` ✅ |
| Document/X-ray analysis | `/api/analyze_*`, `/api/explain_report` ✅ |
| Health probe | `/health` ✅ (proxied in Vite dev) |

### Removed / unused frontend stubs

These were legacy fallbacks with no backend implementation and are no longer called:

- `/api/doctor_session`, `/api/patient_session`, `/me`
- `/api/appointment_request`
- `/api/doctor/copilot/*` (copilot uses WebSockets)

### Dev proxy (`frontend/vite.config.js`)

Proxied to `http://127.0.0.1:8000`:

- `/api` (with WebSocket support)
- `/health`
- `/static`
- `/me`

---

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `GEMINI_API_KEY` | For AI | Chat, vision, embeddings |
| `GEMINI_MODEL` | Optional | Default `gemini-2.0-flash` |
| `GEMINI_EMBED_MODEL` | Optional | Default `text-embedding-004` |
| `DATABASE_URL` | For DB endpoints | Match `docker-compose.yml` creds |
| `JWT_SECRET_KEY` | For auth | Any secure random string |

Prisma schema: `backend/prisma/schema.prisma`

---

## Runtime Validation Checklist

```powershell
# 1. Start database
docker compose up -d postgres

# 2. Generate Prisma client
python -m prisma generate --schema=backend/prisma/schema.prisma

# 3. Start backend
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 4. Health check
curl http://127.0.0.1:8000/health

# 5. Start frontend
cd frontend
npm run dev
```

Expected: `{"status":"ok","app":"DocTalk Backend","version":"1.0.0"}`

---

## Known Operational Notes

1. Without `GEMINI_API_KEY`, AI chat and analysis endpoints degrade gracefully.
2. RAG embedding dimension changed from 384 (Ollama) to 768 (Gemini). Re-upload documents if search quality drops after migration.
3. Backend startup catches DB connection failures and continues — non-DB routes still work.
4. `langchain-ollama` removed from `backend/requirements.txt`.
