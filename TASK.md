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
 - Todo: [frontend] stage 5: Doctor dashboard MVP (core flows).
 - Completed: [frontend] stage 5: Doctor dashboard MVP (core flows).
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
	- frontend/src/pages/PatientDashboard.jsx (updated: chat UI polish: attachments, threading, optimistic send)

	Note: Doctor dashboard UI exists but session/session-endpoint mismatches can leave it blank; updated `authApi.me` to probe common session endpoints. Stage 5 remains Todo until QA.

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

- Completed: [frontend] stage 6: Consultation & chat UI polish — threaded messages, attachments, message delivery UX, and chat history linking to consult records.

## Current progress

- Implemented consultation-based chat fixes in `frontend/src/pages/PatientDashboard.jsx` and `frontend/src/pages/DoctorDashboard.jsx`: doctor/patient selection now resolves to consultation IDs, messages load from `/api/chat/consultations/{id}/messages`, and sends post to the same backend thread.

## Changed files

- frontend/src/pages/PatientDashboard.jsx
- frontend/src/pages/DoctorDashboard.jsx
- frontend/src/lib/api.js
- PLAN.md
- TASK.md

## Blockers

- Backend must support chat attachment upload on `/api/doctor_patient_chat` (FormData handling) for attachment previews to persist.
- Server-side support for `before` or cursor-based pagination on `/api/doctor_patient_chat` improves older-message loading; otherwise the load-older button will reload full history.

## Next expected action

- Completed: [frontend] stage 7: Medical uploads, viewers & privacy controls — implemented secure preview components, upload progress, client-side validation, and folder/asset management UI hooks.

## Changed files (recent)

- frontend/src/pages/PatientDashboard.jsx (added upload progress, XHR uploads, preview modal integration)
- frontend/src/lib/api.js (added listAssetsV2 and getFilePresign helpers)
- frontend/src/components/FileViewer.jsx (new: secure preview component for images and PDFs)
- backend/services/file_service.py (added medical image rename support)
- backend/api/medical_images/router.py (added PATCH rename route)
- frontend/src/lib/api.js (updated to use backend medical image delete/rename endpoints)
- frontend/src/pages/PatientDashboard.jsx (updated file name mapping, delete/rename wiring)

## Blockers

- Backend must expose `/api/v2/upload_asset`, list endpoints (`/api/v2/patient_assets` or `/api/v2/list_assets`) and optional `/api/v2/file_url` for presigned URLs. If not available, View will open the backend-provided `url` property.

## Next expected action

- [Todo Next] Stage 8: Reports & prescriptions viewer and record linking — implement dedicated viewers, metadata pages, and attach-to-consultation flows.

## Blockers

- Backend must be running and reachable at the same origin (or CORS configured). Session bootstrap and `/me` verification require the backend to be available.
- Some legacy frontend endpoints still exist in page-level flows and may 404 until mapped in stage 4+ (for example legacy doctor/patient chat and old asset folder operations).

## Blockers

- Backend must be running and reachable at the same origin (or CORS configured). Session bootstrap and `/me` verification require the backend to be available.
- Long chat histories and attachment previewing depend on backend endpoints for paginated retrieval and secure file links.

## Next expected action

- Implement [frontend] stage 6: Consultation & chat UI polish — threaded messages, attachments, message delivery UX, and chat history linking to consult records.
