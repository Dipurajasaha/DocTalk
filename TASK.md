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
- Changed files:
	- frontend/src/main.jsx
	- frontend/src/App.jsx
	- frontend/src/pages/Login.jsx
	- PLAN.md (stage status updates)

## Blockers

- Backend must be running and reachable at the same origin (or CORS configured). The session bootstrap depends on cookie-based auth endpoints: `/api/patient_session` and `/api/doctor_session`.

## Next expected action

- Implement [frontend] stage 2: RBAC & session UX flow — add a small `SessionContext`, route-level protections, and graceful session-expired UX.
