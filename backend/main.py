from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from io import BytesIO

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.services.storage.file_service import storage_file_service as FileCryptoService
from app.crypto_utils import generate_rsa_key_pair, encrypt_private_key
from app.services.ai.chat_service import AIChatService
from app.services.medical.xray_service import format_xray_analysis_for_chat


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")
PATIENT_DATA_ROOT = os.path.join(DATA_ROOT, "patients")
DOCTOR_DATA_ROOT = os.path.join(DATA_ROOT, "doctors")
STATIC_ROOT = os.path.join(PROJECT_ROOT, "static")
UPLOAD_ROOT = os.path.join(DATA_ROOT, "uploads")
PATIENT_UPLOAD_ROOT = os.path.join(UPLOAD_ROOT, "patient")

os.makedirs(PATIENT_DATA_ROOT, exist_ok=True)
os.makedirs(DOCTOR_DATA_ROOT, exist_ok=True)
os.makedirs(PATIENT_UPLOAD_ROOT, exist_ok=True)


# ----------------- Persistence -----------------
def _write_json_atomic(path: str, data) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


def _load_json(path: str, default):
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return default
    return default


def _load_all():
    res = {"patient": {}, "doctor": {}, "file_keys": {}}
    # load persisted file keys mapping
    res["file_keys"] = _load_json(os.path.join(DATA_ROOT, "file_keys.json"), {})

    for uname in os.listdir(PATIENT_DATA_ROOT):
        udir = os.path.join(PATIENT_DATA_ROOT, uname)
        if not os.path.isdir(udir):
            continue
        pdata = {}
        pdata.update(_load_json(os.path.join(udir, "profile.json"), {}))
        pdata["chat_sessions"] = _load_json(os.path.join(udir, "chat_sessions.json"), [])
        pdata["appointments"] = _load_json(os.path.join(udir, "appointments.json"), [])
        pdata["reports"] = _load_json(os.path.join(udir, "reports.json"), [])
        pdata["medical_images"] = _load_json(os.path.join(udir, "medical_images.json"), [])
        res["patient"][uname] = pdata

    for did in os.listdir(DOCTOR_DATA_ROOT):
        ddir = os.path.join(DOCTOR_DATA_ROOT, did)
        if not os.path.isdir(ddir):
            continue
        ddata = {}
        ddata.update(_load_json(os.path.join(ddir, "doctor_profile.json"), {}))
        ddata["schedules"] = _load_json(os.path.join(ddir, "schedules.json"), [])
        ddata["appointment_requests"] = _load_json(os.path.join(ddir, "requests.json"), [])
        ddata["payments"] = _load_json(os.path.join(ddir, "payments.json"), [])
        ddata["patient_chats"] = _load_json(os.path.join(ddir, "patient_chats.json"), {})
        ddata["assistant_chat"] = _load_json(os.path.join(ddir, "assistant_chat.json"), [])
        res["doctor"][did] = ddata

    return res


def save_file_keys() -> None:
    _write_json_atomic(os.path.join(DATA_ROOT, "file_keys.json"), users.get("file_keys", {}))


users = _load_all()

# Centralized ChatService (LangChain wrapper around underlying LLM)
chat_service = AIChatService(DATA_ROOT)


def save_patient(username: str) -> None:
    pdata = users.get("patient", {}).get(username)
    if not pdata:
        return
    udir = os.path.join(PATIENT_DATA_ROOT, username)
    os.makedirs(udir, exist_ok=True)
    profile = {
        k: v
        for k, v in pdata.items()
        if k not in ("chat_sessions", "appointments", "reports", "medical_images")
    }
    _write_json_atomic(os.path.join(udir, "profile.json"), profile)
    
    # Trim chat_sessions to keep only last 10 conversations
    chat_sessions = pdata.get("chat_sessions", [])
    if len(chat_sessions) > 10:
        chat_sessions = chat_sessions[-10:]
    _write_json_atomic(os.path.join(udir, "chat_sessions.json"), chat_sessions)
    
    _write_json_atomic(os.path.join(udir, "appointments.json"), pdata.get("appointments", []))
    _write_json_atomic(os.path.join(udir, "reports.json"), pdata.get("reports", []))
    _write_json_atomic(os.path.join(udir, "medical_images.json"), pdata.get("medical_images", []))


def save_doctor(doc_id: str) -> None:
    ddata = users.get("doctor", {}).get(doc_id)
    if not ddata:
        return
    ddir = os.path.join(DOCTOR_DATA_ROOT, doc_id)
    os.makedirs(ddir, exist_ok=True)
    profile = {
        k: v
        for k, v in ddata.items()
        if k not in ("schedules", "appointment_requests", "payments", "patient_chats", "assistant_chat")
    }
    _write_json_atomic(os.path.join(ddir, "doctor_profile.json"), profile)
    _write_json_atomic(os.path.join(ddir, "schedules.json"), ddata.get("schedules", []))
    _write_json_atomic(os.path.join(ddir, "requests.json"), ddata.get("appointment_requests", []))
    _write_json_atomic(os.path.join(ddir, "payments.json"), ddata.get("payments", []))
    
    # Trim patient_chats to keep only last 10 per patient
    patient_chats = ddata.get("patient_chats", {})
    if patient_chats:
        for patient_id in patient_chats:
            if isinstance(patient_chats[patient_id], list) and len(patient_chats[patient_id]) > 10:
                patient_chats[patient_id] = patient_chats[patient_id][-10:]
    _write_json_atomic(os.path.join(ddir, "patient_chats.json"), patient_chats)
    
    # Trim assistant_chat to keep only last 10 conversations
    assistant_chat = ddata.get("assistant_chat", [])
    if len(assistant_chat) > 10:
        assistant_chat = assistant_chat[-10:]
    _write_json_atomic(os.path.join(ddir, "assistant_chat.json"), assistant_chat)


def snapshot_all() -> None:
    _write_json_atomic(os.path.join(DATA_ROOT, "snapshot.json"), users)


def _seed_doctors() -> None:
    demo_doctors = [
        {
            "id": "d1",
            "name": "Dr. Prodip Roy",
            "gender": "male",
            "category": "Cardiology",
            "location": "Kolkata - Laketown",
            "address": "Kolkata hospital, building no 4, Laketown, Kolkata-7000012",
        },
        {
            "id": "d2",
            "name": "Dr. Rakhi Sen",
            "gender": "female",
            "category": "Dermatology",
            "location": "Kolkata - Laketown",
            "address": "Kolkata hospital, building no 4, Laketown, Kolkata-7000012",
        },
        {
            "id": "d3",
            "name": "Dr. Rajdip Ch",
            "gender": "male",
            "category": "Orthopedics",
            "location": "Kolkata - Laketown",
            "address": "Kolkata hospital, building no 4, Laketown, Kolkata-7000012",
        },
        {
            "id": "d4",
            "name": "Dr. Sudhi Dhara",
            "gender": "male",
            "category": "Neurology",
            "location": "Kolkata - Laketown",
            "address": "Kolkata hospital, building no 4, Laketown, Kolkata-7000012",
        },
        {
            "id": "d5",
            "name": "Dr. Ritam Roy",
            "gender": "male",
            "category": "General Medicine",
            "location": "Kolkata - Laketown",
            "address": "Kolkata hospital, building no 4, Laketown, Kolkata-7000012",
        },
    ]

    users.setdefault("doctor", {})
    for d in demo_doctors:
        if d["id"] not in users["doctor"]:
            users["doctor"][d["id"]] = {**d, "password": "pass"}
            save_doctor(d["id"])


_seed_doctors()
for uname, pdata in users.get("patient", {}).items():
    if "password" not in pdata:
        pdata["password"] = "pass"
        save_patient(uname)
for did, ddata in users.get("doctor", {}).items():
    if "password" not in ddata:
        ddata["password"] = "pass"
        save_doctor(did)


# ----------------- Helpers -----------------
def _safe_filename(name: str) -> str:
    name = os.path.basename(name or "")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name.strip("._") or f"file_{int(time.time())}"


def _patient_file_dir(username: str, category: str) -> str:
    root = os.path.join(PATIENT_UPLOAD_ROOT, username, category)
    os.makedirs(root, exist_ok=True)
    return root


def format_prescription_for_chat(medicines_with_prices, language="en"):
    if not medicines_with_prices:
        return "No medicines found in prescription."

    response_lines = ["**Prescription Analysis:**\n"]
    for i, medicine in enumerate(medicines_with_prices, 1):
        response_lines.append(f"**{i}. {medicine['name']}**")
        response_lines.append(f"- Dosage: {medicine['dosage']}")
        response_lines.append(f"- Frequency: {medicine['frequency']}")
        response_lines.append(f"- Purpose: {medicine['purpose']}")
        if medicine.get("price"):
            if isinstance(medicine["price"], (int, float)):
                response_lines.append(f"- Price: Rs {medicine['price']}")
            else:
                response_lines.append(f"- Price: {medicine['price']}")
        else:
            response_lines.append("- Price: Price not available")
        if medicine.get("link"):
            response_lines.append(f"- Buy: {medicine['link']}")
        response_lines.append("")
    response_lines.append("You can ask follow-up questions about these medicines.")
    return "\n".join(response_lines)


def is_prescription_related_query(user_msg: str) -> bool:
    if not user_msg:
        return False
    keywords = [
        "medicine",
        "medication",
        "drug",
        "pill",
        "tablet",
        "capsule",
        "dosage",
        "dose",
        "side effect",
        "interaction",
        "prescription",
        "take",
        "when to take",
        "how to take",
        "before meal",
        "after meal",
        "mg",
        "ml",
    ]
    lower = user_msg.lower()
    return any(k in lower for k in keywords)


def get_prescription_context(username: str, user_msg: str):
    try:
        user_store = users.get("patient", {}).get(username, {})
        prescriptions = user_store.get("prescriptions", [])
        if not prescriptions:
            return None
        latest_prescription = prescriptions[0]
        medicines = latest_prescription.get("medicines", [])
        if not medicines:
            return None

        lower = user_msg.lower()
        relevant = []
        for medicine in medicines:
            name = medicine.get("name", "").lower()
            if name in lower or any(word in name for word in lower.split()):
                relevant.append(medicine)
        if not relevant:
            relevant = medicines[:3]

        parts = []
        for m in relevant:
            parts.append(
                f"{m.get('name')}: Dosage: {m.get('dosage','N/A')}, Frequency: {m.get('frequency','N/A')}, Purpose: {m.get('purpose','N/A')}"
            )
        return "Patient's current medicines: " + "; ".join(parts)
    except Exception:
        return None


def _parse_schedule_command(text: str):
    if not text:
        return (None, None)
    lower = text.lower()
    if "schedule" not in lower:
        return (None, None)

    parts = text.replace("T", " ").split()
    patient = None
    dt_parts = []
    for i, p in enumerate(parts):
        pl = p.lower()
        if pl == "patient" and i + 1 < len(parts):
            patient = parts[i + 1]
        if pl == "schedule" and i + 1 < len(parts) and not patient:
            nxt = parts[i + 1]
            if re.match(r"^[A-Za-z0-9_]+$", nxt):
                patient = nxt
        if re.match(r"^20\d{2}-\d{2}-\d{2}$", p):
            dt_parts = [p]
            if i + 1 < len(parts) and re.match(r"^\d{2}:\d{2}$", parts[i + 1]):
                dt_parts.append(parts[i + 1])
                break

    if patient and dt_parts:
        if len(dt_parts) == 2:
            return (patient, f"{dt_parts[0]}T{dt_parts[1]}:00Z")
        return (patient, f"{dt_parts[0]}T09:00:00Z")
    return (None, None)


def _reopen_doctor_patient_chat(doc_id: str, patient_username: str, scheduled_time: str, reason: str):
    if not doc_id or not patient_username:
        return
    doctor = users.get("doctor", {}).setdefault(doc_id, {})
    patient = users.get("patient", {}).setdefault(patient_username, {})

    closed_doc = doctor.setdefault("closed_chats", {})
    closed_pat = patient.setdefault("closed_doctor_chats", {})
    was_closed = False
    if closed_doc.pop(patient_username, None) is not None:
        was_closed = True
    if closed_pat.pop(doc_id, None) is not None:
        was_closed = True

    if was_closed:
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        text = f"Chat reopened for new appointment ({reason}) at {scheduled_time}."
        doctor.setdefault("patient_chats", {}).setdefault(patient_username, []).insert(
            0, {"sender": "system", "text": text, "ts": ts}
        )
        patient.setdefault("doctor_chats", {}).setdefault(doc_id, []).insert(
            0, {"sender": "system", "text": text, "ts": ts}
        )


def _format_datetime_short(iso: str):
    try:
        dt = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


MED_KB = {
    "paracetamol": "Paracetamol is used for mild to moderate pain and fever.",
    "ibuprofen": "Ibuprofen is an NSAID used for pain and inflammation.",
    "amoxicillin": "Amoxicillin is an antibiotic for susceptible bacterial infections.",
    "metformin": "Metformin is commonly used in type 2 diabetes.",
    "atorvastatin": "Atorvastatin is used to lower LDL cholesterol.",
}


def _assistant_general_answer(doctor: dict, doc_id: str, text: str):
    lower = (text or "").lower().strip()
    if not lower:
        return ("Please ask a scheduling or medicine question.", None)
    if lower in ("help", "commands", "menu", "what can you do"):
        return (
            "I can help with upcoming schedules, counts, specific patient appointment times, and general medicine info.",
            None,
        )

    schedules = doctor.get("schedules", [])
    now = datetime.now(timezone.utc)
    upcoming = []
    for s in schedules:
        if s.get("status") != "scheduled":
            continue
        ts = s.get("scheduled_time")
        try:
            dt = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
        except Exception:
            continue
        if dt >= now:
            upcoming.append((dt, s))
    upcoming.sort(key=lambda x: x[0])

    if "upcoming" in lower and ("appointment" in lower or "schedule" in lower):
        if not upcoming:
            return ("No upcoming appointments.", None)
        lines = [f"{s.get('patient')} at {s.get('scheduled_time')}" for _, s in upcoming[:10]]
        return ("Upcoming appointments: " + "; ".join(lines), None)

    if "how many" in lower and "appointment" in lower:
        return (f"You have {len(upcoming)} upcoming appointment(s).", None)

    for med, info in MED_KB.items():
        if med in lower:
            return (info + " (Educational only; not treatment advice.)", None)

    if lower in ("hi", "hello", "hey"):
        return ("Hello! Ask me about your schedule or a medicine.", None)
    if "thank" in lower:
        return ("Glad to help!", None)
    return (
        "I can answer about schedules and simple medicine info, or create a schedule (e.g. 'schedule patient alice 2025-08-20 14:30').",
        None,
    )


# ----------------- FastAPI App -----------------
api = FastAPI(title="HealthCare Backend", version="2.0.0")
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "your_secret_key"),
    same_site="lax",
)


def _read_session(request: Request) -> dict:
    return dict(request.session)


def _require_patient(request: Request):
    sess = _read_session(request)
    user = sess.get("user")
    if not user or sess.get("category") != "patient":
        return (None, JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401))
    return (user, None)


def _require_doctor(request: Request):
    sess = _read_session(request)
    user = sess.get("user")
    if not user or sess.get("category") != "doctor":
        return (None, JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401))
    return (user, None)


def _ensure_user_keys(category: str, username: str, password: str) -> tuple[bool, str | None]:
    if category not in ("patient", "doctor"):
        return (False, "Unsupported category for key bootstrap")
    if not password:
        return (False, "Password required for encryption key bootstrap")

    user = users.get(category, {}).get(username)
    if not user:
        return (False, "User not found for key bootstrap")

    has_keys = bool(user.get("publicKey") and user.get("encryptedPrivateKey"))
    if has_keys:
        return (True, None)

    try:
        public_key_pem, private_key_pem = generate_rsa_key_pair()
        user["publicKey"] = public_key_pem
        user["encryptedPrivateKey"] = encrypt_private_key(private_key_pem, password)
        if category == "patient":
            save_patient(username)
        else:
            save_doctor(username)
        snapshot_all()
        return (True, None)
    except Exception as exc:
        return (False, f"Failed to generate encryption keys: {exc}")


@api.get("/health")
def health():
    return {"status": "ok"}


@api.post("/api/login")
async def api_login(request: Request):
    form = await request.form()
    category = str(form.get("category") or "").strip()
    username = str(form.get("username") or "").strip()
    password = str(form.get("password") or "")

    user = users.get(category, {}).get(username)
    if not user or user.get("password") != password:
        return JSONResponse({"success": False, "error": "Invalid username, password, or category"})

    ok, err = _ensure_user_keys(category, username, password)
    if not ok:
        return JSONResponse({"success": False, "error": err or "Key bootstrap failed"}, status_code=500)

    request.session["user"] = username
    request.session["category"] = category
    return JSONResponse({"success": True})


@api.post("/api/register")
async def api_register(request: Request):
    form = await request.form()
    category = str(form.get("category") or "").strip().lower()
    username = str(form.get("username") or "").strip()

    if category not in ("patient", "doctor"):
        return JSONResponse({"success": False, "error": "Invalid category."}, status_code=400)
    if not username:
        return JSONResponse({"success": False, "error": "Username required."}, status_code=400)

    users.setdefault(category, {})
    if username in users[category]:
        return JSONResponse({"success": False, "error": "Username already exists."})

    user_data = {
        "name": form.get("name"),
        "dob": form.get("dob"),
        "gender": form.get("gender"),
        "password": form.get("password"),
    }
    if category == "patient":
        user_data.update(
            {
                "blood_group": form.get("blood_group"),
                "address": form.get("address"),
                "mobile": form.get("mobile"),
            }
        )
    else:
        user_data.update(
            {
                "registration_number": form.get("registration_number"),
                "hospital_name": form.get("hospital_name"),
                "hospital_location": form.get("hospital_location"),
                "specialization": form.get("specialization"),
                "category": form.get("specialization") or "General Medicine",
            }
        )

    users[category][username] = user_data

    ok, err = _ensure_user_keys(category, username, str(user_data.get("password") or ""))
    if not ok:
        users[category].pop(username, None)
        return JSONResponse({"success": False, "error": err or "User key setup failed"}, status_code=500)

    if category == "patient":
        save_patient(username)
    else:
        save_doctor(username)
    snapshot_all()
    return JSONResponse({"success": True})


@api.post("/api/logout")
def api_logout(request: Request):
    request.session.clear()
    return JSONResponse({"success": True})


@api.get("/api/patient_session")
def api_patient_session(request: Request):
    username, error = _require_patient(request)
    if error:
        return error
    user_info = users.get("patient", {}).get(username, {})
    pic_path = user_info.get("profile_pic")
    if pic_path and str(pic_path).startswith("/static"):
        pic_url = f"{request.url.scheme}://{request.url.netloc}{pic_path}"
    else:
        pic_url = pic_path or "https://randomuser.me/api/portraits/men/1.jpg"
    display_name = user_info.get("display_name") or user_info.get("name") or username
    return JSONResponse(
        {
            "success": True,
            "username": username,
            "display_name": display_name,
            "name": display_name,
            "profile_pic": pic_url,
        }
    )


@api.get("/api/doctor_session")
def api_doctor_session(request: Request):
    doc_id, error = _require_doctor(request)
    if error:
        return error
    doctor = users.get("doctor", {}).get(doc_id, {})
    profile_pic = doctor.get("profile_pic") or "https://randomuser.me/api/portraits/men/12.jpg"
    if str(profile_pic).startswith("/static"):
        profile_pic = f"{request.url.scheme}://{request.url.netloc}{profile_pic}"
    return JSONResponse(
        {
            "success": True,
            "username": doc_id,
            "display_name": doctor.get("name", doc_id),
            "profile_pic": profile_pic,
        }
    )


@api.get("/api/doctors")
def api_doctors():
    docs = []
    for did, d in users.get("doctor", {}).items():
        docs.append(
            {
                "id": did,
                "name": d.get("name", did),
                "gender": d.get("gender", "male"),
                "category": d.get("category") or d.get("specialization") or "General Medicine",
                "location": d.get("location") or d.get("hospital_location") or "Unknown",
                "address": d.get("address") or d.get("hospital_location") or "",
            }
        )
    return JSONResponse({"success": True, "doctors": docs})


@api.get("/api/chat_sessions")
def api_chat_sessions(request: Request):
    username, error = _require_patient(request)
    if error:
        return error
    sessions = users.get("patient", {}).get(username, {}).get("chat_sessions", [])
    return JSONResponse({"success": True, "sessions": sessions})


@api.post("/api/chat")
async def api_chat(request: Request):
    username, error = _require_patient(request)
    if error:
        return error

    try:
        data = await request.json()
    except Exception:
        data = {}

    messages = data.get("messages") or []
    if not messages and data.get("message"):
        messages = [{"role": "user", "content": str(data.get("message"))}]

    language = data.get("language", "en")
    session_id = data.get("session_id")

    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")
            break

    reply = "I received your message but need more information." if not user_msg else f"Echo: {user_msg[:500]}"
    try:
        call_messages = list(messages)
        if is_prescription_related_query(user_msg):
            ctx = get_prescription_context(username, user_msg)
            if ctx:
                call_messages.append({"role": "user", "content": f"Context from patient's prescription: {ctx}"})
        reply = chat_service._chat_impl(username, call_messages, language=language)
    except Exception as e:
        reply = f"Chat service error: {e}"

    disclaimer = (
        "\n\n⚠️ IMPORTANT DISCLAIMER:\nThis AI output is informational only and NOT a medical diagnosis. "
        "Consult a qualified healthcare professional."
    )

    # Do not persist quota/error responses as chat sessions; keep the last valid chat visible.
    if not isinstance(reply, dict):
        reply_text = str(reply)
        if chat_service._is_error_response(reply_text):
            return JSONResponse(
                {
                    "success": False,
                    "error": reply_text,
                    "language": language,
                    "session_id": session_id,
                }
            )

    user_store = users.setdefault("patient", {}).setdefault(username, {})
    chat_sessions = user_store.setdefault("chat_sessions", [])
    if not session_id:
        session_id = f"s_{int(datetime.now(timezone.utc).timestamp()*1000)}"

    server_session = None
    for s in chat_sessions:
        if s.get("id") == session_id:
            server_session = s
            break
    if server_session is None:
        server_session = {
            "id": session_id,
            "title": "",
            "messages": [],
            "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        chat_sessions.insert(0, server_session)

    trimmed = messages[-50:]
    stored_msgs = []
    for m in trimmed:
        stored_msgs.append(
            {
                "sender": "user" if m.get("role") == "user" else "model",
                "text": m.get("content", "")[:5000],
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
    # If reply is structured (dict), return it as JSON to frontend and store a short summary
    if isinstance(reply, dict):
        stored_text = (reply.get("title") or "") + "\n" + (reply.get("description") or "")
        stored_msgs.append(
            {
                "sender": "model",
                "text": stored_text + disclaimer,
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
        api_reply = reply
    else:
        stored_msgs.append(
            {
                "sender": "model",
                "text": str(reply) + disclaimer,
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
        api_reply = {"title": "AI Response", "description": str(reply), "key_points": [], "observations": [], "recommendations": []}
    server_session["messages"] = stored_msgs
    for m in server_session["messages"]:
        if m["sender"] == "user" and m["text"]:
            server_session["title"] = m["text"][:30]
            break

    save_patient(username)
    return JSONResponse({"success": True, "reply": api_reply, "disclaimer": disclaimer, "language": language, "session_id": session_id})


@api.post("/api/upload_prescription")
async def api_upload_prescription(request: Request):
    username, error = _require_patient(request)
    if error:
        return error

    form = await request.form()
    prescription_file = form.get("prescription")
    if not prescription_file or not getattr(prescription_file, "filename", ""):
        return JSONResponse({"success": False, "error": "No prescription file uploaded"}, status_code=400)

    language = str(form.get("language") or "en")
    try:
        file_bytes = await prescription_file.read()
        class _TempUpload:
            def __init__(self, path: str, filename: str):
                self.path = path
                self.filename = filename

            def __fspath__(self):
                return self.path

            def __str__(self):
                return self.path

        ext = os.path.splitext(prescription_file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        wrapped = _TempUpload(tmp_path, prescription_file.filename)
        medicine_data = upload_prescription_file(wrapped, language)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        if not medicine_data:
            return JSONResponse({"success": False, "error": "Could not extract medicine information from file"}, status_code=400)

        medicines_with_prices = []
        for medicine_name, details in medicine_data.items():
            medicine_info = {
                "name": medicine_name,
                "dosage": details[0].get("dosage", "N/A") if details else "N/A",
                "frequency": details[0].get("frequency", "N/A") if details else "N/A",
                "purpose": details[0].get("purpose", "N/A") if details else "N/A",
                "price": None,
                "link": None,
            }
            try:
                price, link = search_price(medicine_name)
                medicine_info["price"] = price
                medicine_info["link"] = link
            except Exception:
                pass
            medicines_with_prices.append(medicine_info)

        user_store = users.setdefault("patient", {}).setdefault(username, {})
        prescriptions = user_store.setdefault("prescriptions", [])
        prescription_record = {
            "id": f"pres_{int(datetime.now(timezone.utc).timestamp()*1000)}",
            "filename": prescription_file.filename,
            "uploaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "medicines": medicines_with_prices,
            "raw_data": medicine_data,
        }
        prescriptions.insert(0, prescription_record)
        save_patient(username)

        chat_response = format_prescription_for_chat(medicines_with_prices, language)
        return JSONResponse(
            {
                "success": True,
                "prescription_id": prescription_record["id"],
                "medicines": medicines_with_prices,
                "chat_response": chat_response,
                "message": f"Successfully processed prescription with {len(medicines_with_prices)} medicines",
            }
        )
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Error processing prescription: {str(e)}"}, status_code=500)


@api.get("/api/get_prescriptions")
def api_get_prescriptions(request: Request):
    username, error = _require_patient(request)
    if error:
        return error
    prescriptions = users.get("patient", {}).get(username, {}).get("prescriptions", [])
    return JSONResponse({"success": True, "prescriptions": prescriptions})


@api.post("/api/appointment_request")
async def api_appointment_request(request: Request):
    username, error = _require_patient(request)
    if error:
        return error

    try:
        data = await request.json()
    except Exception:
        data = {}
    doctor_id = data.get("doctor_id")
    if not doctor_id:
        return JSONResponse({"success": False, "error": "doctor_id required"}, status_code=400)

    doctor = users.get("doctor", {}).get(doctor_id)
    if not doctor:
        return JSONResponse({"success": False, "error": "Doctor not found"}, status_code=404)

    patient_store = users.setdefault("patient", {}).setdefault(username, {})
    appts = patient_store.setdefault("appointments", [])
    for a in appts:
        if a.get("doctor_id") == doctor_id and a.get("status") in ("requested", "pending"):
            return JSONResponse({"success": True, "message": "Already requested"})

    appt = {
        "id": f"apt_{int(datetime.now(timezone.utc).timestamp()*1000)}",
        "doctor_id": doctor_id,
        "doctor_name": doctor.get("name"),
        "category": doctor.get("category"),
        "location": doctor.get("location"),
        "requested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "requested",
    }
    appts.insert(0, appt)
    doctor.setdefault("appointment_requests", []).insert(
        0,
        {
            "patient": username,
            "patient_display": patient_store.get("display_name", username),
            "appointment_id": appt["id"],
            "requested_at": appt["requested_at"],
            "status": "requested",
        },
    )
    _reopen_doctor_patient_chat(doctor_id, username, appt["requested_at"], "New appointment request")
    save_patient(username)
    save_doctor(doctor_id)
    return JSONResponse({"success": True, "appointment": appt})


@api.get("/api/my_appointments")
def api_my_appointments(request: Request):
    username, error = _require_patient(request)
    if error:
        return error
    patient_store = users.get("patient", {}).get(username, {})
    return JSONResponse({"success": True, "appointments": patient_store.get("appointments", [])})


@api.get("/api/doctor_dashboard_data")
def api_doctor_dashboard_data(request: Request):
    doc_id, error = _require_doctor(request)
    if error:
        return error

    doctor = users.get("doctor", {}).setdefault(doc_id, {})
    requests_list = doctor.get("appointment_requests", [])
    schedules = doctor.get("schedules", [])

    monthly_patients = {}
    for s in schedules:
        if s.get("status") in ("completed", "scheduled"):
            ts = s.get("scheduled_time")
            if ts:
                month = ts[:7]
                monthly_patients[month] = monthly_patients.get(month, 0) + 1

    monthly_earnings = {}
    for s in schedules:
        if s.get("status") == "completed":
            ts = s.get("scheduled_time")
            if ts:
                month = ts[:7]
                monthly_earnings[month] = monthly_earnings.get(month, 0) + 50

    return JSONResponse(
        {
            "success": True,
            "total_requests": len(requests_list),
            "total_patients": sum(monthly_patients.values()),
            "monthly_patients": monthly_patients,
            "monthly_earnings": monthly_earnings,
            "upcoming_schedules": [s for s in schedules if s.get("status") == "scheduled"][:20],
            "completed_schedules": [s for s in schedules if s.get("status") == "completed"][:20],
            "requests": requests_list[:50],
            "patient_chat_patients": list(doctor.get("patient_chats", {}).keys()),
            "closed_chats": list(doctor.get("closed_chats", {}).keys()),
        }
    )


@api.post("/api/doctor_schedule")
async def api_doctor_schedule(request: Request):
    doc_id, error = _require_doctor(request)
    if error:
        return error
    try:
        data = await request.json()
    except Exception:
        data = {}
    patient_username = data.get("patient")
    scheduled_time = data.get("scheduled_time")
    note = (data.get("note") or "")[:200]

    if not patient_username or not scheduled_time:
        return JSONResponse({"success": False, "error": "patient and scheduled_time required"}, status_code=400)
    if patient_username not in users.get("patient", {}):
        return JSONResponse({"success": False, "error": "Patient not found"}, status_code=404)

    doctor = users.get("doctor", {}).setdefault(doc_id, {})
    sched = {
        "id": f"sch_{int(datetime.now(timezone.utc).timestamp()*1000)}",
        "patient": patient_username,
        "scheduled_time": scheduled_time,
        "note": note,
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    doctor.setdefault("schedules", []).insert(0, sched)

    pat_store = users.setdefault("patient", {}).setdefault(patient_username, {})
    pat_store.setdefault("appointments", []).insert(
        0,
        {
            "id": sched["id"],
            "doctor_id": doc_id,
            "doctor_name": doctor.get("name", doc_id),
            "category": doctor.get("category", ""),
            "location": doctor.get("location", ""),
            "requested_at": sched["created_at"],
            "status": "scheduled",
            "scheduled_time": scheduled_time,
            "note": note,
        },
    )
    _reopen_doctor_patient_chat(doc_id, patient_username, scheduled_time, "Manual scheduling")
    save_doctor(doc_id)
    save_patient(patient_username)
    return JSONResponse({"success": True, "schedule": sched})


@api.post("/api/doctor_schedule_request")
async def api_doctor_schedule_request(request: Request):
    doc_id, error = _require_doctor(request)
    if error:
        return error

    try:
        data = await request.json()
    except Exception:
        data = {}
    req_id = data.get("appointment_id")
    scheduled_time = data.get("scheduled_time")
    note = (data.get("note") or "")[:200]
    if not req_id or not scheduled_time:
        return JSONResponse({"success": False, "error": "appointment_id and scheduled_time required"}, status_code=400)

    doctor = users.get("doctor", {}).setdefault(doc_id, {})
    target = None
    for r in doctor.get("appointment_requests", []):
        if r.get("appointment_id") == req_id:
            target = r
            break
    if not target:
        return JSONResponse({"success": False, "error": "Request not found"}, status_code=404)

    patient_username = target.get("patient")
    if patient_username not in users.get("patient", {}):
        return JSONResponse({"success": False, "error": "Patient not found"}, status_code=404)

    sched = {
        "id": req_id,
        "patient": patient_username,
        "scheduled_time": scheduled_time,
        "note": note or "Scheduled from request",
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    doctor.setdefault("schedules", []).insert(0, sched)

    pat_store = users.setdefault("patient", {}).setdefault(patient_username, {})
    updated = False
    for a in pat_store.get("appointments", []):
        if a.get("id") == req_id:
            a["status"] = "scheduled"
            a["scheduled_time"] = scheduled_time
            a["note"] = sched["note"]
            updated = True
            break
    if not updated:
        pat_store.setdefault("appointments", []).insert(
            0,
            {
                "id": req_id,
                "doctor_id": doc_id,
                "doctor_name": doctor.get("name", doc_id),
                "category": doctor.get("category", ""),
                "location": doctor.get("location", ""),
                "requested_at": sched["created_at"],
                "status": "scheduled",
                "scheduled_time": scheduled_time,
                "note": sched["note"],
            },
        )

    doctor["appointment_requests"] = [
        r for r in doctor.get("appointment_requests", []) if r.get("appointment_id") != req_id
    ]

    auto_text = f"Appointment scheduled for {patient_username} on {scheduled_time}."
    ts_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    doctor.setdefault("patient_chats", {}).setdefault(patient_username, []).insert(
        0, {"sender": "system", "text": auto_text, "ts": ts_now}
    )
    users.setdefault("patient", {}).setdefault(patient_username, {}).setdefault("doctor_chats", {}).setdefault(
        doc_id, []
    ).insert(0, {"sender": "system", "text": auto_text, "ts": ts_now})

    _reopen_doctor_patient_chat(doc_id, patient_username, scheduled_time, "Scheduled from request")
    save_doctor(doc_id)
    save_patient(patient_username)
    return JSONResponse({"success": True, "scheduled": sched})


@api.post("/api/doctor_complete_schedule")
async def api_doctor_complete_schedule(request: Request):
    doc_id, error = _require_doctor(request)
    if error:
        return error
    try:
        data = await request.json()
    except Exception:
        data = {}
    sched_id = data.get("id")

    doctor = users.get("doctor", {}).setdefault(doc_id, {})
    for s in doctor.get("schedules", []):
        if s.get("id") == sched_id:
            s["status"] = "completed"
            s["completed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            pat = users.get("patient", {}).get(s.get("patient"))
            if pat:
                for a in pat.get("appointments", []):
                    if a.get("id") == sched_id:
                        a["status"] = "completed"
                        a["completed_at"] = s["completed_at"]
                doctor.setdefault("closed_chats", {})[s.get("patient")] = s["completed_at"]
                pat.setdefault("closed_doctor_chats", {})[doc_id] = s["completed_at"]
                closure_text = f"Chat closed after completion of appointment {sched_id}."
                ts_close = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                doctor.setdefault("patient_chats", {}).setdefault(s.get("patient"), []).insert(
                    0, {"sender": "system", "text": closure_text, "ts": ts_close}
                )
                pat.setdefault("doctor_chats", {}).setdefault(doc_id, []).insert(
                    0, {"sender": "system", "text": closure_text, "ts": ts_close}
                )
            save_doctor(doc_id)
            if pat:
                save_patient(s.get("patient"))
            return JSONResponse({"success": True})

    return JSONResponse({"success": False, "error": "Schedule not found"}, status_code=404)


@api.get("/api/doctor_patient_chat")
def api_doctor_patient_chat_get(request: Request, other: str | None = None):
    sess = _read_session(request)
    user = sess.get("user")
    role = sess.get("category")
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    if not other:
        return JSONResponse({"success": False, "error": "Missing other"}, status_code=400)

    disabled = False
    if role == "doctor":
        doctor = users.get("doctor", {}).setdefault(user, {})
        conv = doctor.setdefault("patient_chats", {}).setdefault(other, [])
        if doctor.get("closed_chats", {}).get(other):
            disabled = True
    elif role == "patient":
        patient = users.get("patient", {}).setdefault(user, {})
        conv = patient.setdefault("doctor_chats", {}).setdefault(other, [])
        if patient.get("closed_doctor_chats", {}).get(other):
            disabled = True
    else:
        return JSONResponse({"success": False, "error": "Role not supported"}, status_code=403)

    return JSONResponse({"success": True, "messages": conv[:200], "disabled": disabled})


@api.post("/api/doctor_patient_chat")
async def api_doctor_patient_chat_post(request: Request):
    sess = _read_session(request)
    user = sess.get("user")
    role = sess.get("category")
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    try:
        data = await request.json()
    except Exception:
        data = {}
    other = data.get("other")
    text = (data.get("text") or "").strip()[:1000]
    if not other or not text:
        return JSONResponse({"success": False, "error": "Missing other or text"}, status_code=400)

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if role == "doctor":
        doc_id = user
        doctor = users.get("doctor", {}).setdefault(doc_id, {})
        if doctor.get("closed_chats", {}).get(other):
            return JSONResponse({"success": False, "error": "Chat disabled after appointment completion"}, status_code=403)
        doctor.setdefault("patient_chats", {}).setdefault(other, []).insert(0, {"sender": "doctor", "text": text, "ts": ts})
        pat_store = users.setdefault("patient", {}).setdefault(other, {})
        if pat_store.get("closed_doctor_chats", {}).get(doc_id):
            return JSONResponse({"success": False, "error": "Chat disabled after appointment completion"}, status_code=403)
        pat_store.setdefault("doctor_chats", {}).setdefault(doc_id, []).insert(0, {"sender": "doctor", "text": text, "ts": ts})
        save_doctor(doc_id)
        save_patient(other)
    elif role == "patient":
        uname = user
        pat_store = users.get("patient", {}).setdefault(uname, {})
        if pat_store.get("closed_doctor_chats", {}).get(other):
            return JSONResponse({"success": False, "error": "Chat disabled after appointment completion"}, status_code=403)
        pat_store.setdefault("doctor_chats", {}).setdefault(other, []).insert(0, {"sender": "patient", "text": text, "ts": ts})
        doctor = users.setdefault("doctor", {}).setdefault(other, {})
        if doctor.get("closed_chats", {}).get(uname):
            return JSONResponse({"success": False, "error": "Chat disabled after appointment completion"}, status_code=403)
        doctor.setdefault("patient_chats", {}).setdefault(uname, []).insert(0, {"sender": "patient", "text": text, "ts": ts})
        save_patient(uname)
        save_doctor(other)
    else:
        return JSONResponse({"success": False, "error": "Role not supported"}, status_code=403)

    return JSONResponse({"success": True, "ts": ts})


@api.post("/api/doctor_patient_chat_delete")
async def api_doctor_patient_chat_delete(request: Request):
    sess = _read_session(request)
    user = sess.get("user")
    role = sess.get("category")
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    try:
        data = await request.json()
    except Exception:
        data = {}
    other = data.get("other")
    if not other:
        return JSONResponse({"success": False, "error": "Missing other"}, status_code=400)

    if role == "doctor":
        doc_id = user
        doctor = users.get("doctor", {}).setdefault(doc_id, {})
        removed = doctor.setdefault("patient_chats", {}).pop(other, None) is not None
        doctor.setdefault("closed_chats", {}).pop(other, None)
        pat = users.get("patient", {}).get(other)
        if pat:
            pat.setdefault("doctor_chats", {}).pop(doc_id, None)
            pat.setdefault("closed_doctor_chats", {}).pop(doc_id, None)
            save_patient(other)
        save_doctor(doc_id)
        return JSONResponse({"success": True, "removed": removed})

    if role == "patient":
        uname = user
        pat = users.get("patient", {}).setdefault(uname, {})
        removed = pat.setdefault("doctor_chats", {}).pop(other, None) is not None
        pat.setdefault("closed_doctor_chats", {}).pop(other, None)
        doctor = users.get("doctor", {}).get(other)
        if doctor:
            doctor.setdefault("patient_chats", {}).pop(uname, None)
            doctor.setdefault("closed_chats", {}).pop(uname, None)
            save_doctor(other)
        save_patient(uname)
        return JSONResponse({"success": True, "removed": removed})

    return JSONResponse({"success": False, "error": "Role not supported"}, status_code=403)


@api.get("/api/doctor_assistant_history")
def api_doctor_assistant_history(request: Request):
    doc_id, error = _require_doctor(request)
    if error:
        return error
    doctor = users.get("doctor", {}).setdefault(doc_id, {})
    return JSONResponse({"success": True, "history": doctor.get("assistant_chat", [])[-100:]})


@api.post("/api/doctor_assistant_chat")
async def api_doctor_assistant_chat(request: Request):
    doc_id, error = _require_doctor(request)
    if error:
        return error

    doctor = users.get("doctor", {}).setdefault(doc_id, {})
    try:
        data = await request.json()
    except Exception:
        data = {}
    messages = data.get("messages", [])

    history = doctor.setdefault("assistant_chat", [])
    recent = history[-30:]
    model_messages = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in recent]
    for m in messages:
        model_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    last_user = ""
    for m in reversed(model_messages):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break

    response = "Ask me to schedule, list appointments, or explain medicine basics."
    scheduled = None

    if last_user:
        patient, iso_dt = _parse_schedule_command(last_user)
        if patient and iso_dt:
            if not doctor.get("allow_auto_schedule"):
                response = "Auto-scheduling is disabled. Enable it in settings to let me create schedules."
            elif patient not in users.get("patient", {}):
                response = f"Patient '{patient}' not found."
            else:
                existing_req_id = None
                for r in doctor.get("appointment_requests", []):
                    if r.get("patient") == patient and r.get("status") == "requested":
                        existing_req_id = r.get("appointment_id")
                        break

                sched_id = existing_req_id or f"sch_{int(datetime.now(timezone.utc).timestamp()*1000)}"
                sched = {
                    "id": sched_id,
                    "patient": patient,
                    "scheduled_time": iso_dt,
                    "note": "Auto (assistant)",
                    "status": "scheduled",
                    "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                doctor.setdefault("schedules", []).insert(0, sched)
                if existing_req_id:
                    doctor["appointment_requests"] = [
                        r for r in doctor.get("appointment_requests", []) if r.get("appointment_id") != existing_req_id
                    ]

                pat_store = users.setdefault("patient", {}).setdefault(patient, {})
                updated = False
                for a in pat_store.setdefault("appointments", []):
                    if a.get("id") == sched_id:
                        a["status"] = "scheduled"
                        a["scheduled_time"] = iso_dt
                        a["note"] = sched["note"]
                        updated = True
                        break
                if not updated:
                    pat_store.setdefault("appointments", []).insert(
                        0,
                        {
                            "id": sched_id,
                            "doctor_id": doc_id,
                            "doctor_name": doctor.get("name", doc_id),
                            "category": doctor.get("category", ""),
                            "location": doctor.get("hospital_location", ""),
                            "requested_at": sched["created_at"],
                            "status": "scheduled",
                            "scheduled_time": iso_dt,
                            "note": "Auto (assistant)",
                        },
                    )

                auto_text = f"Appointment scheduled for {patient} on {iso_dt}."
                ts_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                doctor.setdefault("patient_chats", {}).setdefault(patient, []).insert(
                    0, {"sender": "system", "text": auto_text, "ts": ts_now}
                )
                pat_store.setdefault("doctor_chats", {}).setdefault(doc_id, []).insert(
                    0, {"sender": "system", "text": auto_text, "ts": ts_now}
                )
                _reopen_doctor_patient_chat(doc_id, patient, iso_dt, "Assistant scheduled appointment")
                save_doctor(doc_id)
                save_patient(patient)
                scheduled = sched
                response = f"Scheduled patient {patient} at {iso_dt}."
        else:
            deterministic, _none = _assistant_general_answer(doctor, doc_id, last_user)
            use_gemini = True
            key_terms = ("appointment", "schedule", "medicine", "medicines", "drug", "upcoming", "how many")
            if any(k in last_user.lower() for k in key_terms) and "I can answer" not in deterministic:
                response = deterministic
                use_gemini = False

            if use_gemini:
                try:
                    schedules = doctor.get("schedules", [])
                    upcoming_items = []
                    now = datetime.now(timezone.utc)
                    for s in schedules:
                        if s.get("status") == "scheduled":
                            ts = s.get("scheduled_time")
                            try:
                                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            except Exception:
                                continue
                            if dt >= now:
                                upcoming_items.append(f"{s.get('patient')} at {ts}")
                    summary = "Upcoming: " + (", ".join(upcoming_items[:10]) or "None")
                    msg_history = messages + [{"role": "user", "content": f"Context: {summary}. Doctor query: {last_user}"}]
                    gemini_reply = chat_service._chat_impl(doc_id, msg_history)
                    if isinstance(gemini_reply, dict):
                        # store short text for history, return structured reply
                        response_struct = gemini_reply
                        response = (response_struct.get("description") or response_struct.get("title") or "")
                    else:
                        response = gemini_reply or deterministic
                        response_struct = None
                except Exception:
                    response = deterministic
            else:
                response = deterministic

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for m in messages:
        if m.get("role") == "user":
            history.append({"role": "user", "content": m.get("content", "")[:4000], "ts": ts})
    # Store short textual summary in history (avoid storing raw structured JSON)
    if 'response_struct' in locals() and response_struct:
        stored_text = (response_struct.get("title") or "") + "\n" + (response_struct.get("description") or "")
    else:
        stored_text = str(response)
    history.append({"role": "assistant", "content": stored_text[:8000], "ts": ts})
    save_doctor(doc_id)
    # If we have a structured response, return it to frontend; otherwise return text
    if 'response_struct' in locals() and response_struct:
        api_reply = response_struct
    else:
        api_reply = {"title": "Assistant", "description": response, "key_points": [], "observations": [], "recommendations": []}

    return JSONResponse(
        {
            "success": True,
            "reply": api_reply,
            "scheduled": scheduled,
            "allow_auto_schedule": doctor.get("allow_auto_schedule", False),
            "history_length": len(history),
        }
    )


@api.post("/api/update_patient_profile")
async def api_update_patient_profile(request: Request):
    username, error = _require_patient(request)
    if error:
        return error

    form = await request.form()
    user = users.setdefault("patient", {}).setdefault(username, {})

    display_name = str(form.get("display_name") or "").strip()
    if display_name:
        user["display_name"] = display_name[:60]
        user["name"] = user["display_name"]

    new_password = str(form.get("password") or "")
    if new_password:
        user["password"] = new_password

    profile_pic = form.get("profile_pic")
    if profile_pic and getattr(profile_pic, "filename", ""):
        _, ext = os.path.splitext(profile_pic.filename.lower())
        if ext in (".jpg", ".jpeg", ".png", ".gif"):
            filename = _safe_filename(f"{username}_profile{ext}")
            save_dir = _patient_file_dir(username, "images")
            file_path = os.path.join(save_dir, filename)
            content = await profile_pic.read()

            if not user.get("publicKey"):
                return JSONResponse({"success": False, "error": "Encryption keys missing. Please re-login to initialize keys."}, status_code=400)

            try:
                fk_id, enc_file_key, enc_meta = FileCryptoService.process_upload(content, user["publicKey"], file_path)
                file_id = str(time.time()) + filename
                users.setdefault("file_keys", {})[fk_id] = {
                    "id": fk_id,
                    "file_id": file_id,
                    "user_id": username,
                    "encrypted_file_key": enc_file_key,
                    "createdAt": datetime.now().isoformat(),
                }
                save_file_keys()
                user["profile_pic"] = f"/api/file/{file_id}"
                user["_profile_asset"] = {
                    "physical_path": file_path,
                    "encryption": enc_meta,
                    "id": file_id,
                    "name": profile_pic.filename,
                }
            except Exception as exc:
                return JSONResponse({"success": False, "error": f"Encrypted profile upload failed: {exc}"}, status_code=500)

    save_patient(username)
    return JSONResponse(
        {
            "success": True,
            "msg": "Profile updated successfully",
            "display_name": user.get("display_name") or user.get("name") or username,
            "profile_pic": user.get("profile_pic") or "https://randomuser.me/api/portraits/men/1.jpg",
        }
    )


@api.post("/api/explain_report")
async def api_explain_report(request: Request):
    username, error = _require_patient(request)
    if error:
        return error

    form = await request.form()
    report_file = form.get("report")
    image_file = form.get("medical_image")
    language = str(form.get("language") or "en")
    has_report = bool(report_file and getattr(report_file, "filename", ""))
    has_image = bool(image_file and getattr(image_file, "filename", ""))
    if not has_report and not has_image:
        return JSONResponse({"success": False, "error": "No file uploaded"}, status_code=400)

    explanation_text = "Placeholder explanation. Provide a PDF or medical image for AI analysis."
    used = {"report": has_report, "medical_image": has_image}

    patient_user = users.setdefault("patient", {}).setdefault(username, {})
    if not patient_user.get("publicKey"):
        return JSONResponse({"success": False, "error": "Encryption keys missing. Please re-login to initialize keys."}, status_code=400)

    saved_paths = {}
    file_cache = {}
    for label, f in (("report", report_file), ("medical_image", image_file)):
        if f and getattr(f, "filename", ""):
            _, ext = os.path.splitext(f.filename.lower())
            index = len(patient_user.get(label + "s", []))
            safe_name = _safe_filename(f"{username}_{label}_{index}{ext}")
            dest_dir = _patient_file_dir(username, "images" if label == "medical_image" else "reports")
            save_path = os.path.join(dest_dir, safe_name)
            content = await f.read()
            file_cache[label] = {
                "bytes": content,
                "filename": f.filename,
                "ext": ext,
            }
            # Persist file via mandatory encrypted workflow
            file_id = str(time.time()) + _safe_filename(f.filename)
            try:
                fk_id, enc_file_key, enc_meta = FileCryptoService.process_upload(content, patient_user["publicKey"], save_path)
                users.setdefault("file_keys", {})[fk_id] = {
                    "id": fk_id,
                    "file_id": file_id,
                    "user_id": username,
                    "encrypted_file_key": enc_file_key,
                    "createdAt": datetime.now().isoformat(),
                }
                save_file_keys()

                url_path = f"/api/file/{file_id}"
                size_bytes = os.path.getsize(save_path) if os.path.exists(save_path) else 0
                entry = {
                    "id": file_id,
                    "name": f.filename,
                    "url": url_path,
                    "uploaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "size": size_bytes,
                }
                entry["encryption"] = enc_meta
                entry["physical_path"] = save_path
                # Store in both legacy list (for compatibility) and custom_assets (new unified location)
                patient_user.setdefault(label + "s", []).append(entry)
                # Also add to custom_assets with appropriate folder
                custom_assets = patient_user.setdefault("custom_assets", {"folders": ["Reports", "Medical Images"], "files": []})
                folder_name = "Medical Images" if label == "medical_image" else "Reports"
                if folder_name not in custom_assets["folders"]:
                    custom_assets["folders"].append(folder_name)
                custom_assets["files"].append({
                    "id": file_id,
                    "name": f.filename,
                    "url": url_path,
                    "folder": folder_name,
                    "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "size": size_bytes,
                    "encryption": enc_meta,
                    "physical_path": save_path,
                })
                saved_paths[label] = url_path
            except Exception as e:
                return JSONResponse({"success": False, "error": f"Encrypted upload failed for {label}: {e}"}, status_code=500)

    save_patient(username)

    try:
        report_meta = file_cache.get("report")
        image_meta = file_cache.get("medical_image")

        # Support image-only upload from either field.
        doc_stream = None
        img_stream = None

        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        if image_meta and image_meta.get("bytes"):
            img_stream = BytesIO(image_meta["bytes"])
        if report_meta and report_meta.get("bytes"):
            if report_meta.get("ext") in image_exts and not img_stream:
                img_stream = BytesIO(report_meta["bytes"])
            else:
                doc_stream = BytesIO(report_meta["bytes"])

        explanation_text = chat_service.explain_document(username, doc_stream, img_stream, language=language)
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Model processing failed: {e}"}, status_code=500)

    language_note = "" if language == "en" else f" (Requested language: {language})"
    return JSONResponse(
        {
            "success": True,
            "reply": explanation_text,
            "used": used,
            "language": language,
            "saved": saved_paths,
        }
    )


@api.post("/api/analyze_document")
async def api_analyze_document(request: Request):
    """Analyze an existing document by file_id."""
    username, error = _require_patient(request)
    if error:
        return error

    form = await request.form()
    file_id = str(form.get("file_id") or "").strip()
    language = str(form.get("language") or "en")
    
    if not file_id:
        return JSONResponse({"success": False, "error": "file_id required"}, status_code=400)

    # Get file from file_keys
    file_keys = users.get("file_keys", {})
    file_key_entry = None
    for fk_id, entry in file_keys.items():
        if entry.get("file_id") == file_id and entry.get("user_id") == username:
            file_key_entry = entry
            break
    
    if not file_key_entry:
        return JSONResponse({"success": False, "error": "File not found or access denied"}, status_code=403)

    # Get file content via download
    patient_user = users.setdefault("patient", {}).setdefault(username, {})
    custom_assets = patient_user.get("custom_assets", {})
    file_entry = None
    for f in custom_assets.get("files", []):
        if f.get("id") == file_id:
            file_entry = f
            break
    
    if not file_entry:
        return JSONResponse({"success": False, "error": "File metadata not found"}, status_code=404)

    physical_path = file_entry.get("physical_path")
    if not physical_path or not os.path.exists(physical_path):
        return JSONResponse({"success": False, "error": "Physical file not found"}, status_code=404)

    # Decrypt file using user's password from profile
    try:
        encrypted_file_key_b64 = file_key_entry.get("encrypted_file_key")
        encryption_meta = file_entry.get("encryption", {})
        encrypted_private_key_b64 = patient_user.get("encryptedPrivateKey")
        password = patient_user.get("password")
        
        if not password:
            return JSONResponse({"success": False, "error": "Cannot decrypt: password not found in profile"}, status_code=500)
        
        file_bytes = FileCryptoService.process_download(
            physical_path,
            encrypted_file_key_b64,
            encrypted_private_key_b64,
            password,
            encryption_meta
        )
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Decryption failed: {str(e)}"}, status_code=500)

    # Determine file type and analyze
    explanation_text = "Placeholder explanation. File could not be analyzed."
    filename = file_entry.get("name", "")
    _, ext = os.path.splitext(filename.lower())
    
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    doc_stream = None
    img_stream = None
    
    if ext in image_exts:
        img_stream = BytesIO(file_bytes)
    elif ext == ".pdf":
        doc_stream = BytesIO(file_bytes)
    
    if (doc_stream or img_stream):
        try:
            explanation_text = chat_service.explain_document(username, doc_stream, img_stream, language=language)
        except Exception as e:
            return JSONResponse({"success": False, "error": f"Model processing failed: {e}"}, status_code=500)

    language_note = "" if language == "en" else f" (Requested language: {language})"
    return JSONResponse(
        {
            "success": True,
            "reply": explanation_text,
            "filename": filename,
            "language": language,
        }
    )


@api.post("/api/analyze_xray")
async def api_analyze_xray(request: Request):
    """Advanced X-ray analysis with defect detection and healthy comparison generation."""
    username, error = _require_patient(request)
    if error:
        return error

    form = await request.form()
    xray_file = form.get("xray")
    language = str(form.get("language") or "en")
    
    if not xray_file or not getattr(xray_file, "filename", ""):
        return JSONResponse({"success": False, "error": "No X-ray image uploaded"}, status_code=400)

    try:
        # Save uploaded file
        _, ext = os.path.splitext(xray_file.filename.lower())
        if ext not in (".jpg", ".jpeg", ".png", ".gif"):
            return JSONResponse({"success": False, "error": "Only image files (JPG, PNG, GIF) supported"}, status_code=400)
        
        safe_name = _safe_filename(f"{username}_xray_{int(time.time())}{ext}")
        dest_dir = _patient_file_dir(username, "xrays")
        save_path = os.path.join(dest_dir, safe_name)

        patient_user = users.setdefault("patient", {}).setdefault(username, {})
        if not patient_user.get("publicKey"):
            return JSONResponse({"success": False, "error": "Encryption keys missing. Please re-login to initialize keys."}, status_code=400)
        
        content = await xray_file.read()
        file_id = str(time.time()) + safe_name
        # Persist X-ray via mandatory encrypted workflow
        try:
            fk_id, enc_file_key, enc_meta = FileCryptoService.process_upload(content, patient_user["publicKey"], save_path)
            users.setdefault("file_keys", {})[fk_id] = {
                "id": fk_id,
                "file_id": file_id,
                "user_id": username,
                "encrypted_file_key": enc_file_key,
                "createdAt": datetime.now().isoformat(),
            }
            save_file_keys()
        except Exception as exc:
            return JSONResponse({"success": False, "error": f"Encrypted X-ray upload failed: {exc}"}, status_code=500)
        
        # Analyze X-ray via centralized ChatService
        analysis_result = chat_service.analyze_xray(username, save_path, language=language)
        
        if not analysis_result.get("success"):
            return JSONResponse({
                "success": False,
                "error": analysis_result.get("error", "X-ray analysis failed")
            }, status_code=500)
        
        # Format for chat display
        formatted_analysis = format_xray_analysis_for_chat(analysis_result)
        
        # Store analysis in user data
        patient_user.setdefault("xray_analyses", []).insert(0, {
            "filename": xray_file.filename,
            "upload_date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "analysis": analysis_result.get("analysis", {}),
            "has_defect": analysis_result.get("analysis", {}).get("has_defect", False),
            "enc_assets": [
                {
                    "id": file_id,
                    "name": xray_file.filename,
                    "url": f"/api/file/{file_id}",
                    "physical_path": save_path,
                    "encryption": enc_meta,
                    "uploaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            ],
        })
        save_patient(username)
        
        return JSONResponse({
            "success": True,
            "analysis": formatted_analysis,
            "has_defect": analysis_result.get("analysis", {}).get("has_defect", False),
            "severity": analysis_result.get("analysis", {}).get("severity", 0),
            "defect_type": analysis_result.get("analysis", {}).get("defect_type", ""),
            "images": analysis_result.get("images", {}),
            "upload_path": f"/api/file/{file_id}"
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": f"X-ray analysis error: {str(e)}"
        }, status_code=500)


@api.get("/api/v2/patient_assets")
def api_v2_patient_assets(request: Request):
    username, error = _require_patient(request)
    if error:
        return error
    user = users.setdefault("patient", {}).setdefault(username, {})
    custom_assets = user.get("custom_assets", {"folders": ["Reports", "Medical Images"], "files": []})

    if not user.get("_migrated_v2"):
        user["_migrated_v2"] = True
        for r in user.get("reports", []):
            if isinstance(r, dict):
                custom_assets["files"].append({**r, "folder": "Reports", "id": str(time.time()) + r.get("name", "r")})
            else:
                custom_assets["files"].append({"url": r, "name": "Legacy Report", "folder": "Reports", "id": str(time.time())})
        for m in user.get("medical_images", []):
            if isinstance(m, dict):
                custom_assets["files"].append({**m, "folder": "Medical Images", "id": str(time.time()) + m.get("name", "m")})
            else:
                custom_assets["files"].append({"url": m, "name": "Legacy Image", "folder": "Medical Images", "id": str(time.time())})
        user["custom_assets"] = custom_assets
        save_patient(username)

    return JSONResponse({"success": True, "assets": user.get("custom_assets", {"folders": [], "files": []})})


@api.get("/api/analyze/available_documents")
def api_analyze_available_documents(request: Request):
    """List all documents available for analysis (PDFs and images)."""
    username, error = _require_patient(request)
    if error:
        return error
    
    user = users.setdefault("patient", {}).setdefault(username, {})
    custom_assets = user.get("custom_assets", {"folders": [], "files": []})
    
    # Filter only analyzable file types
    analyzable_exts = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    documents = []
    
    for file in custom_assets.get("files", []):
        _, ext = os.path.splitext(file.get("name", "").lower())
        if ext in analyzable_exts:
            documents.append({
                "id": file.get("id"),
                "name": file.get("name"),
                "url": file.get("url"),
                "folder": file.get("folder", ""),
                "uploaded_at": file.get("uploaded_at"),
                "type": "image" if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"} else "pdf"
            })
    
    return JSONResponse({"success": True, "documents": documents})


@api.post("/api/v2/upload_asset")
async def api_v2_upload_asset(request: Request):
    username, error = _require_patient(request)
    if error:
        return error

    form = await request.form()
    file = form.get("file")
    folder = str(form.get("folder") or "")
    if not file or not getattr(file, "filename", ""):
        return JSONResponse({"success": False, "error": "No file chosen"}, status_code=400)

    dest_dir = _patient_file_dir(username, "custom_assets")
    safe_name = _safe_filename(f"{int(time.time())}_{file.filename}")
    save_path = os.path.join(dest_dir, safe_name)
    content = await file.read()

    user = users.setdefault("patient", {}).setdefault(username, {})
    assets = user.setdefault("custom_assets", {"folders": [], "files": []})

    if not user.get("publicKey"):
        return JSONResponse({"success": False, "error": "Encryption keys missing. Please re-login to initialize keys."}, status_code=400)

    # Encrypt upload (mandatory)
    file_id = str(time.time()) + _safe_filename(file.filename)
    try:
        fk_id, enc_file_key, enc_meta = FileCryptoService.process_upload(content, user["publicKey"], save_path)
        users.setdefault("file_keys", {})[fk_id] = {
            "id": fk_id,
            "file_id": file_id,
            "user_id": username,
            "encrypted_file_key": enc_file_key,
            "createdAt": datetime.now().isoformat(),
        }
        save_file_keys()

        url_path = f"/api/file/{file_id}"
        new_asset = {
            "id": file_id,
            "name": file.filename,
            "url": url_path,
            "physical_path": save_path,
            "folder": folder,
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "size": os.path.getsize(save_path) if os.path.exists(save_path) else 0,
            "encryption": enc_meta,
        }

        assets["files"].append(new_asset)
        save_patient(username)
        return JSONResponse({"success": True, "asset": new_asset})
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Upload failure: {str(e)}"}, status_code=500)


@api.post("/api/v2/delete_asset")
async def api_v2_delete_asset(request: Request):
    username, error = _require_patient(request)
    if error:
        return error

    form = await request.form()
    delete_id = form.get("id")
    delete_type = form.get("type")

    user = users.setdefault("patient", {}).setdefault(username, {})
    assets = user.setdefault("custom_assets", {"folders": [], "files": []})

    if delete_type == "folder":
        if delete_id in assets["folders"]:
            assets["folders"].remove(delete_id)
            for f in assets["files"]:
                if f.get("folder") == delete_id:
                    f["folder"] = ""
            save_patient(username)
            return JSONResponse({"success": True})
    else:
        assets["files"] = [f for f in assets["files"] if f.get("id") != delete_id and f.get("url") != delete_id]
        save_patient(username)
        return JSONResponse({"success": True})

    return JSONResponse({"success": False})


@api.post("/api/v2/create_folder")
async def api_v2_create_folder(request: Request):
    username, error = _require_patient(request)
    if error:
        return error

    form = await request.form()
    name = str(form.get("name") or "").strip()
    user = users.setdefault("patient", {}).setdefault(username, {})
    assets = user.setdefault("custom_assets", {"folders": [], "files": []})
    if name and name not in assets["folders"]:
        assets["folders"].append(name)
        save_patient(username)
    return JSONResponse({"success": True})


@api.post("/api/v2/rename_asset")
async def api_v2_rename_asset(request: Request):
    username, error = _require_patient(request)
    if error:
        return error

    form = await request.form()
    old_name = form.get("old_name")
    new_name = form.get("new_name")
    rename_type = form.get("type")
    asset_id = form.get("id")

    user = users.setdefault("patient", {}).setdefault(username, {})
    assets = user.setdefault("custom_assets", {"folders": [], "files": []})

    if rename_type == "folder":
        if old_name in assets["folders"] and new_name and new_name not in assets["folders"]:
            idx = assets["folders"].index(old_name)
            assets["folders"][idx] = new_name
            for f in assets["files"]:
                if f.get("folder") == old_name:
                    f["folder"] = new_name
            save_patient(username)
    else:
        for f in assets["files"]:
            if f.get("id") == asset_id:
                f["name"] = new_name
        save_patient(username)

    return JSONResponse({"success": True})


# Static files for uploaded assets
os.makedirs(STATIC_ROOT, exist_ok=True)
os.makedirs(UPLOAD_ROOT, exist_ok=True)
api.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")
# Static data mount removed to force secure API-based file access.
# Files are exposed via /api/file/{file_id} endpoints handled by application logic.


@api.get("/api/file/{file_id}")
async def api_download_file(request: Request, file_id: str):
    user_id = request.session.get("user")
    category = request.session.get("category")
    if not user_id or not category:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    # Locate metadata across patient records
    target_metadata = None
    target_owner = None

    for uname, pdata in users.get("patient", {}).items():
        assets = pdata.get("custom_assets", {}).get("files", [])
        for a in assets:
            if a.get("id") == file_id:
                target_metadata = a
                target_owner = uname
                break
        if target_metadata:
            break

    if not target_metadata:
        for uname, pdata in users.get("patient", {}).items():
            for xa in pdata.get("xray_analyses", []):
                for ea in xa.get("enc_assets", []):
                    if ea.get("id") == file_id:
                        target_metadata = ea
                        target_owner = uname
                        break
                if target_metadata:
                    break
            if target_metadata:
                break

    # Check patient profile assets (profile_pic stored as protected asset)
    if not target_metadata:
        for uname, pdata in users.get("patient", {}).items():
            pa = pdata.get("_profile_asset")
            if pa and pa.get("id") == file_id:
                target_metadata = pa
                target_owner = uname
                break

    if not target_metadata:
        return JSONResponse({"success": False, "error": "File not found"}, status_code=404)

    # Verify user has a key mapping for this file
    all_keys = users.get("file_keys", {})
    user_key_entry = None
    for k, v in all_keys.items():
        if v.get("file_id") == file_id and v.get("user_id") == user_id:
            user_key_entry = v
            break

    if not user_key_entry and user_id != target_owner:
        return JSONResponse({"success": False, "error": "You do not have access to this file"}, status_code=403)

    # Enforce encrypted-only access through secure key mapping.
    try:
        encryption_meta = target_metadata.get("encryption")
        physical_path = target_metadata.get("physical_path")
        if not encryption_meta or not user_key_entry:
            return JSONResponse({"success": False, "error": "Access denied: missing encryption metadata or key mapping"}, status_code=403)

        user_prof = users.get(category, {}).get(user_id, {})
        password = user_prof.get("password")
        plain_bytes = FileCryptoService.process_download(
            physical_path,
            user_key_entry["encrypted_file_key"],
            user_prof.get("encryptedPrivateKey"),
            password,
            encryption_meta,
        )

        content_type = "application/octet-stream"
        if target_metadata.get("name", "").lower().endswith(".jpg"): content_type = "image/jpeg"
        elif target_metadata.get("name", "").lower().endswith(".png"): content_type = "image/png"
        elif target_metadata.get("name", "").lower().endswith(".pdf"): content_type = "application/pdf"

        from fastapi import Response
        return Response(content=plain_bytes, media_type=content_type)
    except Exception as e:
        print("File download error:", e)
        return JSONResponse({"success": False, "error": "File decryption failed or file corrupted"}, status_code=500)
