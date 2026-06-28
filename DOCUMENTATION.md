# DocTalk — Master Technical Specification

---

## 1. System Architecture Overview

DocTalk is a full-stack healthcare platform with four core pillars:

| Layer | Technology | Entry Point |
|---|---|---|
| **Backend** | Python 3 / FastAPI / Uvicorn | `backend/main.py` → `FastAPI(title="DocTalk Backend", version="1.0.0")` |
| **Frontend** | React 19 / Vite 8 | `frontend/src/main.jsx` → `<App />` |
| **Database** | PostgreSQL (Supabase) via Prisma ORM (async) | `backend/prisma/schema.prisma` |
| **AI Engine** | LangChain / LangGraph / OpenAI / Gemini | `backend/workflows/unified_chat_graph.py` |

**Application bootstrap** (`backend/main.py`): On `startup`, calls `connect_prisma()`. An HTTP middleware (`db_connect_middleware`) calls `ensure_connected()` before every request, returning a 503 if the database is unreachable. CORS is fully permissive (`allow_origins=["*"]`).

---

## 2. Core Configuration (`backend/core/`)

### `config.py` — `Settings` (Pydantic v1 `BaseSettings`)
Loads `.env` from the project root. Key fields:

| Setting | Env Var(s) | Default |
|---|---|---|
| `jwt_secret` | `JWT_SECRET`, `JWT_SECRET_KEY`, `SESSION_SECRET_KEY` | `"doc-talk-dev-secret"` |
| `jwt_algorithm` | `JWT_ALGORITHM` | `"HS256"` |
| `access_token_expire_minutes` | `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
| `openai_api_key` / `openai_model` / `openai_base_url` | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` | — |
| `gemini_api_key` / `gemini_embed_model` | `GEMINI_API_KEY`, `GEMINI_EMBED_MODEL` | — |
| `vision_endpoint` | `VISION_ENDPOINT` | `"gemini"` |
| `rag_embedding_dimension` | `RAG_EMBEDDING_DIMENSION` | `768` |
| `rag_embedding_cache_size` | `RAG_EMBEDDING_CACHE_SIZE` | `128` |

### `database.py` — Prisma Client Lifecycle
- `prisma = Prisma(auto_register=False)` — single global async client.
- `connect_prisma()`: `asyncio.wait_for(prisma.connect(), timeout=15.0)`. Sets module-level `_is_connected` flag.
- `ensure_connected()`: Lazy reconnect if `_is_connected` is `False`.
- `ping_database()`: Runs `SELECT 1 AS ok`. On failure, disconnects and reconnects, then retries.

### `security.py` — Authentication & Password Hashing

**Password hashing** uses `PBKDF2-SHA256` (390,000 iterations, 16-byte random salt). Legacy `bcrypt` hashes (prefixed `$2a$`, `$2b$`, `$2y$`) are also supported in `verify_password()`.

**JWT** (`PyJWT`):
- `create_access_token(user_id, role)` → payload: `{"sub": user_id, "user_id": user_id, "role": role, "iat": ..., "exp": ...}`.
- `decode_access_token(token)` → validates `sub == user_id`, raises `HTTPException(401)` on expiry or invalid token.

**`CurrentUser`** (Pydantic model): `user_id: str`, `role: Literal["patient", "doctor", "hospital"]`.

**`get_current_user`** (FastAPI dependency): Extracts `Bearer` token via `HTTPBearer`, decodes JWT, validates `role ∈ {"patient", "doctor", "hospital"}`.

---

## 3. Database Schema (`backend/prisma/schema.prisma`)

**Provider**: `postgresql` via Prisma Client Python (async interface).

### 3.1 Enums

| Enum | Values |
|---|---|
| `Role` | `patient`, `doctor`, `hospital` |
| `Gender` | `male`, `female`, `other` |
| `SymptomSeverity` | `mild`, `moderate`, `severe`, `critical` |

### 3.2 Core Models

#### `Patient` (`@@map("patients")`)
| Field | Type | Constraints |
|---|---|---|
| `username` | `String` | `@id` (primary key) |
| `name` | `String` | required |
| `password` | `String` | hashed |
| `dob` | `DateTime?` | optional |
| `gender` | `Gender?` | optional enum |
| `bloodGroup`, `address`, `mobile`, `email`, `phone` | `String?` | optional |
| `profilePic` | `String?` | base64 data URL |
| `closedDoctorChats`, `doctorChats`, `xrayAnalyses`, `customAssets` | `Json? @db.JsonB` | flexible JSONB payloads |
| `publicKey`, `encryptedPrivateKey` | `String?` | E2E encryption keys |
| **Relations** | `appointments → Appointment[]`, `consultations → Consultation[]`, `ragDocuments → RagDocument[]`, `fileKeys → FileKey[]` | cascade |

#### `Doctor` (`@@map("doctors")`)
| Field | Type | Constraints |
|---|---|---|
| `doctorId` | `String` | `@id` |
| `role` | `Role` | `@default(doctor)` |
| `specialization`, `experience`, `bio` | `String?` | optional |
| `schedules`, `appointmentRequests`, `payments`, `patientChats`, `closedChats` | `Json? @db.JsonB` | flexible JSONB |
| **Relations** | `appointments → Appointment[]`, `consultations → Consultation[]`, `doctorSlots → DoctorSlot[]`, `fileKeys → FileKey[]` | cascade |

#### `DoctorSlot` (`@@map("doctor_slots")`)
| Field | Type | Constraints |
|---|---|---|
| `id` | `String` | `@id @default(uuid())` |
| `doctorId` | `String` | FK → `Doctor.doctorId` (`onDelete: Cascade`) |
| `startTime`, `endTime` | `DateTime` | required |
| `isBooked` | `Boolean` | `@default(false)` |
| `isActive` | `Boolean` | `@default(true)` |
| **Unique** | `@@unique([doctorId, startTime])` | prevents duplicate slots |

#### `Appointment` (`@@map("appointments")`)
| Field | Type | Constraints |
|---|---|---|
| `id` | `String` | `@id @default(uuid())` |
| `patientUsername` | `String` | FK → `Patient.username` (`onDelete: Cascade`) |
| `doctorId` | `String` | FK → `Doctor.doctorId` (`onDelete: Cascade`) |
| `slotId` | `String?` | `@unique`, FK → `DoctorSlot.id` (`onDelete: SetNull`) |
| `status` | `String` | `@default("PENDING")` — values: `PENDING`, `CONFIRMED`, `REJECTED`, `COMPLETED`, `CANCELLED` |
| `reason`, `note`, `doctorMessage` | `String?` | optional |
| **Indexes** | `@@index([patientUsername])`, `@@index([doctorId])`, `@@index([slotId])`, `@@index([status])` | |

#### `Consultation` (`@@map("consultations")`)
| Field | Type | Constraints |
|---|---|---|
| `id` | `String` | `@id @default(uuid())` |
| `appointmentId` | `String` | `@unique`, FK → `Appointment.id` (`onDelete: Cascade`) |
| `patientUsername`, `doctorId` | `String` | FKs |
| **Relations** | `messages → Message[]`, `ragDocuments → RagDocument[]` | cascade |

#### `Message` (`@@map("messages")`)
| Field | Type | Constraints |
|---|---|---|
| `id` | `String` | `@id @default(uuid())` |
| `consultationId` | `String` | FK → `Consultation.id` (`onDelete: Cascade`) |
| `senderId` | `String` | identifies the sender |
| `senderRole` | `Role` | enum |
| `message` | `String` | text content |
| **Indexes** | `@@index([consultationId, timestamp])`, `@@index([senderId])` | |

#### `FileKey` (`@@map("file_keys")`)
Maps encrypted file keys to a specific `fileId`, scoped to either a `patientUsername` or `doctorId`. Both FKs cascade on delete.

#### `MedicalAsset` (`@@map("medical_assets")`)
| Field | Type | Constraints |
|---|---|---|
| `id` | `String` | `@id @default(uuid())` |
| `userId` | `String` | FK → `User.id` (`onDelete: Cascade`) |
| `folderPath` | `String` | `@default("/my_documents/unclassified/")` |
| `assetCategory` | `String` | `@default("UNCLASSIFIED")` |
| `processingStatus` | `String` | `@default("PENDING")` |
| `extractedText` | `String? @db.Text` | OCR / parsed content |

#### `RagDocument` (`@@map("rag_documents")`)
| Field | Type | Constraints |
|---|---|---|
| `id` | `String` | `@id @default(uuid())` |
| `patientId` | `String` | FK → `Patient.username` (`onDelete: Cascade`) |
| `consultationId` | `String?` | FK → `Consultation.id` (`onDelete: SetNull`) |
| `sourceType` | `String` | e.g. `"consultation"`, `"upload"` |
| `content`, `summary` | `String` | raw text & summary |
| `embedding` | `Unsupported("vector")` | pgvector column |
| `metadata` | `Json? @db.JsonB` | arbitrary metadata |

#### `AiChatSession` / `AiChatMessage` (`@@map("ai_chat_sessions")` / `@@map("ai_chat_messages")`)
Persists AI chatbot conversation history. `AiChatSession` has `userId`, `role`, `mode` (`"default"` / `"patient_scoped"`), `targetPatientId`, and a one-to-many relation with `AiChatMessage` (which stores `role` and `content @db.Text`).

#### `AssetIndex` (`@@map("asset_indexes")`)
Structured metadata extracted from uploaded assets. Indexed by `[patientId, documentType]`, `[patientId, reportType]`, and `[patientId, documentDate]`.

#### `PatientMedicalHistory` (`@@map("patient_medical_histories")`)
Stores structured medical timeline entries with `historyType`, `title`, `value @db.Text`, `source`, `sourceId`, and `recordDate`. Indexed by `[patientId]` and `[patientId, historyType]`.

---

## 4. Backend API Routes

### 4.1 Auth (`backend/api/auth.py`) — Prefix: `/api/auth`

| Method | Path | Request Body | Response | Auth |
|---|---|---|---|---|
| `POST` | `/patient/login` | `LoginRequest{username, password}` | `TokenResponse{access_token, token_type, user_id, role}` | None |
| `POST` | `/patient/signup` | `UserRegistrationRequest{username, name, password}` | `TokenResponse` | None |
| `POST` | `/doctor/login` | `LoginRequest{doctor_id, password}` | `TokenResponse` | None |
| `POST` | `/doctor/signup` | `UserRegistrationRequest{doctor_id, name, password, specialization?, registration_number?, ...}` | `TokenResponse` | None |
| `GET` | `/api/me` | — | `CurrentUserProfileResponse` | Bearer |

**Pydantic validation**: `LoginRequest` enforces exactly one of `username` or `doctor_id` via `@model_validator`. `UserRegistrationRequest` validates password strength (≥8 chars, ≥1 uppercase, ≥1 digit) and name format (`^[a-zA-Z\s.'-]{2,100}$`).

### 4.2 Appointments (`backend/api/appointments.py`) — Prefix: `/api/appointments`

| Method | Path | Request Body | Response | Role Guard |
|---|---|---|---|---|
| `POST` | `/slots` | `list[SlotCreate{startTime, endTime}]` | `list[SlotResponse]` | `doctor` |
| `GET` | `/slots/{doctor_id}` | — | `list[SlotResponse]` | Any authenticated |
| `POST` | `/book/direct` | `DirectBookingRequest{slotId, reason, note?}` | `AppointmentResponse` | `patient` |
| `POST` | `/book/open` | `OpenBookingRequest{doctorId, reason, note?}` | `AppointmentResponse` | `patient` |
| `PUT` | `/{appointment_id}/action` | `DoctorActionRequest{status: ACCEPT\|REJECT, assignedDate?, doctorMessage?}` | `AppointmentResponse` | `doctor` |
| `GET` | `` | — | `list[AppointmentResponse]` | Any (routes by role) |
| `PATCH` | `/{appointment_id}/cancel` | — | `AppointmentActionResponse{success, message}` | Any (ownership check) |

### 4.3 Chat & AI (`backend/api/chat/router.py`) — Prefix: `/api/chat`

**REST Endpoints:**

| Method | Path | Request Body | Response |
|---|---|---|---|
| `GET` | `/consultations` | — | `list[ConsultationResponse]` |
| `GET` | `/consultations/{id}` | — | `ConsultationResponse` |
| `GET` | `/consultations/{id}/messages` | Query: `page`, `limit`, `role?` | `MessageHistoryResponse{items, page, limit, total, has_more}` |
| `POST` | `/consultations` | `ConsultationCreateRequest{appointment_id}` | `ConsultationResponse` |
| `POST` | `/consultations/{id}/messages` | `MessageCreateRequest{message}` | `MessageResponse` |
| `POST` | `/` | `ChatRequest{consultationId, message, language?, useReasoning?, model?}` | `dict` |
| `GET` | `/ai/history` | Query: `ai_session_id`, `target_patient_id?` | `{messages, ai_session_id}` |

**WebSocket Endpoints:**

| Path | Auth | Purpose |
|---|---|---|
| `/ws?token=<jwt>&consultation_id=<id>` | JWT query param | Real-time consultation messaging |
| `/ai/patient/ws?token=<jwt>` | JWT query param, `patient` role only | Patient AI chatbot with streaming |
| `/ai/doctor/ws?token=<jwt>&target_patient_id=<id>` | JWT query param, `doctor` role only | Doctor AI copilot with streaming |
| `/consultations/{id}/messages?token=<jwt>` | JWT query param | WebSocket for a specific consultation |

**AI WebSocket protocol**: On connect, sends `{type: "history", messages: [...]}`. On user text, builds `WorkflowState`, streams via `unified_chat_graph.astream_events(state, config, version="v2")`. Emits `{type: "status", node: "..."}` on node entry, `{type: "token", content: "..."}` for streaming chunks, and `{type: "final", content: "...", ai_session_id: "..."}` on completion. Uses `_StreamingMetadataBuffer` to strip leading JSON metadata objects from the LLM token stream.

**Session isolation**: Generic `ai_session_id` values like `"patient_ai"` are scoped by appending `_{user_id}`.

### 4.4 Medical Assets (`backend/api/medical_assets.py`) — Prefix: `/api/assets`

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/upload` | `multipart/form-data` (file) | `AssetUploadResponse{id}` |
| `GET` | `` | Query: `folder?` | `list[AssetResponse]` |
| `GET` | `/{asset_id}` | — | `AssetResponse` |
| `GET` | `/{asset_id}/download` | — | `FileResponse` |
| `PATCH` | `/{asset_id}/rename` | `{new_name}` | `AssetResponse` |
| `DELETE` | `/{asset_id}` | — | `{success: true}` |

On upload, a `BackgroundTasks` job calls `process_asset_background(id, file_path, file_type, prisma_client)` for OCR/text extraction.

### 4.5 Image Analysis (`backend/api/image_analysis.py`) — Prefix: `/api/images`

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/analyze` | `multipart/form-data` (image file), optional `prompt` and `model` query | `ImageAnalysisResponse` |
| `POST` | `/analyze/base64` | `ImageAnalysisRequest{image_base64, prompt?, model?}` | `ImageAnalysisResponse` |
| `GET` | `/providers` | — | `{vision_endpoint, gemini_configured, imagga_configured}` |

**Vision provider routing** (env `VISION_ENDPOINT`):
- `"gemini"` (default): Uses `google.genai.Client` SDK. Sends image as `Part.from_bytes` with a medical analysis prompt requesting structured JSON (findings, impression, recommendations, confidence, is_abnormal). Runs synchronous SDK call via `asyncio.to_thread`.
- `"imagga"`: Uses Imagga REST API (`httpx`). Uploads image, then fetches `/tags` and `/categories`.

### 4.6 Compatibility / Legacy (`backend/api/compat.py`) — Prefix: `/api`

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/update_patient_profile` | Multipart profile update (display_name, password, profile_pic) |
| `POST` | `/explain_report` | Upload a report/image for AI analysis (OCR + LLM or vision) |
| `POST` | `/analyze_document` | Analyze an existing asset by `file_id` |
| `POST` | `/analyze_xray` | X-ray specific analysis via `xray_analysis_service` |
| `GET` | `/medical-history` | List patient's `PatientMedicalHistory` entries |
| `POST` | `/medical-history` | Create a new `PatientMedicalHistory` entry |
| `DELETE` | `/medical-history/{entry_id}` | Delete an entry (ownership check) |

### 4.7 Stats (`backend/api/stats.py`) — Prefix: `/api/public`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/stats` | Returns global platform statistics (total doctors, patients, appointments) |

---

## 5. Core Services (`backend/services/`)

### 5.1 `AuthService` (`auth_service.py`)
- **`register_patient(username, name, password)`**: Normalizes & validates inputs → calls `_ensure_user_available` (checks both `patient` and `doctor` tables) → `hash_password()` → `client.patient.create()` → `_issue_token()`.
- **`register_doctor(doctor_id, name, password, **extra)`**: Maps snake_case kwargs to Prisma camelCase via `field_map` dict (e.g., `"registration_number" → "registrationNumber"`). Lowercases `gender`.
- **`login_patient` / `login_doctor`**: `find_unique()` → `verify_password()` → 401 if mismatch.
- **`AuthResult`** dataclass: `user_id`, `role`, `access_token`, `token_type="bearer"`.

### 5.2 `AppointmentService` (`appointment_service.py`)
- **`create_slots(doctor_id, slots)`**: Complex idempotent slot management. Sorts desired slots, checks for internal overlaps, queries all existing slots for the doctor, deactivates unbooked slots not in the desired set, reactivates exact matches, creates new slots with `uuid4()`. Returns full refreshed list.
- **`create_direct_booking(patient_id, data)`**: Validates slot availability (not booked, is active, no existing booking). Creates `Appointment` with `status="CONFIRMED"` inside a transactional pattern (rollback slot on failure).
- **`create_open_request(patient_id, data)`**: Creates `Appointment` with `status="PENDING"`, no slot linkage.
- **`handle_doctor_action(doctor_id, appointment_id, data)`**: Validates `ACCEPT` or `REJECT`. On accept, requires `assignedDate` and sets `status="CONFIRMED"`. On reject, sets `status="REJECTED"`.
- **`cancel_appointment(actor_role, actor_id, appointment_id)`**: Ownership check by role. Resets the linked slot (`isBooked=False, isActive=False`). Sets `status="CANCELLED"` and `slotId=None`.
- **Status normalization** (`_normalize_status`): Maps aliases like `"REQUESTED"→"PENDING"`, `"SCHEDULED"→"CONFIRMED"`, `"DECLINED"→"REJECTED"`.

### 5.3 `ChatService` (`chat_service.py`)
- **`get_user_consultations(user_id)`**: Queries consultations where user is patient or doctor, includes appointment and messages.
- **`save_message(consultation_id, user_id, role, message)`**: Creates a `Message` record, updates `Consultation.lastMessageAt`.
- **`get_ai_chat_history(session_id)`**: Fetches `AiChatMessage` records for a session, ordered by `createdAt`.
- **`append_ai_chat_exchange(ai_session_id, user_message, assistant_message)`**: Persists both user and assistant messages to `AiChatMessage`.
- **`ensure_ai_session(user_id, role, ai_session_id, mode)`**: Creates `AiChatSession` if it doesn't exist (upsert pattern).

### 5.4 `AssetService` (`asset_service.py`)
- **`upload_asset(user_id, file)`**: Saves file to `DATA_ROOT/<user_id>/`, creates `MedicalAsset` record with `processingStatus="PENDING"`.
- **`process_asset_background(asset_id, file_path, file_type, client)`**: Runs OCR/text extraction, updates `extractedText` and `processingStatus` to `"COMPLETED"` or `"FAILED"`.
- **`get_asset_file_path(user_id, asset_id)`**: Returns `(Path, original_name, mime_type)`.

### 5.5 `XrayAnalysisService` (`xray_analysis_service.py`)
Uses Gemini vision (via `google.genai` SDK) to analyze medical images. Returns structured JSON with `findings`, `impression`, `recommendations`, `confidence`, `is_abnormal`.

### 5.6 `DocumentAnalyzer`, `LabResultExtractor`, `PatientHistoryExtractor`
Domain-specific AI services that process raw medical text into structured `PatientMedicalHistory` or `AssetIndex` records.

---

## 6. AI & LangGraph Workflows (`backend/workflows/`)

### 6.1 State Schema (`state.py`)

`WorkflowState` is a `TypedDict` with `Annotated` LangGraph fields:

```python
class WorkflowState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # LangGraph message accumulator
    role: Literal["patient", "doctor"]
    mode: Literal["general", "patient_scoped"]
    user_id: str
    target_patient_id: str | None
    ai_session_id: str
    triage_level: str                       # "routine" | "emergency"
    context_payload: dict[str, Any]         # accumulates route/mode metadata
    final_response: str
    execution_plan: list[PlannerTask]       # tasks to execute
    evidence: list[dict[str, Any]]          # accumulated retrieval results
    action_results: list[dict[str, Any]]    # action handler outputs
    retrieval_strategy: str | None          # determined by keyword matching
    memory_context: list[dict]              # conversation memory
    appointment_context: dict               # appointment query results
    consultation_context: list[dict]        # consultation data
    asset_selection_context: dict           # selected assets for RAG
    rag_scope: dict                         # {asset_ids: [...]}
    patient_history_context: list[dict]     # medical history entries
    doctor_availability_context: list[dict] # available slots
    planner_metadata: dict                  # query_type, entities, actions
    shadow_execution_completed: bool
    shadow_response: str
    need_more_actions: bool                 # controls shadow pipeline loop
    execution_iteration: int                # loop counter (max 3)
    pending_tasks: list[PlannerTask]
    response_sections: list[dict]
```

`create_workflow_state()` initializes all fields with safe defaults (`[]`, `{}`, `""`, `False`, `0`).

### 6.2 Graph Topology (`unified_chat_graph.py`)

The compiled graph is built by `build_unified_chat_graph()` using `StateGraph[WorkflowState]` and checkpointed with `MemorySaver()`.

**Nodes** (11 registered):

| Node | Source |
|---|---|
| `log_entry_context` | Logs user_id, target_patient_id, ai_session_id, role |
| `shadow_pipeline` | `run_shadow_pipeline()` — the main data-gathering loop |
| `triage_evaluator` | `patient_nodes.triage_evaluator` |
| `patient_assistant_llm` | `patient_nodes.patient_assistant_llm` |
| `patient_general_llm` | `patient_nodes.patient_general_llm` |
| `doctor_general_llm` | `doctor_nodes.doctor_general_llm` |
| `doctor_scoped_llm` | `doctor_nodes.doctor_scoped_llm` |
| `guardrail` | `shared_nodes.medical_safety_guardrail` |
| `planner` | `planner_node` (registered but used inside shadow_pipeline) |
| `task_executor` | `task_executor_node` (registered but used inside shadow_pipeline) |
| `response_composer` | `response_composer_node` (registered but used inside shadow_pipeline) |

**Edges**:

```
START → log_entry_context → shadow_pipeline
                                    ↓ (conditional: route_by_role)
                    ┌───────────────┼───────────────────┐
                    ↓               ↓                   ↓
          triage_evaluator    doctor_general_llm   doctor_scoped_llm
                ↓ (conditional: route_patient_intent)
        ┌───────┴────────┐
        ↓                ↓
patient_assistant_llm  patient_general_llm
        ↓                ↓
        └───────┬────────┘
                ↓
           guardrail → END

doctor_general_llm → guardrail → END
doctor_scoped_llm  → guardrail → END
```

**`route_by_role(state)`**: If `role == "doctor"` and `mode == "patient_scoped"` → `doctor_scoped_llm`, else if `role == "doctor"` → `doctor_general_llm`, else → `triage_evaluator`.

**`route_patient_intent(state)`**: Calls `classify_intent(state)`. If result is `"emergency"` or `"patient_rag"` → `patient_assistant_llm`, else → `patient_general_llm`.

### 6.3 Shadow Pipeline (`run_shadow_pipeline`)

An imperative `while True` loop that runs before the main LLM nodes:

1. **`planner_node(state)`** → determines `execution_plan` and `retrieval_strategy`.
2. **Loop**:
   - **`task_executor_node(state)`** → executes all tasks in `execution_plan`.
   - **`need_action_decision_node(state)`** → checks if `pending_tasks` exist (max 3 iterations).
   - If `need_more_actions`, replaces `execution_plan` with `pending_tasks` and loops.
3. **`response_composer_node(state)`** → assembles `shadow_response` from all accumulated context.

Returns aggregated state fields: `execution_plan`, `evidence`, `planner_metadata`, `shadow_response`, `patient_history_context`, `consultation_context`, `memory_context`, `appointment_context`, `doctor_availability_context`.

### 6.4 Retrieval Strategy (`nodes/retrieval_strategy.py`)

Keyword-based classification of the user's last message:

| Keywords | Strategy |
|---|---|
| `"latest report"`, `"blood report"`, `"analyze my report"`, etc. | `DOCUMENT_QUERY` |
| `"doctor available"`, `"open slots"`, etc. | `DOCTOR_AVAILABILITY_QUERY` |
| `"appointment"`, `"reschedule"`, `"cancel"`, `"book"`, etc. | `APPOINTMENT_QUERY` |
| `"previous consultation"`, `"last visit"`, `"follow up"`, etc. | `CONSULTATION_QUERY` |
| *(fallback)* | `GENERAL_CHAT` |

`RetrievalStrategy` is a `str` `Enum` with 9 values: `DOCUMENT_QUERY`, `CONSULTATION_QUERY`, `APPOINTMENT_QUERY`, `ASSET_INDEX_QUERY`, `PATIENT_HISTORY_QUERY`, `MEMORY_QUERY`, `DEEP_REASONING`, `GENERAL_CHAT`, `DOCTOR_AVAILABILITY_QUERY`.

### 6.5 Planner Node (`nodes/planner.py`)

1. Gets `retrieval_strategy` from `retrieval_strategy_node`.
2. Parses user intent via `parse_intent(text)` → `ParsedIntent`.
3. Iterates through `PlannerRule` instances (loaded via `load_planner_rules()`). Each rule has `matches()` and `build_tasks()`.
4. Builds `TaskTemplate` objects, converts to `PlannerTask` via `build_task_from_template()`.
5. Deduplicates the `ExecutionPlan`.
6. Falls back to a `general_response` task if plan is empty.

### 6.6 Planner Rules (`planner_rule_registry.py`)

Six `PlannerRule` subclasses:

| Rule | Matches When | Generates Tasks |
|---|---|---|
| `AppointmentRule` | `parsed_intent.is_appointment` or strategy is `APPOINTMENT_QUERY` | `APPOINTMENT`, `APPOINTMENT_BOOK`, `APPOINTMENT_CANCEL`, or `APPOINTMENT_RESCHEDULE` |
| `DoctorAvailabilityRule` | strategy is `DOCTOR_AVAILABILITY_QUERY` | `DOCTOR_AVAILABILITY` |
| `ConsultationRule` | `parsed_intent.is_consultation` or strategy is `CONSULTATION_QUERY` | `MEMORY` + `CONSULTATION` |
| `PatientHistoryRule` | `parsed_intent.is_history` | `PATIENT_HISTORY` |
| `DocumentRule` | `parse_document_query(text)` returns a result | `ASSET_INDEX` |
| `MemoryRule` | strategy is `MEMORY_QUERY` | `MEMORY` |

### 6.7 Task Executor (`nodes/task_executor.py`)

Processes the `execution_plan` queue. For each `PlannerTask`:
- **`task_type == "retrieve"`**: Looks up the retriever by name from `RETRIEVAL_REGISTRY`, checks `requires_patient`/`requires_doctor` guards, and invokes the async retriever function.
- **`task_type == "action"`**: Looks up the action handler from `ACTION_REGISTRY`, invokes it, processes the `action_results` (types: `"appointment_context"`, `"evidence"`, `"message"`).

Results are merged into a `TaskExecutionResult` aggregate. `MAX_PENDING_TASK_DEPTH = 20`.

### 6.8 Retrieval Registry (`retrieval_registry.py`)

| Registry Key | Retriever Function | Data Populated |
|---|---|---|
| `MEMORY` | `retrieve_conversation_memory(session_id)` | `memory_context` |
| `CONSULTATION` | `retrieve_consultations(patient_id, doctor_id, limit=5)` | `consultation_context` |
| `PATIENT_HISTORY` | `get_patient_history(patient_id)` or `get_history_by_type(patient_id, type)` | `patient_history_context`, `evidence` |
| `ASSET_INDEX` | `get_latest_document(patient_id)` / `get_reports_by_report_type(patient_id, type)` + `retrieve_asset_scoped_context(query, asset_ids, patient_id)` | `asset_selection_context`, `rag_scope`, `evidence` |
| `APPOINTMENT` | `retrieve_appointments(patient_id, doctor_id, upcoming_only)` | `appointment_context`, `evidence` |
| `DOCTOR_AVAILABILITY` | `retrieve_doctor_availability(doctor_name)` | `doctor_availability_context`, `evidence` |

### 6.9 Action Registry (`action_registry.py`)

| Registry Key | Handler | Logic |
|---|---|---|
| `APPOINTMENT_BOOK` | `handle_appointment_book` | Resolves doctor from `doctor_availability_context`. Queries unbooked/active/future `DoctorSlot`s. Matches by exact datetime or ordinal (`"first"`, `"second"`, etc.). Books within a `prisma.tx()` transaction (creates `Appointment`, marks slot as booked). Localizes response to `Asia/Kolkata`. |
| `APPOINTMENT_CANCEL` | `handle_appointment_cancel` | Finds the most recent upcoming `CONFIRMED`/`PENDING` appointment for the patient. Resets slot (`isBooked=False, isActive=False`), sets appointment to `CANCELLED`. |
| `APPOINTMENT_RESCHEDULE` | `handle_appointment_reschedule` | Stub — returns action context only. |
| `APPOINTMENT_SEARCH_SLOTS` | `handle_appointment_search_slots` | Stub — returns empty results. |

### 6.10 LLM Nodes

**`triage_evaluator` (`patient_nodes.py`)**:
- Uses `model.with_structured_output(TriageEvaluation)`.
- System prompt: Clinical triage safety classifier looking for severe emergency symptoms (chest pain, trouble breathing, stroke, seizure, blue lips, etc.).
- Output: `TriageEvaluation{is_emergency: bool, rationale: str}`. Flexible `@model_validator` that scans all response keys for emergency/severity fields.

**`patient_general_llm` (`patient_nodes.py`)**:
- Constructs a system prompt: *"You are a helpful, empathetic medical assistant..."*
- Injects all accumulated context (patient history, consultations, memory, appointments, evidence) as JSON into the system message.
- Invokes `llm.ainvoke(messages)` (temperature 0.1).

**`patient_assistant_llm` (`patient_nodes.py`)**:
- Invokes `patient_rag_tool` with the user's query and the current state.
- Builds a system message: *"You are a medical AI. Answer using ONLY this retrieved data..."*

**`doctor_general_llm` (`doctor_nodes.py`)**:
- System prompt: *"You are a highly technical clinical reasoning copilot..."* — focuses on differential considerations, red-flag assessment, and next-step clinical thinking.

**`doctor_scoped_llm` (`doctor_nodes.py`)**:
- Invokes `doctor_rag_tool` scoped to `target_patient_id`.
- Same clinical copilot persona but grounded in specific patient RAG context.

### 6.11 RAG Tools (`nodes/tools.py`)

Two `@tool`-decorated LangChain tools:

- **`patient_rag_tool(query, top_k=5, similarity_threshold=0.30, state)`**: Scoped to `state.user_id`. If `rag_scope.asset_ids` exists, calls `pgvector_service.search_documents_by_assets()`, otherwise `pgvector_service.search_documents()`. Returns `{scope: "patient", items: [...], asset_scoped: bool}`.
- **`doctor_rag_tool(query, top_k=5, similarity_threshold=0.30, state)`**: Scoped to `state.target_patient_id`. Same search logic. Returns `{scope: "doctor", target_patient_id: "..."}`.

### 6.12 Medical Safety Guardrail (`shared_nodes.py`)

The terminal node before `END`. Scans the last AI message for clinical prognosis keywords (`"you have"`, `"diagnose"`, `"suffer from"`). If triggered, **replaces the entire response** with:
> *"I cannot provide a definitive diagnosis. Please consult a licensed physician."*

Stores the `triggered` flag and `original_response` in `context_payload.medical_safety_guardrail`.

### 6.13 Intent Classification (`nodes/routing.py`)

`classify_intent(state) → PatientIntent`:
- **`"emergency"`**: If the message contains any of: `"chest pain"`, `"difficulty breathing"`, `"stroke"`, `"face drooping"`, `"arm weakness"`, `"speech trouble"`, `"severe bleeding"`, `"unconscious"`, `"seizure"`, `"blue lips"`.
- **`"patient_rag"`**: If the message contains any of: `"report"`, `"blood"`, `"pain"`, `"symptom"`, `"medicine"`, `"medication"`, `"prescription"`, `"timeline"`, `"xray"`, `"scan"`, `"lab"`, `"result"`, `"follow up"`, `"checkup"`.
- **`"patient_general"`**: Fallback.

### 6.14 LLM Client (`workflows/common.py`)

`get_workflow_model(temperature=0.2)` returns an `LLMChatModel` from `backend.ai.core_services.llm_client.get_chat_model()`. The model is configured by `OPENAI_API_KEY`, `OPENAI_MODEL`, and `OPENAI_BASE_URL` environment variables (provider-agnostic OpenAI-compatible endpoint).

---

## 7. Frontend Implementation (`frontend/src/`)

### 7.1 Routing (`App.jsx`)

Uses `react-router-dom` v7 `BrowserRouter`.

| Path | Component | Guard |
|---|---|---|
| `/` | `Home` | None |
| `/login` | `Login` | None |
| `/patient/dashboard` | `PatientDashboard` | `RequirePatient` — redirects to `/login` if `!session` or `session.role !== 'patient'` |
| `/doctor/dashboard` | `DoctorDashboard` | `RequireDoctor` — redirects if not `doctor` role |
| `/reports/:id` | `ReportView` | `RequireAuth` — any authenticated user |
| `/prescriptions/:id` | `PrescriptionView` | `RequireAuth` |

Guard components (`RequirePatient`, `RequireDoctor`, `RequireAuth`) all return `null` while `!loaded` and `<Navigate to="/login" replace />` if unauthenticated or wrong role.

A global `<NotificationTray />` renders above all routes. A `justLoggedOut` banner shows a success toast for 3 seconds, and an `expired` banner shows a red session-expired message.

### 7.2 Context Providers (`src/contexts/`)

#### `SessionContext.jsx`
**State held**: `session` (object with user data, role, token), `loaded` (bool), `expired` (bool), `justLoggedOut` (bool).

**Bootstrap flow** (`useEffect → bootstrap()`):
1. Probes `apiClient.get('/health')`.
2. Reads `doctalk_token` and `doctalk_session` from `localStorage`.
3. If token exists, calls `authApi.me(token)` to validate and fetch full profile.
4. Sets `session` with merged data: `{...profileData, role, token}`.

**Exposed methods**:
- `login({token, sessionHint})`: Stores to `localStorage`, validates via `authApi.me()`.
- `logout()`: Clears `localStorage`, sets `justLoggedOut=true` with a 3-second auto-clear timer.
- `markExpired()`: Clears session and sets `expired=true`.

#### `NotificationContext.jsx`
Provides `addNotification({type, message})` for global toast notifications.

#### `AssetCacheContext.jsx`
Maintains an in-memory cache of decrypted medical assets and image URLs. Avoids redundant backend decryption calls.

### 7.3 Key Pages

- **`PatientDashboard.jsx` (189KB)**: Full patient interface — appointments panel, medical assets manager, AI chat via WebSocket (`/api/chat/ai/patient/ws`), document viewer, medical history.
- **`DoctorDashboard.jsx` (75KB)**: Doctor interface — slot management, appointment queue, patient-scoped AI copilot (`/api/chat/ai/doctor/ws?target_patient_id=...`), consultation chat.
- **`Login.jsx` (33KB)**: Tabbed login/signup for patient and doctor roles. Calls `/api/auth/patient/login`, `/api/auth/doctor/login`, etc. On success, calls `session.login({token, sessionHint})` and navigates to the role-specific dashboard.
- **`Home.jsx` (27KB)**: Public landing page with platform overview.

---

## 8. Environment Variables Reference

```env
# Database
DATABASE_URL=postgresql://...          # Prisma connection (via PgBouncer)
DIRECT_URL=postgresql://...            # Direct Prisma connection
SHADOW_DATABASE_URL=                   # For Prisma migrations

# Supabase
SUPABASE_URL=https://...supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...

# Auth
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# LLM (OpenAI-compatible)
OPENAI_API_KEY=...
OPENAI_MODEL=...                       # e.g., "LongCat-2.0-Preview"
OPENAI_BASE_URL=...                    # e.g., https://api.longcat.chat/openai

# Gemini (embeddings + vision)
GEMINI_API_KEY=...
GEMINI_EMBED_MODEL=gemini-embedding-001
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# Vision
VISION_ENDPOINT=gemini                 # "gemini" or "imagga"

# RAG tuning
RAG_EMBEDDING_DIMENSION=768
RAG_EMBEDDING_CACHE_SIZE=128
RAG_MAX_MEMORY_AGE_DAYS=365
AI_REQUEST_TIMEOUT_SECONDS=45
XRAY_ANALYSIS_TIMEOUT_SECONDS=300
```

---

<!-- BEGIN HOSPITAL DEPRECATION ZONE -->
## Hospital Modules (Pending Deprecation)

> **WARNING**: This entire section is quarantined for future removal. Do not couple new features to any of the models, endpoints, or services documented below.

### H.1 Hospital Database Schema

#### `Hospital` (`@@map("hospitals")`)
| Field | Type | Constraints |
|---|---|---|
| `hospitalId` | `String` | `@id` |
| `name` | `String` | required |
| `password` | `String` | hashed |
| `role` | `Role` | `@default(hospital)` |
| `totalBeds`, `availableBeds` | `Int?` | optional |
| `specialties` | `Json? @db.JsonB` | array of `{name, doctors}` objects |
| `isVerified` | `Boolean` | `@default(false)` |
| `displayName`, `address`, `city`, `state`, `registrationNumber`, `phone`, `email`, `website`, `profilePic` | `String?` | optional |
| **Relations** | `symptomReports → SymptomReport[]`, `hospitalNews → HospitalNews[]`, `registeredPatients → Patient[]` (via `Patient.registeredByHospitalId`) | cascade |

#### `SymptomReport` (`@@map("symptom_reports")`)
| Field | Type | Constraints |
|---|---|---|
| `id` | `String` | `@id @default(uuid())` |
| `hospitalId` | `String` | FK → `Hospital.hospitalId` (`onDelete: Cascade`) |
| `patientName` | `String?` | optional patient reference |
| `patientAge` | `Int?` | optional |
| `patientGender` | `Gender?` | optional enum |
| `diseaseName` | `String` | required |
| `symptoms` | `Json @db.JsonB` | required array |
| `newSymptoms` | `Json? @db.JsonB` | optional |
| `severity` | `SymptomSeverity` | `@default(moderate)` |
| `status` | `String` | `@default("admitted")` — `"admitted"`, `"discharged"`, `"deceased"` |
| `isAnonymous` | `Boolean` | `@default(false)` |
| **Indexes** | `@@index([hospitalId])`, `@@index([diseaseName])`, `@@index([reportedDate])` | |

#### `HospitalNews` (`@@map("hospital_news")`)
| Field | Type | Constraints |
|---|---|---|
| `id` | `String` | `@id @default(uuid())` |
| `hospitalId` | `String` | FK → `Hospital.hospitalId` (`onDelete: Cascade`) |
| `title` | `String` | required |
| `content` | `String @db.Text` | required |
| `category` | `String` | `@default("general")` |
| `isGlobal` | `Boolean` | `@default(false)` |
| `priority` | `Int` | `@default(0)` |
| **Indexes** | `@@index([hospitalId])`, `@@index([isGlobal, publishedAt])`, `@@index([category])` | |

### H.2 Hospital Pydantic Schemas (`backend/schemas/hospital_schemas.py`)

**Auth**: `HospitalLoginRequest{hospital_id, password}`, `HospitalRegisterRequest{hospital_id, name, password, address?, city?, state?, registration_number?, phone?, email?, website?}`, `HospitalTokenResponse{access_token, token_type, hospital_id, role}`.

**Symptom Reports**: `SymptomReportCreate{patient_name?, patient_age?(0-150), patient_gender?, patient_username?, disease_name, symptoms: list[str], new_symptoms?, severity: Literal["mild","moderate","severe","critical"], status?, onset_date?, additional_notes?, is_anonymous?}`. `SymptomReportStatusUpdate{status: Literal["admitted","discharged","deceased"]}`.

**Patient Management**: `HospitalPatientRegisterRequest{username(min=4), name(min=2), password(default="Password123", min=8), email?, mobile?, gender?, blood_group?, address?}`.

**Profile**: `HospitalProfileUpdate` includes `total_beds(0-100000)`, `available_beds(0-100000)`, `specialties: list[dict]?`. Has a `@model_validator` enforcing `available_beds <= total_beds` and a `@field_validator` on `specialties` that cleans entries to `{name: str, doctors: int}`.

**Dashboard**: `HospitalDashboardResponse{hospital_id, hospital_name, total_reports, total_news, recent_reports, disease_summary, severity_breakdown, admitted_count, discharged_count, death_count, patients, total_beds, available_beds, specialties}`.

### H.3 Hospital API Routes (`backend/api/hospital.py`)

**Prefix**: `/api/hospital` (authenticated) and `/api/hospital/public` (public).

| Method | Path | Request | Response | Role |
|---|---|---|---|---|
| `POST` | `/auth/login` | `HospitalLoginRequest` | `HospitalTokenResponse` | None |
| `POST` | `/auth/signup` | `HospitalRegisterRequest` | `HospitalTokenResponse` | None |
| `POST` | `/reports` | `SymptomReportCreate` | `SymptomReportResponse` | `hospital` |
| `GET` | `/reports` | Query: `page`, `per_page`, `disease?`, `severity?` | `SymptomReportListResponse` | `hospital` |
| `GET` | `/reports/{report_id}` | — | `SymptomReportResponse` | Any |
| `GET` | `/reports/patient/{username}` | — | `SymptomReportListResponse` | `hospital` |
| `PUT` | `/reports/{report_id}/status` | `SymptomReportStatusUpdate` | `SymptomReportResponse` | `hospital` |
| `GET` | `/detailed-analysis` | — | Analysis dict | `hospital` |
| `POST` | `/news` | `HospitalNewsCreate` | `HospitalNewsResponse` | `hospital` |
| `GET` | `/news` | — | `list[HospitalNewsResponse]` | `hospital` |
| `PUT` | `/profile` | `HospitalProfileUpdate` | `HospitalProfileResponse` | `hospital` |
| `GET` | `/profile` | — | `HospitalProfileResponse` | `hospital` |
| `GET` | `/dashboard` | — | `HospitalDashboardResponse` | `hospital` |
| `POST` | `/register-patient` | `HospitalPatientRegisterRequest` | `HospitalPatientResponse` | `hospital` |
| `GET` | `/patients` | — | `list[HospitalPatientResponse]` | `hospital` |
| `GET` | `/patients/{username}/medical-history` | — | Medical history dict | `hospital` |

**Public routes** (prefix `/api/hospital/public`):

| Method | Path | Response |
|---|---|---|
| `GET` | `/detailed-analysis/global` | Global analysis dict |
| `GET` | `/news/global?limit=10` | `list[HospitalNewsResponse]` |
| `GET` | `/reports/global` | `SymptomReportListResponse` |
| `GET` | `/disease-summary` | `list[{disease, count}]` |

### H.4 Hospital Service (`backend/services/hospital_service.py`, 825 lines)

**`HospitalService`** class (uses `prisma_client`):

- **`register(hospital_id, name, password, **extra)`**: Validates inputs, checks uniqueness via `client.hospital.find_unique()`, hashes password, maps snake_case extras to Prisma camelCase, creates record.
- **`login(hospital_id, password)`**: `find_unique()` → `verify_password()` → `create_access_token(role="hospital")`.

- **`create_symptom_report(hospital_id, data)`**: Validates `disease_name` and `symptoms` (at least one). If `patient_username` provided, verifies patient exists and `registeredByHospitalId == hospital_id`. Converts `severity` string to `SymptomSeverity` enum. Creates `SymptomReport` record. **Cross-model side effect**: If linked to a patient, creates a `PatientMedicalHistory` entry with `historyType="symptom_report"`.
- **`update_report_status(hospital_id, report_id, new_status)`**: Validates status ∈ `["admitted", "discharged", "deceased"]`. Updates the report. If the report was linked to a patient (`patientName` set), updates the corresponding `PatientMedicalHistory` record's title and date.

- **`get_detailed_analysis(hospital_id=None)`**: Fetches all reports (optionally filtered by hospital). Iterates to build per-disease aggregation dicts tracking: total, admitted, discharged, deaths, severity breakdown (mild/moderate/severe/critical), gender counts, ages. Computes: `avg_age`, `mortality_rate` (deaths/total×100), `recovery_rate` (discharged/total×100), `avg_severity_score` (1-4 scale). Returns sorted arrays: `disease_breakdown` (by total, descending), `most_deadly_diseases` (top 10 by mortality rate, filtered to `deaths > 0`).

- **`get_dashboard(hospital_id)`**: Aggregates: total reports, total news, 5 most recent reports, disease summary, severity breakdown, full detailed analysis, admitted/discharged/death counts, registered patients list, bed counts, specialties.

- **`register_patient(hospital_id, data)`**: Creates a new `Patient` record with `registeredByHospitalId` set to the hospital. Validates username (≥4 chars), name (≥2 chars), password (≥8 chars), gender enum. Hashes password via `hash_password()`.

- **`get_patient_full_medical_history(hospital_id, patient_username)`**: Verifies patient ownership. Returns `PatientMedicalHistory` entries + all linked `SymptomReport` records.

### H.5 Hospital Frontend (`frontend/src/pages/HospitalDashboard.jsx`)

A standalone 82KB React component guarded by `RequireHospital`. Interfaces with:
- `/api/hospital/dashboard` for dashboard data
- `/api/hospital/reports` for CRUD operations on symptom reports
- `/api/hospital/news` for news management
- `/api/hospital/profile` for profile updates
- `/api/hospital/patients` for patient registry
- `/api/hospital/detailed-analysis` for analytics

Uses Recharts for data visualization (disease trends, severity breakdowns, mortality statistics).

### H.6 Hospital Routing (`App.jsx`)

```jsx
<Route path="/hospital/dashboard"
  element={<RequireHospital loaded={loaded} session={session}><HospitalDashboard /></RequireHospital>} />
```

The `RequireHospital` guard checks `session.role !== 'hospital'` and redirects to `/login`.
<!-- END HOSPITAL DEPRECATION ZONE -->
