"""Simple smoke test runner for the modular FastAPI app.

Runs a few safe endpoints to validate integration without calling external
LLM services or heavy IO.
"""
import importlib
import sys
import json
from fastapi.testclient import TestClient


def main():
    try:
        m = importlib.import_module("backend.app.main")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"import_error: {e}"}))
        sys.exit(2)

    app = getattr(m, "app")
    client = TestClient(app)

    results = []

    # 1. Health
    r = client.get("/api/health")
    results.append({"endpoint": "/api/health", "status_code": r.status_code, "json": r.json() if r.status_code == 200 else None})

    # 2. Doctors (public)
    r = client.get("/api/doctors")
    try:
        body = r.json()
    except Exception:
        body = None
    results.append({"endpoint": "/api/doctors", "status_code": r.status_code, "json": body})

    # 3. Register (auth) - 409 (exists) is acceptable
    payload = {"role": "patient", "username": "smoke_test_user", "password": "pass", "name": "Smoke Test", "email": "", "phone": ""}
    r = client.post("/api/auth/register", json=payload)
    try:
        body = r.json()
    except Exception:
        body = None
    results.append({"endpoint": "/api/auth/register", "status_code": r.status_code, "json": body})

    # 4. Login
    payload = {"role": "patient", "username": "smoke_test_user", "password": "pass"}
    r = client.post("/api/auth/login", json=payload)
    try:
        body = r.json()
    except Exception:
        body = None
    results.append({"endpoint": "/api/auth/login", "status_code": r.status_code, "json": body})

    # 5. Patient session (requires cookie/session)
    r = client.get("/api/patient_session")
    try:
        body = r.json()
    except Exception:
        body = None
    results.append({"endpoint": "/api/patient_session", "status_code": r.status_code, "json": body})

    # 6. Chat sessions (should return ok list)
    r = client.get("/api/chat_sessions")
    try:
        body = r.json()
    except Exception:
        body = None
    results.append({"endpoint": "/api/chat_sessions", "status_code": r.status_code, "json": body})

    # treat register 409 as OK (already exists)
    ok = True
    for r in results:
        if r["endpoint"] == "/api/auth/register":
            if r["status_code"] not in (200, 201, 409):
                ok = False
                break
        else:
            if not (200 <= r["status_code"] < 300):
                ok = False
                break

    print(json.dumps({"ok": ok, "results": results}, indent=2))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
