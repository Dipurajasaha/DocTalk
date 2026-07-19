# DocTalk AI Chat Workflow — Complete Context Reference

> **Purpose**: This document describes the **entire** AI chat orchestration system for the DocTalk healthcare platform in full technical detail.
> It is designed to serve two purposes:
> 1. **Context for other LLMs**: Feed this file to any LLM to give it complete understanding of the system so it can debug, extend, or reason about any part of it.
> 2. **Study/Viva reference**: Read it section by section to understand every design choice, data flow, and trade-off in the system.
>
> **Last updated from source code: 2026-07-17.**

---

## Table of Contents

1. [System Overview & Philosophy](#1-system-overview--philosophy)
2. [LangGraph Pipeline (Execution Order)](#2-langgraph-pipeline-execution-order)
3. [WorkflowState Schema (Shared Data Bus)](#3-workflowstate-schema-shared-data-bus)
4. [Node-by-Node Deep Dive](#4-node-by-node-deep-dive)
5. [Multi-Turn Appointment Booking Workflow (Payment Flow)](#5-multi-turn-appointment-booking-workflow-payment-flow)
6. [RAG & Vector Search System](#6-rag--vector-search-system)
7. [Conversation Memory System](#7-conversation-memory-system)
8. [LLM Calls: Count, Routing, and Token Budget](#8-llm-calls-count-routing-and-token-budget)
9. [External Dependencies & Services](#9-external-dependencies--services)
10. [Data Models Reference](#10-data-models-reference)
11. [File Index](#11-file-index)
12. [Design Decisions & Known Limitations](#12-design-decisions--known-limitations)

---

## 1. System Overview & Philosophy

DocTalk's AI chat system is a **LangGraph state machine** that processes healthcare chat messages from patients and doctors through a strictly ordered, linear pipeline of **8 nodes**. Every incoming WebSocket message from a user triggers a complete run of this pipeline.

### Why LangGraph (not just LangChain)?
- **State Management**: A massive shared `WorkflowState` TypedDict accumulates data (evidence, triage decisions, payment orders, planner metadata) as it flows through nodes. LangGraph maintains this automatically via its checkpointer.
- **Conditional Routing**: LangGraph allows the Input Guardrail to instantly halt the entire pipeline and jump to `END` (blocked queries), which is not natively possible in LangChain LCEL chains.
- **Checkpointing**: Conversation continuity across turns is handled by LangGraph's `MemorySaver` checkpointer, keyed by `ai_session_id`. (Note: this resets on server restart — it is in-memory only.)

### Why Sequential, Not Parallel?
All task execution inside the `task_executor` node is **sequential**, not parallel (`asyncio.gather` is NOT used), because:
1. Later tasks depend on data produced by earlier tasks (e.g., booking a slot depends on first finding the doctor's `doctorId`).
2. Tasks mutate a shared `ExecutionContext` — parallel writes would cause race conditions.
3. Sequential execution allows fast-failing without wasted compute on doomed downstream tasks.
4. Healthcare database transactions (appointment holds) require strict ordering.

### Role-Based Routing
The system supports two roles:
- **`patient`**: Full access to self-service health querying, booking, document analysis.
- **`doctor`**: Scoped access to a specific patient's data for clinical review.

Role-specific LLM routing happens inside the `llm_orchestrator` node — **the graph itself has no branching edges for roles**.

---

## 2. LangGraph Pipeline (Execution Order)

Defined in `graph/unified_chat_graph.py`. The graph is built by `build_unified_chat_graph()` and compiled with `MemorySaver()`.

```
User Message (via WebSocket)
       │
       ▼
┌──────────────────────┐
│   input_guardrail    │  ← Regex security + Semantic Cache (Trie) + LLM fallback
└──────────┬───────────┘
           │ conditional edge (check_input_guardrail)
           ├──── "blocked" ──→ END (immediate halt, final_response set)
           │
           ▼  "allowed"
┌──────────────────────┐
│  log_entry_context   │  ← Logs: user_id, role, ai_session_id, target_patient_id
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│      planner         │  ← LLM Planner (primary) → Rule-Based Planner (fallback)
│                      │    Hydrates conversation_memory first
│                      │    Sets: execution_plan[], planner_metadata
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    authorization     │  ← Filters execution_plan by allowed_roles per capability
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   task_executor      │  ← Sequential queue runner (dependency-aware)
│                      │    Calls capability handlers via REGISTRY
│                      │    Collects evidence[], manages ExecutionContext
│                      │    Runs ConversationMemoryManager.update() after all tasks
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ recommendation_engine│  ← LLM call (patient-only, conditional)
│                      │    Structured output: RecommendationPrediction
│                      │    Appends care_recommendation evidence block
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  response_composer   │  ← Pure Python (no LLM)
│                      │    Enriches evidence with DB context
│                      │    If action capability succeeded → sets final_response directly
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   llm_orchestrator   │  ← 0-2 LLM calls depending on path
│                      │    If final_response set → wraps AIMessage, 0 LLM calls
│                      │    Doctor path → 1 call (doctor_scoped or doctor_general)
│                      │    Patient path → triage_evaluator (1 call) + response LLM (1 call)
│                      │    Streams via adispatch_custom_event("llm_stream_chunk")
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   output_guardrail   │  ← Pure Regex (no LLM)
│                      │    Blocks diagnosis assertions, UUID leaks, prescription language
│                      │    Appends medical disclaimer if triggered
└──────────┬───────────┘
           │
           ▼
          END → Final response sent via WebSocket to frontend
```

**Edge definitions** (from `unified_chat_graph.py`):
```
START → input_guardrail
input_guardrail → [blocked → END] | [allowed → log_entry_context]
log_entry_context → planner
planner → authorization
authorization → task_executor
task_executor → recommendation_engine
recommendation_engine → response_composer
response_composer → llm_orchestrator
llm_orchestrator → output_guardrail
output_guardrail → END
```

---

## 3. WorkflowState Schema (Shared Data Bus)

Every node receives and returns a `WorkflowState` TypedDict (alias: `UnifiedChatState`). Defined in `graph/state.py`.

```python
class WorkflowState(TypedDict):
    # ── Core Chat Fields ──────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
    # Full LangChain conversation history. add_messages reducer APPENDS
    # new messages instead of replacing.

    role: ChatRole                # Literal["patient", "doctor"]
    mode: ChatMode                # Literal["PATIENT", "DOCTOR_GENERAL", "DOCTOR_PATIENT"]
    user_id: str                  # Authenticated user's username (from JWT)
    target_patient_id: str | None # Doctor mode only: the patient being reviewed
    ai_session_id: str            # Unique session ID = LangGraph thread_id
    language: str                 # "en", "hi", etc. Default: "en"
    triage_level: str             # "routine" or "emergency" (set by triage_evaluator)
    context_payload: dict         # Accumulator for route info, triage data, payment flags
    final_response: str           # The completed AI response text
    workflow_version: str         # Always "v1"

    # ── Planner / Executor Fields ─────────────────────────────────────────
    execution_plan: list[PlannerTask]
    evidence: list[dict]
    action_results: list[dict]
    retrieval_strategy: str | None
    memory_context: list[dict]                # From MEMORY capability
    appointment_context: dict                 # From APPOINTMENT capability
    consultation_context: list[dict]          # From CONSULTATION capability
    asset_selection_context: dict             # From ASSET_INDEX capability
    rag_scope: dict                           # asset_ids for scoped RAG queries
    patient_history_context: list[dict]       # From PATIENT_HISTORY capability
    doctor_availability_context: list[dict]   # From DOCTOR_AVAILABILITY / SEARCH_SLOTS
    planner_metadata: dict                    # Classification results from planner

    # ── Multi-Turn State ──────────────────────────────────────────────────
    shadow_execution_completed: bool
    shadow_response: str
    need_more_actions: bool
    execution_iteration: int
    pending_tasks: list[PlannerTask]
    response_sections: list[dict]

    # ── Payment ──────────────────────────────────────────────────────────
    payment_order: dict | None    # Razorpay order data for frontend popup
    active_workflow: dict | None  # Top-level active workflow state
    payment_successful: bool | None
    payment_failed: bool | None

    # ── Memory & Metrics ──────────────────────────────────────────────────
    conversation_memory: dict             # Cross-turn persistent state (4 slots)
    timing_metrics: dict[str, float]      # e.g. {"planner": 120, "executor": 320}

    # ── Guardrails & Security ─────────────────────────────────────────────
    session_risk_score: Annotated[int, operator.add]  # Cumulative, uses add reducer
    input_guardrail_context: dict
    output_guardrail_context: dict
```

**Key design note**: `session_risk_score` uses `operator.add` as its reducer. This means every node that returns `{"session_risk_score": N}` *adds* N to the existing score rather than replacing it. Both guardrails contribute to this cumulative risk score.

**Factory functions**: `create_workflow_state()` and `create_unified_chat_state()` accept `payment_order`, `payment_successful`, `payment_failed` as explicit parameters and initialize all other fields with safe defaults.

---

## 4. Node-by-Node Deep Dive

### 4.1 Input Guardrail

**File**: `guardrails/input_guardrail.py` + `guardrails/semantic_cache.py`
**LLM Used**: ✅ Yes (conditional fallback only)
**When it runs**: Always. First node.

#### Layer 1: Security Rule Matching (Regex, always runs)

Checks the raw user text against 4 pattern groups:

| Rule Group | Example Patterns | Behavior |
|---|---|---|
| Prompt Injection | `ignore\s+(all\s+)?(previous\s+)?instructions`, `system\s+prompt` | Block always |
| Jailbreak | `\bdan\b`, `developer\s+mode`, `you\s+are\s+(now\s+)?unrestricted` | Block always |
| Role Manipulation | `you\s+are\s+(now\s+)?(a\s+human\|my\s+doctor)` | Block always |
| Out of Scope | `write\s+(a\s+)?(python\|javascript)`, `how\s+to\s+build\s+(a\s+)?bomb` | Block always |
| Strict (HIGH/STRICT only) | `translate\s+this`, `bypass`, `forget` | Block when `risk_score >= 3` |

Risk level escalation: `LOW` (0) → `MEDIUM` (≥1) → `HIGH` (≥3) → `STRICT` (≥5). Each triggered rule adds `len(triggered_rules) * 2` to `session_risk_score`.

#### Layer 2: Semantic Cache Domain Validation (Trie + LLM fallback)

The old TF-IDF approach has been **completely replaced** with a **Trie-based Semantic Cache** backed by the `SemanticCacheWord` PostgreSQL table.

**How it works**:
1. Tokenizes user text into lowercase words, strips stopwords.
2. **Fast path**: If any token matches `ALLOWED_MEDICAL_TERMS` set (`consultation`, `appointment`, `blood`, `report`, `record`, `history`), immediately allows.
3. **Trie lookup** via `SemanticCacheManager`:
   - Loads words from `semantic_cache_words` DB table into two in-memory Tries (one for ALLOWED, one for BLOCKED).
   - **Blocked Trie** uses `search_prefix()` (prefix match — more aggressive blocking).
   - **Allowed Trie** uses `search()` (exact match — more conservative allowing).
   - Returns `"ALLOWED"`, `"BLOCKED"`, or `"UNKNOWN"` (cache miss).
4. **LLM Fallback** (on cache miss only): Calls `complete_text()` with a structured prompt asking the LLM to classify the query as `ALLOWED` or `REJECTED` and extract 1-3 domain keywords. On success, the extracted keywords are **persisted** back to the DB via `add_allowed()` / `add_blocked()` so future lookups hit the cache.
5. **Self-seeding**: If the `semantic_cache_words` table is empty on first load, `_seed_initial()` populates it with ~35 default words (medical terms for ALLOWED, coding/attack terms for BLOCKED).

#### Outputs
- **Allowed**: `{"input_guardrail_context": {"status": "allowed", "domain": "MEDICAL"}, "session_risk_score": 0}`
- **Blocked (security)**: Sets `final_response = "Your request was blocked due to safety policies."` → routes to END
- **Blocked (domain)**: Sets `final_response = "I'm sorry, but DocTalk only supports healthcare-related conversations."` → routes to END

---

### 4.2 Log Entry Context

**File**: `graph/unified_chat_graph.py` (inline `log_entry_context` function)
**LLM Used**: ❌ No
**Purpose**: Emits a structured log line with `user_id`, `target_patient_id`, `ai_session_id`, `role`. Returns empty dict `{}` (does not mutate state).

---

### 4.3 Planner

**File**: `planner/planner.py`, `planner/llm_planner.py`
**LLM Used**: ✅ Yes (primary path via `LLMPlanningEngine`)
**Output**: Sets `execution_plan`, `planner_metadata`, `retrieval_strategy`, `timing_metrics`.

The Planner converts a natural language user message into a structured list of tasks.

#### Step 0: Memory Hydration
`ConversationMemoryManager(state).hydrate_planner_metadata()` runs first. Reads `conversation_memory` to restore:
- `active_workflow` (mid-booking state, unless status is `completed`/`confirmed`/`cancelled`)
- `doctor_name`, `booking_datetime`, `booking_ordinal` (booking entities)
- `appointment_id`, `slot_id`, `amount`, `currency` (payment context)
- `recommended_specialty`, `recommended_doctor_id`, `recommended_doctor_name`

Also reads top-level `state["active_workflow"]` and `state["payment_order"]` which the task_executor sets directly.

#### Step 1: LLM Planner (Primary — `USE_LLM_PLANNER=true`)
`LLMPlanningEngine` makes 1 LLM call using `complete_text()` with a structured prompt expecting JSON:
```json
{
  "confidence": 0.95,
  "reasoning": "User wants to book appointment",
  "query_type": "workflow",
  "tasks": [...],
  "metadata": {...}
}
```
Validated by `PlanningValidator`. If confidence < threshold or validation fails → falls back to rule-based planner.

#### Step 2: Rule-Based Planner (Fallback — `PlanningEngine`)
Runs a goal detection pipeline:

1. **`ContextResolver`** (`planner/context_resolver.py`) — resolves follow-up references, ordinal selections ("the first one"), affirmations ("yes", "confirm")
2. **`IntentParser`** (`planner/parsers/intent_parser.py`) — extracts `intent_type`, `entities`, `actions`, `doctor_name`, `booking_datetime`, `booking_ordinal`
3. **`determine_goal()`** — keyword + intent mapping to goals:
   - Workflow cancellation ("never mind", "cancel this") → clears active_workflow
   - `manage_appointment` → when explicit appointment actions detected
   - `check_doctor_availability` → when availability/booking keywords detected
   - `review_consultation` → when consultation history requested
   - `review_patient_history` → when medical history/medication requested
   - `review_document` → when report/analysis keywords detected
   - `access_memory` → when "remember"/"recall" keywords detected
   - `general_chat` → default fallback
4. **`determine_required_information()`** — sets `query_type` in metadata
5. **`build_execution_plan()`** — converts goals to `PlannerTask` objects with correct `capability_name`
6. **`order_tasks()`** → deduplicates via `ExecutionPlan.deduplicate()`

#### Step 3: Plan Optimizer
`PlanOptimizer.optimize(plan, state)` — removes duplicate capabilities, tracks optimization stats (`original_tasks`, `optimized_tasks`, `duplicates_removed`, `context_reused`, `skipped_retrievals`).

#### Booking Confirmation Detection
The planner has complex logic to detect booking confirmations. It checks:
- If `active_workflow.status` is `waiting_confirmation` or `waiting_payment_confirmation` AND user says "yes"/"confirm"/"proceed"/"ok"/"sure"/"go ahead"
- If `payment_successful` flag is set (from frontend callback)
- Sets `payment_confirmation_requested` and `payment_successful` in metadata accordingly

---

### 4.4 Authorization

**File**: `auth/authorization.py` + `auth/authorization_service.py`
**LLM Used**: ❌ No

Filters `execution_plan` by checking each task's `capability_name` against `allowed_roles` in the capability registry.

**Full role permission table** (from `capability_registry.py` REGISTRY):

| Capability | Type | Allowed Roles |
|---|---|---|
| `MEMORY` | retriever | patient, doctor |
| `CONSULTATION` | retriever | patient, doctor |
| `PATIENT_HISTORY` | retriever | patient, doctor |
| `ASSET_INDEX` | retriever | patient, doctor |
| `APPOINTMENT` | retriever | patient, doctor |
| `DOCTOR_AVAILABILITY` | retriever | **doctor only** |
| `APPOINTMENT_BOOK` | action | **patient only** |
| `APPOINTMENT_CANCEL` | action | **patient only** |
| `APPOINTMENT_RESCHEDULE` | action | **patient only** |
| `APPOINTMENT_SEARCH_SLOTS` | action | **patient only** |

Unsupported role → entire plan cleared. Individual unauthorized tasks → removed from plan.

---

### 4.5 Task Executor

**File**: `executor/task_executor.py`
**LLM Used**: ❌ No

Runs the `execution_plan` queue one task at a time (strictly sequential).

```python
while queue:
    if loops >= MAX_PENDING_TASK_DEPTH (20):
        break

    # Find next task whose depends_on are all in completed_task_ids
    ready_task = find_next_ready(queue, ctx.completed_task_ids)
    if not ready_task:
        break  # Dependency cycle

    queue.remove(ready_task)

    # Evaluate freshness policy
    decision = evaluate_freshness_policy(capability_metadata, state, task)

    # Execute
    result = await execute_single_task(state, task, ctx)

    # Merge into ExecutionContext
    ctx.merge_result(task, result)

    # Spawn follow-up tasks if any
    queue.extend(ctx.pending_tasks)
    ctx.pending_tasks = []
    loops += 1

ctx.finalize()
```

#### Post-Execution State Propagation
After the loop, the executor:
1. Merges `ctx.shared_context` into the result dict (populates state keys like `appointment_context`, `consultation_context`, etc.)
2. If `ctx.metadata["payment_order"]` exists → sets `result_dict["payment_order"]`
3. If `ctx.metadata["active_workflow"]` exists → sets both `result_dict["active_workflow"]` and updates `planner_metadata["active_workflow"]`
4. If `ctx.metadata["clear_payment_order"]` → sets `payment_order = None`
5. Calls `ConversationMemoryManager(state).update(result_dict)` to persist state for next turn

---

### 4.6 Capability Registry

**File**: `executor/capability_registry.py`
**LLM Used**: ❌ No (all pure Python + DB queries)

`REGISTRY: dict[str, Capability]` — maps capability names to handler functions + metadata.

#### All 10 Registered Capabilities

**Retrievers** (6):

| Name | Handler | DB Tables | What it fetches |
|---|---|---|---|
| `MEMORY` | `handle_memory_retrieve` | `AiChatMessage` | Recent AI chat messages for session |
| `CONSULTATION` | `handle_consultation_retrieve` | `Consultation`, `ConsultationMessage` | Past doctor-patient sessions |
| `PATIENT_HISTORY` | `handle_patient_history_retrieve` | `PatientMedicalHistory` | Vitals, conditions, medications |
| `ASSET_INDEX` | `handle_asset_index_retrieve` | `AssetIndex` + `rag_documents` | Document index + vector search |
| `APPOINTMENT` | `handle_appointment_retrieve` | `Appointment`, `Doctor`, `DoctorSlot` | Upcoming/past appointments |
| `DOCTOR_AVAILABILITY` | `handle_doctor_availability_retrieve` | `Doctor`, `DoctorSlot` | Available slots per doctor |

**Actions** (4):

| Name | Handler | What it does |
|---|---|---|
| `APPOINTMENT_BOOK` | `handle_appointment_book` | Multi-stage booking with Razorpay (see Section 5) |
| `APPOINTMENT_CANCEL` | `handle_appointment_cancel` | Cancels appointment + releases DoctorSlot |
| `APPOINTMENT_RESCHEDULE` | `handle_appointment_reschedule` | Returns context message (stub) |
| `APPOINTMENT_SEARCH_SLOTS` | `handle_appointment_search_slots` | Searches DoctorSlot by doctor name/specialty |

#### CapabilityMetadata Fields (`models/capability_metadata.py`)

```python
class CapabilityMetadata(BaseModel):
    capability_name: str
    capability_type: str         # "retriever" | "action"
    always_refresh: bool         # True = always re-execute, skip cache
    allow_memory: bool           # Result can persist to conversation memory
    allow_cache: bool            # Result can be cached for reuse
    priority: int                # Lower = higher priority (10 for retrievers, 20 for actions)
    supports_parallel_execution: bool  # Metadata-only; executor is sequential
    description: str             # Human-readable (used in guardrail TF-IDF corpus)
    target_context_keys: list[str]     # State keys where results are merged
    evidence_behavior: str       # Always "pass_through"
    allowed_roles: list[str]     # Authorization whitelist
```

#### Freshness Policy (`executor/freshness_policy.py`)
For each task, checks `capability_metadata.always_refresh`:
- `True` → forces fresh DB query (used by: `APPOINTMENT`, `DOCTOR_AVAILABILITY`, all actions)
- `False` → permits reuse of cached/in-state data (used by: `MEMORY`, `CONSULTATION`, `PATIENT_HISTORY`, `ASSET_INDEX`)

---

### 4.7 Recommendation Engine

**File**: `recommendation/recommendation_engine.py`
**LLM Used**: ✅ Yes (1 structured output call via `with_structured_output(RecommendationPrediction)`)

#### When SKIPPED (returns `{}` immediately):
- `mode` is `"DOCTOR_GENERAL"` or `"DOCTOR_PATIENT"` (doctor sessions)
- `planner_metadata` contains `"active_workflow"` (mid-booking flow)
- `query_type` is not `"rag"`, `"knowledge"`, or `"general"`
- No latest message in state

#### When it RUNS:
1. Takes last 4 messages from conversation as context.
2. Makes 1 LLM call (`temperature=0.0`) with structured output:
```python
class RecommendationPrediction(BaseModel):
    needs_doctor: bool       # True if symptoms suggest medical consultation
    recommended_specialty: str | None  # "Cardiologist", "General Physician", etc.
    reasoning: str           # Brief explanation
```
3. If `needs_doctor == True` and specialty found:
   - Queries `prisma.doctor.find_many()` for up to 2 doctors matching specialty (case-insensitive substring search on `specialization` field)
   - Falls back to "General Physician" if no exact match found
   - Formats doctor names with prefix: `"" if d.name.startswith("Dr.") else "Dr. "`
4. Appends `care_recommendation` evidence block to state and sets `recommendation_context`.

---

### 4.8 Response Composer

**File**: `composer/response_composer.py`
**LLM Used**: ❌ No

#### Evidence Enrichment
- Evidence with `type == "consultation"` → appended with `consultation_context` JSON (sanitized)
- Evidence with `type == "patient_history"` → appended with `patient_history_context` details

#### Action Short-Circuit (critical design)
If evidence contains a source from `ACTION_CAPABILITIES` (`APPOINTMENT_BOOK`, `APPOINTMENT_CANCEL`, `APPOINTMENT_RESCHEDULE`), sets `result_dict["final_response"]` directly from the evidence content.

This causes the LLM Orchestrator to skip ALL LLM calls and return the action confirmation verbatim.

---

### 4.9 LLM Orchestrator

**File**: `llm/llm_orchestrator.py`
**LLM Used**: ✅ Yes (0-2 calls depending on path)

#### Fast Path (0 LLM calls)
If `state["final_response"]` is already set:
- Wraps as `AIMessage`
- Copies `payment_order` and `active_workflow` from state
- Returns immediately

#### Doctor Path (1 LLM call)
- `mode == "DOCTOR_PATIENT"` → `doctor_scoped_llm()` — evidence injected as context, RAG-capable
- Otherwise → `doctor_general_llm()` — clinical reasoning copilot

Both use `temperature=0.1` and evidence is included in the system message if present.

#### Patient Path (2 LLM calls)
1. **`triage_evaluator()`** — 1 LLM structured output call:
```python
class TriageEvaluation(BaseModel):
    is_emergency: bool   # Chest pain, stroke, bleeding, seizure, etc.
    rationale: str
```
System prompt detects life-threatening symptoms. Sets `triage_level = "emergency"` if triggered.

2. **`classify_intent()`** — Pure Python (no LLM). Routes based on `triage_level` + `planner_metadata.query_type`:

| Intent | Condition | LLM Called |
|---|---|---|
| `emergency` | Emergency terms found in message text | `patient_assistant_llm` |
| `knowledge` | `query_type == "knowledge"` | `patient_knowledge_llm` |
| `patient_rag` | `query_type == "rag"` | `patient_assistant_llm` |
| `workflow` | `query_type in ("workflow", "appointment")` | `patient_general_llm` |
| `patient_general` | `query_type == "general"` or default | `patient_general_llm` |

3. **Response LLM** — 1 streaming LLM call:

| LLM | System Prompt Focus | Evidence? | Temperature |
|---|---|---|---|
| `patient_assistant_llm` | Strict medical report interpreter. NEVER diagnose. Only explain lab values + reference ranges. Must include care_recommendation if present. | ✅ Injected into system prompt | 0.1 |
| `patient_general_llm` | Empathetic assistant. Use ONLY retrieved context. Never invent doctor names. Mention care_recommendation doctors. Handles payment failure acknowledgment. | ✅ Injected into system prompt | 0.1 |
| `patient_knowledge_llm` | Medical educator. General health info from training data. No diagnosis. | ❌ No evidence | 0.1 |

**Message deduplication**: `_dedupe_messages()` removes exact `(type, content)` duplicates from the conversation history before sending to the LLM. This prevents prompt bloat from the WebSocket reloading full DB history each turn + LangGraph checkpointer accumulation.

**Payment failure handling**: `patient_general_llm` explicitly detects `payment_failed`, `"payment not successful"`, `"payment cancelled"` in the latest message and instructs the LLM to NOT start a new booking but offer retry.

**Streaming**: All calls use `async for chunk in llm.astream(messages)` with `adispatch_custom_event("llm_stream_chunk", content)`.

---

### 4.10 Output Guardrail

**File**: `guardrails/output_guardrail.py`
**LLM Used**: ❌ No

Scans the last `AIMessage` in `state["messages"]` for safety violations.

#### Rules

| Rule Category | Trigger Patterns | Action |
|---|---|---|
| Diagnosis Language | "you have", "you are suffering from", "your diagnosis is", "I diagnose you", "this confirms you" | Append medical disclaimer |
| Treatment/Prescription | "I am prescribing", "you must take", "you should take 500mg" | Append medical disclaimer |
| Unsafe Certainty | "I am 100% sure", "I guarantee" | Append medical disclaimer |
| Privacy Leak | UUID regex `[0-9a-f]{8}-...-[0-9a-f]{12}` | Replace with `[REDACTED]` |
| Metadata Leak | "system prompt:", "workflow status:" | Replace with `[REDACTED]` |

**Context-aware relaxation**: For `query_type == "knowledge"`, only rules containing `"Leak"` in their name are enforced. Diagnostic language is acceptable for educational content.

**Medical disclaimer** (appended when diagnosis/treatment rules trigger):
> *This is general health information and not a definitive diagnosis. Please consult a licensed physician for personalized medical advice.*

**Risk scoring**: `session_risk_delta = len(triggered_rules)` is added via the `operator.add` reducer.

---

## 5. Multi-Turn Appointment Booking Workflow (Payment Flow)

The `APPOINTMENT_BOOK` capability handles a 2-4 turn payment flow using Razorpay.

### Stage 1: Slot Search (Turn 1)
User: *"Book an appointment with Dr. Manish"*
- Planner creates `APPOINTMENT_SEARCH_SLOTS` task
- Capability queries `DoctorSlot` table for available unbooked slots
- Returns evidence listing available time slots

### Stage 2: Slot Selection & Payment Order (Turn 2)
User: *"Book the first available slot"*

`handle_appointment_book()`:
1. `PaymentService.release_expired_payment_holds()` — cleans stale holds
2. Resolves slot by `booking_ordinal` ("first" → `slots[0]`) or `booking_datetime` (exact time match)
3. Falls back to `slots[0]` if no match
4. `PaymentService.create_order_for_appointment()`:
   - Creates `PAYMENT_PENDING` appointment
   - Soft-locks `DoctorSlot.isBooked = True`
   - Creates Razorpay order via REST API
   - Returns `{order_id, appointment_id, key_id, amount, currency}`
5. Doctor name formatting: `if not name.startswith("Dr."): name = f"Dr. {name}"`
6. Returns evidence with `action = "confirm_payment"` + `payment_order` in metadata
7. Message: *"Your appointment with Dr. X on July 22 at 4:00 PM has been reserved. The consultation fee is Rs. 500. Do you want to proceed to payment?"*

`payment_order` propagates: `capability → task_executor (ctx.metadata) → state → llm_orchestrator → WebSocket payload → frontend`

### Stage 3: User Confirms → Razorpay Popup (Turn 3)
User: *"ok proceed"*

`handle_appointment_book()` (with existing `appointment_id`):
1. Fetches the pending appointment
2. Gets or creates `pending_payment_order` via `PaymentService.get_pending_payment_order()`
3. Returns `action = "open_razorpay"` + full `payment_order` data
4. Frontend detects `payment_order` → opens Razorpay checkout popup

### Stage 4: Payment Verification & Confirmation (After Payment)
Razorpay callback → Frontend → `POST /api/payments/verify` → Backend verifies HMAC → appointment `CONFIRMED`

Next chat turn with `payment_successful = True`:
1. Fetches confirmed appointment by ID
2. Returns: *"Your payment was successful and your appointment with Dr. X has been confirmed."*
3. Sets `metadata.clear_payment_order = True` and workflow `status = "completed"`

### Consultation Fee Logic
- `DEFAULT_CONSULTATION_FEE_PAISE = 50000` (Rs. 500)
- Source: `doctor.consultationFee` field in DB
- Fallback: if null/0, uses default 50000 paise

---

## 6. RAG & Vector Search System

### Document Ingestion
1. **Text Extraction**: PDF/image text extracted
2. **Chunking** (`asset_service.py`): `RecursiveCharacterTextSplitter` with `chunk_size=1500`, `overlap=150`, separators `["\n\n", "\n", " ", ""]`
3. **Embedding** (`ai/core_services/embeddings.py`): `text-embedding-004` (Google), **768 dimensions**
4. **Storage** (`ai/vectorstore/pgvector_service.py`): `rag_documents` table, raw SQL INSERT with `$7::vector`

### Similarity Search
```sql
SELECT id, patient_id, content, summary, metadata,
       1 - (embedding <=> $1::vector) AS similarity
FROM rag_documents
WHERE patient_id = $2
ORDER BY embedding <=> $1::vector
LIMIT $6
```
- **Distance**: Cosine (`<=>` operator)
- **Score**: `1 - cosine_distance` (0.0 to 1.0)
- **Threshold**: `similarity_threshold = 0.30`
- **top_k**: 5
- **Asset-scoped**: Filters by `metadata->>'asset_id'` when `rag_scope.asset_ids` is set

### RAG Tools (`capabilities/tools/rag_tools.py`)
- `patient_rag_tool`: Scoped to `state["user_id"]`
- `doctor_rag_tool`: Scoped to `state["target_patient_id"]`

---

## 7. Conversation Memory System

**File**: `memory/conversation_memory.py`

Persists workflow context across turns in `state["conversation_memory"]` — nested dict with 4 slots:

```python
conversation_memory = {
    "workflow": {
        "active_workflow": {...},
        "doctor_name": "Dr. Manish",
        "booking_datetime": "2026-07-22T10:30:00+05:30",
        "booking_ordinal": "first",
        "appointment_id": "uuid-...",
        "slot_id": "uuid-...",
        "amount": 50000,
        "currency": "INR",
    },
    "short_term": {
        "last_query_type": "rag",
        "last_capabilities": ["ASSET_INDEX"],
    },
    "recommendation": {
        "recommended_specialty": "Cardiologist",
        "recommended_doctor_id": "doc_manish_rao_6",
        "recommended_doctor_name": "Dr. Manish Rao",
    },
    "semantic": {
        "doctor_availability_context": [...]
    }
}
```

**`hydrate_planner_metadata()`** — START of each turn: injects memory into planner context. Terminal workflows (`completed`/`confirmed`/`cancelled`) clear all booking-related keys.

**`update(result_dict)`** — END of task execution: persists active_workflow, recommendation, and semantic data. If a workflow query has no active_workflow, it expires the previous one along with recommendation.

**Persistence**: Via LangGraph `MemorySaver`. **Resets on server restart.**

---

## 8. LLM Calls: Count, Routing, and Token Budget

### LLM Call Count Per Turn

| Scenario | LLM Calls | Which LLMs |
|---|---|---|
| Simple greeting ("Hi") | 2 | Planner + patient_general_llm |
| Medical question (knowledge) | 3 | Planner + Recommendation + patient_knowledge_llm |
| Medical report analysis | 4 | Planner + Triage + Recommendation + patient_assistant_llm |
| Appointment booking (action) | 1 | Planner only (response_composer sets final_response) |
| Input guardrail cache miss | +1 | Guardrail LLM fallback |
| **Min** | **1** | Planner only (action flows) |
| **Max** | **5** | Guardrail + Planner + Triage + Recommendation + Response |
| **Typical** | **3-4** | — |

### Model Configuration

| Setting | Value | Override |
|---|---|---|
| Chat model | `gemini-2.0-flash` | `GEMINI_MODEL` env var |
| Embedding model | `text-embedding-004` | Settings |
| Embedding dimension | 768 | Settings |
| Temperature (most nodes) | `0.1` (via `get_workflow_model()`) | — |
| Temperature (recommendation) | `0.0` (deterministic) | — |
| Temperature (guardrail fallback) | `0.0` | — |

---

## 9. External Dependencies & Services

### 9.1 WebSocket Chat Router (`api/chat/router.py`)
- FastAPI WebSocket endpoint with JWT auth via query param
- Builds `WorkflowState` via `create_workflow_state()` — passes `payment_order`, `payment_successful`, `payment_failed` from client
- Invokes `unified_chat_graph.astream_events()` for streaming
- Listens for `"llm_stream_chunk"` events → forwards to frontend
- Final message includes `payment_order` from state for frontend Razorpay popup

### 9.2 Payment Service (`services/payment_service.py`)
- `create_order_for_appointment()` — Creates provisional appointment + Razorpay order
- `verify_payment()` — Verifies Razorpay HMAC, promotes to CONFIRMED
- `get_pending_payment_order()` — Fetches pending order for re-display
- `release_expired_payment_holds()` — Cleans stale PAYMENT_PENDING appointments
- `DEFAULT_CONSULTATION_FEE_PAISE = 50000`

### 9.3 LLM Client (`ai/core_services/llm_client.py`)
- `get_chat_model(temperature)` → `ChatGoogleGenerativeAI`
- `complete_text(messages, temperature)` → Non-streaming LLM call
- `_extract_json(text)` → Strips markdown fences from LLM JSON output

### 9.4 Database (Prisma ORM)

| Table | Prisma Model | Used By |
|---|---|---|
| `appointments` | `Appointment` | APPOINTMENT, APPOINTMENT_BOOK, APPOINTMENT_CANCEL |
| `doctors` | `Doctor` | DOCTOR_AVAILABILITY, APPOINTMENT_BOOK, Recommendation |
| `doctor_slots` | `DoctorSlot` | DOCTOR_AVAILABILITY, APPOINTMENT_BOOK |
| `consultations` | `Consultation` | CONSULTATION retriever |
| `messages` | `Message` | CONSULTATION retriever |
| `ai_chat_messages` | `AiChatMessage` | MEMORY retriever |
| `asset_indexes` | `AssetIndex` | ASSET_INDEX retriever |
| `patient_medical_histories` | `PatientMedicalHistory` | PATIENT_HISTORY retriever |
| `rag_documents` | `RagDocument` | pgvector RAG search (raw SQL) |
| `payments` | `Payment` | PaymentService |
| `semantic_cache_words` | `SemanticCacheWord` | Input Guardrail Trie cache |

---

## 10. Data Models Reference

### PlannerTask (`models/planner_task.py`)
```python
@dataclass
class PlannerTask:
    task_type: str          # "retrieve" | "action" | "general_response"
    retriever: str | None   # Registry key e.g. "APPOINTMENT"
    action_handler: str | None  # Registry key e.g. "APPOINTMENT_BOOK"
    action: str | None      # Sub-action e.g. "latest", "upcoming"
    parameters: dict        # Extra params
    task_id: str | None     # For dependency tracking
    depends_on: list[str]   # Task IDs that must complete first
    produces: list[str]     # State keys this task writes
    consumes: list[str]     # State keys this task reads

    @property
    def capability_name -> str | None  # Returns retriever or action_handler
```

### CapabilityResult (`models/capability_result.py`)
```python
@dataclass
class CapabilityResult:
    capability_name: str
    status: str = "SUCCESS"
    evidence: list[dict] = []
    pending_tasks: list = []
    data: Any = None
    metadata: dict = {}    # payment_order, active_workflow, clear_payment_order, etc.
    warnings: list[str] = []
    errors: list[str] = []
    timing_ms: float = 0.0
```

### ExecutionContext (`models/execution_context.py`)
- `completed_task_ids: set[str]` — dependency tracking
- `shared_context: dict` — data produced by tasks
- `evidence: list[dict]` — all evidence blocks
- `metadata: dict` — flags (payment_order, active_workflow, clear_*)
- `stats: ExecutionStatistics` — timing

### ActiveWorkflow (`models/active_workflow.py`)
- `type`: `"appointment_booking"`
- `status`: `"waiting_selection"` | `"waiting_confirmation"` | `"waiting_payment_confirmation"` | `"executing"` | `"completed"` | `"confirmed"` | `"cancelled"`
- `context`: dict with `doctor_name`, `appointment_id`, `slot_id`, `amount`, `currency`, `booking_datetime`, `booking_ordinal`, `available_slots`, `payment_stage`

---

## 11. File Index

```
backend/workflows/
├── WORKFLOW_CONTEXT.md               ← This file
├── __init__.py
├── unified_chat_graph.py             ← Re-exports from graph/
├── state.py                          ← Re-exports from graph/
│
├── graph/
│   ├── unified_chat_graph.py         ← LangGraph 8-node DAG + build_unified_chat_graph()
│   ├── state.py                      ← WorkflowState TypedDict + factory functions
│   └── common.py                     ← get_workflow_model(), latest_message_text(), message_content_text()
│
├── guardrails/
│   ├── input_guardrail.py            ← Regex security + Semantic Cache Trie + LLM fallback
│   ├── output_guardrail.py           ← Regex output safety + disclaimer injection
│   └── semantic_cache.py             ← Trie data structure + SemanticCacheManager (DB-backed)
│
├── auth/
│   ├── authorization.py              ← Authorization node
│   └── authorization_service.py      ← filter_authorized_plan()
│
├── planner/
│   ├── planner.py                    ← PlanningEngine (rule-based) + planner_node entry point
│   ├── llm_planner.py               ← LLMPlanningEngine (primary, LLM call)
│   ├── context_resolver.py           ← ContextResolver (follow-up, ordinal, affirmation)
│   ├── plan_optimizer.py             ← Deduplication + validation
│   ├── planning_validator.py         ← Plan structure validation
│   ├── retrieval_strategy.py         ← RetrievalStrategy enum
│   ├── planner_rule_config.py        ← Keyword sets for rule-based planner
│   ├── planner_rule_order.py         ← Rule priority order
│   ├── planner_rule_loader.py        ← Rule loader
│   ├── planner_rule_registry.py      ← Rule handler functions
│   ├── task_template_registry.py     ← TaskTemplate → PlannerTask conversion
│   └── parsers/
│       ├── intent_parser.py          ← ParsedIntent extraction
│       └── document_query_parser.py  ← DocumentQueryIntent extraction
│
├── executor/
│   ├── capability_registry.py        ← REGISTRY dict + all 10 capability handler functions
│   ├── task_executor.py              ← Sequential task loop + task_executor_node
│   └── freshness_policy.py           ← FreshnessDecision evaluator
│
├── recommendation/
│   └── recommendation_engine.py      ← LLM-powered specialist recommendation (patient-only)
│
├── composer/
│   └── response_composer.py          ← Evidence enrichment + action short-circuit
│
├── llm/
│   ├── llm_orchestrator.py           ← Unified orchestrator (role + intent routing)
│   ├── patient/
│   │   ├── patient_nodes.py          ← triage_evaluator, patient_general_llm,
│   │   │                                patient_knowledge_llm, patient_assistant_llm,
│   │   │                                TriageEvaluation model, _dedupe_messages()
│   │   └── routing.py               ← classify_intent() — keyword + metadata routing
│   └── doctor/
│       └── doctor_nodes.py           ← doctor_general_llm, doctor_scoped_llm
│
├── memory/
│   └── conversation_memory.py        ← ConversationMemoryManager (4-slot cross-turn state)
│
├── capabilities/
│   ├── retrievers/
│   │   ├── appointment_retriever.py
│   │   ├── asset_index_retriever.py
│   │   ├── asset_scoped_rag.py       ← pgvector asset-scoped similarity search
│   │   ├── consultation_retriever.py
│   │   ├── conversation_memory.py
│   │   ├── doctor_availability_retriever.py
│   │   └── patient_history_retriever.py
│   ├── actions/
│   │   └── __init__.py               ← Empty (handlers in capability_registry.py)
│   └── tools/
│       ├── rag_tools.py              ← @tool decorated RAG query functions
│       └── appointment_tools.py
│
├── models/
│   ├── planner_task.py
│   ├── capability_metadata.py
│   ├── capability_result.py
│   ├── execution_context.py
│   ├── execution_plan.py
│   ├── active_workflow.py
│   ├── freshness_decision.py
│   ├── resolved_context.py
│   ├── composed_response.py
│   ├── evidence.py
│   └── task_template.py
│
└── utils/
    ├── logger.py                     ← log_section(), log_key_value(), log_trace(), format_duration()
    └── sanitizer.py                  ← sanitize_for_llm() (strips IDs/UUIDs)
```

---

## 12. Design Decisions & Known Limitations

### Design Decisions

1. **Linear DAG, no loops**: The LangGraph pipeline has no cycles. The planner generates a complete task list in one shot. No agentic re-planning loops. This bounds compute cost and prevents runaway healthcare workflows.

2. **Sequential task execution**: No `asyncio.gather`. Tasks mutate shared `ExecutionContext` and have data dependencies. Race conditions in booking flows are unacceptable.

3. **Actions bypass the LLM**: When `APPOINTMENT_BOOK` or `APPOINTMENT_CANCEL` succeeds, `response_composer` sets `final_response` directly. The LLM Orchestrator detects this and skips all LLM calls. Prevents hallucinated booking details.

4. **Dual guardrails (input + output)**: Input uses Trie + LLM, output uses regex. Both contribute to cumulative `session_risk_score` via `operator.add` reducer.

5. **Semantic Cache replaces TF-IDF**: The old `TFIDFValidator` was replaced with a persistent Trie-based cache (`SemanticCacheWord` table). LLM-classified keywords are saved to DB, making future lookups instant. The cache is self-learning — it grows as users interact.

6. **Payment order propagation**: `payment_order` flows through `capability → ctx.metadata → task_executor → state → llm_orchestrator → WebSocket payload → frontend Razorpay popup`.

7. **Doctor name sanitization**: `if not name.startswith("Dr."): name = f"Dr. {name}"` prevents double-prefix.

8. **LLM Planner with rule-based fallback**: Primary path uses LLM for flexible intent parsing. Falls back to deterministic rule-based planner on low confidence or validation failure. Dual-path ensures reliability.

9. **Message deduplication**: `_dedupe_messages()` in patient LLM nodes removes `(type, content)` duplicates caused by WebSocket history reload + LangGraph checkpointer accumulation.

10. **Payment failure detection in LLM prompt**: `patient_general_llm` explicitly checks for `payment_failed` state and injects a system prompt instruction to NOT start a new booking but offer retry.

### Known Limitations

**A. MemorySaver resets on restart**: All conversation continuity lost on backend restart. Needs Redis/PostgreSQL-backed checkpointer.

**B. `APPOINTMENT_RESCHEDULE` is a stub**: Returns context message only; no actual DB modification.

**C. `patient_knowledge_llm` has no evidence**: Relies entirely on LLM training data. Cannot reference patient's uploaded reports.

**D. `DOCTOR_AVAILABILITY` is doctor-only**: Patients must use `APPOINTMENT_SEARCH_SLOTS` instead.

**E. Semantic Cache cold-start**: On first boot with empty `semantic_cache_words` table, `_seed_initial()` populates ~35 words, but unusual medical terms will miss until the LLM fallback classifies them.

**F. Chunking is character-based**: `RecursiveCharacterTextSplitter(1500/150)` doesn't understand clinical document structure. A lab test header might be split from its value.
