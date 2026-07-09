"""
Self-contained hospital DB integration test runner.
Tests all HospitalService methods against live Supabase PostgreSQL.

Run from the DocTalk/backend directory:
    .venv\Scripts\python.exe tests\run_hospital_tests.py
"""

import asyncio
import os
import sys
import traceback

# ── Path setup: make DocTalk/ a namespace package so
#    "from backend.services.hospital_service" resolves correctly ──
_HERE = os.path.dirname(os.path.abspath(__file__))        # backend/tests
_BACKEND_DIR = os.path.dirname(_HERE)                     # backend
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)              # DocTalk  (has __init__.py)

if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)
os.chdir(_BACKEND_DIR)

# Now we can import using the full "backend" package path.
# This way the relative import (from ..core.database) inside hospital_service.py resolves correctly.
from backend.core.database import connect_prisma, disconnect_prisma, prisma
from backend.core.security import hash_password, verify_password
from fastapi import HTTPException


PASS = 0
FAIL = 0
SKIP = 0

_COLOR_RED = "\033[91m"
_COLOR_GREEN = "\033[92m"
_COLOR_YELLOW = "\033[93m"
_COLOR_CYAN = "\033[96m"
_COLOR_RESET = "\033[0m"

def ok(msg):
    print(f"  {_COLOR_GREEN}[PASS]{_COLOR_RESET} {msg}")

def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  {_COLOR_RED}[FAIL]{_COLOR_RESET} {msg}")

def skip(msg):
    global SKIP
    SKIP += 1
    print(f"  {_COLOR_YELLOW}[SKIP]{_COLOR_RESET} {msg}")

def heading(num, title):
    print(f"\n{_COLOR_CYAN}─── [{num}] {title} ───{_COLOR_RESET}")


async def main():
    global PASS

    print(("+" + "-" * 60 + "+").replace("\\S", "S"))
    print("| DocTalk Hospital Database Integration Tests")
    print("| Testing against Supabase PostgreSQL")
    print(("+" + "-" * 60 + "+").replace("\\S", "S"))
    print()

    # ── Connect ──────────────────────────────────────────────────────
    heading("00", "Database Connection")
    try:
        await connect_prisma()
        ok("Connected to Supabase PostgreSQL via Prisma")
    except Exception as e:
        fail(f"Could not connect to database: {e}")
        print("\nAborting: database connection required for all tests.")
        sys.exit(1)

    # ── 1. REGISTRATION ───────────────────────────────────────────────
    heading("01", "Hospital Registration")
    try:
        from backend.services.hospital_service import HospitalService
        service = HospitalService()
    except Exception as e:
        fail(f"Could not import HospitalService: {e}")
        traceback.print_exc()
        print("\nAborting: HospitalService required.")
        await disconnect_prisma()
        sys.exit(1)

    test_prefix = f"test_{os.urandom(4).hex()}"

    hid1 = f"{test_prefix}_hospital_a"
    try:
        result = await service.register(
            hospital_id=hid1,
            name="Test Hospital Alpha",
            password="StrongPass123!",
        )
        assert result is not None, "register returned None"
        assert result.get("access_token"), "No access_token in response"
        assert result["hospital_id"] == hid1, f"hospital_id mismatch: {result['hospital_id']} != {hid1}"
        assert result["role"] == "hospital", f"role mismatch: {result['role']}"
        ok(f"Registered hospital '{hid1}' and got JWT token")

        # Verify in DB
        db_h = await prisma.hospital.find_unique(where={"hospitalId": hid1})
        assert db_h is not None, "Hospital not found in database"
        assert db_h.name == "Test Hospital Alpha", f"Name mismatch: {db_h.name}"
        assert db_h.password != "StrongPass123!", "Password should be hashed"
        ok(f"Hospital exists in database with name='{db_h.name}' and password is hashed")
        PASS += 2
    except Exception as e:
        fail(f"Registration test failed: {e}\n{traceback.format_exc()}")

    # ── 2. DUPLICATE REGISTRATION ──────────────────────────────────────
    heading("02", "Duplicate Registration (should return 409)")
    try:
        await service.register(hospital_id=hid1, name="Duplicate", password="Pass1234!")
        fail("Duplicate registration should have raised HTTPException(409)")
    except HTTPException as e:
        assert e.status_code == 409, f"Expected 409, got {e.status_code}"
        ok("Duplicate registration correctly raises 409 Conflict")
        PASS += 1
    except Exception as e:
        fail(f"Unexpected error: {e}\n{traceback.format_exc()}")

    # ── 3. MISSING FIELDS REGISTRATION ────────────────────────────────
    heading("03", "Registration with Empty Fields (should return 422)")
    try:
        await service.register(hospital_id="", name="", password="")
        fail("Empty fields should raise HTTPException(422)")
    except HTTPException as e:
        assert e.status_code == 422, f"Expected 422, got {e.status_code}"
        ok("Empty fields correctly raises 422")
        PASS += 1
    except Exception as e:
        fail(f"Unexpected error: {e}\n{traceback.format_exc()}")

    # ── 4. LOGIN SUCCESS ──────────────────────────────────────────────
    heading("04", "Hospital Login (valid credentials)")
    try:
        result = await service.login(hospital_id=hid1, password="StrongPass123!")
        assert result is not None, "Login returned None"
        assert result.get("access_token"), "No access_token in login response"
        assert result["hospital_id"] == hid1
        assert result["role"] == "hospital"
        ok("Successful login with valid credentials returns JWT token")
        PASS += 1
    except Exception as e:
        fail(f"Login with valid credentials failed: {e}\n{traceback.format_exc()}")

    # ── 5. LOGIN WRONG PASSWORD ────────────────────────────────────────
    heading("05", "Hospital Login (wrong password -> 401)")
    try:
        await service.login(hospital_id=hid1, password="WrongPassword!")
        fail("Wrong password should raise 401")
    except HTTPException as e:
        assert e.status_code == 401, f"Expected 401, got {e.status_code}"
        ok("Wrong password correctly raises 401 Unauthorized")
        PASS += 1
    except Exception as e:
        fail(f"Unexpected error: {e}\n{traceback.format_exc()}")

    # ── 6. LOGIN NONEXISTENT ──────────────────────────────────────────
    heading("06", "Hospital Login (non-existent hospital -> 401)")
    try:
        await service.login(hospital_id="i_dont_exist_999", password="SomePass123!")
        fail("Non-existent hospital should raise 401")
    except HTTPException as e:
        assert e.status_code == 401, f"Expected 401, got {e.status_code}"
        ok("Non-existent hospital correctly raises 401 Unauthorized")
        PASS += 1
    except Exception as e:
        fail(f"Unexpected error: {e}\n{traceback.format_exc()}")

    # ── 7. CREATE SYMPTOM REPORT ──────────────────────────────────────
    heading("07", "Symptom Report Creation")
    try:
        report = await service.create_symptom_report(
            hospital_id=hid1,
            data={
                "patient_name": "John Doe",
                "patient_age": 45,
                "patient_gender": "male",
                "disease_name": "Influenza",
                "symptoms": ["fever", "cough", "fatigue"],
                "new_symptoms": ["loss of appetite"],
                "severity": "moderate",
                "additional_notes": "Has underlying condition",
                "is_anonymous": False,
            },
        )
        assert report is not None
        assert report["disease_name"] == "Influenza"
        assert report["patient_name"] == "John Doe"
        assert report["severity"] == "moderate"
        assert report.get("id") is not None
        # Verify in DB
        db_r = await prisma.symptomreport.find_unique(where={"id": report["id"]})
        assert db_r is not None, "Report not found in database"
        assert db_r.diseaseName == "Influenza"
        ok(f"Created symptom report (id={report['id']}) and verified in database")
        PASS += 1
    except Exception as e:
        fail(f"Symptom report creation failed: {e}\n{traceback.format_exc()}")

    # ── 8. LIST HOSPITAL REPORTS ─────────────────────────────────────
    heading("08", "List Hospital Reports")
    try:
        for i in range(3):
            await service.create_symptom_report(
                hospital_id=hid1,
                data={
                    "patient_name": f"Patient {i}",
                    "patient_age": 30 + i,
                    "patient_gender": "female",
                    "disease_name": "COVID-19",
                    "symptoms": ["cough", "fever"],
                    "severity": "mild",
                },
            )
        result = await service.get_hospital_reports(hospital_id=hid1, page=1, per_page=10)
        assert result["total"] >= 4, f"Expected >=4 reports, got {result['total']}"
        assert len(result["reports"]) >= 4, "Expected >=4 reports in list"
        assert result["page"] == 1
        assert result["per_page"] == 10
        ok(f"Listed reports: total={result['total']}, page={result['page']}")
        PASS += 1
    except Exception as e:
        fail(f"List reports failed: {e}\n{traceback.format_exc()}")

    # ── 9. PAGINATION ──────────────────────────────────────────────────
    heading("09", "Report Pagination")
    try:
        hid_pag = f"{test_prefix}_paginate"
        await service.register(hospital_id=hid_pag, name="Paginate Test", password="PagPass1!")
        for i in range(5):
            await service.create_symptom_report(
                hospital_id=hid_pag,
                data={
                    "patient_name": f"Pag {i}",
                    "patient_age": 25,
                    "patient_gender": "male",
                    "disease_name": "Diabetes",
                    "symptoms": ["thirst"],
                    "severity": "moderate",
                },
            )
        page1 = await service.get_hospital_reports(hospital_id=hid_pag, page=1, per_page=2)
        assert len(page1["reports"]) == 2, f"Page 1 should have 2 reports, got {len(page1['reports'])}"
        assert page1["total"] == 5
        page3 = await service.get_hospital_reports(hospital_id=hid_pag, page=3, per_page=2)
        assert len(page3["reports"]) == 1, f"Page 3 should have 1 report, got {len(page3['reports'])}"
        ok(f"Pagination works: page1=2 reports, page3=1 report (total={page1['total']})")
        PASS += 1
    except Exception as e:
        fail(f"Pagination test failed: {e}\n{traceback.format_exc()}")

    # ── 10. FETCH REPORT BY ID ──────────────────────────────────────────
    heading("10", "Get Symptom Report by ID")
    try:
        hid_fetch = f"{test_prefix}_fetch"
        await service.register(hospital_id=hid_fetch, name="Fetch Test", password="FetchPass1!")
        created = await service.create_symptom_report(
            hospital_id=hid_fetch,
            data={
                "patient_name": "Unique Patient",
                "patient_age": 60,
                "patient_gender": "female",
                "disease_name": "Hypertension",
                "symptoms": ["headache", "dizziness"],
                "severity": "severe",
            },
        )
        fetched = await service.get_report_by_id(created["id"])
        assert fetched["id"] == created["id"]
        assert fetched["disease_name"] == "Hypertension"
        assert fetched["severity"] == "severe"
        ok("Fetched report by id and all fields match")
        PASS += 1

        # Non-existent
        try:
            await service.get_report_by_id("non-existent-id-xyz")
            fail("Non-existent report should raise 404")
        except HTTPException as e:
            assert e.status_code == 404
            ok("Non-existent report correctly raises 404 Not Found")
            PASS += 1
    except Exception as e:
        fail(f"Get report tests failed: {e}\n{traceback.format_exc()}")

    # ── 11. REPORT FOR NONEXISTENT HOSPITAL ─────────────────────────────
    heading("11", "Create Report (non-existent hospital -> 404)")
    try:
        await service.create_symptom_report(
            hospital_id="no_such_hospital_999",
            data={"disease_name": "Test", "symptoms": ["test"]},
        )
        fail("Should raise 404 for non-existent hospital")
    except HTTPException as e:
        assert e.status_code == 404
        ok("Report for non-existent hospital correctly raises 404")
        PASS += 1
    except Exception as e:
        fail(f"Unexpected error: {e}\n{traceback.format_exc()}")

    # ── 12. ANONYMOUS REPORT ────────────────────────────────────────────
    heading("12", "Anonymous Symptom Report")
    try:
        hid_anon = f"{test_prefix}_anon"
        await service.register(hospital_id=hid_anon, name="Anon Test", password="AnonPass1!")
        report = await service.create_symptom_report(
            hospital_id=hid_anon,
            data={
                "patient_name": None,
                "patient_age": None,
                "disease_name": "Anon Disease",
                "symptoms": ["symptom1"],
                "severity": "mild",
                "is_anonymous": True,
            },
        )
        assert report["is_anonymous"] is True
        assert report["patient_name"] is None
        ok("Anonymous report created successfully")
        PASS += 1
    except Exception as e:
        fail(f"Anonymous report test failed: {e}\n{traceback.format_exc()}")

    # ── 13. HOSPITAL NEWS ──────────────────────────────────────────────
    heading("13", "Hospital News")
    try:
        news = await service.create_news(
            hospital_id=hid1,
            data={
                "title": "New Wing Opening",
                "content": "We are opening a new wing for cardiology.",
                "category": "announcement",
                "is_global": True,
                "priority": 10,
            },
        )
        assert news["title"] == "New Wing Opening"
        assert news["category"] == "announcement"
        assert news["is_global"] is True
        assert news.get("id") is not None
        db_n = await prisma.hospitalnews.find_unique(where={"id": news["id"]})
        assert db_n is not None, "News not found in database"
        ok(f"Created hospital news (id={news['id']}) and verified in database")
        PASS += 1

        news_list = await service.get_hospital_news(hospital_id=hid1)
        assert len(news_list) >= 1, "Should have at least 1 news item"
        ok(f"Listed {len(news_list)} news items for hospital")

        latest = await service.get_latest_news_all(limit=5)
        assert len(latest) >= 1, "Should fetch at least 1 news item"
        titles = [n["title"] for n in latest]
        assert "New Wing Opening" in titles, "Our news should appear in global latest"
        ok(f"Global latest news feed contains {len(latest)} items, including our test news")
        PASS += 2
    except Exception as e:
        fail(f"Hospital news tests failed: {e}\n{traceback.format_exc()}")

    # ── 14. DISEASE SUMMARY ────────────────────────────────────────────
    heading("14", "Disease Summary (Aggregation)")
    try:
        hid_ds = f"{test_prefix}_disease_summary"
        await service.register(hospital_id=hid_ds, name="Disease Summ", password="DisSum1!")
        diseases = ["Malaria", "Dengue", "Malaria", "Typhoid"]
        for d in diseases:
            await service.create_symptom_report(
                hospital_id=hid_ds,
                data={
                    "patient_name": "Test",
                    "patient_age": 30,
                    "patient_gender": "male",
                    "disease_name": d,
                    "symptoms": ["fever"],
                    "severity": "moderate",
                },
            )
        summary = await service.get_disease_summary(hospital_id=hid_ds)
        assert len(summary) >= 3, f"Expected >=3 disease groups, got {len(summary)}"
        malaria_entry = next((s for s in summary if s["disease"] == "Malaria"), None)
        assert malaria_entry is not None, "Malaria should be in summary"
        assert malaria_entry["count"] == 2, f"Malaria count should be 2, got {malaria_entry['count']}"
        ok("Disease summary: Malaria=2, Dengue=1, Typhoid=1")
        PASS += 1
    except Exception as e:
        fail(f"Disease summary test failed: {e}\n{traceback.format_exc()}")

    # ── 15. SEVERITY BREAKDOWN ─────────────────────────────────────────
    heading("15", "Severity Breakdown (Aggregation)")
    try:
        hid_sb = f"{test_prefix}_severity"
        await service.register(hospital_id=hid_sb, name="Severity Test", password="SevPass1!")
        for s in ["mild", "moderate", "severe", "critical"]:
            await service.create_symptom_report(
                hospital_id=hid_sb,
                data={
                    "patient_name": "Test",
                    "patient_age": 40,
                    "patient_gender": "female",
                    "disease_name": "Common Cold",
                    "symptoms": ["cough"],
                    "severity": s,
                },
            )
        breakdown = await service.get_severity_breakdown(hospital_id=hid_sb)
        assert breakdown["mild"] == 1
        assert breakdown["moderate"] == 1
        assert breakdown["severe"] == 1
        assert breakdown["critical"] == 1
        ok("Severity breakdown: mild=1, moderate=1, severe=1, critical=1")
        PASS += 1
    except Exception as e:
        fail(f"Severity breakdown test failed: {e}\n{traceback.format_exc()}")

    # ── 16. DASHBOARD ──────────────────────────────────────────────────
    heading("16", "Hospital Dashboard")
    try:
        hid_dash = f"{test_prefix}_dashboard"
        await service.register(hospital_id=hid_dash, name="Dash Test", password="DashPass1!")
        for i in range(2):
            await service.create_symptom_report(
                hospital_id=hid_dash,
                data={
                    "patient_name": f"Dash {i}",
                    "patient_age": 35,
                    "patient_gender": "male",
                    "disease_name": "Allergy",
                    "symptoms": ["rash"],
                    "severity": "mild" if i == 0 else "moderate",
                },
            )
        await service.create_news(
            hospital_id=hid_dash,
            data={"title": "Dash News", "content": "Content"},
        )
        dash = await service.get_dashboard(hospital_id=hid_dash)
        assert dash["hospital_name"] == "Dash Test"
        assert dash["total_reports"] >= 2
        assert dash["total_news"] >= 1
        assert len(dash["recent_reports"]) >= 2
        assert len(dash["disease_summary"]) >= 1
        assert "mild" in dash["severity_breakdown"]
        ok(f"Dashboard: reports={dash['total_reports']}, news={dash['total_news']}, disease_groups={len(dash['disease_summary'])}")
        PASS += 1
    except Exception as e:
        fail(f"Dashboard test failed: {e}\n{traceback.format_exc()}")

    # ── 17. GLOBAL DISEASE SUMMARY ────────────────────────────────────
    heading("17", "Global Disease Summary (all hospitals)")
    try:
        summary = await service.get_disease_summary(hospital_id=None)
        assert isinstance(summary, list), "Should return a list"
        ok(f"Global disease summary returned {len(summary)} disease types")
        PASS += 1
    except Exception as e:
        fail(f"Global disease summary failed: {e}\n{traceback.format_exc()}")

    # ── 18. PASSWORD HASHING VERIFICATION ──────────────────────────────
    heading("18", "Password Hashing & Verification")
    try:
        hashed = hash_password("MySecretPass123!")
        assert hashed.startswith("pbkdf2_sha256$"), f"Unexpected hash format: {hashed[:20]}"
        assert verify_password("MySecretPass123!", hashed), "Verify should pass"
        assert not verify_password("WrongPassword!", hashed), "Verify should fail with wrong password"
        assert not verify_password("", hashed), "Empty password should fail"
        assert not verify_password("MySecretPass123!", ""), "Empty hash should fail"
        ok("Password hashing and verification work correctly")
        PASS += 1
    except Exception as e:
        fail(f"Password hashing test failed: {e}\n{traceback.format_exc()}")

    # ── 19. CLEANUP ────────────────────────────────────────────────────
    heading("19", "Cleanup & Database Health Check")
    try:
        result = await prisma.query_raw("SELECT 1 AS ok")
        assert result[0]["ok"] == 1, f"Health check failed: {result}"
        ok(f"Database health check: SELECT 1 AS ok = {result[0]['ok']}")

        prefix = f"{test_prefix}_"
        # Use contains filter (starts_with may not be supported for string id fields)
        hospitals = await prisma.hospital.find_many(where={"hospitalId": {"contains": prefix}})
        for h in hospitals:
            await prisma.hospitalnews.delete_many(where={"hospitalId": h.hospitalId})
            await prisma.symptomreport.delete_many(where={"hospitalId": h.hospitalId})
        deleted = await prisma.hospital.delete_many(where={"hospitalId": {"contains": prefix}})
        ok(f"Cleaned up {deleted} test hospitals and their associated data")

        db_status = await prisma.query_raw("SELECT 1 AS ok")
        assert db_status[0]["ok"] == 1, "DB should still be healthy after cleanup"
        ok("Database connection is healthy after cleanup")
        PASS += 3

        await disconnect_prisma()
        ok("Disconnected from database cleanly")
        PASS += 1
    except Exception as e:
        fail(f"Cleanup/health check failed: {e}\n{traceback.format_exc()}")

    # ── SUMMARY ──────────────────────────────────────────────────────
    total = PASS + FAIL + SKIP
    print(f"\n{'=' * 60}")
    print(f"  Results: {_COLOR_GREEN}{PASS} passed{_COLOR_RESET}, "
          f"{_COLOR_RED}{FAIL} failed{_COLOR_RESET}, "
          f"{_COLOR_YELLOW}{SKIP} skipped{_COLOR_RESET} "
          f"({total} total)")
    print(f"{'=' * 60}")

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())