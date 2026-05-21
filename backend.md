# Backend Technical Reference — HealthCare API

Last updated: 2026-05-18

This document is a comprehensive technical reference for the HealthCare API backend located in the repository root `backend/` and the modular application at `backend/app/`.

It is intended for developers who will maintain, extend, test, or operate the backend. The content reflects the actual implementation in source files and explains architecture, modules, routing, services, data flow, AI pipelines, encryption, storage, testing, and known technical debt.

---

**Table of contents**

- Project Overview
- High-level Architecture
- Folder Structure (explained)
- Routes (endpoints) and routing logic
- Services (detailed per-service reference)
  - AI services
  - Storage services
  - Medical services (prescription, OCR, X-ray)
  - Auth service
  - Patient & doctor services
- Repositories (data access)
- Datastore: JSON persistence and layout
- File storage & encryption (AES-GCM + RSA wrap)
- OCR & Prescription pipeline
- X-ray analysis pipeline
- Authentication and session handling
- Schemas (Pydantic models used)
- Async handling and blocking operations
- Dependency injection and request lifecycle
- Testing & validation (smoke tests, import validation)
- Known technical debt and migration notes
- Final filesystem tree (backend)
- Appendices
  - Example request lifecycles (diagrams)
  - Environment variables and config

---

## Project overview

Purpose
- Provide a compact, modular FastAPI backend for a healthcare educational assistant. It exposes routes for authentication, doctor/patient data, file uploads, AI chat, prescription parsing, and X-ray analysis.
- Store application data as JSON files under `data/` (no external DB dependency required).
- Provide encrypted file storage with AES-GCM + RSA key wrapping.
- Integrate with LLMs (Gemini via `google.generativeai`) for chat, document explanation, prescription extraction, and X-ray analysis.

Audience
- Backend maintainers and developers working on features, testing, or deployment.

Constraints and design decisions (observed in code)
- Async-first routes; blocking operations are offloaded using `asyncio.to_thread` to preserve responsiveness without redesigning blocking libraries.
- Services and repositories separated: routes call services; services call repositories; repositories interact with the JSON data store and file system.
- Minimal external dependencies for configuration and safe imports.
- Lightweight session handling using Starlette's `SessionMiddleware` (cookie-backed server-side session store held in signed cookies).

---

## High-level architecture

Primary layers (top → bottom):

- routes (FastAPI APIRouter modules)
  → services (business logic; orchestrators)
  → repositories (persistence adapters)
  → datastore (JSON files under `data/` and filesystem uploads)

Note: For certain AI or file workflows, services call lower-level helpers (e.g., `services/storage` uses `app.crypto_utils` via `services/storage/encryption_service.py`) but the repository pattern is maintained for persisted metadata.

Diagram (simplified)

```
Frontend --> FastAPI Route --> Service --> Repository --> JsonHealthCareStore (files)
                                    \-> StorageFileService (files + encryption)
                                    \-> AIChatService (LLM calls via Gemini)
```

---

## Folder structure (explain purpose)

Root (important):
- `backend/` — Project root for the backend runtime.
  - `main.py` — legacy/unified entrypoint used in earlier monoliths and still present as an operational entry script and reference; contains initial seeding and some helper wiring.
  - `crypto_utils.py` — low-level cryptographic helpers (RSA keypair, AES-GCM, private key encryption with PBKDF2). Used by the encryption service.
  - `run_smoke_tests.py` — test harness for lightweight smoke tests.
  - `cleanup_old_conversations.py` — maintenance script.
  - `data/` — runtime JSON data and uploads (see Data section below).
  - `app/` — modular FastAPI app (preferred module for route registration and production use)

`backend/app/` (modular app):
- `main.py` — FastAPI application initialization (middleware, routers, CORS, SessionMiddleware). This file mounts routers and sets up `app.state.store`.
- `data_store.py` — `JsonHealthCareStore` implementation (thread-safe JSON persistence). The repository adapters use this store.
- `crypto_utils.py` — re-exported or used low-level crypto helper accessible to services; keep consistent with top-level crypto utilities.
- `config/` — environment-based settings; `settings.py` exposes `settings` with session secret, data root, etc.
- `routes/` — FastAPI APIRouter definitions (`auth.py`, `chat.py`, `file.py`, `patient.py`, `doctor.py`, `legacy_compat.py`). Routes are intentionally thin.
- `services/` — main business logic package.
  - `ai/` — AI/chat services: `chat_service.py`, `chat_workflow_service.py`, `memory_service.py`, `summarizer.py`, `gemini_service.py`.
  - `medical/` — prescription and x-ray related services: `prescription_service.py`, `prescription_impl.py` (concrete extraction logic), `ocr.py`, `medicine_extractor.py`, `xray_service.py`.
  - `storage/` — file and encryption services: `file_service.py` (concrete storage workflows), `encryption_service.py` (typed wrapper for crypto_utils).
  - `auth/` — `auth_service.py` (auth business logic).
  - `file_service.py` (higher-level orchestrator that coordinates repo + storage + AI for uploads and explanations).
- `repositories/` — data access adapters wrapping the `JsonHealthCareStore`: `auth_repository.py`, `file_repository.py`, `patient_repository.py`, `doctor_repository.py`.
- `schemas/` — Pydantic schema re-exports for backward compatibility; canonical models are in `app/schemas.py`.
- `utils/` — small helpers like `logger.py`.
- `prisma/` — schema files present but not required for JSON datastore mode.

---

## Routes (endpoints) and routing logic

All routes are under `backend/app/routes/*` and primarily registered by `app/main.py`.

Key route modules and paths:
- `auth.py` (`/api/auth`) — register, login. Uses `AuthService`.
- `chat.py` (`/api/chat`, `/api/chat_sessions`) — chat endpoints for patients. Depends on `ChatWorkflowService` (which itself composes AI services and memory).
- `file.py` (`/api/file/{file_id}`, `/api/v2/*`) — file download, patient assets, upload, delete, analyze and explain endpoints. Uses `FileService`.
- `patient.py` — patient profile management and appointments.
- `doctor.py` — doctor listing and profile access.
- `legacy_compat.py` — compatibility layer mapping older `/api/*` endpoints used by legacy frontend to modular services and repositories. Kept intentionally minimal and thin; it delegates actual work to services and repositories.

Routing pattern
- Routes are intentionally thin: they validate session/inputs, construct appropriate service instances (via small factory functions that use `request.app.state.store`), and call service methods.
- Dependency injection is achieved through small `Depends` factory functions that instantiate services with repositories built from `request.app.state.store`.

Example: chat route flow (high level)
- Route `/api/chat` accepts `ChatRequest` (Pydantic), extracts username from session, creates `ChatWorkflowService` (composed services), then calls `send_message(...)`.

---

## Services (detailed)

Services contain business logic and orchestrate repositories, storage, and AI components. Keep services small and testable. Below is an exhaustive description of important services present in code.

### AI services

Location: `backend/app/services/ai/`

1) `chat_service.py` — `AIChatService`
- Responsibility: Core AI-driven conversation logic, document explanation, and X-ray analysis orchestration.
- Important methods:
  - `async chat(username, messages, language)` → Offloads to `self._chat_impl` using `asyncio.to_thread`.
  - `_chat_impl(username, messages, language)` → loads sessions, builds efficient context, forms LLM prompt, calls `_call_llm_with_messages`, validates and structures responses, saves back to sessions.
  - `_call_llm_with_messages(messages)` → core LLM invocation wrapper. Uses `google.generativeai` (Gemini) if API key present and supports fallback semantics for different return types from result objects.
  - `explain_document(...)` and `analyze_xray(...)` → document and image analysis. These create controlled system messages and call LLM to request JSON outputs. They parse results and apply small post-processing (e.g., drawing bounding boxes on X-ray image copies).
  - `_ensure_structured` / `_structure_response` → convert free-form LLM output into structured JSON sections (summary, key_findings, observations, risks, recommendations, notes).
  - `_build_force_json_prompt` → helper to coerce LLM into JSON output when initial parsing fails.
- Dependencies: `google.generativeai as genai` (Gemini), LangChain message classes for in-memory message formatting, `JsonHealthCareStore` via file-based session persistence (via `_load_sessions/_save_sessions`).
- Request flow: route -> ChatWorkflowService (which uses MemoryService & GeminiService) -> AIChatService (LLM call) -> returns structured dict saved into sessions via file write.
- Notes: Large synchronous operations (LLM calls, PDF parsing) are run inside `asyncio.to_thread` to avoid blocking the event loop.

2) `chat_workflow_service.py` — `ChatWorkflowService`
- Responsibility: Orchestrates session lifecycle and integrates `AIChatService`, `MemoryService`, `Summarizer`, and `GeminiService`.
- Important methods:
  - `list_sessions(username)` -> delegates to `MemoryService`.
  - `send_message(username, messages, language, session_id)` -> manages session selection/creation, persists session ordering, calls `ai_service.chat`, and shapes API reply (adds disclaimer) before returning to route.
- Dependencies: `AIChatService`, `MemoryService`, `Summarizer`, `GeminiService`.
- Request flow: route -> instantiate ChatWorkflowService -> `send_message` -> AI service call -> update memory -> return response.

3) `memory_service.py` — `MemoryService`
- Responsibility: Load/save chat sessions and build context.
- Important methods:
  - `load_sessions(username)`, `save_sessions(username, sessions)` -> thin wrappers that call `AIChatService`'s file-based storage helpers via `asyncio.to_thread`.
  - `build_context(active_session)` -> delegates to AIChatService's `_build_efficient_context` (offloaded) to compute recent message window and summary.
- Dependencies: `AIChatService` implementation for legacy persistence functions.

4) `summarizer.py` — `Summarizer`
- Responsibility: Provide short summarization of messages.
- Important methods: `summarize_messages(messages)` -> delegates to AIChatService summarization helpers.

5) `gemini_service.py` — `GeminiService`
- Responsibility: Very small wrapper exposing ability to call LLM using prepared `BaseMessage` list. Uses `AIChatService` internals via thread offload.

### Storage services

Location: `backend/app/services/storage/`

1) `file_service.py` (StorageFileService) — `StorageFileService` (in `storage/file_service.py`)
- Responsibility: Implement hybrid file storage encryption workflows; encrypt bytes, write ciphertext to disk, generate RSA-wrapped AES file keys and metadata.
- Important methods:
  - `process_upload(file_bytes, user_public_key, save_path) -> (file_key_id, enc_file_key, encryption_meta)`
  - `process_download(physical_path, enc_file_key, encrypted_private_key_b64, password, encryption_meta) -> bytes`
  - `process_share(enc_file_key, owner_priv_pem, target_public_key) -> enc_file_key_for_target`
- Dependencies: `app.crypto_utils` low-level functions (AES key generation, AES-GCM encryption/decryption, RSA wrap/unwrap).
- Request flow: Service is used by `FileService` orchestrator to encrypt+store files then record file key mapping via repository.

2) `encryption_service.py` — typed wrapper exposing `crypto_utils` functions as an API for services.

### Medical services

Location: `backend/app/services/medical/`

1) `prescription_impl.py`
- Responsibility: The concrete implementation for prescription OCR/text extraction and pricing lookups.
- Important functions: `text_format`, `ocr_image`, `pdf_to_text`, `ocr_pdf`, `upload`, `search_price`, `get_online_price`, `extract_price_with_gemini`.
- Dependencies: PyMuPDF (`fitz`), Pillow, `google.generativeai` for model-based extraction (if API key configured), `requests` to fetch external pharmacy pages for price scraping, `quote` from urllib.
- Notes: This module contains logic to call LLMs for JSON extraction and fallback regex and local heuristics for pricing.

2) `medicine_extractor.py`, `ocr.py`, `prescription_service.py` — thin async wrappers and orchestrators that call `prescription_impl` functions in background threads using `asyncio.to_thread`.

3) `xray_service.py` — formatting utilities and `XRayService` class exposing `format_for_chat`. Core AI-driven image analysis occurs in `AIChatService.analyze_xray` and `FileService.analyze_xray` handles storage and orchestration.

### Auth service

Location: `backend/app/services/auth/auth_service.py`
- Responsibility: Business logic for registration and authentication, delegating persistence to `AuthRepository`.
- Important methods: `authenticate(role, username, password)`, `register_patient`, `register_doctor`.

### Patient & doctor services

- `patient_service.py` and `doctor_service.py` are small orchestrators dealing with higher-level patient/doctor operations and delegating persistence to repositories.

---

## Repositories

Repositories are persistence adapters that translate service requests to `JsonHealthCareStore` and the JSON file layout.

Location: `backend/app/repositories/`

1) `AuthRepository`
- Manages credential checks and creating patient/doctor profiles by delegating to `JsonHealthCareStore`.

2) `PatientRepository`
- Methods: `get_profile`, `update_profile`, `get_appointments`, `create_appointment`.
- Implementation: delegates to `store.get_patient_profile`, `update_patient_profile`, `get_patient_appointments` etc.

3) `DoctorRepository`
- Methods: `list_doctors`, `get_profile`, `update_profile`, `get_requests`.
- Implementation: delegates to `JsonHealthCareStore`.

4) `FileRepository`
- Manages file metadata, `file_keys.json` mapping, and upload path resolution.
- Important methods: `get_profile`, `save_profile`, `upsert_file_key`, `find_file_key_for_user`, `resolve_download_metadata`, `get_upload_path`.
- File metadata persisted inside patient profiles (`custom_assets`, `xray_analyses`) and `file_keys.json` at the data root.

Persistence flow: Services call repository methods; repository writes/reads JSON files through helper methods that perform atomic temp-write-and-replace.

---

## Datastore: `JsonHealthCareStore` and data layout

Location: `backend/app/data_store.py`

Design:
- Lightweight JSON persistence to filesystem under `data/` (configurable via `HEALTHCARE_DATA_ROOT` or default `backend/data`).
- Thread-safe via `threading.RLock` to avoid concurrent write corruption.
- Atomic writes: write to a `.tmp` file then `replace` to the real path.

Patient layout (under `data/patients/<username>/`):
- `profile.json` — primary profile object with fields such as `name`, `email`, `password`, `publicKey`, `encryptedPrivateKey`, `custom_assets` etc.
- `chat_sessions.json` — array of saved chat sessions (session objects contain id, title, messages, summary, timestamps).
- `appointments.json` — patient appointments list.
- `reports.json` — list of uploaded report metadata (legacy slot; migration into `custom_assets` exists).
- `medical_images.json` — legacy list; file migration code merges these into `custom_assets` at first access.

Doctor layout (under `data/doctors/<doctor_id>/`):
- `doctor_profile.json`, `schedules.json`, `requests.json`, `payments.json`, `patient_chats.json`, `assistant_chat.json`.

Global files at data root:
- `file_keys.json` — mapping keyed by generated file key ids (encapsulates file_id, user_id, encrypted_file_key, createdAt).
- `snapshot.json` — snapshot export used by snapshot tooling.

Uploads directory layout (for ciphertext blobs):
- `data/uploads/patient/<username>/<category>/<filename>` — physical ciphertext files stored alongside metadata that includes the original physical path.

Important repository behavior:
- `FileRepository.resolve_download_metadata` searches across patient profiles `custom_assets` and `xray_analyses` to find an asset matching `file_id` (compatibility behavior until all metadata is fully consolidated).

---

## File storage & encryption (detailed)

Design and goals
- Provide confidentiality for uploaded files (reports, images, xrays) using a hybrid cryptosystem:
  - AES-256-GCM symmetric key for encrypting file bytes (fast and streaming-friendly)
  - RSA-OAEP to encrypt (wrap) the AES key for each recipient (owner/target) — stored as base64.
- Keep metadata (nonce/iv, auth_tag) for AES-GCM so ciphertext can be decrypted.
- Store ciphertext physically in `data/uploads/patient/...`.

Components
- `backend/app/crypto_utils.py` — low-level primitives
  - `generate_rsa_key_pair()` → returns (public_pem, private_pem)
  - `encrypt_private_key(private_pem, password)` → uses PBKDF2-HMAC-SHA256 to derive AES key; encrypts private key with AES-GCM; returns base64 payload (salt+nonce+tag+ciphertext)
  - `decrypt_private_key` → reverse of the above
  - `generate_aes_key()` → returns 32 random bytes
  - `encrypt_file_content(data, aes_key)` → AES-GCM encryption returning (ciphertext, nonce, auth_tag)
  - `decrypt_file_content(...)` → decrypts and verifies
  - `encrypt_file_key(file_key, public_key_pem)` → RSA-OAEP encrypt; returns base64
  - `decrypt_file_key(encrypted_b64, private_key_pem)` → RSA-OAEP decrypt to retrieve AES key bytes

- `backend/app/services/storage/encryption_service.py` — small typed wrapper for `crypto_utils` used by higher layers.

- `backend/app/services/storage/file_service.py` — `StorageFileService` (concrete hybrid workflows):
  - `process_upload(file_bytes, user_public_key, save_path)`:
    - generates AES key
    - encrypts file bytes with AES-GCM → ciphertext, nonce, auth_tag
    - writes ciphertext to `save_path`
    - RSA-wraps AES key with user public key → `enc_file_key`
    - generates `file_key_id` and `encryption_meta` with algorithm, iv, auth_tag
    - returns `file_key_id, enc_file_key, encryption_meta`
  - `process_download(physical_path, enc_file_key, encrypted_private_key_b64, password, encryption_meta)`:
    - decrypts encrypted private key with `password`
    - RSA-unwraps AES key using private key
    - reads ciphertext from `physical_path`
    - decrypts AES-GCM using iv & auth_tag from `encryption_meta`
    - returns plaintext file bytes
  - `process_share(enc_file_key, owner_priv_pem, target_public_key)`:
    - decrypts AES key using owner private key, re-encrypts AES key to `target_public_key` — returns new `enc_file_key`.

Repository interaction
- `FileService` orchestrator calls `StorageFileService` during upload and download and stores file key metadata via `FileRepository.upsert_file_key`.
- The file metadata recorded in patient profile objects refers to `physical_path` (absolute path), encryption meta, and link (`/api/file/<file_id>`).

Security notes
- Private keys are encrypted in user profiles using PBKDF2-derived AES key and stored base64. The password is required to decrypt private key locally when downloading a file.
- Session cookies (via `SessionMiddleware`) sign session data with `SESSION_SECRET_KEY` — see `config/settings.py`.

---

## OCR & prescription pipeline

Key module: `backend/app/services/medical/prescription_impl.py` (concrete implementation)

Responsibilities
- Provide OCR for images and PDFs using PyMuPDF (fitz) + Pillow.
- Format textual content and extract structured medicine name/dosage/frequency using the LLM when configured.
- Offer price lookup using heuristics, a local price table (fast fallback), and optionally querying online pharmacy pages and extracting price via regex or LLM-assisted parsing.

Workflow
- `upload(file, language)` inspects the file extension:
  - `.pdf` → `pdf_to_text` to extract text; if that fails → `ocr_pdf` (render pages and OCR each page via `ocr_image`)
  - image types → `ocr_image`
  - `.txt` → read file and `text_format`
- `text_format(text, language)` prepares a language-specific instruction and calls the LLM (Gemini) to return JSON with medicine entries.
- `get_online_price(name)` attempts to query a small list of known pharmacy sites and uses helper `extract_price_with_gemini` (LLM) or `extract_price_regex` fallback; otherwise returns a local estimated price.

Notes
- LLM usage is optional based on presence of `GOOGLE_API_KEY`/`GEMINI_API_KEY` in environment.
- The module contains pragmatic heuristics and rate-limited requests when scraping.

---

## X-ray analysis pipeline

Where: Analysis performed by `AIChatService.analyze_xray` (AI service); `FileService` orchestrates storing the upload and calling analyze.

Workflow
1. Route receives uploaded X-ray image.
2. `FileService.analyze_xray` validates file type, encrypts the file and stores ciphertext using `StorageFileService.process_upload` and records file key.
3. `FileService` offloads analysis to `AIChatService.analyze_xray` via `asyncio.to_thread`.
4. `AIChatService._analyze_xray_impl`:
   - Opens image (Pillow), constructs a system prompt instructing the LLM to return ONLY JSON describing: has_defect (bool), severity (0-10), defect_type, location, affected_area, bounding_box, recommendation.
   - Calls `_call_llm_with_messages` to obtain JSON.
   - Parses and post-processes JSON (adds image_size, optionally draws bounding boxes on a copy of the image), and returns `{"success": True, "analysis": <json>, "images": {...}}` or `{"success": False, "error": ...}`.
5. `FileService` records analysis metadata into `profile['xray_analyses']` including encryption metadata and a link to download the encrypted file.

Presentation
- `xray_service.format_xray_analysis_for_chat` formats analysis into a chat-friendly markdown string (summary, visual comparison placeholders, disclaimer). `FileService` returns both structured analysis and presentation-ready strings.

Caveats
- Analysis is intended for educational purposes only; system prompts explicitly instruct the LLM not to provide clinical diagnoses.

---

## Authentication and session handling

Mechanics
- Session middleware is added in `backend/app/main.py`:
  - `app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)`
  - This uses encrypted/signed cookie-based session storage provided by Starlette.
- Login flow (`/api/auth/login`):
  - `AuthService.authenticate` uses `AuthRepository.check_credentials`, which delegates to `JsonHealthCareStore.check_credentials(role, username, password)`.
  - If authentication succeeds, route sets `request.session['user'] = username` and `request.session['category'] = role` (and `role`), which persists as a signed cookie.
- Role management: `role` is a literal `"patient"` or `"doctor"`. Routes guard by checking session `category`.
  - Example: chat endpoints use `_require_patient` which inspects `request.session`.

Session data and cookies
- Session data is stored signed in cookies. The `SESSION_SECRET_KEY` config setting must be stable across backend instances (for consistent session verification) if multiple instances are used.
- Sensitive items: application stores encrypted private keys in user `profile.json` and keeps password fields present for decrypting private key at runtime. Session cookie only contains short-lived identifiers and is cryptographically signed (not encrypted by default unless configured by Starlette).

Logout flow: `/api/logout` simply clears `request.session`.

---

## Schemas (Pydantic)

Canonical schemas are in `backend/app/schemas.py`.

Selected models
- `LoginRequest`, `RegisterRequest`, `RegisterResponse`, `LoginResponse` — auth models
- `Message`, `ChatRequest`, `ChatReply` — chat message models used by chat route and client
- `AppointmentCreate`, `AppointmentRecord` — appointment models

Validation
- Routes accept Pydantic models which validate request payloads before service invocation.
- Services assume validated inputs but still perform defensive checks when necessary (e.g., file existence checks, encryption presence checks, etc.).

Compatibility
- `app/schemas/chat_schema.py` re-exports models as a compatibility shim. This file can be removed after all callers import `app.schemas` directly. See Technical Debt.

---

## Async handling and blocking operations

General rule in codebase
- FastAPI routes are async. Long-running or blocking operations (LLM calls via `google.generativeai`, file encryption, PyMuPDF PDF parsing, Pillow image processing, network calls for price scraping) are executed in background threads using `asyncio.to_thread` to prevent blocking the event loop.

Examples
- `AIChatService.chat` calls `await asyncio.to_thread(self._chat_impl, ...)`.
- `FileService.explain_report` calls `await asyncio.to_thread(self.chat_service.explain_document, ...)`.
- `FileService.analyze_xray` offloads both file upload encryption and `AIChatService.analyze_xray` to threads.

Why `asyncio.to_thread`?
- The code integrates third-party synchronous libraries (cryptography IO, Pillow, fitz, and LLM SDKs) which are not async-aware. Wrapping these in `asyncio.to_thread` keeps the overall FastAPI process responsive.

Notes for future maintainers
- Where possible, consider migrating to non-blocking libraries or using worker/background tasks (e.g., Celery or RQ) for heavy/long-running tasks.

---

## Dependency injection & repository pattern

- Routes build service instances in factory functions leveraging `request.app.state.store` to instantiate repositories. Example:

```
def _get_file_service(request):
    store = request.app.state.store
    repo = FileRepository(store)
    return FileService(repo)
```

- This approach keeps the route thin and makes services testable by injecting mocked repositories or stores.

---

## Testing & validation

Available checks
- `backend/run_smoke_tests.py` — runs a set of lightweight smoke tests against the modular app instance (register/login/health/doctors/chat_sessions). This harness uses `fastapi.testclient.TestClient(app)`.
- Import sweep: ad-hoc import validation is used during migration to ensure all `backend.*` modules import cleanly.

How to run smoke tests locally

```bash
# activate venv, then
python -m backend.run_smoke_tests
```

Interpreting results
- `ok: true` with listed responses means key endpoints are functioning.

---

## Known technical debt (honest list)

1. Compatibility shims
- `app/schemas/chat_schema.py` re-export remains. Remove after frontend and other call sites use `app.schemas`.

2. Thread-wrapped blocking operations
- Many blocking libraries are used and wrapped with `asyncio.to_thread`. This works but limits throughput. Migrating to async-native solutions, or offloading heavy LLM calls to asynchronous worker queues, would improve scalability.

3. JSON datastore limitations
- The JSON store is simple and convenient for demos and local development but lacks transactional semantics and indexing. For production usage, replace with a proper database.

4. Documentation & tests
- Unit tests and integration tests are limited. The smoke harness covers basic API surface; more exhaustive tests should be added (file encryption E2E, LLM integration, prescription pipeline, x-ray pipeline).

5. Secrets handling
- Private key encryption uses PBKDF2 and AES-GCM, but secret management (env vars for API keys) depends on process environment. Use a secrets manager for production.

---

## Final backend structure tree (representative)

```
backend/
  ├── main.py
  ├── crypto_utils.py
  ├── cleanup_old_conversations.py
  ├── run_smoke_tests.py
  ├── data/
  │   ├── file_keys.json
  │   ├── snapshot.json
  │   ├── patients/
  │   │   └── <username>/profile.json
  │   │   └── <username>/chat_sessions.json
  │   │   └── <username>/appointments.json
  │   │   └── ...
  │   └── uploads/
  │       └── patient/<username>/<category>/<ciphertext files>
  └── app/
      ├── main.py
      ├── data_store.py
      ├── crypto_utils.py
      ├── schemas.py
      ├── config/settings.py
      ├── routes/
      │   ├── auth.py
      │   ├── chat.py
      │   ├── file.py
      │   ├── patient.py
      │   ├── doctor.py
      │   └── legacy_compat.py
      ├── services/
      │   ├── auth/auth_service.py
      │   ├── file_service.py
      │   ├── storage/
      │   │   ├── file_service.py
      │   │   └── encryption_service.py
      │   ├── ai/
      │   │   ├── chat_service.py
      │   │   ├── chat_workflow_service.py
      │   │   ├── memory_service.py
      │   │   ├── summarizer.py
      │   │   └── gemini_service.py
      │   └── medical/
      │       ├── prescription_impl.py
      │       ├── prescription_service.py
      │       ├── ocr.py
      │       └── xray_service.py
      └── repositories/
          ├── auth_repository.py
          ├── file_repository.py
          ├── patient_repository.py
          └── doctor_repository.py
```

---

## Example request lifecycles (detailed)

1) Chat flow (user sends a message)

```
Frontend -> POST /api/chat (ChatRequest)
  -> Route: auth check (session), build ChatWorkflowService via Depends
  -> ChatWorkflowService.send_message
       -> MemoryService.load_sessions(username)
       -> AIChatService.chat (asyncio.to_thread -> _chat_impl)
            -> _build_efficient_context (compile context from messages & summaries)
            -> _call_llm_with_messages (build system/human messages, invoke Gemini via genai)
            -> _ensure_structured/_structure_response (validate/format LLM output)
            -> save session via _save_sessions
       -> ChatWorkflowService returns reply dict
  -> Route returns JSONResponse to frontend
```

2) File upload (patient uploads X-ray)

```
Frontend -> POST /api/v2/upload_asset (multipart)
  -> Route: session check, instantiate FileService(repo)
  -> FileService.upload_asset
       -> check profile publicKey
       -> storage_service.process_upload (AES-GCM encrypt file, write ciphertext)
       -> file_repository.upsert_file_key (store enc_file_key & mapping)
       -> file_repository.save_custom_assets(profile)
  -> Route returns new asset metadata
```

3) File download

```
Frontend -> GET /api/file/<file_id>
  -> Route: session check, instantiate FileService
  -> FileService.download_file
       -> file_repository.resolve_download_metadata(file_id) -> owner + asset
       -> ensure key exists for user or they are owner
       -> storage_service.process_download (decrypt private key via password, unwrap AES key, decrypt content)
  -> Route returns binary response (decrypted bytes) with `Response(content=..., media_type=...)`
```

---

## Environment & configuration (operational)

Key variables (observed in code):
- `SESSION_SECRET_KEY` — used by `SessionMiddleware` to sign session cookies. Default `your_secret_key` if not set (must be changed in production).
- `HEALTHCARE_DATA_ROOT` — optional data root override for JSON and uploads.
- `GOOGLE_API_KEY` or `GEMINI_API_KEY` — used by Gemini (`google.generativeai`) for LLM calls.
- `GEMINI_TEXT_MODEL` — optional override for Gemini model name.
- `GOOGLE_CSE_ID` — used for custom search engine (prescription price discovery) when using Google Custom Search.

Settings accessor: `backend/app/config/settings.py` exposes a `settings` object.

Deployment notes
- Ensure `SESSION_SECRET_KEY` is kept secret and consistent across replicas.
- To enable LLM features, provide `GOOGLE_API_KEY`/`GEMINI_API_KEY` with sufficient quota.
- Ensure `HEALTHCARE_DATA_ROOT` is writable by the process and properly back up `data/` for persistence.

---

## Validation and testing

- `python -m backend.run_smoke_tests` executes a lightweight set of endpoint checks (health, doctors, auth register/login, patient_session, chat_sessions).
- Import checks: A package-level import sweep is used during development to ensure `backend.*` modules import cleanly. This caught ordering issues during migration.

Recommended next tests
- File encryption E2E: simulate upload -> download cycle to validate private key encryption/decryption and AES-GCM integrity.
- LLM integration tests: run chat/explain pipelines with a test API key and verify structured outputs.
- Integration tests for prescription pipeline with sample images/PDFs.

---

## Operational notes & maintenance

- Back up `data/` regularly (contains user profiles, private keys (encrypted), file_keys). Ensure secrets are handled by secure storage.
- Rotate `SESSION_SECRET_KEY` only carefully — rotation invalidates existing session cookies.
- Audit `file_keys.json` periodically to remove stale keys.
- Consider introducing a job queue for long-running AI tasks for improved throughput and observability.

---

## Appendices

### Diagram: Chat flow (ASCII)

```
+------------+      POST /api/chat      +------------------+      +----------------+
| Frontend   | -----------------------> | FastAPI Route    |----> | ChatWorkflowSvc |
| (browser)  |                          | (chat.py)        |      +----------------+
+------------+                          |                  |            |
                                        +------------------+            v
                                                 |                      +------------------+
                                                 v                      | AIChatService    |
                                         dependency factory             | (LLM calls)      |
                                         builds services                +------------------+
                                            |                                   |
                                            v                                   v
                                       ChatWorkflowSvc -> MemoryService -> AIChatService._chat_impl
                                                                        -> _call_llm_with_messages (Gemini)
                                                                        -> _ensure_structured
                                                                        -> save sessions via JsonHealthCareStore
```

### Environment quicklist (for `.env`)

```
SESSION_SECRET_KEY=replace_with_secure_random
HEALTHCARE_DATA_ROOT=/srv/healthapp/data
GOOGLE_API_KEY=ya29.xxxx
GEMINI_TEXT_MODEL=gemini-3.5-flash
GOOGLE_CSE_ID=0123456789:abcdefg
CORS_ORIGINS=*  # use restricted setting in production
```

---

## Final words

This document describes the actual behavior and structure of the current backend implementation. It intentionally avoids prescribing large architectural changes. For future improvement, prioritize:
- Automated integration tests for encryption and AI pipelines.
- Migration off blocking libraries or dispatching heavy tasks to worker infrastructure.
- Replace JSON storage with a DB for multi-instance correctness and performance.

If you want, I can:
- Add a `developer-runbook.md` with commands to run the app locally and to test each pipeline (file E2E, LLM interactive tests).
- Generate a sequence of automated tests for encryption and LLM flows.


---

(End of backend technical reference)
