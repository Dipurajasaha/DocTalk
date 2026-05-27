# Current Task
Frontend integration

# Goal
Connect old frontend with new backend APIs

# Scope
- authentication
- consultations
- doctor dashboard
- chat
- reports

# Files Expected
frontend/src/pages/
frontend/src/components/
frontend/src/api/

# Constraints
- do not rewrite backend
- reuse existing APIs
- preserve RBAC

## Progress (updated)

- Completed: [frontend] stage 1: authentication integration.
- Completed: [frontend] stage 2: RBAC & session UX flow.
- Completed: [frontend] stage 3: API surface mapping & lightweight client SDK.
 - Completed: [frontend] stage 4: Patient dashboard MVP (core flows).
- Changed files:
	- frontend/src/main.jsx
	- frontend/src/App.jsx
	- frontend/src/pages/Login.jsx
	- frontend/src/contexts/SessionContext.jsx (new)
	- frontend/src/lib/apiClient.js (new)
	- frontend/src/lib/api.js (new)
	- frontend/src/pages/PatientDashboard.jsx
	- frontend/src/pages/DoctorDashboard.jsx
	- frontend/src/lib/api.js (updated: added v2 asset & appointment helpers)
	- frontend/src/pages/PatientDashboard.jsx (updated: v2 asset ops, appointment booking, chat wrappers)
	- PLAN.md (stage status updates)
	- TASK.md (this file)

## Recent Fixes (post-validation)

- Applied minimal runtime fixes for Stage 3 validation:
  - Ensured protected API helpers include `auth: true` for appointments, medical images, consultations, and doctor dashboard.
  - Added defensive null/malformed-JSON handling in `SessionContext.jsx` and `Login.jsx`.
  - Added safe guards and `.catch()` handlers in critical dashboard loaders to avoid uncaught promise rejections and trigger session-expired flow on 401/403.

## New Changes (stage 4)

- Implemented Patient dashboard MVP wiring (core flows):
	- Appointment listing: `patientApi.listMyAppointments` with fallback to `listAppointments`.
	- Appointment booking: `patientApi.requestAppointment` called from UI.
	- Asset upload & management: v2 wrappers `uploadAssetV2`, `createFolderV2`, `deleteAssetV2`, `renameAssetV2` and replaced legacy fetch calls with these helpers.
	- Doctor chat: added `getDoctorPatientChat` and `postDoctorPatientChat` helpers and wired patient chat UI to them.

## Blockers

- Backend must be running and reachable at the same origin (or CORS configured). The patient dashboard relies on protected endpoints (`/api/my_appointments` or `/api/appointments`, `/api/appointment_request`, `/api/v2/*` asset ops, `/api/doctor_patient_chat`).
- Some legacy endpoints may still be present in code paths (explain/upload/analysis flows) and may require further mapping in Stage 4+ iterations.

## Next expected action

- Implement [frontend] stage 5: Doctor dashboard MVP (core flows) — calendar, patient queue, chat, and assistant panel.

## Blockers

- Backend must be running and reachable at the same origin (or CORS configured). Session bootstrap and `/me` verification require the backend to be available.
- Some legacy frontend endpoints still exist in page-level flows and may 404 until mapped in stage 4+ (for example legacy doctor/patient chat and old asset folder operations).

## Next expected action

- Implement [frontend] stage 4: Patient dashboard MVP (core flows) — complete appointment list/booking, document upload/list/delete flows, and stable patient chat entry points using current backend contracts.
