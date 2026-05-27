# Frontend Modernization Strategy

The project already contains an existing frontend implementation.

The goal is:
- integrate the existing frontend with the stabilized backend
- incrementally modernize architecture and UX
- preserve reusable UI/components where possible
- avoid unnecessary rewrites
- prioritize stability and feature completion

[Completed] [frontend] stage 1: ***authentication integration***

- objective: Integrate and refactor the existing React frontend with the backend JWT/session model so users can login, register, and maintain an authenticated session.
- features:
  - Login and registration flows for `patient` and `doctor`.
  - Session persistence (cookie or Authorization header) and client-side session checks.
  - Redirects to appropriate dashboards on login.
- frontend areas affected:
  - frontend/src/pages/Login.jsx
  - frontend/src/App.jsx (route guards)
  - frontend/src/main.jsx (session bootstrap)
- backend APIs involved:
  - POST /api/login
  - POST /api/register
  - GET /api/patient_session
  - GET /api/doctor_session
- expected output:
  - Working login/register redirecting to /patient/dashboard or /doctor/dashboard.
  - Client stores/requests session credentials consistently (cookies or Authorization).
- validation/testing goals:
  - Manual: register + login as patient and doctor; verify redirects and protected route access.
  - Automated: add a small integration test that fetches `/api/patient_session` before/after login.

[Completed] [frontend] stage 2: ***RBAC & session UX flow***

- objective: Enforce role-based navigation and client-side flows (menu, visibility, route guards) and handle expired sessions gracefully.
- features:
  - Route guards and role-aware UI elements (hide doctor controls for patients and vice-versa).
  - Central session context/provider with role and basic profile.
  - Clear session-expired UX with re-login flow.
- frontend areas affected:
  - frontend/src/App.jsx (route-level protection)
  - Add `frontend/src/contexts/SessionContext.jsx` (lightweight provider)
  - frontend/src/pages/* for conditional UI
- backend APIs involved:
  - GET /api/patient_session
  - GET /api/doctor_session
  - POST /api/logout (if implemented) or token invalidation endpoint
- expected output:
  - Role-specific navigation and guarded routes; UX shows session-expired and redirects to login.
- validation/testing goals:
  - Manual: attempt to access doctor routes as patient and confirm redirect/403 handling.
  - Unit: session provider tests for correct state transitions.

[Completed] [frontend] stage 3: ***API surface mapping & lightweight client SDK***

- objective: Create a minimal client-side API layer to centralize calls, error handling, and consistent headers/credentials.
- features:
  - `apiClient` wrapper around fetch with centralized error, retries and JSON parsing.
  - Typed small helper functions for common endpoints.
- frontend areas affected:
  - frontend/src/lib/apiClient.js (new)
  - Refactor existing fetch calls in pages to use the client.
- backend APIs involved (initial):
  - /api/my_appointments
  - /api/doctors
  - /api/patient_assets or /api/v2/* asset endpoints
  - /api/doctor_patient_chat and chat endpoints
  - /api/doctor_dashboard_data
- expected output:
  - Consistent API usage across the app, easier retries and global error handling.
- validation/testing goals:
  - Smoke test all refactored pages to ensure parity with previous behavior.
  - Add a small mock-based test for `apiClient` error and retry logic.

[Completed] [frontend] stage 4: ***Patient dashboard MVP (core flows)***

- objective: Deliver a stable, testable patient dashboard with appointment listing, file uploads, and basic chat entry points.
- features:
  - Appointment list & booking UI (read/write to appointments API).
  - Medical assets browser and upload (folders, files) using existing asset endpoints.
  - Launch paths to consult AI explain panel and patient chat.
- frontend areas affected:
  - frontend/src/pages/PatientDashboard.jsx
  - frontend/src/components/XrayAnalyzerPanel.jsx (reuse)
  - frontend/src/styles/patient.css
- backend APIs involved:
  - GET /api/my_appointments
  - POST /api/appointment_request or /api/appointments
  - /api/v2/upload_asset, /api/v2/create_folder, /api/v2/delete_asset, /api/v2/rename_asset
  - /api/doctor_patient_chat (to link to chat)
- expected output:
  - Patient can view appointments, upload files, create folders, and open chat/AI flows.
- validation/testing goals:
  - Manual: upload/download/delete file cycle; create appointment request; basic chat message sends.
  - Basic end-to-end script that runs a happy-path scenario.

[Completed] [frontend] stage 5: ***Doctor dashboard MVP (core flows)***

- objective: Deliver a stable doctor dashboard: schedule view, patient queue, chat, and simple assistant panel.
- features:
  - Calendar view with upcoming schedules and requests.
  - Patient queue and chat reader with message posting.
  - Simple assistant/copilot panel that shows generated notes (read-only initially).
- frontend areas affected:
  - frontend/src/pages/DoctorDashboard.jsx
  - frontend/src/components/StructuredReply.jsx
  - frontend/src/styles/doctor.css
- backend APIs involved:
  - GET /api/doctor_dashboard_data
  - /api/doctor_patient_chat
  - appointment approval endpoints (if present) and /api/processing for consult review
- expected output:
  - Doctor can see and manage a daily schedule, read patient chats, and view assistant outputs.
- validation/testing goals:
  - Manual: doctor login -> view dashboard -> open patient chat -> confirm data matches backend.

[Todo Next] [frontend] stage 6: ***Consultation & chat UI polish***

- objective: Build the consultation experience — threaded messages, attachments, message delivery UX, and chat history linking to consult records.
- features:
  - Persistent consultation thread UI with message grouping, timestamps, and read receipts (visual only).
  - Attachment previews for reports/prescriptions/images and quick actions (download, analyze).
  - Chat input with upload, language selection, and disabled state handling.
- frontend areas affected:
  - frontend/src/pages/PatientDashboard.jsx (docchat flows)
  - frontend/src/pages/DoctorDashboard.jsx (patientchats)
  - frontend/src/components/* chat/message components
- backend APIs involved:
  - /api/doctor_patient_chat (GET/POST)
  - File retrieval endpoints that serve protected files
  - Consultation-related endpoints in /api/appointments or /api/consultations (if present)
- expected output:
  - Smooth chat UX with attachment handling and stable, paginated histories.
- validation/testing goals:
  - Manual: long-history consultation loads; upload image and confirm server-side metadata appears.
  - Performance check: lazy-load older messages and verify render performance.

[Incomplete] [frontend] stage 7: ***Medical uploads, viewers & privacy controls***

- objective: Harden file upload, preview, and secure access patterns to match backend ownership checks and storage.
- features:
  - Secure preview components for PDF, images (medical_images), and prescription files.
  - Upload progress, resumable fallback and client-side basic validation (size, type).
  - Folder/asset management UI with clear ownership and delete/rename flows.
- frontend areas affected:
  - frontend/src/pages/PatientDashboard.jsx
  - frontend/src/components (new viewer components)
  - frontend/src/styles/*
- backend APIs involved:
  - /api/v2/upload_asset
  - /api/v2/ patient_assets and file retrieval
  - /api/file_keys or signed URL endpoints if present
- expected output:
  - Robust upload UX and in-app previews that respect auth and patient isolation.
- validation/testing goals:
  - Manual: upload a variety of files; preview in-browser; verify access denied for other users.
  - Security: attempt file access without credentials and confirm 401/403 responses.

[Incomplete] [frontend] stage 8: ***Reports & prescriptions viewer and record linking***

- objective: Provide dedicated viewers for reports and prescriptions and link them to consultations and copilot summaries.
- features:
  - Report detail page with metadata, download, and contextual RAG notes.
  - Prescription viewer with medication list extraction UI (read-only) and link to prescription analysis if available.
  - UI affordances to attach reports/prescriptions to consultations.
- frontend areas affected:
  - New pages: frontend/src/pages/ReportView.jsx and PrescriptionView.jsx
  - Patient/Doctor dashboards for linking actions
- backend APIs involved:
  - /api/reports (GET detail) and /api/prescriptions
  - /api/prescription_analysis (if available) and rag/retrieval endpoints for context
- expected output:
  - Users can view/download reports and prescriptions in a dedicated reader and see copilot notes tied to the file.
- validation/testing goals:
  - Manual: open report -> see metadata and content; attach to consultation and verify backend link.

[Incomplete] [frontend] stage 9: ***AI / Copilot integration (read-first then action)***

- objective: Integrate the frontend with the existing copilot/AI workflows in a conservative, auditable way (read-only outputs first).
- features:
  - Assistant panel shows copilot outputs (timeline, medication history, risk summary) with provenance metadata.
  - Request UI for doctor to ask targeted questions and a queueing UX while workflows run.
  - Safe display: show model source, confidence, and link to underlying documents.
- frontend areas affected:
  - frontend/src/components/StructuredReply.jsx
  - Doctor and Patient dashboard assistant panels
  - New modal for reviewing copilot reasoning and attaching to consult notes
- backend APIs involved:
  - /api/ai/* and /api/rag/* endpoints (copilot/workflows)
  - /api/processing or workflow endpoints that trigger LangGraph jobs
- expected output:
  - Non-destructive copilot outputs: doctors can view and optionally copy suggestions into visit notes (manual step).
- validation/testing goals:
  - Manual: run copilot for sample patient; verify provenance fields and no write actions occur without explicit doctor action.
  - UX test: ensure outputs are readable on mobile and accessible.

[Incomplete] [frontend] stage 10: ***real-time communication & notifications (incremental)***

- objective: Add near-real-time chat updates and in-app notifications with a progressive enhancement approach (polling → SSE/WebSocket).
- features:
  - Short-interval polling fallback (already present) hardened with exponential backoff.
  - Add Server-Sent Events (SSE) or WebSocket client wrapper behind a flag for live tests.
  - Notification center for new messages, appointment changes, and copilot results.
- frontend areas affected:
  - frontend/src/lib/realTimeClient.js (new)
  - Patient/Doctor dashboard polling loops → replace with event-driven handlers when stable
  - UI badge/notification component
- backend APIs involved:
  - Existing chat endpoints for message send/receive
  - If available: SSE/WebSocket endpoints or a small new endpoint to expose SSE
- expected output:
  - Live-feeling chat with graceful fallback and notifications for critical events.
- validation/testing goals:
  - Manual: verify message arrives within target timeframe with SSE and falls back to polling when SSE fails.
  - Load test: basic concurrency check for real-time endpoint.

[Incomplete] [frontend] stage 11: ***frontend architecture cleanup & state management***

- objective: Consolidate state and patterns into maintainable structure suitable for solo development and incremental scaling.
- features:
  - Introduce a small, explicit state management pattern (React Context + hooks or Zustand) focused on session, notifications, and asset cache.
  - Reorganize `frontend/src` into `pages/`, `components/`, `lib/`, `contexts/`, `styles/` where missing.
  - Add lint/format scripts and a README with frontend development notes.
- frontend areas affected:
  - Project root and many small files; primarily an internal refactor with no user-facing changes.
- backend APIs involved:
  - None (refactor only)
- expected output:
  - Clear developer ergonomics, easier onboard for future contributors, and predictable state flows for the app.
- validation/testing goals:
  - Manual smoke tests across the app to ensure no regressions.
  - Add a few snapshot tests for critical components and basic lint/format verification.

[Incomplete] [frontend] stage 12: ***security, error handling, responsive polish & deployment readiness***

- objective: Final pass for UX polish, security hardening, accessibility, and production build readiness.
- features:
  - Global error and loading UX: centralized toasts, skeletons, and retry affordances.
  - Defensive client-side validation for uploads and form inputs.
  - Responsive CSS fixes for mobile/tablet and WCAG basics.
  - Build and CI checklist: `npm run build`, small smoke-run against local backend, and Docker-ready static site serving instructions.
- frontend areas affected:
  - App shell, error boundaries, global styles, and build scripts (`frontend/package.json`).
- backend APIs involved:
  - Health check endpoints (`/health`, `/db_health`) for deploy smoke tests and any file-serving endpoints for production static assets.
- expected output:
  - Production-ready frontend build, documented deploy steps, and validated end-to-end flows.
- validation/testing goals:
  - Pre-deploy smoke test script: build + run static preview + exercise login + fetch a small set of APIs.
  - Accessibility and responsive QA checklist (manual + Lighthouse spot checks).

Notes and sequencing principles

- Keep changes incremental and testable: each stage must produce a working snapshot that can be manually QA'd.
- Prioritize stability and parity with backend: prefer adapting frontend to existing API shapes rather than backend changes.
- Start with core auth/session work and API client (Stages 1–3), then parallelize patient and doctor dashboard work (Stages 4–6).
- Delay write-heavy AI actions until a conservative read-only copilot UX exists (Stage 9) to reduce risk.
- Use progressive enhancement for real-time features: keep polling as a safe fallback (Stage 10).
- Target small, verifiable deliverables a solo dev can complete within a few days per stage.

Estimate (solo developer, approximate)

- Stages 1–3: 3–6 days
- Stages 4–6: 7–12 days
- Stages 7–9: 6–10 days
- Stages 10–12: 5–9 days

Acceptance criteria (example)

- Auth: login+session persist works for both roles and guards routes.
- Patient: upload, list, appointment flows function end-to-end.
- Doctor: calendar, queue, and patient chat display correct data.
- AI: copilot outputs are readable, labelled, and do not alter records without explicit action.
- Security: unauthorized file access is blocked; session expiry is handled gracefully.

-- End of plan
