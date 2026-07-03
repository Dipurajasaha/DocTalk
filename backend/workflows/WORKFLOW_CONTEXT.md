# DocTalk AI Chat Workflow — Complete Context

> This document describes the **entire** AI chat orchestration system for the DocTalk healthcare platform. It is designed to be fed as context to another LLM so it can understand, reason about, extend, or debug this workflow.

---

## 1. High-Level Architecture

The AI chat system is a **LangGraph state machine** that processes patient and doctor chat messages. It has **two execution pipelines** that run in sequence on every message:

1. **Shadow Pipeline** — A deterministic, keyword-driven pipeline that runs **before** the LLM. It parses the user's intent, plans retrieval tasks, executes them against the database, and collects structured evidence (appointments, medical history, doctor availability, consultation records, uploaded documents via RAG). This pipeline does NOT call the LLM; it purely gathers data.

2. **Legacy LLM Pipeline** — After the shadow pipeline enriches the state with retrieved context, the message is routed to the appropriate LLM node based on the user's role (patient/doctor). The LLM node generates a natural-language response grounded in the retrieved data, and the response passes through a medical safety guardrail before being returned.

### Execution Flow

```
User Message (via WebSocket)
       │
       ▼
┌─────────────────────┐
│  log_entry_context   │  Logs user/session metadata
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   shadow_pipeline    │  Intent parsing → Planning → Task Execution → Response Composition
│                      │  (runs planner_node → task_executor_node loop → response_composer_node)
│                      │  Enriches state with: appointment_context, patient_history_context,
│                      │  doctor_availability_context, consultation_context, memory_context,
│                      │  evidence[], rag_scope, asset_selection_context
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   route_by_role      │  Conditional edge based on state["role"] and state["mode"]
└──┬───────┬───────┬──┘
   │       │       │
   ▼       ▼       ▼
PATIENT  DOCTOR   DOCTOR
 PATH    GENERAL  SCOPED
   │       │       │
   ▼       │       │
triage_    │       │
evaluator  │       │
   │       │       │
   ▼       │       │
classify_  │       │
intent     │       │
  ┌┴┐      │       │
  │ │      │       │
  ▼ ▼      ▼       ▼
patient_ patient_ doctor_  doctor_
assist.  general  general  scoped
_llm     _llm     _llm     _llm
  │       │       │       │
  └───┬───┘       └───┬───┘
      │               │
      ▼               ▼
┌─────────────────────────┐
│ medical_safety_guardrail │  Regex-based check for prohibited prognosis language
└──────────┬──────────────┘
           │
           ▼
          END → Response sent via WebSocket
```

---

## 2. State Schema

Every node receives and returns a `WorkflowState` TypedDict. The full schema is defined in `state.py`:

```python
class WorkflowState(TypedDict):
    # ── Core Chat Fields ──
    messages: Annotated[list[BaseMessage], add_messages]  # Full conversation history
    role: "patient" | "doctor"                            # Who is chatting
    mode: "general" | "patient_scoped"                    # Doctor mode: general or scoped to a patient
    user_id: str                                          # Authenticated user ID
    target_patient_id: str | None                         # Patient ID for doctor-scoped queries
    ai_session_id: str                                    # Unique AI session ID
    triage_level: str                                     # "routine" or "emergency"
    context_payload: dict[str, Any]                       # Metadata accumulator (route info, triage, guardrail)
    final_response: str                                   # The final LLM response text
    workflow_version: str                                 # Always "v1"

    # ── Shadow Pipeline Fields ──
    execution_plan: list[PlannerTask]                     # Tasks to execute (retrieve or action)
    evidence: list[dict[str, Any]]                        # Collected evidence from all tasks
    action_results: list[dict[str, Any]]                  # Results from action handlers
    retrieval_strategy: str | None                        # Enum value from RetrievalStrategy
    memory_context: list[dict[str, Any]]                  # Previous conversation messages
    appointment_context: dict[str, Any]                   # Appointment data and action results
    consultation_context: list[dict[str, Any]]            # Past doctor-patient consultations
    asset_selection_context: dict[str, Any]               # Selected document/asset IDs
    rag_scope: dict[str, Any]                             # Contains asset_ids for scoped RAG
    patient_history_context: list[dict[str, Any]]         # Medical history entries
    doctor_availability_context: list[dict[str, Any]]     # Available doctor time slots
    planner_metadata: dict[str, Any]                      # Planner classification info
    shadow_execution_completed: bool                      # Whether shadow pipeline finished
    shadow_response: str                                  # Text summary from shadow pipeline
    need_more_actions: bool                               # Whether executor loop should continue
    execution_iteration: int                              # Current executor loop iteration
    pending_tasks: list[PlannerTask]                      # Tasks spawned during execution
    response_sections: list[dict[str, Any]]               # Structured response sections
```

---

## 3. Shadow Pipeline — Detailed Breakdown

The shadow pipeline is implemented as `run_shadow_pipeline()` in `unified_chat_graph.py`. It is a single LangGraph node that internally chains three sub-steps:

### 3.1 Planner Node (`planner_node`)

**File:** `planner/planner.py`

1. Calls `retrieval_strategy_node` to determine the retrieval strategy via keyword matching.
2. Calls `parse_intent()` to extract structured intent from the user's message.
3. Iterates through ordered planner rules to generate an `ExecutionPlan` of `PlannerTask` objects.
4. Falls back to a `general_response` task if no rules matched.

**Retrieval Strategy** (`planner/retrieval_strategy.py`): Keyword-based classification into one of:
- `DOCTOR_AVAILABILITY_QUERY` — "doctor available", "slots", "availability", etc.
- `DOCUMENT_QUERY` — "latest report", "blood report", "analyze my report", etc.
- `APPOINTMENT_QUERY` — "appointment", "book", "cancel", "schedule", etc.
- `CONSULTATION_QUERY` — "previous consultation", "last visit", etc.
- `GENERAL_CHAT` — everything else

**Intent Parser** (`planner/parsers/intent_parser.py`): Produces a `ParsedIntent` dataclass with:
- `intent_type`: "appointment", "symptom", "consultation", "patient_history", or None
- `entities`: detected keywords (e.g., "cardiologist", "chest pain")
- `actions`: detected verbs (e.g., "book", "cancel", "upcoming", "list")
- `doctor_name`: regex-extracted doctor name
- `booking_datetime` / `booking_ordinal`: for booking-specific intents
- `is_appointment`, `is_consultation`, `is_history`: boolean flags

**Planner Rules** (`planner/planner_rule_registry.py`): Executed in order defined by `RULE_EXECUTION_ORDER`:
1. `PatientHistoryRule` — triggers on "medical history", "medications", "surgery", "allergy", etc.
2. `DocumentRule` — triggers on "compare", "latest", "analyze" combined with "blood", "mri", "prescription", "report"
3. `AppointmentRule` — triggers on appointment entities + actions (book/cancel/reschedule/list/upcoming)
4. `DoctorAvailabilityRule` — triggers on `DOCTOR_AVAILABILITY_QUERY` strategy
5. `ConsultationRule` — triggers on symptom entities or consultation triggers ("recommend", etc.)
6. `MemoryRule` — triggers on `MEMORY_QUERY` strategy

Each rule produces `TaskTemplate` objects that are converted to `PlannerTask` objects via `task_template_registry.py`.

### 3.2 Task Executor Node (`task_executor_node`)

**File:** `executor/task_executor.py`

Processes the `execution_plan` queue. Each `PlannerTask` has a `task_type`:

- **`"retrieve"`** — Looks up the retriever by name from `retrieval_registry.py` and calls it. Retrievers are async functions that query the database and return structured data.
- **`"action"`** — Looks up the action handler by name from `action_registry.py` and calls it. Action handlers perform write operations (e.g., booking an appointment).

The executor runs in a loop: if a task produces `pending_tasks`, those are appended to the queue. A safety limit of `MAX_PENDING_TASK_DEPTH = 20` prevents infinite loops.

**Retrieval Registry** (`executor/retrieval_registry.py`): Maps retriever names to async functions:

| Name | Retriever | Database Table | Returns |
|------|-----------|----------------|---------|
| `MEMORY` | `retrieve_memory_wrapper` | `AiChatMessage` | `memory_context` |
| `CONSULTATION` | `retrieve_consultation_wrapper` | `Consultation` + `ConsultationMessage` | `consultation_context` |
| `PATIENT_HISTORY` | `retrieve_patient_history_wrapper` | `PatientHistory` (via service) | `patient_history_context` |
| `ASSET_INDEX` | `retrieve_asset_index_wrapper` | `AssetIndex` + pgvector RAG | `asset_selection_context`, `rag_scope`, `evidence` |
| `APPOINTMENT` | `retrieve_appointment_wrapper` | `Appointment` + `Doctor` + `DoctorSlot` | `appointment_context`, `evidence` |
| `DOCTOR_AVAILABILITY` | `retrieve_doctor_availability_wrapper` | `Doctor` + `DoctorSlot` | `doctor_availability_context`, `evidence` |

**Action Registry** (`executor/action_registry.py`): Maps action names to async handlers:

| Name | Handler | Effect |
|------|---------|--------|
| `APPOINTMENT_BOOK` | `handle_appointment_book` | Creates appointment + marks slot as booked (DB transaction) |
| `APPOINTMENT_CANCEL` | `handle_appointment_cancel` | Cancels appointment + releases slot (marks inactive) |
| `APPOINTMENT_RESCHEDULE` | `handle_appointment_reschedule` | Stub — returns context only |
| `APPOINTMENT_SEARCH_SLOTS` | `handle_appointment_search_slots` | Stub — no-op |

### 3.3 Need-More-Actions Decision Node

**File:** `executor/need_action_decision.py`

Simple gate: returns `need_more_actions = True` if `pending_tasks` is non-empty and `execution_iteration < 3`.

### 3.4 Response Composer Node

**File:** `composer/response_composer.py`

Takes all the enriched context from the state and produces a `ComposedResponse`. This builds `response_sections` (a list of typed content blocks) and a `shadow_response` text summary. The shadow response is NOT the final user-visible response — it's an intermediate summary used for debugging. The actual LLM generates the user-facing response downstream.

---

## 4. LLM Pipeline — Detailed Breakdown

### 4.1 Route by Role (`route_by_role`)

Conditional edge function:
- `role == "doctor"` + `mode == "patient_scoped"` → `doctor_scoped_llm`
- `role == "doctor"` + anything else → `doctor_general_llm`
- `role == "patient"` → `triage_evaluator`

### 4.2 Triage Evaluator (Patient Only)

**File:** `llm/patient/patient_nodes.py`

- Uses `model.with_structured_output(TriageEvaluation)` for structured LLM classification.
- Schema: `TriageEvaluation(is_emergency: bool, rationale: str)`
- Emergency symptoms: chest pain, breathing difficulty, stroke, seizure, unconsciousness, severe bleeding, blue lips.
- Sets `triage_level = "emergency"` in state if triggered.
- The `TriageEvaluation` model includes a `parse_flexible_fields` validator that handles varying LLM output field names.

### 4.3 Classify Intent (Patient Only)

**File:** `llm/patient/routing.py`

Keyword-based routing (NOT an LLM call):
- Emergency terms → `"emergency"` → routes to `patient_assistant_llm`
- Clinical terms (report, blood, pain, symptom, etc.) → `"patient_rag"` → routes to `patient_assistant_llm`
- Everything else → `"patient_general"` → routes to `patient_general_llm`

### 4.4 Patient General LLM

**File:** `llm/patient/patient_nodes.py` → `patient_general_llm()`

- Injects ALL shadow pipeline context (patient history, consultations, memory, appointments, evidence) into the system prompt.
- System prompt: "You are a helpful, empathetic medical assistant... Use ONLY retrieved context data."
- When context is available, sends only the latest message (not full history) to avoid confusing the LLM with previous AI messages.

### 4.5 Patient Assistant LLM (With RAG)

**File:** `llm/patient/patient_nodes.py` → `patient_assistant_llm()`

- Calls `patient_rag_tool` which queries pgvector with the user's message scoped to their `user_id`.
- If `rag_scope.asset_ids` is set (by shadow pipeline), it calls `search_documents_by_assets` for targeted retrieval.
- System prompt: "You are a medical AI. Answer the user's query using ONLY this retrieved data."

### 4.6 Doctor General LLM

**File:** `llm/doctor/doctor_nodes.py` → `doctor_general_llm()`

- System prompt: "You are a highly technical clinical reasoning copilot..."
- No RAG. Sends full message history.

### 4.7 Doctor Scoped LLM

**File:** `llm/doctor/doctor_nodes.py` → `doctor_scoped_llm()`

- Calls `doctor_rag_tool` scoped to `target_patient_id`.
- System prompt includes retrieved patient records.

### 4.8 Medical Safety Guardrail

**File:** `guardrails/medical_safety_guardrail.py`

- Scans the last AI message for: `"you have"`, `"diagnose"`, `"suffer from"` (case-insensitive).
- If triggered, **replaces** the entire response with: "I cannot provide a definitive diagnosis. Please consult a licensed physician."

---

## 5. RAG Tools

**File:** `capabilities/tools/rag_tools.py`

Two LangChain `@tool` decorated functions that query the pgvector vector store:

### `patient_rag_tool`
- Scoped to `state["user_id"]`
- If `rag_scope.asset_ids` exists → `pgvector_service.search_documents_by_assets()`
- Otherwise → `pgvector_service.search_documents()`
- Default: `top_k=5`, `similarity_threshold=0.30`

### `doctor_rag_tool`
- Scoped to `state["target_patient_id"]`
- Same logic as patient_rag_tool but for a different user scope.

---

## 6. Data Models

### PlannerTask (`models/planner_task.py`)
```python
@dataclass
class PlannerTask:
    task_type: str                    # "retrieve" | "action" | "general_response"
    retriever: str | None             # Registry key (e.g., "APPOINTMENT", "PATIENT_HISTORY")
    action_handler: str | None        # Registry key (e.g., "APPOINTMENT_BOOK")
    action: str | None                # Sub-action (e.g., "latest", "upcoming")
    parameters: dict[str, Any]        # Extra params (booking_datetime, doctor_name, etc.)
```

### ExecutionPlan (`models/execution_plan.py`)
- A list of `PlannerTask` with `deduplicate()` (by task signature) and `to_list()`.

### TaskExecutionResult (`models/task_execution_result.py`)
- Aggregate container that merges results from multiple task executions.
- Tracks all context types and supports `pending_tasks` for chained execution.

### ComposedResponse (`models/composed_response.py`)
- Converts enriched state into `response_sections` and a `shadow_response` text.

### ParsedIntent (`planner/parsers/intent_parser.py`)
- Structured extraction of user intent, entities, actions, doctor name, booking details.

### DocumentQueryIntent (`planner/parsers/document_query_parser.py`)
- Specialized parser for document/report queries (compare, latest, analyze).

### TaskTemplate (`models/task_template.py`)
- Simple `(template_name, parameters)` pair produced by planner rules, converted to `PlannerTask` via the task template registry.

---

## 7. External Dependencies (Outside `workflows/`)

### 7.1 Chat Router (`backend/api/chat/router.py`)
- FastAPI WebSocket endpoint that receives user messages.
- Authenticates via JWT token in query params.
- Builds `WorkflowState` via `create_workflow_state()`.
- Invokes `unified_chat_graph` via `astream_events()` for token streaming.
- Includes a `_StreamingMetadataBuffer` that strips leading JSON metadata from streamed tokens.
- Includes `_sanitize_ai_message()` that removes JSON fences, XML tags, and leading JSON objects.
- Persists messages to `AiChatMessage` table.

### 7.2 LLM Client (`backend/ai/core_services/llm_client.py`)
- Provides `get_chat_model()` which returns a LangChain-compatible chat model.
- Configured via env vars: `GEMINI_API_KEY`, `GEMINI_MODEL` (default: `gemini-2.0-flash`).
- Default temperature: `0.2` (overridden to `0.1` in some nodes).

### 7.3 Vector Store (`backend/ai/vectorstore/pgvector_service.py`)
- `pgvector_service.search_documents()` — similarity search scoped to a patient.
- `pgvector_service.search_documents_by_assets()` — similarity search scoped to specific asset IDs.
- Embeddings via `text-embedding-004` (768 dims).

### 7.4 Prompt Templates (`backend/ai/prompts/templates.py`)
- `PromptService` with templates for: summary, X-ray analysis, consultation review.
- Includes `_context_block()` with prompt injection defense (strips "ignore previous instructions", etc.).

### 7.5 Database (Prisma ORM)
- Tables accessed by retrievers: `Appointment`, `Doctor`, `DoctorSlot`, `Consultation`, `ConsultationMessage`, `AiChatMessage`, `AssetIndex`, `PatientHistory`.

### 7.6 Checkpointer
- `MemorySaver()` — in-memory LangGraph checkpointer.
- Conversation continuity is keyed by `ai_session_id`.
- **Resets on server restart** (no persistent checkpointing).

---

## 8. LLM Model Configuration

| Setting | Value |
|---------|-------|
| Chat Model | `gemini-2.0-flash` (override: `GEMINI_MODEL` env var) |
| Embeddings | `text-embedding-004` (768 dims) |
| Temperature | `0.1`–`0.2` (varies by node) |
| API Key | `GEMINI_API_KEY` (required) |

---

## 9. File Index

```
backend/workflows/
├── WORKFLOW_CONTEXT.md            ← This file
├── graph/
│   ├── unified_chat_graph.py      ← Main graph definition & shadow pipeline
│   ├── state.py                   ← WorkflowState TypedDict & factory functions
│   └── common.py                  ← get_workflow_model(), latest_message_text()
├── planner/
│   ├── planner.py                 ← Planner node
│   ├── retrieval_strategy.py      ← RetrievalStrategy enum & node
│   ├── planner_rule_config.py     ← Keyword configs
│   ├── planner_rule_order.py      ← Rule execution order
│   ├── planner_rule_loader.py     ← Rule loader
│   ├── planner_rule_registry.py   ← Planner rules
│   ├── task_template_registry.py  ← Converts TaskTemplate → PlannerTask
│   └── parsers/
│       ├── intent_parser.py       ← ParsedIntent extraction
│       └── document_query_parser.py ← DocumentQueryIntent extraction
├── executor/
│   ├── task_executor.py           ← Task executor node
│   ├── retrieval_registry.py      ← Maps retrievers
│   ├── action_registry.py         ← Maps action handlers
│   └── need_action_decision.py    ← Decision node for loop
├── capabilities/
│   ├── retrievers/                ← 7 DB retrievers
│   ├── actions/                   ← Action handler implementations
│   └── tools/                     ← RAG tools & appointment tools
├── composer/
│   ├── response_composer.py       ← ComposedResponse node
│   └── evidence_collector.py      ← Evidence collector
├── llm/
│   ├── patient/                   ├── patient_nodes.py & routing.py
│   └── doctor/                    └── doctor_nodes.py
├── guardrails/
│   └── medical_safety_guardrail.py ← Medical safety filter
└── models/                        ← Dataclasses (PlannerTask, ExecutionPlan, etc.)
```

---

## 10. Key Design Decisions & Known Limitations

1. **Keyword-based routing**: Both `classify_intent` and `retrieval_strategy_node` use hardcoded keyword lists. No LLM is involved in intent classification (except triage). This is fast but brittle — novel phrasings may be misrouted.

2. **Shadow pipeline runs synchronously inside a single node**: `run_shadow_pipeline()` calls `planner_node → task_executor_node (loop) → response_composer_node` in sequence as a regular Python function, not as separate LangGraph edges. This means LangGraph's checkpointing/visualization doesn't capture the shadow pipeline's internal steps.

3. **Dual retrieval paths**: The shadow pipeline retrieves structured data from the database (appointments, history). The LLM nodes may additionally call RAG tools for vector similarity search. These are independent — the shadow pipeline doesn't use pgvector, and the RAG tools don't query the relational DB.

4. **MemorySaver is ephemeral**: Conversation state resets on server restart. There is no persistent checkpointer.

5. **`tools/appointment_tools.py` is unused**: These LangChain `@tool` wrappers exist but are never passed to any LLM as tools. The actual appointment booking goes through the `action_registry` instead.

6. **Medical safety guardrail is regex-only**: Simple substring matching on "you have", "diagnose", "suffer from". Can produce false positives (e.g., "Do you have any questions?") and false negatives (rephrased diagnoses).

7. **No true agentic behavior**: The LLM never autonomously decides which tools to call. All tool/retriever selection is pre-determined by keyword matching before the LLM is invoked.
