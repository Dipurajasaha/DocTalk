# DocTalk — Data Flow Diagrams

> **Project**: DocTalk — AI-powered digital healthcare platform  
> **Architecture**: React 19 (Frontend) ↔ FastAPI (Backend) ↔ PostgreSQL/Supabase (Database)  
> **AI Engine**: LangGraph State Machine with streaming WebSocket

---

## Table of Contents

1. [AI Health Assistant Chat (Patient)](#1-ai-health-assistant-chat-patient)
2. [Appointment Booking Flow](#2-appointment-booking-flow)
3. [Doctor-Patient Consultation Chat](#3-doctor-patient-consultation-chat)
4. [Doctor AI Copilot (Patient-Scoped RAG)](#4-doctor-ai-copilot-patient-scoped-rag)
5. [Prescription Issuance & Verification](#5-prescription-issuance--verification)
6. [Medical Document Upload & Analysis](#6-medical-document-upload--analysis)
7. [AI-Automated Payment Processing](#7-ai-automated-payment-processing)

---

## 1. AI Health Assistant Chat (Patient)

The patient asks a health question and receives a streaming AI response through a WebSocket connection. The AI pipeline runs through a LangGraph state machine with 7 stages.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (PatientDashboard.jsx)                                                     │
│                                                                                      │
│  ┌──────────────┐   ┌──────────────────────┐   ┌──────────────────────────────────┐ │
│  │ User types    │   │ buildAiChatWebSocket │   │ WebSocket onmessage handler      │ │
│  │ message in    │──▶│ Url({role:'patient', │──▶│ - Parses event type              │ │
│  │ chat input    │   │   token})            │   │ - "status" → setProcessingState  │ │
│  └──────────────┘   └──────────────────────┘   │ - "token"  → append to finalText │ │
│                                                 │ - "final"  → save to messages[]  │ │
│                                                 └──────────────┬───────────────────┘ │
│                                                                  │                    │
│                          Vite Proxy (ws://localhost:5173 → ws://127.0.0.1:8000)      │
└──────────────────────────────────────────────────────────────────┼───────────────────┘
                                                                   │
                    ┌──────────────────────────────────────────────┼──────────────────────────┐
                    │  BACKEND                                      │                          │
                    │                                              ▼                          │
                    │  ┌──────────────────────────────────────────────────────────────────┐   │
                    │  │  /api/chat/ai/patient/ws  (router.py → _run_ai_websocket)       │   │
                    │  │                                                                  │   │
                    │  │  1. Authenticate via ?token=<JWT>                                │   │
                    │  │  2. Accept WebSocket connection                                  │   │
                    │  │  3. Load chat history from DB (AiChatMessage table)              │   │
                    │  │  4. Send {"type":"history", "messages":[...]} to client          │   │
                    │  │  5. Enter message loop:                                         │   │
                    │  │     - Receive user message via WebSocket                         │   │
                    │  │     - Build input_state with messages, role, mode, user_id       │   │
                    │  │     - Invoke unified_chat_graph.astream_events()                 │   │
                    │  │     - Stream tokens back to client via WebSocket                 │   │
                    │  │     - Save exchange to DB (AiChatMessage)                        │   │
                    │  └──────────────────────────┬───────────────────────────────────────┘   │
                    │                             │                                          │
                    │                             ▼                                          │
                    │  ┌──────────────────────────────────────────────────────────────────┐   │
                    │  │  LangGraph Workflow (unified_chat_graph.py)                      │   │
                    │  │                                                                  │   │
                    │  │  ┌──────────────┐    ┌──────────────────┐    ┌───────────────┐   │   │
                    │  │  │ 1. Input     │───▶│ 2. Log Entry     │───▶│ 3. Planner    │   │   │
                    │  │  │ Guardrail    │    │ Context          │    │ Node          │   │   │
                    │  │  │ (checks for  │    │ (records session │    │ (classifies   │   │   │
                    │  │  │ blocked      │    │  metadata)       │    │  intent:      │   │   │
                    │  │  │ content)     │    └──────────────────┘    │  appointment? │   │   │
                    │  │  └──────┬───────┘                            │  medical QA?  │   │   │
                    │  │         │ (blocked → END)                    │  slot lookup?)│   │   │
                    │  │         ▼                                    └───────┬───────┘   │   │
                    │  │  ┌──────────────┐    ┌──────────────────┐           │           │   │
                    │  │  │ 4. Auth      │◀───│ 3. Planner      │           │           │   │
                    │  │  │ (role-based  │    │ (builds exec     │           │           │   │
                    │  │  │  permission  │    │  plan)           │           │           │   │
                    │  │  │  check)      │    └──────────────────┘           │           │   │
                    │  │  └──────┬───────┘                                   │           │   │
                    │  │         ▼                                           ▼           │   │
                    │  │  ┌──────────────────────────────────────────────────────────┐   │   │
                    │  │  │ 5. Task Executor (Shadow Pipeline — loops up to 3×)     │   │   │
                    │  │  │                                                          │   │   │
                    │  │  │  Retrieval Tasks:          Action Tasks:                 │   │   │
                    │  │  │  ┌──────────────────┐     ┌────────────────────────┐     │   │   │
                    │  │  │  │ • RAG vector     │     │ • Book appointment    │     │   │   │
                    │  │  │  │   search (pgvec) │     │ • Cancel appointment  │     │   │   │
                    │  │  │  │ • Slot lookup    │     │ • Process payment     │     │   │   │
                    │  │  │  │ • Patient record │     │ • Get doctor info     │     │   │   │
                    │  │  │  │ • Doctor list    │     └────────────────────────┘     │   │   │
                    │  │  │  └──────────────────┘                                    │   │   │
                    │  │  └──────────────────────────┬───────────────────────────────┘   │   │
                    │  │                             ▼                                   │   │
                    │  │  ┌──────────────────────────────────────────────────────────┐   │   │
                    │  │  │ 6. Recommendation Engine  │  7. Response Composer        │   │   │
                    │  │  │ (evaluates options,       │  (assembles evidence into    │   │   │
                    │  │  │  suggests next steps)     │   structured sections)       │   │   │
                    │  │  └──────────────────────────┴───────────────────────────────┘   │   │
                    │  │                             │                                   │   │
                    │  │                             ▼                                   │   │
                    │  │  ┌──────────────────────────────────────────────────────────┐   │   │
                    │  │  │ 8. LLM Orchestrator (routes to correct LLM node)        │   │   │
                    │  │  │                                                          │   │   │
                    │  │  │  ┌─────────────────────┐  ┌──────────────────────────┐   │   │   │
                    │  │  │  │ PATIENT mode:       │  │ DOCTOR mode:             │   │   │   │
                    │  │  │  │ • Triage Evaluator  │  │ • General Copilot        │   │   │   │
                    │  │  │  │ • Emergency path    │  │ • Patient-Scoped RAG     │   │   │   │
                    │  │  │  │ • General/RAG       │  │   Copilot                │   │   │   │
                    │  │  │  └─────────────────────┘  └──────────────────────────┘   │   │   │
                    │  │  └──────────────────────────┬───────────────────────────────┘   │   │
                    │  │                             ▼                                   │   │
                    │  │  ┌──────────────────────────────────────────────────────────┐   │   │
                    │  │  │ 9. Output Guardrail (Medical Safety Check)               │   │   │
                    │  │  │  • Scans for diagnostic overreach                        │   │   │
                    │  │  │  • Replaces "you have..." → professional disclaimer      │   │   │
                    │  │  │  • Final check before delivery to user                   │   │   │
                    │  │  └──────────────────────────────────────────────────────────┘   │   │
                    │  └──────────────────────────────────────────────────────────────────┘   │
                    │                                                                          │
                    │  ┌──────────────────────────────────────────────────────────────────┐   │
                    │  │  Database Layer (Prisma ORM → Supabase PostgreSQL)               │   │
                    │  │                                                                  │   │
                    │  │  Tables accessed:                                                │   │
                    │  │  • AiChatSession — stores session metadata (mode, role, userId)  │   │
                    │  │  • AiChatMessage — stores message history per session            │   │
                    │  │  • DoctorSlot — for slot availability lookups                    │   │
                    │  │  • Appointment — for booking operations                          │   │
                    │  │  • MedicalAsset — for RAG document retrieval (pgvector)          │   │
                    │  │  • Doctor — for doctor listing                                   │   │
                    │  └──────────────────────────────────────────────────────────────────┘   │
                    └──────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Steps (Patient AI Chat):

| Step | From | To | Data | Protocol |
|------|------|----|------|----------|
| 1 | PatientDashboard.jsx | Vite Proxy | `{ message: "I have a headache", language: "en" }` | WebSocket |
| 2 | Vite Proxy | `/api/chat/ai/patient/ws` | Forwarded with `?token=<JWT>` | WebSocket |
| 3 | `_run_ai_websocket()` | `ChatService.get_ai_chat_history()` | `ai_session_id="patient_ai_{userId}"` | Internal |
| 4 | `ChatService` | `AiChatMessage` table | `SELECT * WHERE sessionId = ?` | Prisma ORM |
| 5 | DB | WebSocket client | `{"type":"history", "messages":[...]}` | WebSocket |
| 6 | WebSocket client | `_run_ai_websocket()` | User's new message text | WebSocket |
| 7 | `_run_ai_websocket()` | `unified_chat_graph.astream_events()` | `input_state` with messages, role, mode | LangGraph |
| 8 | Graph → Planner Node | Task Executor | Intent classification + execution plan | Internal |
| 9 | Task Executor | DB (various tables) | Slot lookups, RAG search, patient records | Prisma ORM |
| 10 | Task Executor | Response Composer | Retrieved evidence + action results | Internal |
| 11 | Response Composer | LLM Orchestrator | Structured context for LLM | Internal |
| 12 | LLM Orchestrator | OpenAI-compatible API | Prompt + conversation history | HTTP/REST |
| 13 | OpenAI API | LLM Orchestrator | Streaming token response | HTTP/SSE |
| 14 | LLM Orchestrator | Output Guardrail | Raw LLM response | Internal |
| 15 | Output Guardrail | WebSocket client | `{"type":"token", "content":"..."}` (streaming) | WebSocket |
| 16 | Output Guardrail | WebSocket client | `{"type":"final", "content":"..."}` (complete) | WebSocket |
| 17 | `_run_ai_websocket()` | `ChatService.append_ai_chat_exchange()` | User message + AI response | Internal |
| 18 | `ChatService` | `AiChatMessage` table | `INSERT INTO AiChatMessage` | Prisma ORM |

---

## 2. Appointment Booking Flow

A patient browses available slots for a doctor and books an appointment. The doctor can then accept or reject the booking.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (PatientDashboard.jsx — "appointments" panel)                                  │
│                                                                                          │
│  ┌─────────────────────┐   ┌──────────────────────┐   ┌──────────────────────────────┐  │
│  │ 1. Select Doctor    │   │ 2. View Available    │   │ 3. Book Appointment          │  │
│  │    from dropdown    │──▶│    Slots (auto-loads  │──▶│    (Direct or Open Request)  │  │
│  │                     │   │    on doctor change)  │   │                              │  │
│  └─────────────────────┘   └──────────────────────┘   └──────────────┬───────────────┘  │
│                                                                       │                  │
│  API Calls:                                                           │                  │
│  ┌────────────────────────────────────────────────────────────────────┼──────────────┐   │
│  │ patientApi.getAvailableSlots(doctorId)                             │              │   │
│  │ patientApi.listDoctors()                                           │              │   │
│  │ patientApi.bookDirectAppointment(slotId, reason, note)  ◄─────────┘              │   │
│  │ patientApi.bookOpenAppointment(doctorId, reason, note)                            │   │
│  └───────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  Vite Proxy: /api → http://127.0.0.1:8000                                               │
└──────────────────────────────────────────────────────────────────────┬───────────────────┘
                                                                       │
                    ┌──────────────────────────────────────────────────┼──────────────────────────┐
                    │  BACKEND                                         │                          │
                    │                                                  ▼                          │
                    │  ┌──────────────────────────────────────────────────────────────────────┐   │
                    │  │  GET /api/appointments/slots/{doctor_id}  (appointments.py)          │   │
                    │  │  └─ AppointmentService.get_available_slots(doctor_id)                │   │
                    │  │     └─ DB: DoctorSlot.find_many(where={doctorId, isBooked:false,     │   │
                    │  │                                        isActive:true})               │   │
                    │  │                                                                      │   │
                    │  │  POST /api/appointments/book/direct  (appointments.py)               │   │
                    │  │  └─ AppointmentService.create_direct_booking(patient_id, data)       │   │
                    │  │     ├─ Validate slot exists & not booked                            │   │
                    │  │     ├─ DB: DoctorSlot.update(id, {isBooked: true})                  │   │
                    │  │     ├─ DB: Appointment.create({patientUsername, doctorId, slotId,   │   │
                    │  │     │                    appointmentDate, status:"CONFIRMED"})       │   │
                    │  │     └─ Return serialized appointment                                │   │
                    │  │                                                                      │   │
                    │  │  POST /api/appointments/book/open  (appointments.py)                 │   │
                    │  │  └─ AppointmentService.create_open_request(patient_id, data)         │   │
                    │  │     ├─ Validate doctor exists                                       │   │
                    │  │     ├─ DB: Appointment.create({patientUsername, doctorId,            │   │
                    │  │     │                    status:"PENDING", requestedAt})             │   │
                    │  │     └─ Return serialized appointment                                │   │
                    │  │                                                                      │   │
                    │  │  PUT /api/appointments/{id}/action  (appointments.py)                │   │
                    │  │  └─ AppointmentService.handle_doctor_action(doctor_id, id, data)     │   │
                    │  │     ├─ Validate doctor owns appointment                             │   │
                    │  │     ├─ If ACCEPT: DB: Appointment.update(status:"CONFIRMED",        │   │
                    │  │     │                appointmentDate, scheduledTime)                 │   │
                    │  │     ├─ If REJECT: DB: Appointment.update(status:"REJECTED")         │   │
                    │  │     └─ Return serialized appointment                                │   │
                    │  └──────────────────────────────────────────────────────────────────────┘   │
                    │                                                                              │
                    │  ┌──────────────────────────────────────────────────────────────────────┐   │
                    │  │  Database Tables Accessed:                                            │   │
                    │  │                                                                      │   │
                    │  │  DoctorSlot:  id, doctorId, startTime, endTime, isBooked, isActive   │   │
                    │  │  Appointment: id, patientUsername, doctorId, slotId, appointmentDate, │   │
                    │  │              scheduledTime, reason, status, doctorMessage, requestedAt│   │
                    │  │  Doctor:      doctorId, name, specialization, ...                    │   │
                    │  │  Patient:     username, name, ...                                    │   │
                    │  └──────────────────────────────────────────────────────────────────────┘   │
                    └──────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Steps (Appointment Booking):

| Step | From | To | Data | Protocol |
|------|------|----|------|----------|
| 1 | PatientDashboard.jsx | `/api/appointments/slots/{doctorId}` | `GET` with JWT Bearer token | HTTP/REST |
| 2 | `appointments.py` | `AppointmentService.get_available_slots()` | `doctor_id` | Internal |
| 3 | `AppointmentService` | `DoctorSlot` table | `SELECT WHERE doctorId=? AND isBooked=false AND isActive=true` | Prisma ORM |
| 4 | DB → `appointments.py` → Client | PatientDashboard.jsx | `[{id, startTime, endTime, ...}]` | HTTP/REST |
| 5 | PatientDashboard.jsx | `/api/appointments/book/direct` | `POST {slotId, reason, note}` + JWT | HTTP/REST |
| 6 | `appointments.py` | `AppointmentService.create_direct_booking()` | `patient_id, {slotId, reason, note}` | Internal |
| 7 | `AppointmentService` | `DoctorSlot` table | `UPDATE SET isBooked=true WHERE id=?` | Prisma ORM |
| 8 | `AppointmentService` | `Appointment` table | `INSERT INTO Appointment (...)` | Prisma ORM |
| 9 | DB → `appointments.py` → Client | PatientDashboard.jsx | `{id, status:"CONFIRMED", ...}` | HTTP/REST |
| 10 | DoctorDashboard.jsx | `/api/appointments/{id}/action` | `PUT {status:"ACCEPT", assignedDate}` + JWT | HTTP/REST |
| 11 | `appointments.py` | `AppointmentService.handle_doctor_action()` | `doctor_id, id, {status, assignedDate}` | Internal |
| 12 | `AppointmentService` | `Appointment` table | `UPDATE SET status="CONFIRMED", ... WHERE id=?` | Prisma ORM |

---

## 3. Doctor-Patient Consultation Chat

Real-time messaging between a patient and doctor during an active consultation, using WebSocket with polling fallback.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND                                                                                 │
│                                                                                          │
│  ┌──────────────────────────────┐          ┌──────────────────────────────────────────┐  │
│  │  PatientDashboard.jsx        │          │  DoctorDashboard.jsx                    │  │
│  │  ("docchat" panel)           │          │  ("consultations" panel)                │  │
│  │                              │          │                                         │  │
│  │  createRealTimeClient({      │          │  createRealTimeClient({                 │  │
│  │    url: `/api/chat/          │          │    url: `/api/chat/                     │  │
│  │     consultations/{id}/      │          │     consultations/{id}/                 │  │
│  │     messages`,               │          │     messages`,                          │  │
│  │    mode: 'auto',             │          │    mode: 'auto',                        │  │
│  │    pollInterval: 5000,       │          │    pollInterval: 5000,                  │  │
│  │    pollRequest: () =>        │          │    pollRequest: () =>                   │  │
│  │     patientApi               │          │     doctorApi                           │  │
│  │     .getConsultationMessages │          │     .getConsultationMessages            │  │
│  │     (id, 1, 20),             │          │     (id, 1, 20),                        │  │
│  │    onMessage: (payload) =>   │          │    onMessage: (payload) =>              │  │
│  │     setDocMessages(...)      │          │     setMessages(...)                    │  │
│  │  })                          │          │  })                                     │  │
│  └──────────────┬───────────────┘          └──────────────────┬───────────────────────┘  │
│                 │                                             │                          │
│                 │  WebSocket (auto) or Polling (fallback)     │                          │
│                 └──────────────────────┬──────────────────────┘                          │
│                                        │                                                 │
│                    Vite Proxy: /api → http://127.0.0.1:8000                              │
└────────────────────────────────────────┼─────────────────────────────────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────────────────────────────────────┐
                    │  BACKEND           │                                                    │
                    │                    ▼                                                    │
                    │  ┌──────────────────────────────────────────────────────────────────┐   │
                    │  │  WebSocket: /api/chat/consultations/{consultation_id}/messages   │   │
                    │  │  (router.py → websocket_consultation_messages)                   │   │
                    │  │                                                                  │   │
                    │  │  1. Authenticate via ?token=<JWT>                                │   │
                    │  │  2. Accept WebSocket connection                                  │   │
                    │  │  3. Send consultation history (last 100 messages)                │   │
                    │  │  4. Message loop:                                                │   │
                    │  │     - Receive: {"type":"message", "message":"Hello doctor"}      │   │
                    │  │     - ChatService.save_message(consultation_id, sender, msg)     │   │
                    │  │     - Broadcast: {"type":"message", "item": {...}}               │   │
                    │  └──────────────────────────────────────────────────────────────────┘   │
                    │                                                                          │
                    │  ┌──────────────────────────────────────────────────────────────────┐   │
                    │  │  REST Fallback Endpoints:                                        │   │
                    │  │                                                                  │   │
                    │  │  GET  /api/chat/consultations/{id}/messages?page=1&limit=20      │   │
                    │  │  └─ ChatService.get_consultation_messages(id, userId, page,      │   │
                    │  │                                        limit)                    │   │
                    │  │     └─ DB: Message.find_many(where={consultationId},             │   │
                    │  │                    order={timestamp:"asc"}, skip, take)           │   │
                    │  │                                                                  │   │
                    │  │  POST /api/chat/consultations/{id}/messages                      │   │
                    │  │  └─ ChatService.save_message(id, senderId, role, content)        │   │
                    │  │     └─ DB: Message.create({consultationId, senderId,             │   │
                    │  │                    senderRole, message, timestamp})              │   │
                    │  └──────────────────────────────────────────────────────────────────┘   │
                    │                                                                          │
                    │  ┌──────────────────────────────────────────────────────────────────┐   │
                    │  │  Database:                                                        │   │
                    │  │  ┌─────────────────────────────────────────────────────────────┐  │   │
                    │  │  │  Consultation: id, appointmentId, patientUsername, doctorId, │  │   │
                    │  │  │               createdAt, updatedAt, lastMessageAt            │  │   │
                    │  │  ├─────────────────────────────────────────────────────────────┤  │   │
                    │  │  │  Message: id, consultationId, senderId, senderRole,          │  │   │
                    │  │  │           message, timestamp                                 │  │   │
                    │  │  └─────────────────────────────────────────────────────────────┘  │   │
                    │  └──────────────────────────────────────────────────────────────────┘   │
                    └──────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Steps (Consultation Chat):

| Step | From | To | Data | Protocol |
|------|------|----|------|----------|
| 1 | PatientDashboard.jsx | `/api/chat/consultations/{id}/messages` | WebSocket connect with `?token=<JWT>` | WebSocket |
| 2 | `websocket_consultation_messages()` | `ChatService.get_consultation_messages()` | `consultation_id, user_id, page=1, limit=100` | Internal |
| 3 | `ChatService` | `Message` table | `SELECT WHERE consultationId=? ORDER BY timestamp ASC` | Prisma ORM |
| 4 | DB → WebSocket client | PatientDashboard.jsx | `{"type":"history", "messages":[...]}` | WebSocket |
| 5 | Patient types message | WebSocket | `{"type":"message", "message":"Hello doctor"}` | WebSocket |
| 6 | `websocket_consultation_messages()` | `ChatService.save_message()` | `consultation_id, sender_id, role, content` | Internal |
| 7 | `ChatService` | `Message` table | `INSERT INTO Message (...)` | Prisma ORM |
| 8 | `ChatService` | `Consultation` table | `UPDATE SET lastMessageAt=NOW() WHERE id=?` | Prisma ORM |
| 9 | WebSocket | PatientDashboard.jsx | `{"type":"message", "item":{...}}` | WebSocket |
| 10 | DoctorDashboard.jsx polls | `GET /api/chat/consultations/{id}/messages` | Polling request (every 5s) | HTTP/REST |
| 11 | `ChatService` | `Message` table | `SELECT WHERE consultationId=?` | Prisma ORM |
| 12 | DB → DoctorDashboard.jsx | Doctor sees new message | `{items: [...], total, has_more}` | HTTP/REST |

---

## 4. Doctor AI Copilot (Patient-Scoped RAG)

A doctor selects a specific patient and asks the AI copilot questions about that patient's medical history. The AI retrieves the patient's documents and records via RAG.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (DoctorDashboard.jsx — "copilot" panel)                                        │
│                                                                                          │
│  ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────────────┐  │
│  │ 1. Doctor selects    │   │ 2. buildAiChatWebSocket│  │ 3. WebSocket message loop    │  │
│  │    a patient from    │──▶│   Url({role:'doctor',  │──▶│  - Send patient-scoped      │  │
│  │    patient list      │   │    token,              │   │    query                     │  │
│  │                      │   │    targetPatientId})   │   │  - Receive streaming tokens  │  │
│  └──────────────────────┘   └──────────────────────┘   └──────────────┬───────────────┘  │
│                                                                        │                  │
│  Vite Proxy: /api → http://127.0.0.1:8000                              │                  │
└────────────────────────────────────────────────────────────────────────┼──────────────────┘
                                                                         │
                    ┌────────────────────────────────────────────────────┼──────────────────────────┐
                    │  BACKEND                                           │                          │
                    │                                                    ▼                          │
                    │  ┌────────────────────────────────────────────────────────────────────────┐   │
                    │  │  WebSocket: /api/chat/ai/doctor/ws?token=<JWT>&target_patient_id=<id>  │   │
                    │  │  (router.py → _run_ai_websocket with expected_role="doctor")           │   │
                    │  │                                                                        │   │
                    │  │  initial_mode = "DOCTOR_PATIENT" (because target_patient_id is set)    │   │
                    │  │  ai_session_id = "doctor_ai_{userId}"                                  │   │
                    │  └──────────────────────────┬─────────────────────────────────────────────┘   │
                    │                             │                                               │
                    │                             ▼                                               │
                    │  ┌────────────────────────────────────────────────────────────────────────┐   │
                    │  │  LangGraph Workflow (DOCTOR_PATIENT mode)                              │   │
                    │  │                                                                        │   │
                    │  │  1. Input Guardrail → 2. Log Entry → 3. Planner                        │   │
                    │  │     │                                                                    │   │
                    │  │     ▼                                                                    │   │
                    │  │  4. Authorization (checks doctor has access to this patient)            │   │
                    │  │     │                                                                    │   │
                    │  │     ▼                                                                    │   │
                    │  │  5. Task Executor — Patient-Scoped Retrieval:                           │   │
                    │  │     ┌──────────────────────────────────────────────────────────────┐   │   │
                    │  │     │ • RAG vector search over patient's MedicalAsset documents    │   │   │
                    │  │     │   (pgvector similarity search on embeddings)                 │   │   │
                    │  │     │ • Fetch patient's Appointment history                        │   │   │
                    │  │     │ • Fetch patient's Consultation history                       │   │   │
                    │  │     │ • Fetch patient's Prescription history                       │   │   │
                    │  │     └──────────────────────────────────────────────────────────────┘   │   │
                    │  │     │                                                                    │   │
                    │  │     ▼                                                                    │   │
                    │  │  6. Recommendation Engine → 7. Response Composer                        │   │
                    │  │     │                                                                    │   │
                    │  │     ▼                                                                    │   │
                    │  │  8. LLM Orchestrator → Patient-Scoped RAG Copilot LLM Node              │   │
                    │  │     │  (Uses patient's medical context + doctor's question)              │   │
                    │  │     ▼                                                                    │   │
                    │  │  9. Output Guardrail → Final Response to WebSocket                      │   │
                    │  └────────────────────────────────────────────────────────────────────────┘   │
                    │                                                                              │
                    │  ┌────────────────────────────────────────────────────────────────────────┐   │
                    │  │  Database / Vector Store:                                              │   │
                    │  │                                                                        │   │
                    │  │  MedicalAsset:  id, patientUsername, file_name, file_type,             │   │
                    │  │                folder_path, extracted_text, embedding (pgvector)       │   │
                    │  │  Appointment:   patientUsername, doctorId, status, ...                 │   │
                    │  │  Consultation:  patientUsername, doctorId, ...                         │   │
                    │  │  Prescription:  patientUsername, doctorId, ...                         │   │
                    │  │                                                                        │   │
                    │  │  RAG Flow:                                                             │   │
                    │  │  ┌────────────────────────────────────────────────────────────────┐   │   │
                    │  │  │ 1. Embed user query using Gemini Embedding API                 │   │   │
                    │  │  │ 2. pgvector similarity search: SELECT * FROM MedicalAsset      │   │   │
                    │  │  │    WHERE patientUsername=? ORDER BY embedding <=> ?query LIMIT 5│   │   │
                    │  │  │ 3. Return matched document chunks as context for LLM           │   │   │
                    │  │  └────────────────────────────────────────────────────────────────┘   │   │
                    │  └────────────────────────────────────────────────────────────────────────┘   │
                    └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Prescription Issuance & Verification

A doctor issues a digital prescription for a patient they have consulted. The prescription is cryptographically signed (Ed25519), rendered as a PDF with a QR verification code, and stored as a medical asset. Patients and third parties can verify prescription authenticity via the QR code.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND                                                                                 │
│                                                                                          │
│  ┌───────────────────────────────────┐     ┌───────────────────────────────────────────┐ │
│  │  DoctorDashboard.jsx              │     │  PatientDashboard.jsx                    │ │
│  │  ("Prescriptions" panel)          │     │  ("Prescriptions" panel)                 │ │
│  │                                   │     │                                           │ │
│  │  ┌─────────────────────────────┐  │     │  ┌───────────────────────────────────┐   │ │
│  │  │ 1. Doctor fills medicines   │  │     │  │ 1. View issued prescriptions      │   │ │
│  │  │    (name, dosage, frequency,│  │     │  │    (list with status, date,       │   │ │
│  │  │    duration, notes)         │  │     │  │    doctor name)                   │   │ │
│  │  ├─────────────────────────────┤  │     │  ├───────────────────────────────────┤   │ │
│  │  │ 2. Optional: sick note      │  │     │  │ 2. Download PDF of prescription   │   │ │
│  │  │    (reason, start/end date) │  │     │  │    (/api/prescriptions/{id}/pdf)  │   │ │
│  │  ├─────────────────────────────┤  │     │  ├───────────────────────────────────┤   │ │
│  │  │ 3. Issue prescription       │  │     │  │ 3. View QR code on PDF            │   │ │
│  │  │    POST /api/prescriptions  │  │     │  │    (embedded in generated PDF)    │   │ │
│  │  └─────────────────────────────┘  │     │  └───────────────────────────────────┘   │ │
│  └───────────────────────────────────┘     └───────────────────────────────────────────┘ │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │  PublicVerify.jsx (Public — no auth required)                                    │   │
│  │                                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │ 1. User scans QR code on prescription PDF                                │   │   │
│  │  │ 2. QR encodes → /verify?token=<qrToken>                                  │   │   │
│  │  │ 3. Frontend calls: GET /api/prescriptions/verify/{qrToken}               │   │   │
│  │  │ 4. Displays: Found ✓/✗, Valid Signature ✓/✗, Status,                    │   │   │
│  │  │    Doctor Name, Patient Name (masked), Issue Date,                       │   │   │
│  │  │    Medicines Count, Revoked status/reason                                │   │   │
│  │  └──────────────────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  Vite Proxy: /api → http://127.0.0.1:8000                                               │
└──────────────────────────────────────────────────────────┬───────────────────────────────┘
                                                           │
                    ┌──────────────────────────────────────┼──────────────────────────────────────┐
                    │  BACKEND                             │                                      │
                    │                                      ▼                                      │
                    │  ┌──────────────────────────────────────────────────────────────────────┐   │
                    │  │  POST /api/prescriptions  (prescriptions.py → issue_prescription)    │   │
                    │  │                                                                      │   │
                    │  │  1. Authenticate doctor via JWT                                     │   │
                    │  │  2. Validate:                                                       │   │
                    │  │     - patientUsername exists                                        │   │
                    │  │     - Doctor has signature saved (signatureImageBase64)             │   │
                    │  │     - Doctor has consulted this patient (Consultation table check)  │   │
                    │  │     - At least one medicine or sick note provided                   │   │
                    │  │  3. Clean medicine/sick note data                                   │   │
                    │  │  4. Generate prescription number: e.g. "DT-2026-000001"             │   │
                    │  │  5. Cryptographically sign prescription using Ed25519:              │   │
                    │  │     ┌──────────────────────────────────────────────────────────┐   │   │
                    │  │     │  sign_prescription(number, doctor_id, patient, meds,     │   │   │
                    │  │     │    sick_note, issued_at) → {content_hash, signature_b64,│   │   │
                    │  │     │    signing_key_id}                                      │   │   │
                    │  │     └──────────────────────────────────────────────────────────┘   │   │
                    │  │  6. DB: Insert Prescription record with:                           │   │
                    │  │     - id, prescriptionNumber, doctorId, patientUsername            │   │
                    │  │     - medicines (JSON), sickNote (JSON), doctorNotes               │   │
                    │  │     - contentHash, signature (b64), signingKeyId, qrToken          │   │
                    │  │     - status: "ACTIVE", issuedAt                                   │   │
                    │  │  7. Generate PDF via render_prescription_pdf():                    │   │
                    │  │     ┌──────────────────────────────────────────────────────────┐   │   │
                    │  │     │  • Security border (double-rule)                         │   │   │
                    │  │     │  • Letterhead (doctor + hospital identity)               │   │   │
                    │  │     │  • Rx symbol + medicines table                           │   │   │
                    │  │     │  • Doctor's signature image                              │   │   │
                    │  │     │  • QR code → /verify?token=<qrToken>                    │   │   │
                    │  │     │  • Content hash fingerprint (human-readable)             │   │   │
                    │  │     └──────────────────────────────────────────────────────────┘   │   │
                    │  │  8. Store PDF as MedicalAsset via AssetService:                    │   │   │
                    │  │     - create_generated_asset(patient, filename, bytes)             │   │   │
                    │  │     - process_asset_background (OCR, embedding)                    │   │   │
                    │  │  9. DB: Update Prescription with pdfAssetId, pdfFileName           │   │   │
                    │  │  10. Return serialized prescription + verification data           │   │   │
                    │  └──────────────────────────────────────────────────────────────────────┘   │
                    │                                                                              │
                    │  ┌──────────────────────────────────────────────────────────────────────┐   │
                    │  │  GET /api/prescriptions/verify/{qr_token}  (prescriptions.py)         │   │
                    │  │  └─ PrescriptionService.verify_by_qr_token(qr_token)                  │   │
                    │  │     ├─ DB: Find Prescription by qrToken                               │   │
                    │  │     ├─ verify_prescription(content_hash, signature, public_key)       │   │
                    │  │     │    └─ Ed25519 signature verification                            │   │
                    │  │     └─ Return: {found, valid_signature, status,                       │   │
                    │  │                 prescription_number, doctor_name,                     │   │
                    │  │                 patient_name_masked, issued_at,                      │   │
                    │  │                 medicines_count, revoked, revoked_reason}             │   │
                    │  └──────────────────────────────────────────────────────────────────────┘   │
                    │                                                                              │
                    │  ┌──────────────────────────────────────────────────────────────────────┐   │
                    │  │  Other Endpoints:                                                    │   │
                    │  │                                                                      │   │
                    │  │  GET  /api/prescriptions/mine  (Patient lists own prescriptions)     │   │
                    │  │  GET  /api/prescriptions/issued?patient_username=  (Doctor lists)    │   │
                    │  │  GET  /api/prescriptions/{id}  (View single prescription)            │   │
                    │  │  GET  /api/prescriptions/{id}/pdf  (Download PDF)                    │   │
                    │  │  POST /api/prescriptions/{id}/revoke  (Doctor revokes)               │   │
                    │  │  POST /api/prescriptions/{id}/supersede  (Doctor re-issues)          │   │
                    │  │                                                                      │   │
                    │  │  GET  /api/prescriptions/public-key  (Get Ed25519 public key)        │   │
                    │  │  POST /api/prescriptions/signature  (Doctor saves signature image)   │   │
                    │  │  GET  /api/prescriptions/signature/status  (Check signature exists)  │   │
                    │  └──────────────────────────────────────────────────────────────────────┘   │
                    │                                                                              │
                    │  ┌──────────────────────────────────────────────────────────────────────┐   │
                    │  │  Database:                                                            │   │
                    │  │  ┌───────────────────────────────────────────────────────────────┐   │   │
                    │  │  │  Prescription: id, prescriptionNumber, doctorId,               │   │   │
                    │  │  │                patientUsername, consultationId,                 │   │   │
                    │  │  │                medicines (Json), sickNote (Json),              │   │   │
                    │  │  │                doctorNotes, status (ACTIVE/REVOKED/SUPERSEDED), │   │   │
                    │  │  │                contentHash, signature, signingKeyId,            │   │   │
                    │  │  │                qrToken, pdfAssetId, pdfFileName,               │   │   │
                    │  │  │                supersedesId, supersededById,                   │   │   │
                    │  │  │                issuedAt, revokedAt, revokedReason               │   │   │
                    │  │  ├───────────────────────────────────────────────────────────────┤   │   │
                    │  │  │  MedicalAsset: (stores PDF bytes + embedding for RAG)         │   │   │
                    │  │  ├───────────────────────────────────────────────────────────────┤   │   │
                    │  │  │  Doctor: signatureImageBase64, signatureUpdatedAt              │   │   │
                    │  │  └───────────────────────────────────────────────────────────────┘   │   │
                    │  └──────────────────────────────────────────────────────────────────────┘   │
                    └──────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Steps (Prescription Issuance):

| Step | From | To | Data | Protocol |
|------|------|----|------|----------|
| 1 | DoctorDashboard.jsx | `/api/prescriptions` | `POST {patientUsername, medicines:[...], sickNote?, consultationId?, doctorNotes?}` + JWT | HTTP/REST |
| 2 | `prescriptions.py` | `PrescriptionService.issue()` | `doctor_id, data` | Internal |
| 3 | `PrescriptionService` | `Consultation` table | `SELECT WHERE doctorId=? AND patientUsername=?` (must exist) | Prisma ORM |
| 4 | `PrescriptionService` | `Doctor` table | `SELECT signatureImageBase64` (must exist) | Prisma ORM |
| 5 | `PrescriptionService` | `sign_prescription()` | `prescription_number, doctor_id, patient, medicines, issued_at` | Internal (Ed25519) |
| 6 | `sign_prescription()` | `PrescriptionService` | `{content_hash, signature_b64, signing_key_id}` | Internal |
| 7 | `PrescriptionService` | `Prescription` table | `INSERT INTO Prescription (...)` | Prisma ORM |
| 8 | `PrescriptionService` | `render_prescription_pdf()` | Serialized prescription + doctor + patient data | Internal |
| 9 | `render_prescription_pdf()` | QR code + PDF bytes | ReportLab renders A4 PDF with QR, signature, security border | Internal |
| 10 | `PrescriptionService` | `AssetService.create_generated_asset()` | `patient_username, filename="DT-2026-000001.pdf", source_bytes` | Internal |
| 11 | `AssetService` | Supabase Storage (or local) | Store PDF file | File System |
| 12 | `AssetService` | `MedicalAsset` table | `INSERT INTO MedicalAsset (patientUsername, file_name, ...)` | Prisma ORM |
| 13 | `PrescriptionService` | `Prescription` table | `UPDATE SET pdfAssetId=?, pdfFileName=? WHERE id=?` | Prisma ORM |
| 14 | DB → `prescriptions.py` → DoctorDashboard.jsx | `{id, prescriptionNumber, status:"ACTIVE", ...}` | HTTP/REST |
| 15 | Public (QR scanner) → PublicVerify.jsx | `GET /api/prescriptions/verify/{qrToken}` | No auth required | HTTP/REST |
| 16 | `PrescriptionService.verify_by_qr_token()` | `Prescription` table | `SELECT WHERE qrToken=?` | Prisma ORM |
| 17 | `PrescriptionService` | `verify_prescription()` | `content_hash, signature, public_key` | Internal (Ed25519 verify) |
| 18 | DB → `prescriptions.py` → PublicVerify.jsx | `{found:true, valid_signature:true, status:"ACTIVE", doctor_name, ...}` | HTTP/REST |

### 5a. Patient-Side Prescription Analysis with Medicine Price Lookup

When a patient views an issued prescription, they can analyze each medicine to see its **purpose, price, platform, and product link**. The system uses Google Gemini with web search grounding to fetch real-time pricing from online pharmacies.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (PatientPrescriptionsList.jsx)                                                  │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │  1. Patient navigates to "My Prescriptions" page                                  │   │
│  │     ├─ useEffect on mount → prescriptionApi.listMine()                           │   │
│  │     └─ Displays list of prescriptions with status badges                          │   │
│  │                                                                                    │   │
│  │  2. Patient clicks on a prescription to expand it                                 │   │
│  │     ├─ Shows medicines table: Name, Dosage, Frequency, Duration                   │   │
│  │     ├─ Auto-fetches price data on mount for ALL prescriptions in background       │   │
│  │     │  (via useEffect on prescriptions[] → medicinePriceApi.lookupPrices)         │   │
│  │     └─ Alternatively clicks "Show medicine prices" button per prescription        │   │
│  │                                                                                    │   │
│  │  3. For each medicine, displays enriched columns:                                 │   │
│  │     ┌────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐        │   │
│  │     │ Medicine   │ Dosage   │ Purpose  │ Price    │ Platform │ Link     │        │   │
│  │     ├────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤        │   │
│  │     │ Paracetamol│ 500mg    │ Fever    │ ₹30.50   │ 1mg      │ 🔗       │        │   │
│  │     │ Amoxicillin│ 250mg    │ Infection│ ₹120.00  │ Apollo   │ 🔗       │        │   │
│  │     └────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘        │   │
│  │                                                                                    │   │
│  │  4. Price columns display:                                                        │   │
│  │     - purpose: Medical use description from web search                            │   │
│  │     - price: Current INR price (₹XXX)                                             │   │
│  │     - platform_name: Online pharmacy name (1mg, Apollo, Netmeds, PharmEasy)       │   │
│  │     - source_url: Clickable link to product page (opens in new tab)               │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  API Call:                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │  medicinePriceApi.lookupPrices(["Paracetamol", "Amoxicillin", ...])               │   │
│  │  └─ POST /api/medicine-prices  { medicines: [...] }  + JWT                       │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  Vite Proxy: /api → http://127.0.0.1:8000                                               │
└──────────────────────────────────────────────────────────┬───────────────────────────────┘
                                                           │
                    ┌──────────────────────────────────────┼──────────────────────────────────────┐
                    │  BACKEND                             │                                      │
                    │                                      ▼                                      │
                    │  ┌──────────────────────────────────────────────────────────────────────┐   │
                    │  │  POST /api/medicine-prices  (medicine_prices.py)                     │   │
                    │  │                                                                      │   │
                    │  │  1. Authenticate patient via JWT                                     │   │
                    │  │  2. Validate: medicines array (max 20, non-empty)                    │   │
                    │  │  3. Call search_medicine_prices(medicine_names)                      │   │
                    │  │     ┌────────────────────────────────────────────────────────────┐   │   │
                    │  │     │  MedicinePriceService — Gemini Web Search Flow:             │   │   │
                    │  │     │                                                             │   │   │
                    │  │     │  a. Create Gemini client with GEMINI_API_KEY                │   │   │
                    │  │     │  b. Build prompt asking for:                                │   │   │
                    │  │     │     • medicine_name — exact name                            │   │   │
                    │  │     │     • purpose — what it's used for (1-2 sentences)          │   │   │
                    │  │     │     • price — current INR price (₹XXX)                     │   │   │
                    │  │     │     • platform_name — online pharmacy name                  │   │   │
                    │  │     │     • source_url — product page URL                         │   │   │
                    │  │     │  c. Call Gemini model with Google Search grounding:         │   │   │
                    │  │     │     tools=[GoogleSearch()] — enables web search             │   │   │
                    │  │     │  d. Extract grounding_chunks from response metadata         │   │   │
                    │  │     │     (contains URIs + titles from web results)               │   │   │
                    │  │     │  e. Parse JSON from Gemini response                        │   │   │
                    │  │     │  f. Validate results & enrich with source URLs              │   │   │
                    │  │     │     from grounding_chunks if missing                        │   │   │
                    │  │     │  g. Fallback: if JSON parse fails, return "Not found"       │   │   │
                    │  │     │     for each medicine with first grounding URI              │   │   │
                    │  │     └────────────────────────────────────────────────────────────┘   │   │
                    │  │  4. Return validated results array                                   │   │   │
                    │  └──────────────────────────────────────────────────────────────────────┘   │
                    │                                                                              │
                    │  ┌──────────────────────────────────────────────────────────────────────┐   │
                    │  │  External API:                                                        │   │
                    │  │                                                                      │   │
                    │  │  ┌──────────────────────────────────────────────────────────────┐   │   │
                    │  │  │  Google Gemini API (with Google Search grounding)             │   │   │
                    │  │  │                                                               │   │   │
                    │  │  │  Model: gemini-2.5-flash (or configured GEMINI_MODEL)          │   │   │
                    │  │  │  Tool: GoogleSearch() — enables real-time web search           │   │   │
                    │  │  │                                                               │   │   │
                    │  │  │  Returns: structured JSON + grounding_metadata                 │   │   │
                    │  │  │  {                                                             │   │   │
                    │  │  │    "results": [{                                               │   │   │
                    │  │  │      "medicine_name": "Paracetamol",                          │   │   │
                    │  │  │      "purpose": "Used to treat fever and mild to moderate pain",│   │   │
                    │  │  │      "price": "₹30.50",                                       │   │   │
                    │  │  │      "platform_name": "Tata 1mg",                             │   │   │
                    │  │  │      "source_url": "https://www.1mg.com/..."                  │   │   │
                    │  │  │    }]                                                          │   │   │
                    │  │  │  }                                                             │   │   │
                    │  │  └──────────────────────────────────────────────────────────────┘   │   │
                    │  └──────────────────────────────────────────────────────────────────────┘   │
                    │                                                                              │
                    │  ┌──────────────────────────────────────────────────────────────────────┐   │
                    │  │  Database: (no DB writes — read-only operation)                      │   │
                    │  └──────────────────────────────────────────────────────────────────────┘   │
                    └──────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Steps (Prescription Analysis / Medicine Price Lookup):

| Step | From | To | Data | Protocol |
|------|------|----|------|----------|
| 1 | PatientPrescriptionsList.jsx | `prescriptionApi.listMine()` | `GET /api/prescriptions/mine` + JWT | HTTP/REST |
| 2 | Patient clicks "Show medicine prices" | `medicinePriceApi.lookupPrices()` | `POST /api/medicine-prices {medicines: ["Paracetamol", "Amoxicillin"]}` + JWT | HTTP/REST |
| 3 | `medicine_prices.py` | `search_medicine_prices()` | `["Paracetamol", "Amoxicillin"]` | Internal |
| 4 | `search_medicine_prices()` | Gemini API (Google GenAI SDK) | Prompt + medicine list + `tools=[GoogleSearch()]` | HTTP/REST (async thread) |
| 5 | Gemini API | Web search | Google Search grounding fetches real-time pricing from online pharmacies | External (Google) |
| 6 | Gemini API → `search_medicine_prices()` | `{results: [{medicine_name, purpose, price, platform_name, source_url}], grounding_chunks}` | Internal |
| 7 | `search_medicine_prices()` | JSON parser + validator | Validate results, enrich missing source_urls from grounding_chunks | Internal |
| 8 | `search_medicine_prices()` → `medicine_prices.py` | `[{medicine_name, purpose, price, platform_name, source_url}]` | Internal |
| 9 | Backend → PatientPrescriptionsList.jsx | `{results: [{medicine_name:"Paracetamol", purpose:"Fever reliever", price:"₹30.50", platform_name:"Tata 1mg", source_url:"https://..."}]}` | HTTP/REST |
| 10 | PatientPrescriptionsList.jsx renders enriched table | For each medicine: name (from prescription), dosage, purpose, price, platform (as clickable link), duration | UI Render |

---

## 6. Medical Document Upload & Analysis

A patient uploads a medical document (PDF, X-ray image, report). The file is stored, text is extracted, and optionally analyzed by AI vision.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (PatientDashboard.jsx — "documents" or "explain" panel)                        │
│                                                                                          │
│  ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────────────┐  │
│  │ 1. User selects file │   │ 2. Upload via         │   │ 3. File appears in asset    │  │
│  │    (PDF/Image)       │──▶│    patientApi         │──▶│    list with folder          │  │
│  │                      │   │    .uploadAsset(file)  │   │    organization              │  │
│  └──────────────────────┘   └──────────┬───────────┘   └──────────────────────────────┘  │
│                                        │                                                 │
│  Vite Proxy: /api → http://127.0.0.1:8000                                                │
└────────────────────────────────────────┼─────────────────────────────────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────────────────────────────────────┐
                    │  BACKEND           │                                                    │
                    │                    ▼                                                    │
                    │  ┌──────────────────────────────────────────────────────────────────┐   │
                    │  │  POST /api/assets/upload  (medical_assets.py)                    │   │
                    │  │                                                                  │   │
                    │  │  1. Authenticate user (patient)                                  │   │
                    │  │  2. Validate file type & size                                   │   │
                    │  │  3. Store file in Supabase Storage (or local filesystem)         │   │
                    │  │  4. Create MedicalAsset record in DB                             │   │
                    │  │  5. Extract text:                                               │   │
                    │  │     ┌──────────────────────────────────────────────────────┐   │   │
                    │  │     │ • PDF → PyMuPDF (fitz) for text extraction           │   │   │
                    │  │     │ • Images → Tesseract OCR for text extraction         │   │   │
                    │  │     │ • Store extracted_text in MedicalAsset record        │   │   │
                    │  │     └──────────────────────────────────────────────────────┘   │   │
                    │  │  6. Generate embedding via Gemini Embedding API               │   │   │
                    │  │  7. Store embedding in pgvector column for RAG search         │   │   │
                    │  │  8. Return asset metadata to client                          │   │   │
                    │  └──────────────────────────────────────────────────────────────────┘   │
                    │                                                                          │
                    │  ┌──────────────────────────────────────────────────────────────────┐   │
                    │  │  POST /api/images/analyze  (image_analysis.py)                    │   │
                    │  │  (For X-ray / medical image AI analysis)                          │   │
                    │  │                                                                  │   │
                    │  │  1. Receive image (file or base64)                               │   │
                    │  │  2. Send to Gemini Vision API (or Imagga)                        │   │
                    │  │  3. Parse structured findings:                                   │   │
                    │  │     ┌──────────────────────────────────────────────────────┐   │   │
                    │  │     │ • Findings / observations                            │   │   │
                    │  │     │ • Clinical impression                               │   │   │
                    │  │     │ • Follow-up recommendations                         │   │   │
                    │  │     └──────────────────────────────────────────────────────┘   │   │
                    │  │  4. Return analysis result to client                         │   │   │
                    │  └──────────────────────────────────────────────────────────────────┘   │
                    │                                                                          │
                    │  ┌──────────────────────────────────────────────────────────────────┐   │
                    │  │  Database:                                                        │   │
                    │  │  MedicalAsset: id, patientUsername, file_name, file_type,         │   │
                    │  │               folder_path, file_size, extracted_text,             │   │
                    │  │               embedding (vector), storage_path, created_at        │   │
                    │  └──────────────────────────────────────────────────────────────────┘   │
                    └──────────────────────────────────────────────────────────────────────────┘
```

---

## 7. AI-Automated Payment Processing

The patient initiates a payment conversationally through the AI Assistant. The AI's LangGraph state machine classifies the intent as `PAYMENT_QUERY`, generates a `PAYMENT_PROCESS` task, and executes the entire payment lifecycle securely.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (PatientDashboard.jsx / AI Chat)                                          │
│                                                                                     │
│  ┌─────────────────────┐   ┌──────────────────────┐   ┌─────────────────────────┐   │
│  │ User types:         │   │ AI processes via     │   │ AI confirms payment     │   │
│  │ "Pay for my last    │──▶│ WebSocket and routes │──▶│ securely and returns    │   │
│  │ consultation"       │   │ to Payment Handler   │   │ transaction details     │   │
│  └─────────────────────┘   └──────────────────────┘   └─────────────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────┼──────────────────────────────────────────────┐
│  BACKEND (FastAPI / LangGraph)       ▼                                              │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Planner Node: Intent parsed as `is_payment`. Builds `PAYMENT_PROCESS` task. │   │
│  │ 2. Task Executor: Calls `handle_payment_process()` in Action Registry.         │   │
│  │    ├─ Looks up target Consultation / Appointment.                              │   │
│  │    ├─ Computes payment amount and verifies no prior payment.                   │   │
│  │    ├─ Interfaces with Razorpay API (or internal ledger) to execute payment.    │   │
│  │    └─ Updates `payment_context` inside WorkflowState.                          │   │
│  │ 3. Response Composer: Formats `{"status": "success", "amount": 500, ...}`      │   │
│  │ 4. LLM Node: Generates conversational confirmation for the user.               │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

| Step | From | To | Data | Protocol |
|------|------|----|------|----------|
| 1 | PatientDashboard.jsx | `/api/chat/ai/patient/ws` | `{"message": "pay for appointment"}` | WebSocket |
| 2 | `unified_chat_graph` | Planner Node | Strategy: `PAYMENT_QUERY` | Internal |
| 3 | Planner Node | Task Executor | Task: `PAYMENT_PROCESS` | Internal |
| 4 | Task Executor | Razorpay Gateway | Create payment transaction | REST/SDK |
| 5 | Task Executor | `Appointment` / DB | Update payment status to paid | Prisma ORM |
| 6 | Task Executor | LLM Orchestrator | `payment_context` payload | Internal |
| 7 | LLM Orchestrator | PatientDashboard.jsx | Streaming confirmation response | WebSocket |

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React 19 + Vite)                              │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  SessionContext (JWT Auth)                                                    │   │
│  │  ├─ Stores token in localStorage                                             │   │
│  │  ├─ Validates via GET /api/me on page load                                   │   │
│  │  └─ Provides user object to all child components                             │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  API Layer (lib/api.js + lib/apiClient.js)                                   │   │
│  │  ├─ REST calls via fetch with JWT Bearer token                               │   │
│  │  ├─ WebSocket connections via lib/realTimeClient.js                          │   │
│  │  └─ Automatic token injection & retry logic                                  │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  Pages & Components                                                          │   │
│  │  ├─ PatientDashboard.jsx  → AI Chat, Appointments, Documents, X-ray         │   │
│  │  ├─ DoctorDashboard.jsx   → Copilot, Slots, Consultations, Prescriptions    │   │
│  │  ├─ AdminDashboard.jsx    → User management, Invites, Stats                 │   │
│  │  └─ HospitalDashboard.jsx → Reports, News, Disease tracking                 │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────────────┘
                                       │
              Vite Proxy (dev) or Nginx (prod) — /api → backend:8000
                                       │
┌──────────────────────────────────────┼──────────────────────────────────────────────┐
│                              BACKEND (FastAPI + Uvicorn)                             │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  API Routers (backend/api/)                                                   │   │
│  │  ├─ auth.py          → Login, Signup, Profile, /api/me                       │   │
│  │  ├─ appointments.py  → Slots, Booking, Doctor actions                        │   │
│  │  ├─ chat/router.py   → Consultations, AI WebSocket, Messages                 │   │
│  │  ├─ medical_assets.py→ Upload, Download, Delete, Rename                      │   │
│  │  ├─ image_analysis.py→ Vision AI (Gemini/Imagga)                             │   │
│  │  ├─ prescriptions.py → Issue, List, Verify (digital signing)                 │   │
│  │  ├─ hospital.py      → Reports, News, Disease surveillance                   │   │
│  │  └─ admin.py         → Invites, User management, Stats                       │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  Service Layer (backend/services/)                                            │   │
│  │  ├─ auth_service.py         → Password hashing, JWT creation                 │   │
│  │  ├─ appointment_service.py  → Slot management, booking logic                 │   │
│  │  ├─ chat_service.py         → Messages, AI sessions, history                 │   │
│  │  ├─ asset_service.py        → File storage, metadata management              │   │
│  │  └─ ... (prescription, hospital, xray, etc.)                                 │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  LangGraph Workflow Engine (backend/workflows/)                               │   │
│  │                                                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ Input        │→│ Log Entry    │→│ Planner      │→│ Authorization    │  │   │
│  │  │ Guardrail    │  │ Context      │  │ Node         │  │ Node             │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘  │   │
│  │       │                                                                       │   │
│  │       ▼                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │  Task Executor (Shadow Pipeline — loops up to 3×)                       │ │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐            │ │   │
│  │  │  │ RAG Vector   │  │ DB Query     │  │ Action              │            │ │   │
│  │  │  │ Search       │  │ (Slots, Appt,│  │ (Book, Cancel,      │            │ │   │
│  │  │  │ (pgvector)   │  │  Patients)   │  │  Process Payment)   │            │ │   │
│  │  │  └──────────────┘  └──────────────┘  └─────────────────────┘            │ │   │
│  │  └──────────────────────────────────────────────────────────────────────┘    │   │
│  │       │                                                                       │   │
│  │       ▼                                                                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐  │   │
│  │  │ Recommendation│→│ Response     │→│ LLM Orchestrator │→│ Output       │  │   │
│  │  │ Engine        │  │ Composer     │  │ (Routes to      │  │ Guardrail    │  │   │
│  │  │               │  │              │  │  correct LLM)   │  │ (Medical     │  │   │
│  │  │               │  │              │  │                  │  │  Safety)     │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘  └──────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  AI Services (backend/ai/)                                                    │   │
│  │  ├─ core_services/llm_client.py  → OpenAI-compatible API calls               │   │
│  │  ├─ core_services/ocr.py        → Tesseract OCR for images                   │   │
│  │  ├─ vectorstore/                → pgvector integration for RAG               │   │
│  │  └─ prompts/                    → System prompts for each LLM node           │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  Core (backend/core/)                                                         │   │
│  │  ├─ config.py    → Pydantic BaseSettings from .env                           │   │
│  │  ├─ database.py  → Prisma client lifecycle (singleton)                       │   │
│  │  ├─ security.py  → JWT encode/decode, password hashing, auth dependencies    │   │
│  │  └─ crypto_utils.py → File encryption/decryption                             │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────────────┘
                                       │
              Prisma ORM (async) — auto-generated client
                                       │
┌──────────────────────────────────────┼──────────────────────────────────────────────┐
│                           DATABASE (Supabase PostgreSQL + pgvector)                  │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  Core Tables:                                                                 │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ Patient      │  │ Doctor       │  │ Admin        │  │ Hospital         │  │   │
│  │  │ (username,   │  │ (doctorId,   │  │ (adminId,    │  │ (hospitalId,     │  │   │
│  │  │  name, hash, │  │  name, hash, │  │  name, hash, │  │  name, location) │  │   │
│  │  │  profile)    │  │  specializ.) │  │  role)       │  │                  │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘  │   │
│  │                                                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ DoctorSlot   │  │ Appointment  │  │ Consultation │  │ Message          │  │   │
│  │  │ (doctorId,   │  │ (patient,    │  │ (apptId,     │  │ (consultationId, │  │   │
│  │  │  startTime,  │  │  doctor,     │  │  patient,    │  │  senderId,       │  │   │
│  │  │  endTime,    │  │  slot,       │  │  doctor)     │  │  message,        │  │   │
│  │  │  isBooked)   │  │  status)     │  │              │  │  timestamp)      │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘  │   │
│  │                                                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐   │   │
│  │  │ MedicalAsset │  │ AiChatSession│  │ AiChatMessage                    │   │   │
│  │  │ (patient,    │  │ (userId,     │  │ (sessionId, role, content,       │   │   │
│  │  │  file,       │  │  role, mode, │  │  createdAt)                      │   │   │
│  │  │  embedding)  │  │  targetPt)   │  │                                  │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────────┘   │   │
│  │                                                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐   │   │
│  │  │ Prescription │  │ HospitalReport│ │ HospitalNews                    │   │   │
│  │  │ (patient,    │  │ (hospital,    │  │ (hospital, title, content,      │   │   │
│  │  │  doctor,     │  │  disease,     │  │  priority, publishedAt)         │   │   │
│  │  │  medicines)  │  │  severity)    │  │                                  │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  pgvector Extension:                                                          │   │
│  │  ┌──────────────────────────────────────────────────────────────────────┐   │   │
│  │  │  MedicalAsset.embedding → VECTOR(768) for RAG similarity search      │   │   │
│  │  │  Query: SELECT * FROM "MedicalAsset"                                 │   │   │
│  │  │         WHERE "patientUsername" = $1                                 │   │   │
│  │  │         ORDER BY embedding <=> $2::vector LIMIT 5                    │   │   │
│  │  └──────────────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Legend

| Symbol | Meaning |
|--------|---------|
| `──▶` | Data flow direction |
| `┌──┐` | Component / Module |
| `WebSocket` | Real-time bidirectional communication |
| `HTTP/REST` | Request-response API call |
| `Prisma ORM` | Database query via Prisma client |
| `Internal` | In-process function call |
| `pgvector` | Vector similarity search |

---

*Generated from codebase analysis — DocTalk project structure and data flow documentation.*