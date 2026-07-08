"""
================================================================================
AI Workflow Regression Test Runner
================================================================================

This is a standalone testing utility to verify AI chat workflows.

# Configuration
Edit the CONFIG section below to customize your testing environment.
You can toggle between testing the 'patient' or 'doctor' workflows by simply
changing the `ROLE` variable.

# Adding New Prompts
To add new test cases, simply add your dictionaries to the `TEST_PROMPTS` list below.
Format: {"category": "CATEGORY_NAME", "prompt": "Your test prompt"}

# Running the Tests
Simply execute this script from the terminal:
    python workflow_test.py

The results will be written to the configured OUTPUT_FILE in CSV format, 
and a complete console log will be saved in the logs/ directory.
================================================================================
"""

import asyncio
import csv
import json
import logging
import time
import requests
import websockets
import subprocess
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
os.makedirs("logs", exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
log_filename = f"logs/regression_{timestamp}.log"
log_file = open(log_filename, "w", encoding="utf-8")

def log_print(*args, **kwargs):
    """Prints to console and also writes to the log file."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        pass
    print(*args, file=log_file, **kwargs)
    log_file.flush()

# ==============================================================================
# CONFIG
# ==============================================================================

ROLE = "patient"  # Options: "patient", "doctor"

PATIENT_USERNAME = "patientdipu"
PATIENT_PASSWORD = "raja1234Raja@"

DOCTOR_ID = "DocDipu"
DOCTOR_PASSWORD = "D94461328d@"
TARGET_PATIENT_ID = "patientdipu" # Only used when ROLE = "doctor"

API_BASE = "http://localhost:8000/api"
WS_BASE = "ws://localhost:8000/api"

CLEAR_CHAT_BEFORE_EACH_TEST = True
AUTO_CREATE_DOCTOR_SLOTS = True

OUTPUT_FILE = "test_results.csv"

# ==============================================================================
# TEST PROMPTS
# ==============================================================================

TEST_PROMPTS = [
    {
        "category": "GENERAL",
        "prompt": "Hello"
    },
    {
        "category": "KNOWLEDGE",
        "prompt": "Tell me about anemia."
    },
    {
        "category": "RAG",
        "prompt": "Explain my latest blood report.",
        "clear_chat": True
    },
    {
        "category": "MEMORY",
        "prompt": "Summarize my previous consultations.",
        "clear_chat": False
    },
    {
        "category": "MULTI-CAPABILITY",
        "prompt": "Summarize my previous consultations and latest blood report."
    },
    {
        "category": "WORKFLOW_SEQUENCE",
        "prompt": "Is there any appointment slots available for Dr. DocDipu?",
        "clear_chat": False
    },
    {
        "category": "WORKFLOW_SEQUENCE",
        "prompt": "Book the first available slot.",
        "clear_chat": False
    },
    {
        "category": "WORKFLOW_SEQUENCE",
        "prompt": "Yes, please book it.",
        "clear_chat": False
    },
    {
        "category": "WORKFLOW_SEQUENCE",
        "prompt": "Cancel my appointment.",
        "clear_chat": False
    }
]

# ==============================================================================
# HELPERS
# ==============================================================================

def login_patient() -> str | None:
    """Authenticate as a patient and return the access token."""
    try:
        res = requests.post(f"{API_BASE}/auth/patient/login", json={
            "username": PATIENT_USERNAME,
            "password": PATIENT_PASSWORD
        })
        res.raise_for_status()
        return res.json()["access_token"]
    except Exception as e:
        logger.error(f"Failed to authenticate patient: {e}")
        return None

def login_doctor() -> str | None:
    """Authenticate as a doctor and return the access token."""
    try:
        res = requests.post(f"{API_BASE}/auth/doctor/login", json={
            "doctor_id": DOCTOR_ID,
            "password": DOCTOR_PASSWORD
        })
        res.raise_for_status()
        return res.json()["access_token"]
    except Exception as e:
        logger.error(f"Failed to authenticate doctor: {e}")
        return None

def setup_doctor_slots(doc_token: str) -> None:
    """Create test doctor slots (requires doctor token)."""
    try:
        headers = {"Authorization": f"Bearer {doc_token}"}
        slots = [
            {"startTime": "2026-07-07T16:00:00+05:30", "endTime": "2026-07-07T16:30:00+05:30"},
            {"startTime": "2026-07-07T16:30:00+05:30", "endTime": "2026-07-07T17:00:00+05:30"},
            {"startTime": "2026-07-07T21:30:00+05:30", "endTime": "2026-07-07T22:00:00+05:30"}
        ]
        res = requests.post(f"{API_BASE}/appointments/slots", json=slots, headers=headers)
        if res.status_code in (200, 201):
            logger.info(f"Successfully created slots for doctor {DOCTOR_ID}.")
        else:
            logger.warning(f"Failed to create slots: {res.text}")
    except Exception as e:
        logger.error(f"Failed to create doctor slots: {e}")

def get_websocket_url(token: str) -> str:
    """Construct the appropriate websocket URL based on the configured role."""
    if ROLE == "patient":
        return f"{WS_BASE}/chat/ai/patient/ws?token={token}"
    elif ROLE == "doctor":
        return f"{WS_BASE}/chat/ai/doctor/ws?token={token}&patient_id={TARGET_PATIENT_ID}"
    else:
        raise ValueError(f"Invalid ROLE configured: {ROLE}")

def clear_chats() -> None:
    """Clear AI chats using the backend script."""
    # NOTE: Assuming python is available in PATH or inside the active virtual environment
    import sys
    subprocess.run([sys.executable, "-B", "backend/clear_ai_chats.py"], capture_output=True)

async def test_single_prompt(query: str, ws_url: str) -> tuple[str, str, int]:
    """
    Test a single prompt via websocket.
    Returns: (output_text, status, execution_time_ms)
    """
    final_response = "ERROR: Unknown"
    status_ok = False
    start_time = time.time()
    
    try:
        async with websockets.connect(ws_url) as ws:
            # wait for history payload which is sent initially on connection
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(msg)
                if data.get("type") == "history":
                    break
                    
            await ws.send(query)
            
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=180.0)
                    
                    try:
                        data = json.loads(msg)
                    except json.JSONDecodeError:
                        final_response = msg
                        status_ok = True
                        break
                    
                    if isinstance(data, dict):
                        if data.get("type") == "final":
                            final_response = data.get("content", "")
                            status_ok = True
                            break
                        elif data.get("type") == "error":
                            final_response = f"SERVER ERROR: {data.get('content', '')}"
                            status_ok = False
                            break
                    else:
                        final_response = msg
                        status_ok = True
                        break
                except asyncio.TimeoutError:
                    final_response = "TIMEOUT"
                    status_ok = False
                    break
                except Exception as e:
                    final_response = f"ERROR: {e}"
                    status_ok = False
                    break
    except Exception as e:
        final_response = f"WS ERROR: {e}"
        status_ok = False
        
    end_time = time.time()
    exec_time_ms = int((end_time - start_time) * 1000)
    
    return final_response, "PASS" if status_ok else "FAIL", exec_time_ms

def save_results(results: list[dict]) -> None:
    """Save results to CSV."""
    file_name = OUTPUT_FILE
    try:
        with open(file_name, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["Input", "Output", "Status", "Execution Time (ms)"])
            writer.writeheader()
            writer.writerows(results)
        log_print(f"\nSaved {len(results)} results to {file_name}")
    except PermissionError:
        fallback = "test_results_fallback.csv"
        log_print(f"\nPermission denied for {file_name}. Saving to {fallback}...")
        with open(fallback, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["Input", "Output", "Status", "Execution Time (ms)"])
            writer.writeheader()
            writer.writerows(results)
        log_print(f"Saved {len(results)} results to {fallback}")

# ==============================================================================
# MAIN RUNNER
# ==============================================================================

async def main():
    log_print(f"Initializing Test Runner (Role: {ROLE.upper()})")
    
    # 1. Prepare Environment
    if AUTO_CREATE_DOCTOR_SLOTS:
        doc_token = login_doctor()
        if doc_token:
            setup_doctor_slots(doc_token)
        else:
            log_print("Skipping doctor slot creation due to login failure.")
            
    # 2. Authenticate
    token = login_patient() if ROLE == "patient" else login_doctor()
    if not token:
        log_print(f"Failed to authenticate as {ROLE}. Aborting tests.")
        return
        
    ws_url = get_websocket_url(token)
    results = []
    failed_tests = []
    
    total_tests = len(TEST_PROMPTS)
    passed_count = 0
    failed_count = 0
    total_time_ms = 0
    
    log_print(f"\nStarting {total_tests} tests...\n")
    
    # 3. Execute Tests
    for i, test_case in enumerate(TEST_PROMPTS, 1):
        category = test_case.get("category", "UNKNOWN")
        query = test_case.get("prompt", "")
        
        log_print("-" * 60)
        log_print(f"[{i}/{total_tests}]")
        log_print(f"Category: {category}")
        log_print(f"Prompt:   {query}")
        
        clear_chat_for_this_test = test_case.get("clear_chat", CLEAR_CHAT_BEFORE_EACH_TEST)
        if clear_chat_for_this_test:
            clear_chats()
            
        output, status, exec_time = await test_single_prompt(query, ws_url)
        
        log_print(f"Status:   {status}")
        log_print(f"Time:     {exec_time} ms")
        log_print(f"\nFinal Response:\n{output}\n")
        
        total_time_ms += exec_time
        if status == "PASS":
            passed_count += 1
        else:
            failed_count += 1
            failed_tests.append({
                "prompt": query,
                "category": category,
                "reason": output
            })
        
        formatted_response = output.replace('\n', '\\n').replace('\r', '') if output else ""
        results.append({
            "Input": query,
            "Output": formatted_response,
            "Status": status,
            "Execution Time (ms)": exec_time
        })
        
    log_print("=" * 60)
    log_print("SUMMARY")
    log_print("=" * 60)
    log_print(f"Total Tests            : {total_tests}")
    log_print(f"Passed                 : {passed_count}")
    log_print(f"Failed                 : {failed_count}")
    avg_time = int(total_time_ms / total_tests) if total_tests > 0 else 0
    log_print(f"Average Execution Time : {avg_time} ms")
    log_print("=" * 60)
    
    if failed_tests:
        log_print("\nFAILED TESTS")
        log_print("=" * 60)
        for fail in failed_tests:
            log_print(f"Category: {fail['category']}")
            log_print(f"Prompt:   {fail['prompt']}")
            log_print(f"Reason:   {fail['reason']}")
            log_print("-" * 40)
            
    save_results(results)
    
    log_print(f"Console log saved to {log_filename}")
    log_file.close()

if __name__ == "__main__":
    asyncio.run(main())
