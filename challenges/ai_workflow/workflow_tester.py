from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Any

import requests
import websockets
from openai import AsyncOpenAI
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

load_dotenv(ROOT / ".env")

backend_init = ROOT / "backend" / "__init__.py"
if "backend" not in sys.modules and backend_init.exists():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "backend",
        backend_init,
        submodule_search_locations=[str(ROOT / "backend")],
    )
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules["backend"] = module
        spec.loader.exec_module(module)


API_BASE = "http://localhost:8000/api"
WS_BASE = "ws://localhost:8000/api"

ROLE = "patient"

PATIENT_USERNAME = "patientdipu"
PATIENT_PASSWORD = "raja1234Raja@"

DOCTOR_ID = "DocDipu"
DOCTOR_PASSWORD = "D94461328d@"
TARGET_PATIENT_ID = "patientdipu"

INPUT_CSV = Path(__file__).with_name("workflow_queries.csv")
OUTPUT_CSV = INPUT_CSV

CLEAR_CHAT_BEFORE_EACH_TEST = True
AUTO_CREATE_DOCTOR_SLOTS = True

JUDGE_MODEL = os.getenv("OPENAI_MODEL") or ""
JUDGE_API_KEY = os.getenv("OPENAI_API_KEY") or ""
JUDGE_BASE_URL = os.getenv("OPENAI_BASE_URL") or None
_judge_client: AsyncOpenAI | None = None


def get_judge_client() -> AsyncOpenAI:
    global _judge_client
    if _judge_client is None:
        if not JUDGE_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required for the standalone judge client")
        _judge_client = AsyncOpenAI(api_key=JUDGE_API_KEY, base_url=JUDGE_BASE_URL)
    return _judge_client


def login_patient() -> str | None:
    res = requests.post(
        f"{API_BASE}/auth/patient/login",
        json={"username": PATIENT_USERNAME, "password": PATIENT_PASSWORD},
        timeout=30,
    )
    res.raise_for_status()
    return res.json()["access_token"]


def login_doctor() -> str | None:
    res = requests.post(
        f"{API_BASE}/auth/doctor/login",
        json={"doctor_id": DOCTOR_ID, "password": DOCTOR_PASSWORD},
        timeout=30,
    )
    res.raise_for_status()
    return res.json()["access_token"]


def create_doctor_slots() -> None:
    doc_token = login_doctor()
    if not doc_token:
        return

    headers = {"Authorization": f"Bearer {doc_token}"}
    slots = [
        {"startTime": "2026-07-10T16:00:00+05:30", "endTime": "2026-07-10T16:30:00+05:30"},
        {"startTime": "2026-07-10T16:30:00+05:30", "endTime": "2026-07-10T17:00:00+05:30"},
        {"startTime": "2026-07-10T21:30:00+05:30", "endTime": "2026-07-10T22:00:00+05:30"},
    ]
    res = requests.post(f"{API_BASE}/appointments/slots", json=slots, headers=headers, timeout=30)
    res.raise_for_status()


def clear_chats() -> None:
    subprocess.run([sys.executable, "-B", str(ROOT / "backend" / "clear_ai_chats.py")], check=False)
    print("Chat history cleared.")


def get_websocket_url(token: str) -> str:
    if ROLE == "patient":
        return f"{WS_BASE}/chat/ai/patient/ws?token={token}"
    return f"{WS_BASE}/chat/ai/doctor/ws?token={token}&patient_id={TARGET_PATIENT_ID}"


async def run_workflow_query(query: str, ws_url: str) -> str:
    final_response = ""
    async with websockets.connect(ws_url) as ws:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
            data = json.loads(msg)
            if data.get("type") == "history":
                break

        await ws.send(query)

        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=180.0)
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                return msg

            if isinstance(data, dict):
                if data.get("type") == "final":
                    return str(data.get("content", ""))
                if data.get("type") == "error":
                    return f"SERVER ERROR: {data.get('content', '')}"
            else:
                return msg


async def judge_result(query: str, expected_output: str, output: str) -> str:
    if not JUDGE_MODEL:
        raise RuntimeError("OPENAI_MODEL is required for the standalone judge client")

    prompt = f"""
You are a regression test judge for the DocTalk healthcare workflow.

Return exactly one word: PASS or FAIL.

Judge the output by intent, not by exact wording.

PASS if:
- the response matches the user's intent
- the response is a correct medical answer, summary, redirect, refusal, or appointment action
- the response is shorter or more verbose than expected but still clearly correct

FAIL if:
- the response is unrelated
- the response contradicts the query
- the response misses the core medical meaning or action
- the response is clearly broken or incomplete

Important:
- A polite refusal for an out-of-scope query is PASS.
- A general medical explanation for anemia, fever, cough, medications, allergies, or similar health questions is PASS.
- A detailed blood report summary is PASS.
- An appointment availability, booking, or cancellation response that matches the intent is PASS.

Query: {query}
Expected intent: {expected_output}
Actual output: {output}
""".strip()

    verdict = await get_judge_client().chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=10,
    )
    verdict = str(verdict.choices[0].message.content or "").strip().upper()
    if verdict.startswith("PASS"):
        return "PASS"
    if verdict.startswith("FAIL"):
        return "FAIL"
    return "FAIL"


def load_rows() -> list[dict[str, str]]:
    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(
                {
                    "query": str(row.get("query", "")).strip(),
                    "expectes_output": str(row.get("expectes_output", row.get("expected_output", ""))).strip(),
                    "output": str(row.get("output", "")).strip(),
                    "result": str(row.get("result", "")).strip(),
                    "response_time_seconds": str(row.get("response_time_seconds", "")).strip(),
                }
            )
        return rows


def save_rows(rows: list[dict[str, Any]]) -> None:
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["query", "expectes_output", "output", "result", "response_time_seconds"],
        )
        writer.writeheader()
        writer.writerows(rows)


async def main() -> None:
    rows = load_rows()
    if AUTO_CREATE_DOCTOR_SLOTS:
        try:
            create_doctor_slots()
        except Exception:
            pass

    token = login_patient()
    if not token:
        raise RuntimeError("Failed to authenticate patient")

    ws_url = get_websocket_url(token)

    for idx, row in enumerate(rows, start=1):
        if CLEAR_CHAT_BEFORE_EACH_TEST:
            clear_chats()

        query = row["query"]
        expected_output = row["expectes_output"]

        start = time.time()
        output = await run_workflow_query(query, ws_url)
        elapsed_ms = int((time.time() - start) * 1000)
        elapsed_seconds = round(elapsed_ms / 1000, 3)

        result = await judge_result(query, expected_output, output)

        row["output"] = output.replace("\n", "\\n").replace("\r", "")
        row["result"] = result
        row["response_time_seconds"] = f"{elapsed_seconds:.3f}"
        print(f"[{idx}/{len(rows)}] {result} {elapsed_ms}ms - {query}")
        save_rows(rows)


if __name__ == "__main__":
    asyncio.run(main())
