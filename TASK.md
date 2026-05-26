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
- Changed files:
	- frontend/src/main.jsx
	- frontend/src/App.jsx
	- frontend/src/pages/Login.jsx
	- frontend/src/contexts/SessionContext.jsx (new)
	- frontend/src/lib/apiClient.js (new)
	- frontend/src/lib/api.js (new)
	- frontend/src/pages/PatientDashboard.jsx
	- frontend/src/pages/DoctorDashboard.jsx
	- PLAN.md (stage status updates)
	- TASK.md (this file)

## Recent Fixes (post-validation)

- Applied minimal runtime fixes for Stage 3 validation:
  - Ensured protected API helpers include `auth: true` for appointments, medical images, consultations, and doctor dashboard.
  - Added defensive null/malformed-JSON handling in `SessionContext.jsx` and `Login.jsx`.
  - Added safe guards and `.catch()` handlers in critical dashboard loaders to avoid uncaught promise rejections and trigger session-expired flow on 401/403.

## Blockers

- Backend must be running and reachable at the same origin (or CORS configured). Session bootstrap and `/me` verification require the backend to be available.
- Some legacy frontend endpoints still exist in page-level flows and may 404 until mapped in stage 4+ (for example legacy doctor/patient chat and old asset folder operations).

## Next expected action

- Implement [frontend] stage 4: Patient dashboard MVP (core flows) — complete appointment list/booking, document upload/list/delete flows, and stable patient chat entry points using current backend contracts.
