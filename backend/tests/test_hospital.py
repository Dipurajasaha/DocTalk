"""
Comprehensive tests for Hospital database interactions.

Tests all HospitalService methods that interact with Supabase PostgreSQL.

Run this file directly:
    cmd /c "cd /d DocTalk\backend && .venv\Scripts\python.exe -m tests.test_hospital"
  OR
    cd DocTalk\backend && .venv\Scripts\python.exe -m tests.test_hospital
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from typing import Any

# Add backend parent to path so 'backend' is importable as a package
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_HERE)
_PARENT = os.path.dirname(_BACKEND_DIR)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from backend.core.database import connect_prisma, disconnect_prisma, prisma
from backend.services.hospital_service import HospitalService


# ── helpers ──────────────────────────────────────────────────────────────


def async_test(coro):
    """Decorator that runs an async test method."""
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


# unique prefix so parallel runs don't collide
_PREFIX = f"test_{os.urandom(4).hex()}"


def uid(name: str) -> str:
    return f"{_PREFIX}_{name}"


def ok(result: Any, msg: str = ""):
    """Custom assertion: value should be truthy."""
    assert result, msg or f"Expected truthy value, got {result}"


def eq(a: Any, b: Any, msg: str = ""):
    assert a == b, msg or f"Expected {a} == {b}"


# ── test class ───────────────────────────────────────────────────────────


class TestHospitalDB(unittest.TestCase):
    """Live integration tests against the Supabase PostgreSQL database."""

    @classmethod
    @async_test
    async def setUpClass(cls):
        """Connect to the database once before all tests."""
        await connect_prisma()
        cls.service = HospitalService()

    @classmethod
    @async_test
    async def tearDownClass(cls):
        """Clean up all test data and disconnect."""
        # Clean up any test hospital data
        test_id_prefix = f"{_PREFIX}_"
        try:
            # Fetch all test hospitals
            hospitals = await prisma.hospital.find_many(
                where={"hospitalId": {"starts_with": test_id_prefix}}
            )
            for h in hospitals:
                # Delete associated news and reports first (cascade should handle it,
                # but being explicit)
                await prisma.hospitalnews.delete_many(
                    where={"hospitalId": h.hospitalId}
                )
                await prisma.symptomreport.delete_many(
                    where={"hospitalId": h.hospitalId}
                )
            # Delete all test hospitals
            await prisma.hospital.delete_many(
                where={"hospitalId": {"starts_with": test_id_prefix}}
            )
        except Exception:
            pass  # Best-effort cleanup

        await disconnect_prisma()

    # ─────────────────────────── AUTH TESTS ───────────────────────────

    @async_test
    async def test_01_register_hospital(self):
        """Register a new hospital and verify it's stored in the database."""
        hid = uid("hospital_a")
        result = await self.service.register(
            hospital_id=hid,
            name="Test Hospital Alpha",
            password="StrongPass123!",
        )
        ok(result, "register should return a result dict")
        ok(result.get("access_token"), "response should contain access_token")
        eq(result["hospital_id"], hid, "hospital_id should match")
        eq(result["role"], "hospital", "role should be hospital")

        # Verify it actually exists in DB
        db_hospital = await prisma.hospital.find_unique(
            where={"hospitalId": hid}
        )
        ok(db_hospital, "hospital should exist in database")
        eq(db_hospital.name, "Test Hospital Alpha")
        eq(db_hospital.hospitalId, hid)

    @async_test
    async def test_02_register_duplicate_hospital(self):
        """Registering the same hospital_id twice should raise 409."""
        hid = uid("hospital_dup")
        await self.service.register(
            hospital_id=hid,
            name="First",
            password="Pass1234!",
        )
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            await self.service.register(
                hospital_id=hid,
                name="Second",
                password="Pass5678!",
            )
        eq(ctx.exception.status_code, 409, "duplicate should raise 409")

    @async_test
    async def test_03_login_success(self):
        """Valid credentials should return a token."""
        hid = uid("hospital_login")
        await self.service.register(
            hospital_id=hid,
            name="Login Hospital",
            password="LoginPass123!",
        )
        result = await self.service.login(
            hospital_id=hid,
            password="LoginPass123!",
        )
        ok(result.get("access_token"), "successful login should return access_token")
        eq(result["hospital_id"], hid)
        eq(result["role"], "hospital")

    @async_test
    async def test_04_login_wrong_password(self):
        """Wrong password should raise 401."""
        hid = uid("hospital_wrong")
        await self.service.register(
            hospital_id=hid,
            name="Wrong Pass",
            password="CorrectPass1!",
        )
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            await self.service.login(
                hospital_id=hid,
                password="WrongPass1!",
            )
        eq(ctx.exception.status_code, 401, "wrong password should raise 401")

    @async_test
    async def test_05_login_nonexistent_hospital(self):
        """Login with non-existent hospital_id should raise 401."""
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            await self.service.login(
                hospital_id="nonexistent_hospital_id_xyz",
                password="SomePass123!",
            )
        eq(ctx.exception.status_code, 401, "non-existent hospital should raise 401")

    # ─────────────────────── SYMPTOM REPORT TESTS ───────────────────────

    @async_test
    async def test_06_create_symptom_report(self):
        """Create a symptom report and verify it's stored."""
        hid = uid("hospital_report")
        await self.service.register(
            hospital_id=hid,
            name="Report Hospital",
            password="ReportPass1!",
        )

        report = await self.service.create_symptom_report(
            hospital_id=hid,
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
        ok(report, "create_symptom_report should return a dict")
        eq(report["disease_name"], "Influenza")
        eq(report["patient_name"], "John Doe")
        eq(report["severity"], "moderate")
        ok(report.get("id"), "report should have an id")

        # Verify in DB
        db_report = await prisma.symptomreport.find_unique(
            where={"id": report["id"]}
        )
        ok(db_report, "report should exist in database")
        eq(db_report.diseaseName, "Influenza")

    @async_test
    async def test_07_get_hospital_reports(self):
        """Fetch paginated reports for a hospital."""
        hid = uid("hospital_reports_list")
        await self.service.register(
            hospital_id=hid,
            name="List Reports Hospital",
            password="ListPass1!",
        )

        # Create 3 reports
        for i in range(3):
            await self.service.create_symptom_report(
                hospital_id=hid,
                data={
                    "patient_name": f"Patient {i}",
                    "patient_age": 30 + i,
                    "patient_gender": "female",
                    "disease_name": "COVID-19",
                    "symptoms": ["cough", "fever"],
                    "severity": "mild",
                },
            )

        result = await self.service.get_hospital_reports(
            hospital_id=hid,
            page=1,
            per_page=10,
        )
        ok(result, "get_hospital_reports should return a dict")
        ok(result["total"] >= 3, f"expected at least 3 reports, got {result['total']}")
        ok(len(result["reports"]) >= 3, f"expected at least 3 reports in list, got {len(result['reports'])}")
        eq(result["page"], 1)
        eq(result["per_page"], 10)

    @async_test
    async def test_08_get_hospital_reports_pagination(self):
        """Test pagination — page 2 should return results after skipping."""
        hid = uid("hospital_paginate")
        await self.service.register(
            hospital_id=hid,
            name="Paginate Hospital",
            password="PagPass1!",
        )

        # Create 5 reports
        for i in range(5):
            await self.service.create_symptom_report(
                hospital_id=hid,
                data={
                    "patient_name": f"Pag Patient {i}",
                    "patient_age": 25,
                    "patient_gender": "male",
                    "disease_name": "Diabetes",
                    "symptoms": ["thirst", "frequent urination"],
                    "severity": "moderate",
                },
            )

        # Page 1 with per_page=2
        page1 = await self.service.get_hospital_reports(
            hospital_id=hid,
            page=1,
            per_page=2,
        )
        eq(len(page1["reports"]), 2, "page 1 should have exactly 2 reports")
        eq(page1["total"], 5)

        # Page 3 (should have 1 report: 5 - 2*2 = 1)
        page3 = await self.service.get_hospital_reports(
            hospital_id=hid,
            page=3,
            per_page=2,
        )
        eq(len(page3["reports"]), 1, "page 3 should have 1 report")

    @async_test
    async def test_09_get_report_by_id(self):
        """Fetch a specific report by its ID."""
        hid = uid("hospital_get_one")
        await self.service.register(
            hospital_id=hid,
            name="Get One Hospital",
            password="GetPass1!",
        )

        created = await self.service.create_symptom_report(
            hospital_id=hid,
            data={
                "patient_name": "Unique Patient",
                "patient_age": 60,
                "patient_gender": "female",
                "disease_name": "Hypertension",
                "symptoms": ["headache", "dizziness"],
                "severity": "severe",
            },
        )

        fetched = await self.service.get_report_by_id(created["id"])
        ok(fetched, "should fetch report by id")
        eq(fetched["id"], created["id"])
        eq(fetched["disease_name"], "Hypertension")
        eq(fetched["severity"], "severe")
        eq(fetched["patient_name"], "Unique Patient")

    @async_test
    async def test_10_get_report_by_id_not_found(self):
        """Fetching non-existent report id should raise 404."""
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            await self.service.get_report_by_id("non-existent-report-id-xyz")
        eq(ctx.exception.status_code, 404)

    # ─────────────────────── HOSPITAL NEWS TESTS ───────────────────────

    @async_test
    async def test_11_create_hospital_news(self):
        """Create hospital news and verify it's stored."""
        hid = uid("hospital_news_create")
        await self.service.register(
            hospital_id=hid,
            name="News Hospital",
            password="NewsPass1!",
        )

        news = await self.service.create_news(
            hospital_id=hid,
            data={
                "title": "New Wing Opening",
                "content": "We are opening a new wing for cardiology.",
                "category": "announcement",
                "is_global": True,
                "priority": 10,
            },
        )
        ok(news, "create_news should return a dict")
        eq(news["title"], "New Wing Opening")
        eq(news["category"], "announcement")
        eq(news["is_global"], True)
        eq(news["priority"], 10)
        ok(news.get("id"), "news should have an id")

        # Verify in DB
        db_news = await prisma.hospitalnews.find_unique(
            where={"id": news["id"]}
        )
        ok(db_news, "news should exist in database")

    @async_test
    async def test_12_get_hospital_news(self):
        """List news for a specific hospital."""
        hid = uid("hospital_news_list")
        await self.service.register(
            hospital_id=hid,
            name="List News Hospital",
            password="NewsList1!",
        )

        for i in range(3):
            await self.service.create_news(
                hospital_id=hid,
                data={
                    "title": f"News Item {i}",
                    "content": f"Content for item {i}",
                    "category": "general",
                },
            )

        news_list = await self.service.get_hospital_news(hospital_id=hid)
        ok(len(news_list) >= 3, f"expected at least 3 news items, got {len(news_list)}")

    @async_test
    async def test_13_get_latest_news_all(self):
        """Fetch latest news across all hospitals."""
        hid = uid("hospital_news_global")
        await self.service.register(
            hospital_id=hid,
            name="Global News Hospital",
            password="GlobalN1!",
        )

        await self.service.create_news(
            hospital_id=hid,
            data={
                "title": "Global Announcement",
                "content": "This is a global announcement.",
                "category": "announcement",
                "is_global": True,
                "priority": 5,
            },
        )

        latest = await self.service.get_latest_news_all(limit=5)
        ok(len(latest) >= 1, "should fetch at least 1 news item")
        # Check if our news is in the results
        titles = [n["title"] for n in latest]
        ok("Global Announcement" in titles, "our global news should be in the results")

    # ─────────────────────── AGGREGATION TESTS ───────────────────────

    @async_test
    async def test_14_get_disease_summary(self):
        """Aggregate report counts grouped by disease."""
        hid = uid("hospital_disease_summary")
        await self.service.register(
            hospital_id=hid,
            name="Disease Summary Hospital",
            password="DisSum1!",
        )

        # Create reports with different diseases
        diseases = ["Malaria", "Dengue", "Malaria", "Typhoid"]
        for d in diseases:
            await self.service.create_symptom_report(
                hospital_id=hid,
                data={
                    "patient_name": "Test",
                    "patient_age": 30,
                    "patient_gender": "male",
                    "disease_name": d,
                    "symptoms": ["fever"],
                    "severity": "moderate",
                },
            )

        summary = await self.service.get_disease_summary(hospital_id=hid)
        ok(len(summary) >= 3, f"expected at least 3 disease groups, got {len(summary)}")
        # Find Malaria count
        malaria_entry = next((s for s in summary if s["disease"] == "Malaria"), None)
        ok(malaria_entry, "Malaria should be in summary")
        eq(malaria_entry["count"], 2, "Malaria should have count 2")

    @async_test
    async def test_15_get_severity_breakdown(self):
        """Aggregate report counts by severity level."""
        hid = uid("hospital_severity")
        await self.service.register(
            hospital_id=hid,
            name="Severity Hospital",
            password="SevPass1!",
        )

        severities = ["mild", "moderate", "severe", "critical"]
        for s in severities:
            await self.service.create_symptom_report(
                hospital_id=hid,
                data={
                    "patient_name": "Test",
                    "patient_age": 40,
                    "patient_gender": "female",
                    "disease_name": "Common Cold",
                    "symptoms": ["cough"],
                    "severity": s,
                },
            )

        breakdown = await self.service.get_severity_breakdown(hospital_id=hid)
        eq(breakdown["mild"], 1)
        eq(breakdown["moderate"], 1)
        eq(breakdown["severe"], 1)
        eq(breakdown["critical"], 1)

    # ─────────────────────── DASHBOARD TESTS ───────────────────────

    @async_test
    async def test_16_get_dashboard(self):
        """Fetch the full dashboard for a hospital."""
        hid = uid("hospital_dashboard")
        await self.service.register(
            hospital_id=hid,
            name="Dashboard Hospital",
            password="DashPass1!",
        )

        # Create some reports and news
        for i in range(2):
            await self.service.create_symptom_report(
                hospital_id=hid,
                data={
                    "patient_name": f"Dash Patient {i}",
                    "patient_age": 35,
                    "patient_gender": "male",
                    "disease_name": "Allergy",
                    "symptoms": ["rash", "itching"],
                    "severity": "mild" if i == 0 else "moderate",
                },
            )

        await self.service.create_news(
            hospital_id=hid,
            data={
                "title": "Dash News",
                "content": "Dashboard hospital news.",
            },
        )

        dash = await self.service.get_dashboard(hospital_id=hid)
        ok(dash, "get_dashboard should return a result")
        eq(dash["hospital_name"], "Dashboard Hospital")
        eq(dash["hospital_id"], hid)
        ok(dash["total_reports"] >= 2, f"expected >=2 reports, got {dash['total_reports']}")
        ok(dash["total_news"] >= 1, f"expected >=1 news, got {dash['total_news']}")
        ok(len(dash["recent_reports"]) >= 2, "should have at least 2 recent reports")
        ok(len(dash["disease_summary"]) >= 1, "should have disease summary")
        ok("mild" in dash["severity_breakdown"], "severity breakdown should have mild")

    # ─────────────────────── EDGE CASES ───────────────────────

    @async_test
    async def test_17_register_missing_fields(self):
        """Register with empty fields should raise 422."""
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            await self.service.register(
                hospital_id="",
                name="",
                password="",
            )
        eq(ctx.exception.status_code, 422)

    @async_test
    async def test_18_report_for_nonexistent_hospital(self):
        """Creating a report for non-existent hospital should raise 404."""
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            await self.service.create_symptom_report(
                hospital_id="i_do_not_exist_99999",
                data={
                    "disease_name": "Test",
                    "symptoms": ["test"],
                },
            )
        eq(ctx.exception.status_code, 404)

    @async_test
    async def test_19_anonymous_report(self):
        """Create an anonymous report."""
        hid = uid("hospital_anon")
        await self.service.register(
            hospital_id=hid,
            name="Anon Hospital",
            password="AnonPass1!",
        )

        report = await self.service.create_symptom_report(
            hospital_id=hid,
            data={
                "patient_name": None,
                "patient_age": None,
                "disease_name": "Anon Disease",
                "symptoms": ["symptom1"],
                "severity": "mild",
                "is_anonymous": True,
            },
        )
        eq(report["is_anonymous"], True)
        ok(report["patient_name"] is None, "anonymous report should have no patient name")

    @async_test
    async def test_20_get_disease_summary_global(self):
        """get_disease_summary without hospital_id returns all hospitals."""
        summary = await self.service.get_disease_summary(hospital_id=None)
        ok(isinstance(summary, list), "should return a list")
        if summary:
            ok("disease" in summary[0], "result should have disease key")
            ok("count" in summary[0], "result should have count key")


if __name__ == "__main__":
    unittest.main(verbosity=2)