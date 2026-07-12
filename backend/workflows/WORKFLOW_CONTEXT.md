# DocTalk AI Chat Workflow — Complete Context

> This document describes the **entire** AI chat orchestration system for the DocTalk healthcare platform. It is designed to be fed as context to another LLM so it can understand, reason about, extend, or debug this workflow.
> 
> **Updated from source code on 2026-07-11.**

---

## 1. High-Level Architecture

The AI chat system is a **LangGraph state machine** that processes patient and doctor chat messages through a **linear pipeline of 8 nodes**. There is no branching at the graph level — role-based routing happens internally inside the `llm_orchestrator` node.

### Execution Flow

```
User Message (via WebSocket)
       │
       ▼
┌─────────────────────┐
│   input_guardrail    │  Security: Prompt injection / jailbreak / role manipulation detection
│                      │  Domain: TF-IDF cosine similarity validates medical relevance
│                      │  Verdict: ALLOW → continue │ BLOCK → set final_response + END
└──────────┬──────────┘
           │ (conditional edge)
           ▼
┌─────────────────────┐
│  log_entry_context   │  Logs user_id, target_patient_id, ai_session_id, role
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      planner         │  Intent parsing → Rule-based plan generation → LLM fallback planner
│                      │  Hydrates conversation_memory → Produces execution_plan[]
│                      │  Sets planner_metadata (query_type, active_workflow, entities, etc.)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    authorization     │  Filters execution_plan by role-based allowed_roles from CapabilityMetadata
│                      │  Rejects capabilities the current user's role is not authorized for
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   task_executor      │  Executes PlannerTask queue (retrieve / action) via capability_registry
│                      │  Supports task dependencies (depends_on, produces, consumes)
│                      │  Tracks execution via ExecutionContext (evidence, timing, statistics)
│                      │  Runs ConversationMemoryManager.update() at end
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ recommendation_engine│  Patient-only, evidence-driven specialist recommendation
│                      │  Rule-based specialty detection (keyword matching on evidence)
│                      │  Searches past consultations/appointments for previously seen doctors
│                      │  Appends care_recommendation evidence block
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  response_composer   │  Enriches evidence with consultation/history detail
│                      │  Detects action capabilities (BOOK/CANCEL) → sets final_response directly
│                      │  Otherwise, passes enriched evidence for LLM to consume
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   llm_orchestrator   │  Internal sub-routing (no graph edges):
│                      │  • If final_response already set → wraps as AIMessage (action confirmation)
│                      │  • Doctor + DOCTOR_PATIENT → doctor_scoped_llm
│                      │  • Doctor + anything else → doctor_general_llm
│                      │  • Patient → triage_evaluator → classify_intent → route to:
│                      │    - emergency/patient_rag → patient_assistant_llm
│                      │    - knowledge → patient_knowledge_llm
│                      │    - patient_general → patient_general_llm
│                      │  All LLM calls stream via adispatch_custom_event("llm_stream_chunk")
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   output_guardrail   │  Scans AI response for:
│                      │  • Diagnostic assertion patterns ("you have", "your diagnosis is")
│                      │  • Treatment/prescription patterns ("I am prescribing", "you must take")
│                      │  • Unsafe certainty ("I guarantee", "100% sure")
│                      │  • Privacy leaks (UUID patterns)
│                      │  • Metadata leaks ("system prompt:", "workflow status:")
│                      │  Actions: Append disclaimer, redact UUIDs, increment session_risk_score
└──────────┬──────────┘
           │
           ▼
          END → Response sent via WebSocket
```

---

## 2. State Schema

Every node receives and returns a `WorkflowState` TypedDict. The full schema is defined in `graph/state.py`:

```python
class WorkflowState(TypedDict):
    # ── Core Chat Fields ──
    messages: Annotated[list[BaseMessage], add_messages]  # Full conversation history
    role: "patient" | "doctor"                            # Who is chatting
    mode: "PATIENT" | "DOCTOR_GENERAL" | "DOCTOR_PATIENT" # Chat mode enum
    user_id: str                                          # Authenticated user ID
    target_patient_id: str | None                         # Patient ID for doctor-scoped queries
    ai_session_id: str                                    # Unique AI session ID
    language: str                                         # Language code (default: "en")
    triage_level: str                                     # "routine" or "emergency"
    context_payload: dict[str, Any]                       # Metadata accumulator (route info, triage)
    final_response: str                                   # The final LLM response text
    workflow_version: str                                 # Always "v1"

    # ── Planner / Executor Fields ──
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

    # ── New Fields (v2 architecture) ──
    timing_metrics: dict[str, float]                      # Performance timing per stage
    conversation_memory: dict[str, Any]                   # Persistent cross-turn memory
    recommendation_context: dict[str, Any]                # Specialist recommendation data
    session_risk_score: int                               # Cumulative security risk score
    input_guardrail_context: dict[str, Any]               # Input guardrail decision + rules
    output_guardrail_context: dict[str, Any]              # Output guardrail decision + rules
```

**Aliases**: `UnifiedChatState = WorkflowState` (backward compat).

**Factory functions**: `create_workflow_state()` and `create_unified_chat_state()` initialize all fields with safe defaults.

---

## 3. Node-by-Node Breakdown

### 3.1 Input Guardrail

**File:** `guardrails/input_guardrail.py`

A deterministic security gate that runs **before** any planning. It checks two dimensions:

**Security Rules** (regex-based):
- **Prompt Injection**: "ignore previous instructions", "disregard instructions", "system prompt", "new instructions"
- **Jailbreak**: "DAN", "developer mode", "you are unrestricted"
- **Role Manipulation**: "you are my doctor", "act as a human"
- **Out of Scope**: "write a python script", "how to build a bomb"
- **Strict Patterns** (only when `session_risk_score >= 3`): "translate this", "summarize this url", "forget", "bypass"

**Domain Validation** (TF-IDF cosine similarity):
- Uses a `TFIDFValidator` that builds a TF-IDF corpus from:
  - `CORE_CONVERSATION` — greetings, thanks, bye
  - `CORE_MEDICAL_KNOWLEDGE` — diseases, symptoms, lab terms
  - Dynamically injected capability descriptions from `capability_registry.REGISTRY`
- Classifies input as `"CONVERSATION"`, `"MEDICAL"`, or `"UNSUPPORTED"`
- Contains a fast-path shortcut: if any token matches a hardcoded `medical_hint_terms` set, it returns `"MEDICAL"` immediately without TF-IDF
- Threshold: `similarity < 0.05` → `"UNSUPPORTED"`
- `"UNSUPPORTED"` queries are blocked

**Risk Scoring**: Each triggered rule increments `session_risk_score` by `len(triggered_rules) * 2`. Higher risk unlocks stricter blocking rules.

**Outputs when blocked**:
- Security violation → `"Your request was blocked due to safety policies."`
- Domain violation → `"I'm sorry, but DocTalk only supports healthcare-related conversations."`

---

### 3.2 Planner

**File:** `planner/planner.py`

The `PlanningEngine` class runs a rule-based goal determination pipeline:

1. **ConversationMemory Hydration**: `ConversationMemoryManager.hydrate_planner_metadata()` reads `conversation_memory` to restore `active_workflow`, `doctor_name`, `booking_datetime`, `booking_ordinal`, and recommendation state from previous turns.

2. **Context Resolution**: `ContextResolver` (`planner/context_resolver.py`) analyzes the user's message in the context of prior state. It detects follow-up patterns (e.g., "what did they say?" refers to previous query type) and resolves references.

3. **Intent Parsing**: `parse_intent()` from `planner/parsers/intent_parser.py` produces a `ParsedIntent` with:
   - `intent_type`: "appointment", "symptom", "consultation", "patient_history", or None
   - `entities`, `actions`, `doctor_name`, `booking_datetime`, `booking_ordinal`
   - Boolean flags: `is_appointment`, `is_consultation`, `is_history`

4. **Goal Determination**: `determine_goal()` runs priority-ordered rules:
   - Workflow cancellation detection ("never mind", "cancel this", "forget it")
   - Appointment workflows (book, cancel, reschedule, upcoming, list)
   - Active workflow continuation (booking confirmation flows)
   - Document/report queries (latest, compare, analyze)
   - Patient history queries
   - Consultation queries
   - Doctor availability queries
   - Medical knowledge queries

5. **LLM Planner Fallback**: `planner/llm_planner.py` — If rule-based planning fails or returns an empty plan, the `LLMPlanningEngine` generates a JSON execution plan using structured output. Falls back to keyword rule planner if the LLM output is invalid.

6. **Plan Optimization**: `planner/plan_optimizer.py` — Deduplicates and validates the execution plan.

**Key output**: Sets `execution_plan` (list of `PlannerTask`s) and `planner_metadata` (includes `query_type`, `active_workflow`, `detected_entities`, etc.)

---

### 3.3 Authorization

**File:** `auth/authorization.py` + `auth/authorization_service.py`

Runs after the planner, before execution. Filters the `execution_plan` by checking each task's `capability_name` against the `allowed_roles` metadata in the capability registry.

- Supported roles: `["patient", "doctor"]`
- Unsupported roles get their entire plan cleared
- Each capability defines its `allowed_roles` in `CapabilityMetadata`

**Example role restrictions from the registry**:

| Capability | Allowed Roles |
|-----------|--------------|
| `MEMORY` | patient, doctor |
| `CONSULTATION` | patient, doctor |
| `PATIENT_HISTORY` | patient, doctor |
| `ASSET_INDEX` | patient, doctor |
| `APPOINTMENT` | patient, doctor |
| `DOCTOR_AVAILABILITY` | doctor |
| `APPOINTMENT_BOOK` | patient |
| `APPOINTMENT_CANCEL` | patient |
| `APPOINTMENT_RESCHEDULE` | patient |
| `APPOINTMENT_SEARCH_SLOTS` | patient |

---

### 3.4 Task Executor

**File:** `executor/task_executor.py`

Executes the `execution_plan` queue. Each `PlannerTask` is dispatched to the `capability_registry` by `capability_name`.

**Execution loop**:
1. Picks the next task whose `depends_on` list is fully satisfied (all deps in `completed_task_ids`)
2. Evaluates freshness policy (`executor/freshness_policy.py`) — decides if capability needs fresh execution or can reuse cached data
3. Calls the capability handler with `(state, params)`
4. Merges result into `ExecutionContext` — routes data to `shared_context` via `produces`/`target_context_keys`
5. Appends any `pending_tasks` from the result to the queue
6. Safety limit: `MAX_PENDING_TASK_DEPTH = 20`

**ExecutionContext** (`models/execution_context.py`):
- Tracks: `completed_task_ids`, `produced_data`, `consumed_data`, `shared_context`, `evidence`, `warnings`, `metadata`, `stats`
- `merge_result()` handles data routing via explicit `produces` keys or implicit `target_context_keys` from capability metadata
- `finalize()` computes total execution timing

After execution, runs `ConversationMemoryManager.update()` to persist state across turns.

---

### 3.5 Capability Registry

**File:** `executor/capability_registry.py`

A flat `REGISTRY: dict[str, Capability]` mapping capability names to handlers and metadata. Each capability is a TypedDict:

```python
class Capability(TypedDict):
    name: str
    handler: Callable[[UnifiedChatState, dict[str, Any]], Awaitable[CapabilityResult]]
    metadata: CapabilityMetadata
```

**Retrievers** (query data, no side effects):

| Name | Handler | What it retrieves |
|------|---------|-------------------|
| `MEMORY` | `handle_memory_retrieve` | Previous AI conversation messages from `AiChatMessage` |
| `CONSULTATION` | `handle_consultation_retrieve` | Past doctor-patient consultations |
| `PATIENT_HISTORY` | `handle_patient_history_retrieve` | Structured medical history (vitals, conditions) |
| `ASSET_INDEX` | `handle_asset_index_retrieve` | Document/report selection + scoped RAG vector search |
| `APPOINTMENT` | `handle_appointment_retrieve` | Upcoming/past appointments |
| `DOCTOR_AVAILABILITY` | `handle_doctor_availability_retrieve` | Available doctor time slots |

**Actions** (write operations):

| Name | Handler | Effect |
|------|---------|--------|
| `APPOINTMENT_BOOK` | `handle_appointment_book` | Creates appointment + marks slot as booked (DB transaction) |
| `APPOINTMENT_CANCEL` | `handle_appointment_cancel` | Cancels appointment + releases slot |
| `APPOINTMENT_RESCHEDULE` | `handle_appointment_reschedule` | Stub — returns context message only |
| `APPOINTMENT_SEARCH_SLOTS` | `handle_appointment_search_slots` | Searches available slots by doctor name/specialty |

**CapabilityMetadata** (`models/capability_metadata.py`):
```python
class CapabilityMetadata(BaseModel):
    capability_name: str
    capability_type: "retriever" | "action"
    always_refresh: bool          # Force fresh execution every time
    allow_memory: bool            # Result can persist to memory
    allow_cache: bool             # Result can be cached
    priority: int                 # Execution priority (lower = higher)
    supports_parallel_execution: bool
    description: str              # Human-readable (also used by TF-IDF validator)
    target_context_keys: list[str]  # State keys where results are merged
    evidence_behavior: str        # Always "pass_through"
    allowed_roles: list[str]      # Authorization whitelist
```

---

### 3.6 Recommendation Engine

**File:** `recommendation/recommendation_engine.py`

Patient-only node that runs after execution and before the LLM. It generates specialist referral recommendations.

**When it runs**:
- Skipped for doctors (`mode` is `DOCTOR_GENERAL` or `DOCTOR_PATIENT`)
- Skipped if there's an `active_workflow` in planner_metadata
- Only executes when `query_type` is `rag`, `knowledge`, or `general`
- Only executes when evidence contains medical evidence (`type` in `["rag", "symptom_analysis", "medical_analysis"]`)

**Specialty detection** (rule-based keyword matching on evidence text):
1. Endocrinologist — HbA1c, FBS, diabetes
2. Cardiologist — ECG, chest pain, troponin
3. Nephrologist — creatinine, eGFR, kidney
4. Gastroenterologist — SGPT, SGOT, bilirubin, liver
5. Pulmonologist — respiratory, asthma, COPD
6. Dermatologist — skin, rash
7. Ophthalmologist — eye, vision
8. Neurologist — seizure, stroke, brain
9. Orthopedic Surgeon — bone, fracture, joint
10. Urologist — urinary, bladder
11. Hematologist — severe + blood terms
12. General Physician — hemoglobin, CBC, RBC

**Doctor matching**: Searches `consultation_context` and `appointment_context` for a previously seen doctor matching the recommended specialty.

**Output**: Appends a `care_recommendation` evidence block and populates `recommendation_context` with `recommended_specialty`, `recommended_doctor_id/name`, and confidence.

---

### 3.7 Response Composer

**File:** `composer/response_composer.py`

Enriches evidence blocks with detailed context:
- Consultation evidence gets `consultation_context` details appended (sanitized via `sanitize_for_llm`)
- Patient history evidence gets `patient_history_context` details appended

**Action capability handling**: If evidence contains a result from `APPOINTMENT_BOOK`, `APPOINTMENT_CANCEL`, or `APPOINTMENT_RESCHEDULE`, the composer sets `final_response` directly from the evidence content. This causes the LLM orchestrator to skip the LLM call entirely and return the action confirmation as-is.

---

### 3.8 LLM Orchestrator

**File:** `llm/llm_orchestrator.py`

Replaces the previous graph-level role-based routing with a single node that handles all sub-routing internally.

**Flow**:
1. If `final_response` is already set (by response_composer for action confirmations) → wraps as `AIMessage` and returns immediately
2. **Doctor path**:
   - `mode == "DOCTOR_PATIENT"` → `doctor_scoped_llm()` (RAG against target patient)
   - Otherwise → `doctor_general_llm()` (clinical reasoning copilot, no RAG)
3. **Patient path** (three sub-steps in sequence):
   - `triage_evaluator()` — structured LLM classification (`TriageEvaluation`)
   - `classify_intent()` — keyword + planner metadata routing
   - Route to one of:
     - `patient_assistant_llm()` — for `emergency` or `patient_rag` (medical report interpretation with RAG)
     - `patient_knowledge_llm()` — for `knowledge` (general medical education, no RAG, no evidence)
     - `patient_general_llm()` — for `patient_general` (empathetic assistant with evidence context)

**Patient Intent Classification** (`llm/patient/routing.py`):
```
PatientIntent = "patient_rag" | "patient_general" | "emergency" | "knowledge" | "workflow"

Priority order:
1. Emergency terms → "emergency"
2. planner_metadata.query_type == "knowledge" → "knowledge"
3. planner_metadata.query_type == "rag" → "patient_rag"
4. planner_metadata.query_type in ("workflow", "appointment") → "workflow"
5. planner_metadata.query_type == "general" → "patient_general"
6. Clinical keyword fallback → "patient_rag"
7. Default → "patient_general"
```

**All LLM calls stream** via `adispatch_custom_event("llm_stream_chunk", content)`.

---

### 3.9 Output Guardrail

**File:** `guardrails/output_guardrail.py`

Scans the last AI message for safety violations:

| Rule Category | Patterns | Action |
|--------------|----------|--------|
| Diagnostic Assertion | "you have", "your diagnosis is", "this confirms you", "I diagnose you" | Append medical disclaimer |
| Treatment/Prescription | "I am prescribing", "you must take", "you should take 500mg" | Append medical disclaimer |
| Unsafe Certainty | "I am 100% sure", "I guarantee" | Append medical disclaimer |
| Privacy Leak | UUID patterns (`[0-9a-f]{8}-...`) | Replace with `[REDACTED]` |
| Metadata Leak | "system prompt:", "workflow status:" | Replace with `[REDACTED]` |

**Context-aware relaxation**: For `query_type == "knowledge"`, only privacy/metadata leak rules are checked (diagnosis language is acceptable for educational content).

**Risk scoring**: `session_risk_delta = len(triggered_rules)`, added to `session_risk_score`.

**Medical disclaimer** (appended when diagnosis/treatment/certainty rules trigger):
> *This is general health information and not a definitive diagnosis. Please consult a licensed physician for personalized medical advice.*

---

## 4. Conversation Memory Manager

**File:** `memory/conversation_memory.py`

A cross-turn memory system that persists workflow state across conversation turns. Stored in `state["conversation_memory"]` as a nested dict with four slots:

| Slot | Purpose | Example keys |
|------|---------|-------------|
| `workflow` | Active multi-turn workflow state | `active_workflow`, `doctor_name`, `booking_datetime` |
| `semantic` | Semantic references for follow-ups | (reserved for future use) |
| `short_term` | Short-term turn context | `last_query_type`, `last_capabilities` |
| `recommendation` | Persisted specialist recommendations | `recommended_specialty`, `recommended_doctor_id` |

**`hydrate_planner_metadata()`**: Called at the start of each planner turn to restore context from the previous turn's memory into `planner_metadata`.

**`update(result_dict)`**: Called at the end of task execution to persist the current turn's state into memory for the next turn.

---

## 5. Data Models

### PlannerTask (`models/planner_task.py`)
```python
@dataclass
class PlannerTask:
    task_type: str                    # "retrieve" | "action" | "general_response"
    retriever: str | None             # Registry key (e.g., "APPOINTMENT", "PATIENT_HISTORY")
    action_handler: str | None        # Registry key (e.g., "APPOINTMENT_BOOK")
    action: str | None                # Sub-action (e.g., "latest", "upcoming")
    parameters: dict[str, Any]        # Extra params (booking_datetime, doctor_name, etc.)

    # Dependency metadata
    task_id: str | None               # Unique task identifier for dependency tracking
    depends_on: list[str] | None      # Task IDs this task depends on
    produces: list[str] | None        # State keys this task produces
    consumes: list[str] | None        # State keys this task consumes

    @property
    capability_name -> str | None     # Returns retriever or action_handler based on task_type
```

### CapabilityResult (`models/capability_result.py`)
```python
@dataclass
class CapabilityResult:
    capability_name: str
    status: str = "SUCCESS"           # "SUCCESS" | "FAILED"
    evidence: list[dict[str, Any]]    # Evidence blocks produced
    pending_tasks: list[...]          # Dynamically spawned follow-up tasks
    data: Any                         # Generic result data
    metadata: dict[str, Any]          # Flags (e.g., clear_doctor_availability)
    warnings: list[str]
    errors: list[str]
    timing_ms: float
```

### ExecutionContext (`models/execution_context.py`)
- Central accumulator for the entire execution cycle
- Tracks: `completed_task_ids`, `produced_data`, `consumed_data`, `shared_context`, `evidence`, `warnings`, `metadata`, `stats`
- `merge_result()` routes capability data into `shared_context` via `produces` keys or `target_context_keys`

### ActiveWorkflow (`models/active_workflow.py`)
- Represents a multi-turn workflow (e.g., appointment booking flow)
- Fields: `workflow_type`, `status`, `context` (dict), `started_at`

### FreshnessDecision (`models/freshness_decision.py`)
- Output of the freshness policy evaluator
- Fields: `execute_fresh`, `reuse_existing`, `ignore_memory`, `ignore_cache`, `reason`

### ResolvedContext (`models/resolved_context.py`)
- Output of the context resolver
- Fields: `has_reference`, `resolved_type`, `resolved_data`

---

## 6. RAG Tools

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

## 7. Utility Modules

### Sanitizer (`utils/sanitizer.py`)
- `sanitize_for_llm(data)` — Recursively strips internal IDs (`id`, `_id`, `*_id`, `*Id`), `uuid`, and `metadata` keys from dicts before passing to LLMs. Prevents UUID/PII leakage.

### Logger (`utils/logger.py`)
- `log_section()`, `log_key_value()`, `log_trace()`, `log_error()`, `format_duration()`
- `log_trace()` only outputs when `DEBUG_VERBOSE=true` env var is set

---

## 8. External Dependencies (Outside `workflows/`)

### 8.1 Chat Router (`backend/api/chat/router.py`)
- FastAPI WebSocket endpoint that receives user messages
- Authenticates via JWT token in query params
- Builds `WorkflowState` via `create_workflow_state()`
- Invokes `unified_chat_graph` via `astream_events()` for token streaming
- **Streaming**: Listens for custom `"llm_stream_chunk"` events dispatched by LLM nodes
- **Loading UI**: Emits user-friendly node transition statuses using a strict whitelist to prevent internal LangChain runnables from flooding the frontend
- Persists messages to `AiChatMessage` table

### 8.2 LLM Client (`backend/ai/core_services/llm_client.py`)
- Provides `get_chat_model()` returning a LangChain-compatible chat model
- Configured via env vars: `GEMINI_API_KEY`, `GEMINI_MODEL` (default: `gemini-2.0-flash`)
- Default temperature: `0.2` (overridden to `0.1` in triage evaluator)

### 8.3 Vector Store (`backend/ai/vectorstore/pgvector_service.py`)
- `pgvector_service.search_documents()` — similarity search scoped to a patient
- `pgvector_service.search_documents_by_assets()` — similarity search scoped to specific asset IDs
- Embeddings via `text-embedding-004` (768 dims)

### 8.4 Prompt Templates (`backend/ai/prompts/templates.py`)
- `PromptService` / `medical_prompt_service` with templates for summary, X-ray analysis, consultation review
- Includes `_language_hint()` for multilingual support
- Includes `_context_block()` with prompt injection defense

### 8.5 Database (Prisma ORM)
- Tables accessed by capabilities: `Appointment`, `Doctor`, `DoctorSlot`, `Consultation`, `ConsultationMessage`, `AiChatMessage`, `AssetIndex`, `PatientMedicalHistory`

### 8.6 Checkpointer
- `MemorySaver()` — in-memory LangGraph checkpointer
- Conversation continuity is keyed by `ai_session_id`
- **Resets on server restart** (no persistent checkpointing)

---

## 9. LLM Model Configuration

| Setting | Value |
|---------|-------|
| Chat Model | `gemini-2.0-flash` (override: `GEMINI_MODEL` env var) |
| Embeddings | `text-embedding-004` (768 dims) |
| Temperature | `0.1` (triage) / `0.2` (all other nodes) |
| API Key | `GEMINI_API_KEY` (required) |

---

## 10. File Index

```
backend/workflows/
├── WORKFLOW_CONTEXT.md               ← This file
├── __init__.py                       ← Package init
├── unified_chat_graph.py             ← Re-exports from graph/
├── state.py                          ← Re-exports from graph/
│
├── graph/
│   ├── unified_chat_graph.py         ← Main graph definition (8-node linear pipeline)
│   ├── state.py                      ← WorkflowState TypedDict & factory functions
│   └── common.py                     ← get_workflow_model(), latest_message_text()
│
├── guardrails/
│   ├── input_guardrail.py            ← Input security + TF-IDF domain validation
│   └── output_guardrail.py           ← Output safety scanning + disclaimer injection
│
├── auth/
│   ├── authorization.py              ← Authorization node (filters plan by role)
│   └── authorization_service.py      ← filter_authorized_plan() logic
│
├── planner/
│   ├── planner.py                    ← PlanningEngine class (main planner node)
│   ├── llm_planner.py               ← LLM-based fallback planner
│   ├── context_resolver.py           ← Follow-up / reference resolution
│   ├── plan_optimizer.py             ← Plan deduplication / validation
│   ├── planning_validator.py         ← Plan validation rules
│   ├── retrieval_strategy.py         ← RetrievalStrategy enum
│   ├── planner_rule_config.py        ← Keyword configs
│   ├── planner_rule_order.py         ← Rule execution order
│   ├── planner_rule_loader.py        ← Rule loader
│   ├── planner_rule_registry.py      ← Planner rules
│   ├── task_template_registry.py     ← Converts TaskTemplate → PlannerTask
│   └── parsers/
│       ├── intent_parser.py          ← ParsedIntent extraction
│       └── document_query_parser.py  ← DocumentQueryIntent extraction
│
├── executor/
│   ├── capability_registry.py        ← REGISTRY: all capability handlers + metadata
│   ├── task_executor.py              ← Task executor node (queue-based loop)
│   └── freshness_policy.py           ← Freshness decision evaluator
│
├── recommendation/
│   └── recommendation_engine.py      ← Specialist recommendation engine (patient-only)
│
├── composer/
│   └── response_composer.py          ← Evidence enrichment + action response composer
│
├── llm/
│   ├── llm_orchestrator.py           ← Unified LLM orchestrator node
│   ├── patient/
│   │   ├── patient_nodes.py          ← triage_evaluator, patient_general_llm,
│   │   │                                patient_knowledge_llm, patient_assistant_llm
│   │   └── routing.py               ← classify_intent() (keyword + metadata routing)
│   └── doctor/
│       └── doctor_nodes.py           ← doctor_general_llm, doctor_scoped_llm
│
├── memory/
│   └── conversation_memory.py        ← ConversationMemoryManager (cross-turn state)
│
├── capabilities/
│   ├── retrievers/                   ← DB retriever implementations
│   ├── actions/                      ← Action handler implementations
│   └── tools/                        ← RAG tools (pgvector queries)
│
├── models/
│   ├── planner_task.py               ← PlannerTask dataclass (with dependency metadata)
│   ├── capability_metadata.py        ← CapabilityMetadata Pydantic model
│   ├── capability_result.py          ← CapabilityResult dataclass
│   ├── execution_context.py          ← ExecutionContext + ExecutionStatistics
│   ├── execution_plan.py             ← ExecutionPlan container
│   ├── active_workflow.py            ← ActiveWorkflow (multi-turn workflow state)
│   ├── freshness_decision.py         ← FreshnessDecision Pydantic model
│   ├── resolved_context.py           ← ResolvedContext dataclass
│   ├── composed_response.py          ← ComposedResponse
│   ├── evidence.py                   ← Evidence model
│   └── task_template.py              ← TaskTemplate
│
├── utils/
│   ├── logger.py                     ← Structured console logging utilities
│   └── sanitizer.py                  ← sanitize_for_llm() (strips IDs/metadata)
│
├── parsers/                          ← (legacy directory, parsers moved to planner/parsers/)
├── nodes/                            ← (legacy directory, __init__.py re-exports only)
├── retrievers/                       ← (legacy directory)
└── tools/                            ← (legacy directory)
```

---

## 11. Key Design Decisions & Known Limitations

1. **Linear pipeline, internal routing**: The graph is a flat 8-node pipeline with no branching edges. All role/intent-based routing happens inside `llm_orchestrator_node`. This simplifies graph visualization and checkpointing, but means the graph structure doesn't reflect the actual control flow.

2. **Capability-centric architecture**: The old separate retrieval/action registries have been unified into a single `capability_registry.py` with `CapabilityMetadata` governing execution policy, authorization, freshness, and evidence behavior per capability.

3. **Authorization is separate from planning**: The planner generates a maximal plan; the authorization layer then strips unauthorized capabilities. This separation of concerns allows the planner to evolve without worrying about role checks.

4. **Dual guardrails (input + output)**: Input guardrail uses regex + TF-IDF for domain validation. Output guardrail uses regex for response safety. Both contribute to a cumulative `session_risk_score` that escalates blocking sensitivity.

5. **Conversation memory is in-state**: `conversation_memory` is stored inside `WorkflowState` and persists via the LangGraph checkpointer. It resets on server restart because `MemorySaver()` is in-memory.

6. **Task dependency support**: `PlannerTask` supports `depends_on`, `produces`, and `consumes` fields for DAG-based execution ordering, though most current capabilities run independently.

7. **Action capabilities bypass the LLM**: When an action like `APPOINTMENT_BOOK` succeeds, the response composer sets `final_response` directly, and the LLM orchestrator wraps it as an `AIMessage` without calling any LLM. This avoids the LLM hallucinating additional details about the booking.

8. **Recommendation engine is rule-based**: Uses keyword matching on evidence text to determine specialty. No LLM is used for recommendation. Matches against previously consulted doctors from consultation/appointment history.

9. **TF-IDF domain validator is rebuilt per request**: The `TFIDFValidator` constructs its corpus fresh on every `input_guardrail_node` call. This is intentional for correctness (the capability registry could change) but is a performance concern at scale.

10. **`patient_knowledge_llm` is a pure LLM call**: Unlike `patient_general_llm` and `patient_assistant_llm`, the knowledge LLM receives no evidence context — it relies entirely on the LLM's training data for medical education responses.
