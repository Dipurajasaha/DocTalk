# AI Chat Workflow — LangGraph Unified Chat Graph

## Overview

The AI chat system is built on a **LangGraph** state machine that routes messages
through different processing paths depending on the user's **role** (`patient` or
`doctor`) and the conversation **mode** (`general` or `patient_scoped`). Every
request passes through a shared entry point, gets routed to the appropriate
LLM node, and then flows through a medical safety guardrail before returning a
response.

All workflow code lives under `backend/workflows/`.

---

## Architecture at a Glance

The graph has **8 nodes** (plus `START`/`END`). RAG tool calls happen *inside*
the LLM nodes — they are not separate graph nodes.

```
                        ┌──────────────────────┐
                        │        START          │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │  log_entry_context    │   logs user/session metadata
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │   route_by_role       │   conditional: role + mode
                        └──┬────────┬───────┬──┘
                           │        │       │
               ┌───────────▼──┐  ┌──▼───┐  ┌▼───────────────┐
               │  PATIENT PATH│  │DOCTOR│  │ DOCTOR SCOPED  │
               │              │  │GENERAL│  │    PATH        │
               └──────┬───────┘  └──┬───┘  └───────┬────────┘
                      │             │              │
               ┌──────▼───────┐     │       ┌──────▼────────┐
               │  triage_     │     │       │ doctor_       │
               │  evaluator   │     │       │ scoped_llm    │
               │              │     │       │               │
               │ LLM classifies│    │       │ ┌───────────┐ │
               │ emergency vs │     │       │ │doctor_rag│ │
               │ routine      │     │       │ │  _tool    │ │
               └──────┬───────┘     │       │ │(pgvector) │ │
                      │             │       │ └─────┬─────┘ │
               ┌──────▼───────┐     │       │       │       │
               │ classify_    │     │       │  LLM + context │
               │ intent       │     │       │       │       │
               │              │     │       └───────┼───────┘
               │ keyword-based│     │               │
               │ routing      │     │               │
               └──┬───────┬───┘     │               │
                  │       │         │               │
         ┌────────▼──┐ ┌──▼──────┐  │               │
         │ patient_  │ │ patient_│  │               │
         │ assistant │ │ general │  │               │
         │ _llm      │ │ _llm    │  │               │
         │           │ │         │  │               │
         │ ┌───────┐ │ │ no RAG  │  │               │
         │ │patient│ │ │         │  │               │
         │ │_rag_  │ │ │         │  │               │
         │ │tool   │ │ │         │  │               │
         │ └───┬───┘ │ │         │  │               │
         │     │     │ │         │  │               │
         │ LLM+ctx    │ │         │  │               │
         └─────┬──────┘ └────┬────┘  │               │
               │             │       │               │
               │      ┌──────▼───────▼───┐           │
               │      │ doctor_general_  │           │
               │      │ llm              │           │
               │      │                  │           │
               │      │ LLM only (no RAG)│           │
               │      └──────┬───────────┘           │
               │             │                       │
               └──────┬──────┘                       │
                      │            ┌─────────────────┘
                      ▼            ▼
             ┌─────────────────────────┐
             │  medical_safety_        │   checks for "you have",
             │  guardrail              │   "diagnose", "suffer from"
             │                         │   → replaces with disclaimer
             └───────────┬─────────────┘
                         │
             ┌───────────▼─────────────┐
             │          END            │
             └─────────────────────────┘
```

### RAG sub-steps (inside LLM nodes)

The RAG tools are **not** separate graph nodes — they are called internally by
the LLM nodes. Here is where each tool is invoked:

| Node                   | RAG Tool            | Scope                         |
| ---------------------- | ------------------- | ----------------------------- |
| `patient_assistant_llm`| `patient_rag_tool`  | `user_id` (own records)       |
| `doctor_scoped_llm`    | `doctor_rag_tool`   | `target_patient_id` (patient) |
| `patient_general_llm`  | *(none)*            | General health chat           |
| `doctor_general_llm`   | *(none)*            | General medical reasoning     |

---

## State (`backend/workflows/state.py`)

Every node receives and returns a `WorkflowState` (a `TypedDict` with LangGraph's
`add_messages` reducer for the message list):

| Field               | Type                          | Purpose                                          |
| ------------------- | ----------------------------- | ------------------------------------------------ |
| `messages`          | `list[BaseMessage]`           | Full conversation history (Human + AI messages)  |
| `role`              | `"patient"` \| `"doctor"`     | Who is sending the message                       |
| `mode`              | `"general"` \| `"patient_scoped"` | Doctor-only: general chat or scoped to a patient |
| `user_id`           | `str`                         | Authenticated user ID                            |
| `target_patient_id` | `str \| None`                 | Patient context for doctor-scoped queries        |
| `ai_session_id`     | `str`                         | Unique AI session identifier                     |
| `triage_level`      | `str`                         | `"routine"` or `"emergency"`                     |
| `context_payload`   | `dict`                        | Metadata accumulator (route info, RAG results,   |
|                     |                               |   triage evaluation, guardrail status)           |
| `final_response`    | `str`                         | The LLM-generated response text                  |

---

## Nodes

### 1. `log_entry_context` — Entry Logger

**File:** `backend/workflows/unified_chat_graph.py`

A lightweight async node that logs the incoming request metadata (`user_id`,
`target_patient_id`, `ai_session_id`, `role`) for observability. Returns no
state changes.

---

### 2. `triage_evaluator` — Emergency Triage (Patient Only)

**File:** `backend/workflows/nodes/patient_nodes.py`

- Invoked **only for patients**.
- Sends the last patient message to `qwen2.5:7b-instruct` with a structured
  output schema (`TriageEvaluation`) that classifies whether the message
  contains **emergency symptoms** (chest pain, breathing difficulty, stroke,
  seizure, unconsciousness, severe bleeding, blue lips, etc.).
- If `is_emergency` is `True`, sets `triage_level` to `"emergency"` in the state.
- Stores the full triage evaluation in `context_payload["triage_evaluation"]`.

---

### 3. `classify_intent` — Intent Classifier (Patient Only)

**File:** `backend/workflows/nodes/routing.py`

- Invoked **after triage** for patient role.
- Keyword-based routing that decides whether the patient query needs document
  retrieval:
  - **Emergency terms** (chest pain, stroke, seizure, etc.) → routes to
    `patient_assistant_llm` (with RAG) so the patient gets context-aware help.
  - **Clinical terms** (`"report"`, `"blood"`, `"pain"`, `"xray"`, `"scan"`,
    `"prescription"`, `"medication"`, `"lab"`, `"result"`, etc.) → routes to
    `patient_assistant_llm` (with RAG).
  - **General queries** (greetings, small talk, non-medical questions) → routes
    to `patient_general_llm` (no RAG, faster and cheaper).

---

### 4. `patient_assistant_llm` — Patient-Facing AI (With RAG)

**File:** `backend/workflows/nodes/patient_nodes.py`

- Invoked for **clinical/emergency patient queries** (after intent classification).
- Calls `patient_rag_tool` to retrieve the patient's own medical records from
  the pgvector vector store (scoped to `user_id`).
- Injects the retrieved context into a system prompt and calls the LLM
  (`qwen2.5:7b-instruct`, temperature 0.1).
- Returns an empathetic, patient-friendly response grounded in their records.

---

### 5. `patient_general_llm` — Patient-Facing AI (No RAG)

**File:** `backend/workflows/nodes/patient_nodes.py`

- Invoked for **general/non-clinical patient queries** (after intent classification).
- Does **not** call RAG — responds with a general health assistant prompt.
- Faster and avoids unnecessary vector store queries for casual conversation.

---

### 6. `doctor_general_llm` — Doctor General Copilot

**File:** `backend/workflows/nodes/doctor_nodes.py`

- Invoked for **doctors in `general` mode** (no specific patient context).
- Uses a clinical reasoning system prompt focused on differential diagnosis,
  red-flag assessment, and next-step clinical thinking.
- Does **not** call RAG — the doctor asks general medical questions.
- Returns a concise, technical clinical response.

---

### 7. `doctor_scoped_llm` — Doctor Patient-Scoped Copilot

**File:** `backend/workflows/nodes/doctor_nodes.py`

- Invoked for **doctors in `patient_scoped` mode** (a specific
  `target_patient_id` is set).
- Calls `doctor_rag_tool` to retrieve the target patient's medical records
  from pgvector (scoped to `target_patient_id`).
- Injects the retrieved context into the same clinical reasoning system prompt.
- Returns a response grounded in the specific patient's data.

---

### 8. `medical_safety_guardrail` — Safety Filter

**File:** `backend/workflows/nodes/shared_nodes.py`

- The **final node** before `END` for all roles.
- Scans the last AI message for **prohibited clinical prognosis keywords**:
  `"you have"`, `"diagnose"`, `"suffer from"`.
- If triggered, **replaces** the LLM response with a medical disclaimer:
  > *"I cannot provide a definitive diagnosis. Please consult a licensed physician."*
- Stores guardrail status in `context_payload["medical_safety_guardrail"]`.

---

## Edges

| From                        | To                         | Type        | Condition / Logic                                          |
| --------------------------- | -------------------------- | ----------- | ----------------------------------------------------------- |
| `START`                     | `log_entry_context`        | Direct      | Always                                                      |
| `log_entry_context`         | `triage_evaluator`         | Conditional | `role == "patient"`                                         |
| `log_entry_context`         | `doctor_general_llm`      | Conditional | `role == "doctor"` AND `mode != "patient_scoped"`           |
| `log_entry_context`         | `doctor_scoped_llm`        | Conditional | `role == "doctor"` AND `mode == "patient_scoped"`           |
| `triage_evaluator`          | `classify_intent`          | Direct      | Always                                                      |
| `classify_intent`           | `patient_assistant_llm`    | Conditional | `intent == "patient_rag"` OR `intent == "emergency"`        |
| `classify_intent`           | `patient_general_llm`      | Conditional | `intent == "patient_general"`                                |
| `patient_assistant_llm`     | `guardrail`                | Direct      | Always                                                      |
| `patient_general_llm`       | `guardrail`                | Direct      | Always                                                      |
| `doctor_general_llm`        | `guardrail`                | Direct      | Always                                                      |
| `doctor_scoped_llm`         | `guardrail`                | Direct      | Always                                                      |
| `guardrail`                 | `END`                      | Direct      | Always                                                      |

Two conditional routing functions implement the branching:

- **`route_by_role`** (`unified_chat_graph.py`) — reads `state["role"]` and
  `state["mode"]` to pick the correct entry node.
- **`route_patient_intent`** (`unified_chat_graph.py`) — calls `classify_intent`
  and routes to the RAG or general patient LLM based on the result.

---

## RAG Tools (`backend/workflows/nodes/tools.py`)

Two LangChain tools backed by the pgvector vector store:

| Tool                | Scope         | Filters by                          |
| ------------------- | ------------- | ----------------------------------- |
| `patient_rag_tool`  | Patient       | `user_id` (own records only)        |
| `doctor_rag_tool`   | Doctor        | `target_patient_id` (patient records) |

Both tools call `pgvector_service.search_documents()` with a configurable
`top_k` (default 5) and `similarity_threshold` (default 0.30). The retrieved
documents are injected into the LLM system prompt as context.

---

## How It's Invoked

The FastAPI WebSocket router (`backend/api/chat/router.py`) is the main entry
point:

1. A WebSocket connection is established with a JWT token for authentication.
2. The router builds a `WorkflowState` from the incoming `ChatRequest`
   (containing `role`, `mode`, `user_id`, `target_patient_id`, message history).
3. The `unified_chat_graph` is invoked via `ainvoke()` or `astream_events()`,
   with a `MemorySaver` checkpointer keyed by `ai_session_id` for conversation
   continuity.
4. The final response is extracted from `state["final_response"]` and sent back
   over the WebSocket.

---

## Model Configuration

- **Chat model:** `qwen2.5:7b-instruct` via Ollama (default base URL:
  `http://localhost:11434`)
- **Temperature:** `0.1` for all LLM nodes (low randomness for clinical safety)
- **Embeddings:** `nomic-embed-text` (384 dimensions) for pgvector retrieval
- **Checkpointer:** `MemorySaver` (in-memory; resets on server restart)