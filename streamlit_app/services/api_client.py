import os
import requests
from typing import Optional


class ApiClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = base_url or os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def health(self):
        return self.session.get(f"{self.base_url}/health", timeout=5)

    def db_health(self):
        return self.session.get(f"{self.base_url}/db-health", timeout=5)

    def list_ollama_models(self):
        # lightweight probe endpoint if available
        try:
            return self.session.get(f"{self.base_url}/api/ai/models", timeout=5)
        except Exception:
            return None

    def signup_patient(self, username, name, password):
        return self.session.post(f"{self.base_url}/api/auth/patient/signup", json={"username": username, "name": name, "password": password}, timeout=10)

    def signup_doctor(self, doctor_id, name, password):
        return self.session.post(f"{self.base_url}/api/auth/doctor/signup", json={"doctor_id": doctor_id, "name": name, "password": password}, timeout=10)

    def login_doctor(self, doctor_id, password):
        return self.session.post(f"{self.base_url}/api/auth/doctor/login", json={"doctor_id": doctor_id, "password": password}, timeout=10)

    def login_patient(self, username, password):
        return self.session.post(f"{self.base_url}/api/auth/patient/login", json={"username": username, "password": password}, timeout=10)

    def create_appointment(self, token, payload):
        headers = {"Authorization": f"Bearer {token}"}
        return self.session.post(f"{self.base_url}/api/appointments", json=payload, headers=headers, timeout=10)

    def create_consultation(self, token, payload):
        headers = {"Authorization": f"Bearer {token}"}
        return self.session.post(f"{self.base_url}/api/chat/consultations", json=payload, headers=headers, timeout=10)

    def list_consultations(self, token):
        headers = {"Authorization": f"Bearer {token}"}
        return self.session.get(f"{self.base_url}/api/chat/consultations", headers=headers, timeout=10)

    def list_appointments(self, token):
        headers = {"Authorization": f"Bearer {token}"}
        return self.session.get(f"{self.base_url}/api/appointments", headers=headers, timeout=10)

    def get_my_patient_profile(self, token):
        headers = {"Authorization": f"Bearer {token}"}
        return self.session.get(f"{self.base_url}/api/patient/me", headers=headers, timeout=10)

    def get_my_doctor_profile(self, token):
        headers = {"Authorization": f"Bearer {token}"}
        return self.session.get(f"{self.base_url}/api/doctor/me", headers=headers, timeout=10)

    def send_message(self, token, consultation_id, message):
        headers = {"Authorization": f"Bearer {token}"}
        return self.session.post(f"{self.base_url}/api/chat/consultations/{consultation_id}/messages", json={"message": message}, headers=headers, timeout=30)

    def rag_ingest(self, token, payload):
        headers = {"Authorization": f"Bearer {token}"}
        return self.session.post(f"{self.base_url}/api/rag/ingest", json=payload, headers=headers, timeout=15)

    def rag_search(self, token, payload):
        headers = {"Authorization": f"Bearer {token}"}
        return self.session.post(f"{self.base_url}/api/rag/search", json=payload, headers=headers, timeout=15)
