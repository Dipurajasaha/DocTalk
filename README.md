<p align="center">
  <h1 align="center">🩺 DocTalk</h1>
  <p align="center">
    <strong>An AI-powered digital healthcare platform connecting patients and doctors through intelligent diagnostics, real-time consultations, and seamless appointment management.</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/FastAPI-0.118-009688?style=flat-square&logo=fastapi" alt="FastAPI" />
    <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react" alt="React" />
    <img src="https://img.shields.io/badge/LangGraph-1.1-4B0082?style=flat-square" alt="LangGraph" />
    <img src="https://img.shields.io/badge/PostgreSQL-Supabase-3ECF8E?style=flat-square&logo=supabase" alt="Supabase" />
    <img src="https://img.shields.io/badge/Prisma-0.15-2D3748?style=flat-square&logo=prisma" alt="Prisma" />
    <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python" />
  </p>
</p>

---

## What is DocTalk?

DocTalk is a full-stack healthcare application that replaces fragmented clinic workflows with a single unified platform. Patients can book appointments, upload medical documents for AI analysis, chat with an intelligent health assistant, and communicate with their doctors in real-time. Doctors get a clinical reasoning copilot, patient-scoped record retrieval, and a complete slot-based scheduling system.

Under the hood, DocTalk orchestrates AI workflows using **LangGraph** state machines that combine triage evaluation, retrieval-augmented generation (RAG) over patient medical records, and a multi-step shadow execution pipeline — all behind a streaming WebSocket interface that feels instant.

---

## ✨ Core Capabilities

### For Patients
- **Intelligent AI Health Assistant** — Ask health questions in natural language. The system triages for emergencies, retrieves your medical history and uploaded documents via RAG, and responds with contextualized, evidence-backed answers.
- **Appointment Booking** — Browse doctor availability, select an open slot, and confirm — or let the AI assistant book for you conversationally ("Book me the first available slot with Dr. Sharma").
- **AI-Automated Payments** — The AI workflow can now handle the full payment lifecycle conversationally. Ask the assistant to process, verify, or review a consultation payment and the workflow executes it end-to-end without leaving the chat.
- **Medical Document Vault** — Upload reports, prescriptions, and X-rays. Files are stored securely with optional encryption. Text is extracted automatically (OCR for images, PDF parsing for documents) and indexed for AI retrieval.
- **AI Image & X-ray Analysis** — Upload a medical image for AI-powered analysis via Gemini Vision. Receive structured findings, clinical impressions, and follow-up recommendations.

### For Doctors
- **Clinical Reasoning Copilot** — An AI assistant with a medical-specialist persona that uses clinical terminology, differential reasoning, and red-flag assessment to support decision-making.
- **Patient-Scoped RAG** — When viewing a specific patient, the copilot retrieves and reasons over that patient's full document and record history — reports, consultations, and medical timeline.
- **Slot-Based Scheduling** — Create availability windows, accept or reject incoming appointment requests, and manage your calendar.
- **Digital Prescriptions & QR Verification** — Compose structured prescriptions, attach a digital signature, and generate verifiable public QR codes for pharmacies to validate authenticity.
- **Real-Time Consultation Chat** — WebSocket-powered messaging with patients during active consultations.

### Platform-Wide
- **Neumorphic & 3D User Interface** — A premium, modern UI featuring a custom Neumorphic design system, GSAP micro-animations, and interactive 3D elements powered by ThreeJS and React Three Fiber.
- **Medical Safety Guardrail** — A terminal AI node that scans every response for diagnostic overreach (e.g., "you have..." / "I diagnose...") and replaces it with a professional disclaimer. Zero hallucinated diagnoses reach the user.
- **Role-Based Access Control** — JWT-authenticated sessions with strict route guards. Patients only see patient features; doctors only see doctor features. Every API endpoint and React route enforces this.
- **Streaming AI Responses** — WebSocket connections stream tokens in real-time with node-level status updates, so users see the AI "thinking" through each stage.

---

## 🏛️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  FRONTEND — React 19 + Vite 8                                    │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │  SessionContext │  │  PatientDashboard│  │  DoctorDashboard │ │
│  │  (JWT + Auth)   │  │  (Chat, Assets,  │  │  (Copilot, Slots,│ │
│  │                 │  │   Appointments)  │  │   Consultations) │ │
│  └────────┬───────┘  └────────┬─────────┘  └────────┬─────────┘ │
│           └───────────────────┼──────────────────────┘           │
│                               │ REST + WebSocket                 │
│            Vite Proxy  /api → │ http://127.0.0.1:8000            │
└───────────────────────────────┼──────────────────────────────────┘
                                │
┌───────────────────────────────┼──────────────────────────────────┐
│  BACKEND — FastAPI + Uvicorn                                     │
│  ┌────────────┐  ┌──────────────────┐  ┌──────────────────────┐ │
│  │  Auth API   │  │  Appointments API│  │  Chat & AI API       │ │
│  │  /api/auth  │  │  /api/appointments│ │  /api/chat           │ │
│  └──────┬─────┘  └────────┬─────────┘  └────────┬─────────────┘ │
│         │                  │                      │               │
│  ┌──────┴──────────────────┴──────────────────────┴────────────┐ │
│  │                    Service Layer                             │ │
│  │  AuthService · AppointmentService · ChatService · AssetSvc  │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                              │                                    │
│  ┌───────────────────────────┴──────────────────────────────────┐│
│  │              LangGraph Workflow Engine                        ││
│  │  ┌─────────┐  ┌───────────┐  ┌─────────────┐  ┌──────────┐ ││
│  │  │ Planner │→ │ Executor  │→ │  Composer    │→ │ LLM Node │ ││
│  │  │  Node   │  │  (Shadow  │  │  (Response   │  │ + Safety │ ││
│  │  │         │  │  Pipeline)│  │   Builder)   │  │ Guardrail│ ││
│  │  └─────────┘  └───────────┘  └─────────────┘  └──────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                    │
│  ┌───────────────────────────┴──────────────────────────────────┐│
│  │  Prisma ORM (async) → Supabase PostgreSQL + pgvector         ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

### The AI Pipeline in Detail

When a user sends a message through the AI chat WebSocket, it passes through a **LangGraph StateGraph** with the following flow:

1. **Log Entry Context** → Records session metadata
2. **Shadow Pipeline** → An iterative data-gathering loop:
   - *Planner Node* classifies intent (appointments? medical records? doctor availability? **payments?**) and builds an execution plan
   - *Task Executor* runs retrieval tasks (database queries, RAG vector search, slot lookups) and action tasks (booking, cancelling, **processing payments**)
   - *Need-Action Decision* checks if more data is needed (loops up to 3×)
   - *Response Composer* assembles all gathered evidence into structured sections
3. **Role-Based Routing** → Routes to the appropriate LLM node:
   - Patients → Triage Evaluator → Emergency path or General/RAG Assistant
   - Doctors → General Copilot or Patient-Scoped RAG Copilot
4. **Medical Safety Guardrail** → Final check before delivery to the user

---

## 🧰 Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Vite 8, React Router 7, Radix UI, Recharts, react-markdown |
| **UI & Animations** | Custom Neumorphism, TailwindCSS, ThreeJS (`@react-three/fiber`), GSAP |
| **Backend** | Python 3.11+, FastAPI 0.118, Uvicorn, Pydantic v2 |
| **Database** | PostgreSQL (Supabase), Prisma ORM (async Python client), pgvector |
| **AI / LLM** | LangChain 1.2, LangGraph 1.1, OpenAI-compatible API, Google Gemini (vision + embeddings) |
| **Auth** | JWT (PyJWT), PBKDF2-SHA256 password hashing, bcrypt (legacy support) |
| **Integrations** | Razorpay (payments API) |
| **File Processing** | PyMuPDF (PDF), Tesseract OCR (images), Pillow, qrcode |
| **Security** | cryptography (file encryption), role-based route guards |

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.11+** | Must be on `PATH` |
| **Node.js 18+** | For the React frontend |
| **Supabase project** | Free tier works — you need `DATABASE_URL` and Supabase keys |
| **AI API keys** | At least one of: OpenAI-compatible endpoint, Gemini API key |
| **Tesseract OCR** *(optional)* | Required for image-based document OCR |

### 1. Clone & Configure

```bash
git clone https://github.com/Dipurajasaha/DocTalk.git
cd DocTalk
```

Create a `.env` file in the project root:

```env
# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://...?pgbouncer=true
DIRECT_URL=postgresql://...

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Auth
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Admin security
ADMIN_ID=first-admin
ADMIN_NAME=Platform Owner
ADMIN_PASSWORD=choose-a-strong-password
ADMIN_EMAIL=admin@example.com

# LLM (any OpenAI-compatible endpoint)
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o              # or any compatible model
OPENAI_BASE_URL=https://api.openai.com/v1

# Gemini (for embeddings + vision)
GEMINI_API_KEY=your-gemini-key
GEMINI_EMBED_MODEL=gemini-embedding-001
VISION_ENDPOINT=gemini
```

### 2. One-Command Launch (Windows)

DocTalk ships with a single root `package.json` that delegates everything to [`start_dev.ps1`](./start_dev.ps1). Running the following from the **project root** is the only command you need:

```powershell
npm run dev
```

Under the hood, this executes:

```
powershell -NoProfile -ExecutionPolicy Bypass -File start_dev.ps1
```

[`start_dev.ps1`](./start_dev.ps1) performs all setup automatically on first run and skips steps that are already done:

| Step | What happens |
|---|---|
| **Python venv** | Creates `.venv/` if it doesn't exist |
| **Backend deps** | Runs `pip install -r backend/requirements.txt` only when `requirements.txt` is newer than the last install flag |
| **Frontend deps** | Runs `npm install` in `frontend/` only when `node_modules/` is missing |
| **Root deps** | Installs root `node_modules/` (for `concurrently`) if missing |
| **Prisma client** | Regenerates the Python Prisma client from `backend/prisma/schema.prisma` |
| **Backend server** | Starts `uvicorn backend.main:app --reload` on `http://127.0.0.1:8000` |
| **Frontend server** | Starts Vite dev server, typically on `http://localhost:5173` |

Both servers run concurrently in the same terminal window (via `npx concurrently`). Press **Ctrl+C** once to stop both.

> **Alternative**: You can also invoke the script directly:
> ```powershell
> .\start_dev.ps1
> ```
> Or, on Command Prompt:
> ```batch
> start_dev.bat
> ```

### Admin onboarding

Admin accounts are not self-registered anymore. The first admin must be created with the one-time bootstrap script:

```powershell
cd DocTalk
$env:ADMIN_ID='first-admin'
$env:ADMIN_NAME='Platform Owner'
$env:ADMIN_PASSWORD='choose-a-strong-password'
python -m backend.scripts.bootstrap_admin
```

After that, existing admins can create one-time invite tokens from the admin dashboard or the `/api/admin/invites` endpoint, and new admins must join through the invite acceptance flow.

### 3. Manual Setup (Cross-Platform)

If you're not on Windows or prefer manual control:

```bash
# Backend
python -m venv .venv
# source .venv/bin/activate          # Linux/macOS
.venv\Scripts\activate           # Windows
pip install -r backend/requirements.txt
python -m prisma generate --schema=backend/prisma/schema.prisma
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (in a separate terminal)
cd frontend
npm install
npm run dev
```

### 4. Database Setup

Run Prisma migrations against your Supabase database:

```bash
npx prisma migrate dev --schema=backend/prisma/schema.prisma
```

> **Note**: Ensure the `pgvector` extension is enabled in your Supabase project for RAG document search to work. You can enable it from the Supabase dashboard under **Database → Extensions**.

---

## 📁 Project Structure

```
DocTalk/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── core/                      # Settings, db client, security auth
│   ├── api/                       # REST API Routers
│   │   ├── auth.py, users.py      # Auth & Profile management
│   │   ├── appointments.py        # Scheduling & Bookings
│   │   ├── chat/                  # WebSocket & REST AI Chat
│   │   ├── payments.py            # Razorpay integration
│   │   ├── prescriptions.py       # Digital prescriptions & QR
│   │   └── hospital.py, stats.py  # Admin & hospital operations
│   ├── schemas/                   # Pydantic data models
│   ├── services/                  # Business logic layer
│   ├── workflows/                 # LangGraph Agent Engine
│   │   ├── auth/                  # Token & context verification
│   │   ├── capabilities/          # RAG, Booking, DB retrieval tasks
│   │   ├── composer/              # Response synthesis
│   │   ├── executor/              # Capability-based executor
│   │   ├── graph/                 # Main StateGraph definitions
│   │   ├── guardrails/            # Medical safety checks
│   │   ├── llm/                   # LLM node execution
│   │   ├── memory/                # Session and context memory
│   │   ├── models/                # Graph state TypedDicts
│   │   ├── planner/               # Intent classification node
│   │   ├── recommendation/        # Dynamic suggestions & next steps
│   │   └── utils/                 # Helper functions & formatters
│   ├── ai/                        # Embeddings, Vision, and LLM clients
│   ├── scripts/                   # Bootstrap scripts (admin creation)
│   ├── tests/                     # Integration and API tests
│   └── prisma/
│       └── schema.prisma          # Database schema (Prisma ORM)
├── challenges/                    # Interactive verification/test challenges
├── data/                          # DB initialization scripts and user uploads
├── frontend/
│   └── src/
│       ├── App.jsx                # React Router + role guards
│       ├── contexts/              # SessionContext, NotificationContext
│       ├── pages/                 # Dashboards, Home, Login, Composer, Verify
│       ├── components/            # Shared UI components (3D Canvas, Copilot)
│       └── styles/                # Custom Neumorphic CSS (patient, doctor, home)
├── .env.example                   # Example environment configuration template
├── appointment_rules.md           # Business rules for doctor appointments
├── DOCUMENTATION.md               # Detailed technical documentation
├── flowLogic.md                   # LangGraph state machine flow logic
├── start_dev.ps1                  # One-click dev launcher (PowerShell)
├── start_dev.bat                  # One-click dev launcher (CMD)
└── package.json                   # Root scripts & launch configurations (concurrently)
```

---

## 🔌 API Overview

The backend exposes a REST + WebSocket API at `http://127.0.0.1:8000`. Key endpoint groups:

| Prefix | Purpose | Examples |
|---|---|---|
| `/api/auth` | Authentication | `POST /patient/login`, `POST /doctor/signup`, `GET /api/me` |
| `/api/appointments` | Scheduling | `POST /slots`, `POST /book/direct`, `PUT /{id}/action` |
| `/api/chat` | Consultations & AI | `GET /consultations`, `WS /ai/patient/ws`, `WS /ai/doctor/ws` |
| `/api/prescriptions`| Digital Prescriptions | `POST /create`, `GET /{id}`, `GET /public/verify/{qr}` |
| `/api/payments` | Razorpay integration | `POST /create-order`, `POST /verify` |
| `/api/assets` | Medical documents | `POST /upload`, `GET /{id}/download`, `DELETE /{id}` |
| `/api/images` | Vision analysis | `POST /analyze`, `POST /analyze/base64` |
| `/health` | System | `GET /health`, `GET /health/db` |

All authenticated endpoints require a `Bearer` token in the `Authorization` header. WebSocket endpoints accept the token as a `?token=` query parameter.

> **Interactive docs** are available at `http://127.0.0.1:8000/docs` (Swagger UI) when the backend is running.

---

## 🔐 Authentication Flow

```
┌──────────┐     POST /api/auth/patient/login     ┌───────────┐
│  Client   │ ──────────────────────────────────→  │  FastAPI   │
│           │     {username, password}             │           │
│           │  ←──────────────────────────────────  │  verify_  │
│           │     {access_token, role, user_id}    │  password  │
│           │                                       │  + JWT     │
│           │     GET /api/me                       │           │
│           │  ──── Authorization: Bearer <token> → │  decode_  │
│           │  ←── {user_id, role, name, ...}       │  token    │
└──────────┘                                       └───────────┘
```

- **Passwords**: Hashed with PBKDF2-SHA256 (390k iterations, 16-byte salt). Legacy bcrypt hashes are auto-detected and supported.
- **Tokens**: JWT with HS256. Payload contains `sub`, `user_id`, `role`, `iat`, `exp`. Default expiry: 60 minutes.
- **Frontend**: `SessionContext` bootstraps on page load — reads token from `localStorage`, validates via `/api/me`, and hydrates the session object.

---

## 🤖 AI Configuration

DocTalk's AI is **provider-agnostic** by design. Text generation uses any OpenAI-compatible API, while embeddings and vision use Google Gemini.

| Purpose | Config Vars | Notes |
|---|---|---|
| **Chat / Reasoning** | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` | Any OpenAI-compatible endpoint works (OpenAI, Azure, local LLMs via LiteLLM/Ollama, etc.) |
| **Embeddings** | `GEMINI_API_KEY`, `GEMINI_EMBED_MODEL` | Powers RAG vector search via pgvector |
| **Vision / Image Analysis** | `VISION_ENDPOINT`, `GEMINI_API_KEY` | Set to `"gemini"` (default) or `"imagga"` for tag-based analysis |

### Switching LLM Providers

To use a different LLM (e.g., a local Ollama model):

```env
OPENAI_API_KEY=ollama
OPENAI_MODEL=llama3
OPENAI_BASE_URL=http://localhost:11434/v1
```

---

## 🧪 Health Checks

| Endpoint | Purpose |
|---|---|
| `GET /health` | Returns `{"status": "ok", "app": "DocTalk Backend", "version": "1.0.0"}` |
| `GET /health/db` | Pings PostgreSQL with `SELECT 1`, auto-reconnects on failure |

---

## 📄 License

This project is for educational and demonstration purposes.

---

<p align="center">
  <sub>Built with ❤️ for better healthcare through technology.</sub>
</p>
