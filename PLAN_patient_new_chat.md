# Plan: Let patients create new AI chat sessions

**STATUS: IMPLEMENTED + 2 post-rollout bug fixes applied.** See "Fixes applied (post-implementation)" at the bottom.

## Goal
Today a patient has exactly one AI chat ("Analyze Report" / AI Health Assistant panel).
The websocket and analyze endpoints hardcode a single session id `patient_ai_{user_id}`,
so a patient can only ever talk in that one session. We let a patient:

1. Create a **new** chat (new `AiChatSession` row in the DB).
2. See a list of their AI chats and switch between them.
3. Have every AI interaction (streaming chat + document/report analysis) write to the
   currently-selected session.

The "+" trigger is on the **Analyze Report** sidebar button, with a session dropdown +
delete (×) in the AI panel header.

## Current behaviour (findings)

- DB model already exists: `AiChatSession` (`backend/prisma/schema.prisma:367`) with
  `id, userId, role, mode, targetPatientId, title, createdAt, updatedAt` and a `messages`
  relation to `AiChatMessage` (`onDelete: Cascade`). **`title` is already present but unused**
  → no schema change strictly required. (No `migrations/` folder exists; project uses
  `prisma db push`.)
- Patient AI websocket: `backend/api/chat/router.py:739` →
  `_run_ai_websocket(..., ai_session_id="patient_ai", expected_role="patient")`.
  Inside `_run_ai_websocket` (line 506) the generic id is rewritten to
  `patient_ai_{user_id}`. There was no way to target a specific session.
- AI history REST: `GET /api/chat/ai/history` (router.py:719) also collapses
  `patient_ai` → `patient_ai_{user_id}`.
- Document analysis: `POST /api/analyze_document` (`backend/api/compat.py:206`) accepts an
  `ai_session_id` form field but **ignored it** and forced `patient_ai_{user_id}`.
- Report analysis: `POST /api/explain_report` (`backend/api/compat.py`) did NOT accept
  `ai_session_id` at all and also forced `patient_ai_{user_id}`; it is the endpoint the
  upload path (`handleExplainUpload`) actually calls.
- Service layer: `ChatService.ensure_ai_session` (upsert), `get_ai_chat_history`,
  `append_ai_chat_exchange` in `backend/services/chat_service.py`.
- Frontend patient chat lives in `PatientDashboard.jsx` panel `activePanel === 'explain'`:
  - `loadChatHistory()` → `patientApi.getAiChatHistory('patient_ai')`.
  - `handleChatSubmit()` → `buildAiChatWebSocketUrl({ role:'patient', token })`.
  - `handleAnalyzeSelected()` posts `ai_session_id: 'patient_ai'`.
  - `handleExplainUpload` calls `/api/explain_report` without any session id.
  - `buildAiChatWebSocketUrl` in `frontend/src/lib/realTimeClient.js:8`.
  - `patientApi.getAiChatHistory` in `frontend/src/lib/api.js`.
  - Sidebar "Analyze Report" button.

## Design decisions

- **Session id scheme:** keep the existing chat working by treating
  `patient_ai_{user_id}` as the implicit "default" session. New chats get a unique id
  `patient_ai_{user_id}_{uuid4hex}`. This keeps back-compat and makes ownership easy to
  validate by id shape + DB `userId` check.
- **Ownership validation (required for security):** now that the client sends a session id,
  every path (websocket, history, analyze, delete) verifies the session belongs to the
  current user: the row's `userId == current_user.user_id` and `role == current_user.role`
  (or the id equals the default `patient_ai_{user_id}`, which we auto-create). The
  shared helper `get_owned_ai_session(user_id, role, ai_session_id)` does this; the
  websocket closes with `1008` / history/analyze return `403` when not owned.
- **Titles:** default `"New Chat"`. When the first user message is sent, the title is set
  to a trimmed prefix of that message. This is implemented inside
  `append_ai_chat_exchange` (which already receives `user_message`) by calling
  `set_ai_session_title_if_empty` when a non-empty `user_message` is present — no extra
  endpoint needed.
- **Default-session flag:** `AiSessionResponse` carries an `is_default` boolean so the UI
  can disable deletion / guard only the real default session. The id shape
  `patient_ai_{user_id}_{hex}` cannot be distinguished from `patient_ai_{user_id}` by a
  prefix check alone, so the flag comes from the backend.
- **No prisma schema migration needed** — reuse `AiChatSession`/`title`. We only add
  service + API + UI code. (Will run `prisma generate` to be safe.)

---

## Backend changes

### 1. `backend/services/chat_service.py`
Added methods:

- `list_ai_sessions(user_id, role)`:
  ```python
  sessions = await self.client.aichatsession.find_many(
      where={"userId": user_id, "role": role},
      order={"updatedAt": "desc"},
  )
  default_id = self._default_ai_session_id(user_id, role)
  return [self._serialize_ai_session(s, is_default=str(s.id) == default_id) for s in sessions]
  ```
- `create_ai_session(user_id, role, title=None, mode="PATIENT")`:
  - id `f"{'patient_ai' if role=='patient' else 'doctor_ai'}_{user_id}_{uuid4().hex}"`
  - `self.client.aichatsession.create(...)` with `title or "New Chat"`, `is_default=False`.
  - return serialized session.
- `get_owned_ai_session(user_id, role, ai_session_id)`:
  - generic ids (`patient_ai`/`doctor_ai`) resolve to the user-scoped default.
  - fetch by id; return `None` if missing or `userId != user_id` / `role != role`.
  - Used by websocket/history/analyze/delete to authorize.
- `set_ai_session_title_if_empty(ai_session_id, title)`: update title only when currently
  null / "New Chat". Called from `append_ai_chat_exchange` when `user_message` is present.
- `delete_ai_session(user_id, role, ai_session_id)`:
  - reject the default session (`patient_ai`/`doctor_ai`/the scoped default) with 400.
  - verify ownership (404 if not owned), then **explicitly** delete child messages via
    `aichatmessage.delete_many(where={"sessionId": id})` before
    `aichatsession.delete` (defensive: guarantees success even if the DB-level FK cascade
    is not enforced).
- `_serialize_ai_session(record, *, is_default=False)` →
  `{ id, title, mode, is_default, created_at, updated_at }`.
- `_default_ai_session_id(user_id, role)` helper.

### 2. `backend/schemas/chat_schemas.py`
Added pydantic models:
- `AiSessionResponse { id, title, mode, is_default, created_at, updated_at }`
- `AiSessionCreateRequest { title: str | None }`

### 3. `backend/api/chat/router.py`
New REST endpoints (all `Depends(get_current_user)` + `get_chat_service`):

- `GET  /api/chat/ai/sessions` → `list_ai_sessions(...)`. Ensures the default session row
  exists first (calls `ensure_ai_session` for `patient_ai_{user_id}`) so the existing chat
  always appears in the list.
- `POST /api/chat/ai/sessions` (body `AiSessionCreateRequest`) → `create_ai_session(...)`.
- `DELETE /api/chat/ai/sessions/{ai_session_id}` → `delete_ai_session(...)`.

Modified:
- `_run_ai_websocket(...)`: reads the real session id from
  `websocket.query_params.get("ai_session_id")`. Generic id → scoped default
  (`f"{base}_{user_id}")`; explicit id → `get_owned_ai_session` ownership check, else
  `websocket.close(code=1008)`.
- `patient_ai_websocket` / `doctor_ai_websocket`: pass
  `ai_session_id = websocket.query_params.get("ai_session_id") or "patient_ai"` into
  `_run_ai_websocket`.
- `fetch_ai_chat_history`: when a specific (non-generic) `ai_session_id` is passed, validate
  ownership with `get_owned_ai_session` (403 if not owned).
- Auto-title: implemented inside `append_ai_chat_exchange` (see design decisions).

### 4. `backend/api/compat.py`
- `analyze_document` (line ~206): replaced the block that forced `patient_ai_{user_id}` with
  a shared `_resolve_analysis_session_id` helper — generic/empty → default; explicit owned
  id → used; explicit unowned id → falls back to default (never leaks into another user's
  session). Then `ensure_ai_session` + `append_ai_chat_exchange` against the resolved id.
- `explain_report`: now accepts `ai_session_id: str = Form(default="")`, requires
  `Depends(get_current_user)`, and persists the reply into the resolved session via the same
  `_resolve_analysis_session_id` helper (so uploaded-file analysis is tied to the active
  session). Added `import json` (was missing despite prior usage).

### 5. `backend/workflows/llm/patient/patient_nodes.py` (conversation-memory fix)
See "Fixes applied (post-implementation)" #1. `patient_general_llm` / `patient_assistant_llm`
no longer truncate `state["messages"]` to the last message when retrieved context is
present, and a `_dedupe_messages` helper collapses the (checkpoint + db-history)
duplication.

---

## Frontend changes

### 1. `frontend/src/lib/api.js`
- `getAiChatHistory(aiSessionId='patient_ai', targetPatientId='')` — kept.
- Added:
  ```js
  listAiSessions: () => apiClient.get('/api/chat/ai/sessions', { retries: 1, auth: true }),
  createAiSession: (title = '') => apiClient.post('/api/chat/ai/sessions', { title }, { retries: 0, auth: true }),
  deleteAiSession: (id) => apiClient.delete(`/api/chat/ai/sessions/${encodeURIComponent(id)}`, { retries: 0, auth: true }),
  ```

### 2. `frontend/src/lib/realTimeClient.js`
- `buildAiChatWebSocketUrl({ role, token, targetPatientId, aiSessionId })` appends
  `&ai_session_id=<id>` for both patient and doctor urls when `aiSessionId` is provided.

### 3. `frontend/src/pages/PatientDashboard.jsx`
- **State:** `aiSessions` (list) and `activeAiSessionId` (string, init `'patient_ai'`).
- **Load sessions:** new `loadAiSessions()` hits `patientApi.listAiSessions()`, sets
  `aiSessions`, and reconciles `activeAiSessionId` to the default (via `s.is_default`) or
  keeps an explicit id that is present in the list. Called from the `explain`-panel effect
  alongside `loadChatHistory()`; `activeAiSessionId` is in the effect deps.
- **`loadChatHistory()`**: uses `activeAiSessionId` instead of the literal `'patient_ai'`.
- **`handleChatSubmit()`**: passes `aiSessionId: activeAiSessionId` into
  `buildAiChatWebSocketUrl`; refreshes `loadAiSessions()` after a successful send.
- **`handleAnalyzeSelected()`** and **`handleExplainUpload()`**: send
  `ai_session_id: activeAiSessionId` in the form data.
- **"+" on the Analyze Report sidebar button**: flex row with the nav label + a "+" icon
  button → `handleNewChat()` (create session, `loadAiSessions`, `setActiveAiSessionId(s.id)`,
  `setMessages([])`, open `explain` panel).
- **Session switcher UI** in the `explain` panel header: a `<select>` bound to `aiSessions`
  (`title` fallback "New Chat"), a delete (×) button (disabled for the default session via
  `is_default`), and the existing language `<select>`. Selecting an item sets
  `activeAiSessionId` and clears messages; `handleDeleteSession(id)` confirms, calls
  `patientApi.deleteAiSession`, then `loadAiSessions()` + clears messages.

### 4. Styling
- Reuse existing inline styles / `patient.css`. Minimal purple-themed (`#6C5CE7`) styles for
  the "+" icon button and the session dropdown/delete.

---

## DB
- No schema migration required: `AiChatSession` already supports multiple sessions per user
  and has a `title` column. New rows are created via `create_ai_session` /
  `ensure_ai_session`. Run `prisma generate` (and `prisma db push` only if the generated
  client is stale) to be safe.

---

## Testing / verification
1. **Backend:** as a patient —
   - `POST /api/chat/ai/sessions` → returns a new id; row appears in `ai_chat_sessions`.
   - `GET /api/chat/ai/sessions` → lists default (flagged `is_default:true`) + new.
   - Connect ws `/api/chat/ai/patient/ws?token=...&ai_session_id=<new>`; send a message;
     confirm `ai_chat_messages` are tied to `<new>` and title auto-updates.
   - `GET /api/chat/ai/history?ai_session_id=<new>` returns only that session's messages.
   - Ownership: another user's session id → rejected (1008 / 403).
2. **Frontend manual:**
   - Click "+" on Analyze Report → new empty chat, panel opens.
   - Switch between chats via the dropdown → history loads per session.
   - Ask a follow-up about an earlier turn in any (including older) chat → assistant now
     references it (see Fix #1).
   - Analyze a document / report → result appended to the active session only.
   - Delete a non-default chat via × → removed from list; default chat's × is disabled.
   - Reload page → sessions persist (DB-backed).
3. Confirm the old single chat still works (default `patient_ai_{user_id}` shows its prior
   history).

## Files touched
- `backend/services/chat_service.py` (new methods + `_serialize_ai_session` `is_default`)
- `backend/schemas/chat_schemas.py` (`AiSessionResponse` w/ `is_default`, `AiSessionCreateRequest`)
- `backend/api/chat/router.py` (new endpoints + ws/history session-id & ownership handling)
- `backend/api/compat.py` (respect session id in `analyze_document` **and** `explain_report`)
- `backend/workflows/llm/patient/patient_nodes.py` (conversation-history fix, see Fix #1)
- `frontend/src/lib/api.js` (session APIs)
- `frontend/src/lib/realTimeClient.js` (ws url session id)
- `frontend/src/pages/PatientDashboard.jsx` ("+" button, session switcher, delete, wiring)

---

## Fixes applied (post-implementation)

Both caught during manual testing after the feature shipped.

### Fix #1 — AI forgot earlier turns when resuming an older chat
**Symptom:** Switching to an older chat and asking about a previous conversation, the
assistant answered as if it had no memory, even though `ai_chat_messages` contained the
records.

**Root cause:** `patient_general_llm` and `patient_assistant_llm`
(`backend/workflows/llm/patient/patient_nodes.py`) truncated the conversation to only the
**last** message whenever retrieved context (`evidence`) was present:
```python
if context_str and all_messages:
    chat_messages = [all_messages[-1]]   # discards all history
```
When you ask about a previous conversation, the planner runs the `MEMORY` capability, which
populates `evidence` with only `"Retrieved N previous conversation messages."` (a count, not
the content). That truthy `context_str` triggered the truncation, so the real history — which
lives only in `state["messages"]` (reloaded from `ai_chat_messages`) — was dropped. The
doctor nodes had no such truncation, confirming it was patient-specific.

**Fix:** Both patient LLM nodes now always pass the full (de-duplicated) `state["messages"]`
history to the model; retrieved context is still surfaced via the system prompt. Added a
`_dedupe_messages` helper to collapse the duplication that occurs because the websocket
reloads DB history each turn while the LangGraph `MemorySaver` checkpointer also accumulates
it. `patient_nodes.py` byte-compiles cleanly.

### Fix #2 — Could not delete any chat
**Symptom:** Clicking the delete (×) button did nothing for every chat.

**Root cause:** The frontend `isDefaultSession` helper used the regex
`/^(patient_ai|doctor_ai)_/`, which matches **every** patient session id, because both the
default (`patient_ai_{user_id}`) and new chats (`patient_ai_{user_id}_{hex}`) start with
`patient_ai_`. So `disabled={isDefaultSession(activeAiSessionId)}` was always `true` and the
button was permanently disabled.

**Fix:**
- Backend `AiSessionResponse` now carries `is_default` (computed in `list_ai_sessions` by
  comparing the row id to the exact default id `patient_ai_{user_id}`; `create_ai_session`
  always returns `is_default=False`).
- Removed the broken `isDefaultSession` regex. The UI now derives "is default" from
  `session.is_default`: `loadAiSessions` reconcile uses `s.is_default` to pick the default;
  `handleDeleteSession` and the delete button use `activeSession.is_default`.
- Backend `delete_ai_session` also deletes child messages explicitly
  (`aichatmessage.delete_many`) before deleting the session, so deletion succeeds even if
  the DB-level `onDelete: Cascade` is not enforced by the running database.

**Result:** Only the true default chat is protected; every other chat's × button is enabled,
confirms, and is removed from the list.
