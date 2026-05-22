import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonHealthCareStore:
    def __init__(self, data_root: str | None = None) -> None:
        default_root = Path(__file__).resolve().parents[3] / "data"
        self.data_root = Path(data_root or os.getenv("HEALTHCARE_DATA_ROOT") or default_root)
        self.patients_root = self.data_root / "patients"
        self.doctors_root = self.data_root / "doctors"
        self._lock = threading.RLock()

        self.patients_root.mkdir(parents=True, exist_ok=True)
        self.doctors_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp.replace(path)

    def list_doctors(self) -> list[dict[str, Any]]:
        with self._lock:
            doctors: list[dict[str, Any]] = []
            for doctor_id in sorted(os.listdir(self.doctors_root)):
                profile_path = self.doctors_root / doctor_id / "doctor_profile.json"
                profile = self._read_json(profile_path, {})
                if profile:
                    profile.setdefault("doctor_id", doctor_id)
                    doctors.append(profile)
            return doctors

    def get_patient_profile(self, username: str) -> dict[str, Any]:
        with self._lock:
            return self._read_json(self.patients_root / username / "profile.json", {})

    def create_patient_profile(self, username: str, profile: dict[str, Any]) -> bool:
        with self._lock:
            profile_path = self.patients_root / username / "profile.json"
            if profile_path.exists():
                return False

            payload = {
                "username": username,
                **{k: v for k, v in profile.items() if v is not None},
            }
            self._write_json(profile_path, payload)

            appointments_path = self.patients_root / username / "appointments.json"
            if not appointments_path.exists():
                self._write_json(appointments_path, [])

            return True

    def update_patient_profile(self, username: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self.get_patient_profile(username)
            current.update({k: v for k, v in updates.items() if v is not None})
            current.setdefault("username", username)
            self._write_json(self.patients_root / username / "profile.json", current)
            return current

    def get_doctor_profile(self, doctor_id: str) -> dict[str, Any]:
        with self._lock:
            return self._read_json(self.doctors_root / doctor_id / "doctor_profile.json", {})

    def create_doctor_profile(self, doctor_id: str, profile: dict[str, Any]) -> bool:
        with self._lock:
            profile_path = self.doctors_root / doctor_id / "doctor_profile.json"
            if profile_path.exists():
                return False

            payload = {
                "doctor_id": doctor_id,
                **{k: v for k, v in profile.items() if v is not None},
            }
            self._write_json(profile_path, payload)

            requests_path = self.doctors_root / doctor_id / "requests.json"
            if not requests_path.exists():
                self._write_json(requests_path, [])

            return True

    def update_doctor_profile(self, doctor_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self.get_doctor_profile(doctor_id)
            current.update({k: v for k, v in updates.items() if v is not None})
            current.setdefault("doctor_id", doctor_id)
            self._write_json(self.doctors_root / doctor_id / "doctor_profile.json", current)
            return current

    def get_patient_appointments(self, username: str) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_json(self.patients_root / username / "appointments.json", [])

    def get_doctor_requests(self, doctor_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_json(self.doctors_root / doctor_id / "requests.json", [])

    def create_appointment(self, appointment: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            appointment_id = f"apt_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
            payload = {
                "id": appointment_id,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                **appointment,
            }

            patient_file = self.patients_root / payload["patient"] / "appointments.json"
            doctor_file = self.doctors_root / payload["doctor_id"] / "requests.json"

            patient_items = self._read_json(patient_file, [])
            patient_items.insert(0, payload)
            self._write_json(patient_file, patient_items)

            doctor_items = self._read_json(doctor_file, [])
            doctor_items.insert(0, payload)
            self._write_json(doctor_file, doctor_items)

            return payload

    def check_credentials(self, role: str, username: str, password: str) -> bool:
        with self._lock:
            if role == "patient":
                profile = self.get_patient_profile(username)
            else:
                profile = self.get_doctor_profile(username)

            if not profile:
                return False

            saved_password = profile.get("password")
            if saved_password is None:
                return True
            return str(saved_password) == str(password)
