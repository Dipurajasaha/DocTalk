# DocTalk Codebase Context

## Current Snapshot
DocTalk is a FastAPI + Prisma + PostgreSQL backend with a React/Vite frontend. The current codebase is a healthcare platform for authenticated patient and doctor workflows, appointment and consultation management, protected medical asset storage, retrieval-augmented memory, and LangGraph-based AI/copilot workflows.

The main product surface is the FastAPI backend in `backend/` and the Vite app in `frontend/`. The `streamlit_app/` folder exists as an auxiliary app, but the current primary UI is the React frontend.

## Repository Layout

- `backend/` - FastAPI application package, services, workflows, copilot helpers, middleware, and core infrastructure.
- `frontend/` - React/Vite application, route shell, dashboards, viewers, and the browser API client.
- `prisma/schema.prisma` - authoritative database schema.
- `data/` - persistent runtime data, including uploads and database init scripts.
- `docker-compose.yml` - local PostgreSQL pgvector stack and pgAdmin.
- `requirements.txt` - backend Python dependencies.
- `package.json` - root Prisma config and dotenv dependency only.
- `frontend/package.json` - frontend dependencies and Vite scripts.

## Runtime And Build Expectations

- Backend startup is FastAPI through `backend.main:app`.
- Frontend development uses Vite (`npm run dev`) and production build uses `npm run build` inside `frontend/`.
- PostgreSQL should be available locally, typically via `docker-compose.yml`.
- The backend expects `DATABASE_URL`, `DIRECT_URL`, `SHADOW_DATABASE_URL`, and a JWT secret in non-development environments.
- `backend/core/config.py` resolves the workspace data root and loads `.env` from the repository root.
- For backend validation, use the workspace venv Python executable rather than relying on a global `uvicorn.exe`.

## Backend Architecture

### Entry Point And Cross-Cutting Concerns

- `backend/main.py` creates the FastAPI app, configures CORS, adds rate limiting middleware, and wires lifespan startup/shutdown.
- On startup, the app connects Prisma and ensures the RAG schema exists.
- Global handlers convert validation errors to a structured 422 response and unexpected exceptions to a generic 500.
- Health endpoints are `/health` and `/db-health`.

### Backend Package Roles

- `backend/api/` contains thin FastAPI routers.
- `backend/services/` contains business logic, database access, file handling, retrieval, and AI orchestration.
- `backend/workflows/` contains LangGraph orchestrations for report, prescription, x-ray, consultation, and doctor copilot flows.
- `backend/copilot/` contains clinician-facing supporting services such as patient overview and timeline composition.
- `backend/middleware/` contains bearer-auth and rate limit middleware.
- `backend/core/` contains settings, constants, Prisma connection helpers, logging, and JWT/security wiring.
- `backend/utils/` contains JWT and password helpers.
- `backend/vectorstore/` contains pgvector integration.

### Auth Model

- Authentication is bearer-token based.
- `backend/middleware/auth_middleware.py` reads `Authorization: Bearer <token>` and decodes the JWT payload.
- There is no cookie session auth in the current backend auth dependency chain.
- `CurrentUser` carries `user_id` and `role`, where `role` is either `patient` or `doctor`.

### Current API Surface

#### Auth Routes

`backend/api/auth/router.py` defines:

- `POST /api/auth/patient/signup`
- `POST /api/auth/patient/login`
- `POST /api/auth/doctor/signup`
- `POST /api/auth/doctor/login`
- `GET /me`
- `GET /doctor-only`
- `GET /patient-only`

The auth router is not mounted under an `/api/auth` prefix in `main.py`; the `/api/auth/...` paths are defined explicitly in the route decorators.

#### Patient Routes

`backend/api/patient/router.py` defines:

- `GET /api/patient/me`
- `PUT /api/patient/me`
- `GET /api/patient/{patient_id}` for doctor access only

#### Doctor Routes

`backend/api/doctor/router.py` defines:

- `GET /api/doctor/me`
- `PUT /api/doctor/me`
- `GET /api/doctor/list`
- `GET /api/doctor/copilot/consultations/{consultation_id}`
- `GET /api/doctor/copilot/patients/{patient_id}`

#### Appointment Routes

`backend/api/appointments/router.py` defines:

- `POST /api/appointments`
- `GET /api/appointments`
- `GET /api/appointments/patient/history`
- `GET /api/appointments/doctor/history`
- `PATCH /api/appointments/{appointment_id}/approve`
- `PATCH /api/appointments/{appointment_id}/reject`
- `PATCH /api/appointments/{appointment_id}/cancel`

#### Chat And Consultation Routes

`backend/api/chat/router.py` defines:

- `POST /api/chat/consultations`
- `GET /api/chat/consultations`
- `GET /api/chat/consultations/{consultation_id}`
- `POST /api/chat/consultations/{consultation_id}/messages`
- `GET /api/chat/consultations/{consultation_id}/messages`
- `POST /api/chat/consultations/{consultation_id}/analysis`

#### Medical Asset Routes

`backend/api/medical_images/router.py`, `backend/api/reports/router.py`, and `backend/api/prescriptions/router.py` each expose the same shape:

- `POST /api/<asset>/upload`
- `GET /api/<asset>`
- `GET /api/<asset>/{id}`
- `GET /api/<asset>/{id}/download`
- `DELETE /api/<asset>/{id}`
- `PATCH /api/<asset>/{id}`

Where `<asset>` is `medical_images`, `reports`, or `prescriptions`.

#### Processing Routes

`backend/api/processing/router.py` defines:

- `POST /api/processing/analyze-report`
- `POST /api/processing/analyze-prescription`
- `POST /api/processing/analyze-xray`

These routes accept JSON payloads with `asset_id` and `language`.

#### RAG Routes

`backend/api/rag/router.py` defines:

- `POST /api/rag/ingest`
- `POST /api/rag/search`
- `GET /api/rag/patient-memory`

#### AI Package State

- `backend/api/ai/__init__.py` only defines a router prefix (`/api/ai`) and currently has no concrete endpoints.
- There is no separate active `/api/ai/*` feature surface in the current backend routers.

### Core Backend Services

#### Appointment And Consultation Logic

- `backend/services/appointment_service.py` owns appointment create/list/approve/reject/cancel logic.
- Appointment create is patient-only and generates a custom string id from patient, doctor, date, time, and timestamp.
- Duplicate active appointments are rejected.
- Appointment statuses include `pending`, `requested`, `scheduled`, `completed`, `cancelled`, and `declined`.
- `backend/services/chat_service.py` owns consultation creation, listing, message send/history, and consultation analysis.
- A consultation is one-to-one with an appointment and is created from an appointment id.
- Messages are stored with sender role metadata and consultation history is paginated.
- `ChatService.analyze_consultation_context` builds a transcript from the most recent messages and invokes the patient chat workflow.
- For doctor requests, consultation analysis also triggers a best-effort doctor copilot timeline refresh.

#### Profile Services

- `backend/services/patient_service.py` handles patient profile fetch/update.
- `backend/services/doctor_service.py` handles doctor profile fetch/update and doctor listing/filtering.
- These services map snake_case API fields to Prisma camelCase columns.

#### Medical Asset Services

- `backend/services/file_service.py` is the shared storage/validation layer for reports, prescriptions, and medical images.
- `MedicalFileService` is the base class used by `ReportService`, `PrescriptionService`, and `MedicalImageService`.
- `backend/services/report_service.py`, `prescription_service.py`, and `medical_image_service.py` only configure file-type-specific storage and allowed MIME/extension sets.
- Stored files are written under `data/uploads/<asset_kind>/<patient_id>/<uuid>.<ext>`.
- Asset records store relative `storedPath` values, not absolute paths.
- Upload validation checks file name, MIME type, extension, size, and the saved file content.
- Invalid or corrupted image/PDF uploads are rejected with 422 rather than being left on disk.
- Deletion removes the Prisma record first and then unlinks the file.
- Rename only updates the original file name in metadata; it does not move the file on disk.

#### Processing And Workflow Services

- `backend/services/medical_processing_service.py` routes report/prescription/x-ray analysis through LangGraph workflows.
- `analyze_report`, `analyze_prescription`, and `analyze_xray` return the workflow `formatted_result` payload.
- `medical_processing_service` also ingests derived summaries into RAG when the workflow path supports it.
- `backend/services/rag_service.py` owns semantic memory storage, schema bootstrap, duplicate suppression, embedding writes, and scoped search.
- `backend/services/context_builder_service.py` assembles retrieval context from RAG plus recent consultation messages.
- `backend/services/response_formatter.py` normalizes AI outputs into stable summary/findings/recommendations/warnings structures.
- `backend/services/ai_service.py` uses Ollama when available and falls back to local heuristics if the provider is unavailable.

### Workflow Layer

- `backend/workflows/doctor_copilot_workflow.py` is a LangGraph flow with overview and timeline refresh steps.
- `backend/workflows/report_analysis_workflow.py`, `prescription_workflow.py`, and `xray_workflow.py` handle the medical analysis flows.
- `backend/workflows/patient_chat_workflow.py` handles consultation chat analysis.
- The workflow package is the coordination layer; services invoke workflows rather than embedding orchestration in routers.

### Copilot Layer

- `backend/copilot/patient_overview_service.py` and related copilot services build the clinician-facing summary payloads.
- Doctor copilot payloads include patient summary, recent consultations, recurring symptoms, medication history, recent reports, key findings, timeline, risk highlights, explainability, warnings, and metadata.
- Doctor copilot metadata includes workflow status, logs, timings, retries, and errors.
- The copilot layer is read-oriented and should be treated as informational support rather than an autonomous action system.

## Database And Storage

### Prisma Schema

The schema in `prisma/schema.prisma` is the source of truth.

Key models:

- `Patient` - primary key `username`, profile fields, JSONB history fields, relations to appointments, consultations, assets, RAG docs, and file keys.
- `Doctor` - primary key `doctorId`, profile fields, JSONB scheduling/chat state, relations to appointments, consultations, and file keys.
- `Appointment` - custom string primary key, links a patient and doctor, owns scheduling metadata and status.
- `Consultation` - UUID primary key, unique per appointment, owns message and asset relations.
- `Message` - consultation-scoped chat message with sender role and timestamp.
- `Report`, `Prescription`, `MedicalImage` - file metadata records with patient ownership, uploader metadata, optional consultation linkage, stored path, MIME type, and size.
- `RagDocument` - vector-backed semantic memory row.
- `FileKey` - encrypted file key mapping table present in the schema.

### Important Schema Notes

- `Report`, `Prescription`, and `MedicalImage` all use the same relational pattern.
- `Consultation.appointmentId` is unique.
- `RagDocument.embedding` is defined as `Unsupported("vector")` in Prisma and backed by pgvector in PostgreSQL.
- The schema still contains `publicKey`, `encryptedPrivateKey`, and `FileKey` columns/tables, but the currently visible upload/download services are based on auth and ownership checks, not a separate per-file encryption workflow.

### Storage Layout

- `data/uploads/medical_images/`
- `data/uploads/prescriptions/`
- `data/uploads/reports/`

Files are physically stored by patient id under each asset type directory. There is no backend folder hierarchy beyond that path segment.

### Database Bootstrapping

- `docker-compose.yml` uses `pgvector/pgvector:pg16` for PostgreSQL.
- `data/initdb/enable_extensions.sql` is mounted into the Postgres container for initial extension setup.
- `backend/services/rag_service.py` also attempts to create the `vector` extension and RAG table/indexes at runtime.

## Frontend Architecture

### App Shell And Routes

`frontend/src/App.jsx` defines the main routes:

- `/` - `Home`
- `/login` - `Login`
- `/patient/dashboard` - patient dashboard, protected by patient role
- `/doctor/dashboard` - doctor dashboard, protected by doctor role
- `/reports/:id` - report viewer, protected by any authenticated session
- `/prescriptions/:id` - prescription viewer, protected by any authenticated session

The route guards are local to `App.jsx` and are driven by the session context.

### Session And State Management

- `frontend/src/contexts/SessionContext.jsx` is the only global state provider in the current frontend.
- Session state is stored in local component state plus `localStorage` keys `doctalk_token` and `doctalk_session`.
- `SessionContext.bootstrap()` probes `/health` before checking stored token state.
- `authApi.me()` is used to verify the token and hydrate the user profile.
- The frontend treats logout as a client-side state clear because there is no server logout endpoint in the current backend.
- `markExpired()` clears stored credentials and shows the expired-session banner.

### API Client Structure

- `frontend/src/lib/apiClient.js` is a thin fetch wrapper with retries, JSON parsing, bearer injection, and a uniform `ApiError` type.
- `frontend/src/lib/api.js` centralizes auth, patient, doctor, and asset helper calls.
- `resolvePatientUploadTarget()` routes uploads by MIME/type hint.
- `resolvePatientAssetKind()` guesses an asset kind from stored metadata, file name, or MIME type.
- `patientApi.renameAsset()` tries report, prescription, and image rename routes in sequence to survive inconsistent asset typing.
- `doctorApi.dashboardData()` composes the dashboard client-side from appointments and consultations because there is no dedicated backend dashboard endpoint.

### Frontend Pages

- `frontend/src/pages/Home.jsx` is a marketing/landing page.
- `frontend/src/pages/Login.jsx` handles patient and doctor login/registration.
- `frontend/src/pages/PatientDashboard.jsx` is the largest patient workspace.
- `frontend/src/pages/DoctorDashboard.jsx` is the largest doctor workspace.
- `frontend/src/pages/ReportView.jsx` and `PrescriptionView.jsx` are dedicated record viewers.

### Patient Dashboard Architecture

PatientDashboard is organized into local panels rather than subroutes. The current panels are:

- `explain` - AI health assistant / document analysis UI.
- `documents` - asset browser with upload, preview, rename, and delete.
- `xray` - x-ray analysis panel.
- `appointments` - appointment booking and cancellation.
- `docchat` - patient-to-doctor consultation messaging.
- `profile` - profile edit form.

Important behavior:

- Assets are loaded by combining `listMedicalImages()`, `listReports()`, and `listPrescriptions()`.
- Uploads use `XMLHttpRequest` to show progress.
- Upload target selection is based on file type:
  - images -> `/api/medical_images/upload`
  - PDFs with prescription-like names -> `/api/prescriptions/upload`
  - other PDFs -> `/api/reports/upload`
- Client-side upload state includes a queue and progress indicators.
- Folder UI exists in the patient dashboard, but backend folder management is not implemented.
- `handleCreateFolder()` currently only alerts that folder management is unsupported.
- Patient document rename/delete flows are implemented against the asset-specific routes.
- File preview uses the shared `FileViewer` modal.
- Patient consultation chat uses consultation endpoints and polls every 5 seconds when active.
- Appointment booking uses `/api/appointments` and cancellation uses `/api/appointments/{id}/cancel`.

### Doctor Dashboard Architecture

DoctorDashboard is also local-tab driven. The current tabs are:

- `dashboard` - summary cards, chart, and schedule overview.
- `sessions` - schedule and appointment management.
- `patientchats` - consultation chat reader and sender.
- `assistant` - legacy AI assistant panel.
- `payments` - mostly static/mock UI.
- `settings` - profile settings UI.

Important behavior:

- Dashboard summary data is composed client-side from appointments and consultations.
- Session scheduling UI keeps slot state locally; it is not persisted by the backend.
- The payments view is mostly static/mock content.
- The assistant panel still uses legacy fetch calls rather than current backend copilot routes.
- Patient chat polling is used for message refresh.

### Viewer Architecture

- `frontend/src/components/FileViewer.jsx` is the shared preview modal.
- It fetches the protected download URL with the bearer token, creates a blob URL, and renders images or PDFs inline when possible.
- If the file cannot be previewed, it falls back to a direct download/open-in-new-tab link.
- `frontend/src/pages/ReportView.jsx` and `PrescriptionView.jsx` are dedicated pages that show metadata, preview, and a consultation attach selector.
- The attach actions currently depend on backend routes that are not implemented, so the UI treats 404 as unsupported.

### X-Ray Panel

- `frontend/src/components/XrayAnalyzerPanel.jsx` is still wired to a legacy `/api/analyze_xray` endpoint.
- The current backend route is `/api/processing/analyze-xray` and expects a stored `asset_id`, not a raw file upload.
- Treat the current x-ray panel as legacy until it is re-wired to the processing route.

### Frontend Styling And UI State

- Styling is split across `frontend/src/index.css` and `frontend/src/styles/*.css`.
- State management is mostly local `useState` and `useEffect` inside each page.
- There is no Redux/Zustand-style global store.
- React Router is the only routing layer.

## Current Implementation Stage

The current code matches the completed frontend work through stages 1-8 from `PLAN.md`.

- Stage 1 - authentication integration: complete.
- Stage 2 - RBAC and session UX: complete.
- Stage 3 - API surface mapping and client SDK: complete.
- Stage 4 - patient dashboard core flows: complete.
- Stage 5 - doctor dashboard core flows: complete.
- Stage 6 - consultation and chat UI polish: complete.
- Stage 7 - medical uploads, viewers, and privacy controls: complete.
- Stage 8 - reports and prescriptions viewer/linking: complete.
- Stage 9 - AI/copilot integration: next planned area, but not fully wired in the current frontend.
- Stage 10+ - real-time, cleanup, and production hardening: incomplete.

## Important Business Rules

- Patient and doctor identity values are not abstract numeric ids in the UI; patient ids are usernames and doctor ids are doctorId strings.
- Appointment creation is patient-only.
- Consultation creation is always tied to an appointment.
- Consultation access is limited to the owning patient and doctor.
- Doctor file uploads require an explicit consultation id and must belong to the doctor and patient on that consultation.
- Patient file uploads must be for the authenticated patient only.
- Medical assets are listed per patient for patients, and per consultation scope for doctors.
- RAG access is scoped to the authenticated requester and patient context.

## Known Backend Limitations And Unsupported Legacy Paths

These are present in the current frontend, but they are not canonical backend contracts:

- `POST /api/update_patient_profile`
- `GET /api/chat`
- `POST /api/explain_report`
- `POST /api/analyze_document`
- `GET /api/doctor_assistant_history`
- `POST /api/doctor_assistant_chat`
- `POST /api/doctor_schedule_request`
- `POST /api/doctor_complete_schedule`
- `GET /api/doctor_dashboard_data`
- `POST /api/appointment_request`
- `POST /api/analyze_xray`
- `POST /api/reports/{id}/attach`
- `POST /api/prescriptions/{id}/attach`

Current backend alternatives or reality:

- Patient profile updates belong on `PUT /api/patient/me`.
- Chat is consultation-based under `/api/chat/consultations/...`.
- Medical analysis is driven by `/api/processing/...` and RAG/workflow services.
- Doctor dashboard data is currently composed client-side from existing endpoints.
- Folder management is not implemented in the backend file service.
- Logout is client-side only.
- The AI router package exists, but `/api/ai/*` has no active endpoints yet.

## Stable Implementation Decisions

- Routes remain thin and delegate to services.
- Workflows own multi-step AI orchestration.
- Prisma is the schema source of truth.
- File uploads are handled through a shared file service with type-specific configuration.
- RAG is patient-scoped and consultation-aware.
- The frontend uses a single global session context and otherwise keeps state local to each page.
- Protected file access always goes through backend download endpoints plus bearer auth.
- The current upload/storage approach is filesystem-based, not object-storage-based.

## Validation Checklist

- Backend: run with the workspace venv Python and verify `/health` and `/db-health`.
- Frontend: `cd frontend && npm run build`.
- Local dev: `cd frontend && npm run dev` plus `python -m uvicorn backend.main:app --reload`.
- Database: confirm PostgreSQL is running with the pgvector image and that the `vector` extension is available.
- Asset flows: verify upload, download, rename, delete, and preview for images, reports, and prescriptions.
- Consultation flows: verify create/list/send/history for patient and doctor roles.

## Notes For Future Agents

- Prefer `backend/main.py`, `backend/services/`, and `backend/workflows/` when changing backend behavior.
- Prefer `frontend/src/lib/api.js` and `frontend/src/contexts/SessionContext.jsx` when changing frontend auth or API calls.
- If a frontend call uses a legacy endpoint, verify whether there is a real backend route before treating it as part of the current architecture.
- Keep the current route patterns and storage layout stable unless the backend is intentionally being redesigned.

---

This file is the primary long-term workspace memory for the current DocTalk codebase snapshot.