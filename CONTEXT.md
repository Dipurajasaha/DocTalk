# DocTalk Codebase Context

## Overview
DocTalk is a healthcare platform implemented as a Python FastAPI backend plus a React/Vite frontend. It includes secure patient and doctor workflows, appointment and consultation management, medical asset handling, RAG/semantic retrieval, AI-assisted clinical workflows, and Prisma/Postgres persistence.

## High-level architecture
- **Backend:** FastAPI application in `backend/`
- **Frontend:** React + Vite app in `frontend/`
- **Database:** Prisma schema in `prisma/schema.prisma` targeting PostgreSQL with `pgvector` support
- **Storage:** local filesystem under `data/uploads/` for medical assets and report files
- **AI & retrieval:** LangChain, LangGraph, local AI routing, vector search, and service-level prompt/context assembly

## Root-level files
- `README.md` — high-level project instructions and legacy architecture notes
- `package.json` — root package dependencies for frontend tooling and Prisma
- `requirements.txt` — backend Python dependencies
- `docker-compose.yml` — optional compose configuration (not inspected in detail here)
- `start_dev.bat` — development startup script
- `CONTEXT.md` — this repository context summary

## Backend structure
`backend/` contains the application package and runtime code.

### Main entrypoint
- `backend/main.py` — creates FastAPI `app`, registers routers, configures CORS and rate limiting, manages lifespan startup/shutdown, connects to Prisma, and exposes health checks.

### Packages and modules
- `backend/api/` — FastAPI route modules for authentication, patient, doctor, appointments, chat, medical assets, AI/RAG, processing, and reporting
- `backend/services/` — business logic and domain services such as AI, appointment, auth, chat, context building, doctor/patient workflows, embeddings, file processing, medical image analysis, prescription handling, retrieval, reports, summaries, and safety
- `backend/workflows/` — higher-level orchestration graphs and workflow coordination for doctor copilot, patient chat, prescriptions, reports, and x-ray processing
- `backend/core/` — shared configuration, constants, database connection helpers, logging, and security utilities
- `backend/middleware/` — request middleware, including authentication and rate limiting
- `backend/utils/` — JWT and password utilities
- `backend/vectorstore/` — vector store integration, including `pgvector_service.py`
- `backend/copilot/` — medical copilot services for clinical risk, medication history, patient overview, symptom progression, and timeline
- `backend/agents/` — agent definitions for doctor assistant, summarizer, and triage workflows

### Backend dependencies
- `fastapi`
- `uvicorn[standard]`
- `python-multipart`
- `pydantic`
- `itsdangerous`
- `python-dotenv`
- `prisma`
- `PyJWT`
- `bcrypt`
- `Pillow`
- `requests`
- `PyMuPDF`
- `httpx`
- `langchain`
- `langchain-core`
- `langgraph`

## Frontend structure
`frontend/` contains the React/Vite application.

### Source layout
- `frontend/src/App.jsx` — main app shell
- `frontend/src/main.jsx` — React bootstrapping entrypoint
- `frontend/src/index.css` — global styles
- `frontend/src/pages/` — page-level routes and views
- `frontend/src/components/` — UI components
- `frontend/src/lib/` — lightweight API client and endpoint helper wrappers
- `frontend/src/styles/` — reusable style assets

### Frontend dependencies
- Only `dotenv` is declared in `frontend/package.json`
- `prisma` is included as a dev dependency for schema tooling

## Data, persistence, and storage
- `prisma/schema.prisma` — authoritative database schema for PostgreSQL and pgvector
- `data/initdb/enable_extensions.sql` — SQL for enabling database extensions such as `pgvector`
- `data/uploads/medical_images/` — storage for medical image files
- `data/uploads/prescriptions/` — storage for prescription files
- `data/uploads/reports/` — storage for report files

## Key domain areas
- **Authentication:** JWT-based user authentication, role-aware access control, and patient/doctor security boundaries
- **Appointments & consultations:** scheduling, visit management, chat threads, and clinical review workflows
- **Medical assets:** image, report, and prescription upload metadata, secure access, and file storage
- **AI/RAG:** retrieval-augmented generation, semantic memory, context assembly, and AI route handling
- **Clinical workflows:** doctor copilot, patient chat, prescription analysis, report generation, and x-ray analysis
- **Database & vector search:** Prisma + PostgreSQL with `pgvector` for embeddings and contextual retrieval

## Important notes for future development
- The backend application is assembled via `backend.main.py`; route modules are mounted directly in the `FastAPI` app.
- Database lifecycle hooks connect/disconnect Prisma and ensure the RAG schema is present at startup.
- Service modules implement the core domain logic; route handlers should remain thin and delegate to services/workflows.
- Workflows in `backend/workflows/` appear to be the coordination layer for multi-step AI and clinical tasks.
- `backend/copilot/` services provide specialized clinical reasoning support and likely integrate with the AI prompt/context layers.

## Recommended startup commands
1. Activate Python virtual environment.
2. Install backend dependencies: `pip install -r requirements.txt`
3. Install frontend dependencies: `cd frontend && npm install`
4. Start backend during development: `python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000`
5. Start frontend dev server: `cd frontend && npm run dev`

## Notes for an agent
- This repo is primarily backend-first with a separate frontend app.
- Use `backend/main.py` as the backend entry point for API route discovery and service wiring.
- Check `backend/api/`, `backend/services/`, and `backend/workflows/` first for business logic changes.
- Preserve existing role-based access patterns and patient/doctor scoping when extending endpoints.
- Verify Prisma schema changes in `prisma/schema.prisma` and any required database extension setup in `data/initdb/enable_extensions.sql`.

# Architecture Rules
- Routes stay thin
- Business logic in services
- Workflows orchestrate services
- Agents wrap workflows/services
- AI isolated in ai_service.py
- Prisma schema is source of truth
- RAG must enforce patient isolation

# Coding Conventions
- Prefer async
- Reuse existing services
- Avoid duplicate workflows
- Avoid direct Prisma in routes
- Keep APIs typed and structured

# Current System Status
- Backend stabilized
- Ollama local stack active
- Contextual RAG active
- LangGraph workflows active
- Doctor copilot active
- Current focus: frontend integration
- Frontend integration status: stages 1-8 are complete; stage 9 is the next active stage.
- Patient dashboard now supports routed uploads, document viewers, and rename flows for medical images, reports, and prescriptions.
---

*Generated as a workspace-wide context summary for DocTalk.*
