"""Insert a dummy PatientHistoryRecord row for quick manual testing.

Usage (from backend/):
    ..\\.venv\\Scripts\\python.exe scripts/seed_patient_history_record.py

Set PATIENT_ID env var to target a specific patient, otherwise a test id is used.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Allow importing backend packages when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from prisma import Prisma, Json

load_dotenv("G:/My_Projects/final_year_health_test/DocTalk/.env", override=True)

_PHR_JSON_FIELDS = ("conditions", "medications", "allergies")


def _wrap_json_fields(data: dict) -> dict:
    for field in _PHR_JSON_FIELDS:
        if field in data and data[field] is not None:
            data[field] = Json(data[field])
    return data


async def main() -> None:
    patient_id = os.environ.get("PATIENT_ID", "seed_test_patient_001")
    db = Prisma()
    await db.connect()

    data = _wrap_json_fields(
        {
            "bloodGroup": "O+",
            "weight": "72",
            "bmi": "23.4",
            "bloodPressure": "120/80",
            "heartRate": "78",
            "spo2": "98",
            "temperature": "36.8",
            "bloodSugarFasting": "92",
            "bloodSugarPP": "130",
            "conditions": [
                {"id": "seed:asthma", "name": "Asthma", "value": "Mild"},
            ],
            "medications": [
                {"id": "seed:paracetamol", "name": "Paracetamol", "value": "500mg"},
            ],
            "allergies": [
                {"id": "seed:peanuts", "name": "Peanuts", "value": "Severe"},
            ],
        }
    )
    data["patientId"] = patient_id

    created = await db.patienthistoryrecord.create(data=data)
    print("Inserted PatientHistoryRecord:", created.id, "for patient", patient_id)

    latest = await db.patienthistoryrecord.find_first(
        where={"patientId": patient_id},
        order=[{"recordDate": "desc"}, {"createdAt": "desc"}],
    )
    print("Latest record fetched OK:", latest.id if latest else None)

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
