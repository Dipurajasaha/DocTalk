from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import fitz
import requests
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.core.database import connect_prisma, disconnect_prisma
from backend.services.embedding_service import embedding_service
from backend.services.rag_service import rag_service
from backend.services.summary_service import medical_summary_service

BASE = os.getenv('BASE_URL', 'http://127.0.0.1:8002')
TIMEOUT = 90
session = requests.Session()
results: list[dict] = []
failures: list[dict] = []


def record(name, resp=None):
    entry = {'name': name}
    if resp is not None:
        entry['status_code'] = getattr(resp, 'status_code', None)
        try:
            entry['json'] = resp.json()
        except Exception:
            entry['text'] = getattr(resp, 'text', '')[:500]
    results.append(entry)
    return entry


def require(condition, check_name, detail):
    if not condition:
        failures.append({'check': check_name, 'detail': detail})


def auth_headers(token):
    return {'Authorization': f'Bearer {token}'}


def mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        return 'application/pdf'
    if suffix in {'.jpg', '.jpeg'}:
        return 'image/jpeg'
    if suffix == '.png':
        return 'image/png'
    if suffix == '.webp':
        return 'image/webp'
    return 'text/plain'


def create_pdf(path: Path, title: str, lines: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), title, fontsize=16)
    y = 110
    for line in lines:
        page.insert_text((72, y), line, fontsize=12)
        y += 20
    doc.save(path)
    doc.close()


def create_xray_png(path: Path) -> None:
    img = Image.new('RGB', (256, 256), 'white')
    draw = ImageDraw.Draw(img)
    draw.ellipse((48, 48, 208, 208), outline='black', width=6)
    draw.line((90, 130, 166, 130), fill='gray', width=4)
    draw.line((128, 90, 128, 166), fill='gray', width=4)
    img.save(path)


async def local_checks() -> None:
    summary = await medical_summary_service.build_summary(
        'ocr',
        'Impression: Mild peribronchial thickening. Follow up recommended.',
        findings=['Mild peribronchial thickening.'],
        recommendations=['Follow up with pulmonology.'],
    )
    require(bool(summary.summary), 'local_summary', summary)

    vector = await embedding_service.embed_text(summary.summary)
    require(len(vector) == embedding_service.dimension, 'vector_dimension', {'expected': embedding_service.dimension, 'actual': len(vector)})

    invalid_vector_failed = False
    try:
        embedding_service.validate_vector([1.0, 2.0, 3.0])
    except Exception:
        invalid_vector_failed = True
    require(invalid_vector_failed, 'invalid_vector_rejected', 'Expected invalid vector validation to fail')

    duplicate_preview = await rag_service.ingest_medical_summary(
        patient_id='local_rag_patient',
        source_type='ocr',
        content='Impression: local check',
        summary='Local duplicate ingestion check',
        metadata={'scope': 'local'},
    )
    duplicate_repeat = await rag_service.ingest_medical_summary(
        patient_id='local_rag_patient',
        source_type='ocr',
        content='Impression: local check',
        summary='Local duplicate ingestion check',
        metadata={'scope': 'local'},
    )
    require(duplicate_preview['id'] == duplicate_repeat['id'], 'duplicate_ingestion', {'first': duplicate_preview['id'], 'second': duplicate_repeat['id']})


async def run_local_checks() -> None:
    await connect_prisma()
    try:
        await local_checks()
    finally:
        await disconnect_prisma()


asyncio.run(run_local_checks())

try:
    health = session.get(f'{BASE}/health', timeout=TIMEOUT)
    record('health', health)
    require(health.status_code == 200, 'health_status', health.text)
except Exception as exc:
    print(json.dumps({'ok': False, 'error': f'backend unreachable: {exc}'}, indent=2))
    raise SystemExit(1)

with TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    report_pdf = tmp / 'report.pdf'
    prescription_pdf = tmp / 'prescription.pdf'
    xray_png = tmp / 'xray.png'
    corrupt_png = tmp / 'corrupt.png'
    create_pdf(report_pdf, 'Radiology Report', [
        'Impression: Mild peribronchial thickening.',
        'Findings: No focal consolidation is seen.',
        'Follow up with pulmonology if symptoms persist.',
    ])
    create_pdf(prescription_pdf, 'Prescription', [
        'Amoxicillin 500 mg twice daily after food for 5 days.',
        'Paracetamol 650 mg once daily as needed for pain.',
    ])
    create_xray_png(xray_png)
    corrupt_png.write_bytes(b'not a real png')

    run_id = uuid.uuid4().hex[:8]
    patient = f'ragp_{run_id}'
    patient2 = f'ragq_{run_id}'
    doctor = f'ragd_{run_id}'
    doctor2 = f'ragx_{run_id}'

    def signup_patient(username: str) -> str:
        resp = session.post(f'{BASE}/api/auth/patient/signup', json={'username': username, 'name': username, 'password': 'Password123!'}, timeout=TIMEOUT)
        record(f'signup_patient:{username}', resp)
        require(resp.status_code == 200, 'signup_patient_status', resp.text)
        return resp.json()['access_token']

    def signup_doctor(doctor_id: str) -> str:
        resp = session.post(f'{BASE}/api/auth/doctor/signup', json={'doctor_id': doctor_id, 'name': doctor_id, 'password': 'Password123!'}, timeout=TIMEOUT)
        record(f'signup_doctor:{doctor_id}', resp)
        require(resp.status_code == 200, 'signup_doctor_status', resp.text)
        return resp.json()['access_token']

    patient_token = signup_patient(patient)
    patient2_token = signup_patient(patient2)
    doctor_token = signup_doctor(doctor)
    doctor2_token = signup_doctor(doctor2)

    appt_resp = session.post(
        f'{BASE}/api/appointments',
        headers=auth_headers(patient_token),
        json={
            'doctor_id': doctor,
            'date': '2026-05-22',
            'time': '10:30',
            'reason': 'Recurring cough and chest discomfort',
            'note': 'Need follow up and review',
        },
        timeout=TIMEOUT,
    )
    record('create_appointment', appt_resp)
    require(appt_resp.status_code == 200, 'appointment_status', appt_resp.text)
    appointment_id = appt_resp.json()['id']

    approve_resp = session.patch(f'{BASE}/api/appointments/{appointment_id}/approve', headers=auth_headers(doctor_token), timeout=TIMEOUT)
    record('approve_appointment', approve_resp)
    require(approve_resp.status_code == 200, 'approve_status', approve_resp.text)

    consult_resp = session.post(
        f'{BASE}/api/chat/consultations',
        headers=auth_headers(patient_token),
        json={'appointment_id': appointment_id},
        timeout=TIMEOUT,
    )
    record('create_consultation', consult_resp)
    require(consult_resp.status_code == 200, 'consultation_status', consult_resp.text)
    consultation_id = consult_resp.json()['id']

    def upload_asset(path: Path, token: str, endpoint: str):
        with path.open('rb') as fh:
            resp = session.post(
                f'{BASE}{endpoint}',
                headers=auth_headers(token),
                data={'patient_id': patient, 'consultation_id': consultation_id},
                files={'file': (path.name, fh, mime_for(path))},
                timeout=TIMEOUT,
            )
        record(f'upload:{endpoint}:{path.name}', resp)
        return resp

    report_up = upload_asset(report_pdf, patient_token, '/api/reports/upload')
    prescription_up = upload_asset(prescription_pdf, patient_token, '/api/prescriptions/upload')
    xray_up = upload_asset(xray_png, patient_token, '/api/medical_images/upload')

    for name, resp in [('report', report_up), ('prescription', prescription_up), ('xray', xray_up)]:
        require(resp.status_code in (200, 201), f'{name}_upload_status', resp.text)
        require(bool(resp.json().get('stored_path')), f'{name}_stored_path', resp.json())

    report_proc = session.post(f'{BASE}/api/processing/analyze-report', headers=auth_headers(patient_token), json={'asset_id': report_up.json()['id'], 'language': 'en'}, timeout=TIMEOUT)
    prescription_proc = session.post(f'{BASE}/api/processing/analyze-prescription', headers=auth_headers(patient_token), json={'asset_id': prescription_up.json()['id'], 'language': 'en'}, timeout=TIMEOUT)
    xray_proc = session.post(f'{BASE}/api/processing/analyze-xray', headers=auth_headers(patient_token), json={'asset_id': xray_up.json()['id'], 'language': 'en'}, timeout=TIMEOUT)
    record('process_report', report_proc)
    record('process_prescription', prescription_proc)
    record('process_xray', xray_proc)

    for name, resp in [('report', report_proc), ('prescription', prescription_proc), ('xray', xray_proc)]:
        require(resp.status_code == 200, f'{name}_process_status', resp.text)
        body = resp.json()
        require(body.get('success') is True, f'{name}_process_success', body)
        require(set(body.keys()) == {'success', 'extracted_text', 'findings', 'summary', 'recommendations', 'warnings'}, f'{name}_process_shape', body)

    manual_ingest = session.post(
        f'{BASE}/api/rag/ingest',
        headers=auth_headers(patient_token),
        json={
            'patient_id': patient,
            'consultation_id': consultation_id,
            'source_type': 'consultation',
            'content': 'Patient reports recurring cough and occasional chest discomfort. No fever reported.',
            'summary': 'Recurring cough with chest discomfort discussed during consultation.',
            'findings': ['Recurring cough', 'Occasional chest discomfort'],
            'recommendations': ['Monitor symptoms', 'Follow up if symptoms worsen'],
            'metadata': {'source': 'manual_test'},
        },
        timeout=TIMEOUT,
    )
    record('rag_ingest', manual_ingest)
    require(manual_ingest.status_code == 200, 'rag_ingest_status', manual_ingest.text)
    manual_id = manual_ingest.json()['id']

    duplicate_ingest = session.post(
        f'{BASE}/api/rag/ingest',
        headers=auth_headers(patient_token),
        json={
            'patient_id': patient,
            'consultation_id': consultation_id,
            'source_type': 'consultation',
            'content': 'Patient reports recurring cough and occasional chest discomfort. No fever reported.',
            'summary': 'Recurring cough with chest discomfort discussed during consultation.',
            'findings': ['Recurring cough', 'Occasional chest discomfort'],
            'recommendations': ['Monitor symptoms', 'Follow up if symptoms worsen'],
            'metadata': {'source': 'manual_test'},
        },
        timeout=TIMEOUT,
    )
    record('rag_ingest_duplicate', duplicate_ingest)
    require(duplicate_ingest.status_code == 200, 'rag_duplicate_status', duplicate_ingest.text)
    require(duplicate_ingest.json()['id'] == manual_id, 'rag_duplicate_id', duplicate_ingest.json())

    patient_search = session.post(
        f'{BASE}/api/rag/search',
        headers=auth_headers(patient_token),
        json={'patient_id': patient, 'query': 'recurring cough chest discomfort', 'consultation_id': consultation_id, 'source_type': 'consultation', 'top_k': 5, 'similarity_threshold': 0.2},
        timeout=TIMEOUT,
    )
    record('rag_search_patient', patient_search)
    require(patient_search.status_code == 200, 'patient_search_status', patient_search.text)
    require(len(patient_search.json().get('items', [])) >= 1, 'patient_search_results', patient_search.json())

    memory_search = session.get(
        f'{BASE}/api/rag/patient-memory',
        headers=auth_headers(patient_token),
        params={'query': 'amoxicillin', 'top_k': 5, 'similarity_threshold': 0.15},
        timeout=TIMEOUT,
    )
    record('rag_patient_memory', memory_search)
    require(memory_search.status_code == 200, 'patient_memory_status', memory_search.text)
    require(len(memory_search.json().get('items', [])) >= 1, 'patient_memory_results', memory_search.json())

    doctor_search = session.post(
        f'{BASE}/api/rag/search',
        headers=auth_headers(doctor_token),
        json={'patient_id': patient, 'query': 'amoxicillin', 'consultation_id': consultation_id, 'top_k': 5, 'similarity_threshold': 0.15},
        timeout=TIMEOUT,
    )
    record('rag_search_doctor', doctor_search)
    require(doctor_search.status_code == 200, 'doctor_search_status', doctor_search.text)

    unauthorized_patient = session.post(
        f'{BASE}/api/rag/search',
        headers=auth_headers(patient2_token),
        json={'patient_id': patient, 'query': 'amoxicillin', 'consultation_id': consultation_id, 'top_k': 5},
        timeout=TIMEOUT,
    )
    record('rag_search_unauthorized_patient', unauthorized_patient)
    require(unauthorized_patient.status_code == 403, 'unauthorized_patient_status', unauthorized_patient.text)

    unauthorized_doctor = session.post(
        f'{BASE}/api/rag/search',
        headers=auth_headers(doctor2_token),
        json={'patient_id': patient, 'query': 'amoxicillin', 'consultation_id': consultation_id, 'top_k': 5},
        timeout=TIMEOUT,
    )
    record('rag_search_unauthorized_doctor', unauthorized_doctor)
    require(unauthorized_doctor.status_code == 403, 'unauthorized_doctor_status', unauthorized_doctor.text)

    corrupt_upload = session.post(
        f'{BASE}/api/medical_images/upload',
        headers=auth_headers(patient_token),
        data={'patient_id': patient, 'consultation_id': consultation_id},
        files={'file': ('corrupt.png', corrupt_png.open('rb'), mime_for(corrupt_png))},
        timeout=TIMEOUT,
    )
    record('corrupt_upload', corrupt_upload)
    require(corrupt_upload.status_code in (422, 415), 'corrupt_upload_status', corrupt_upload.text)

summary = {'ok': not failures, 'failures': failures, 'results_count': len(results)}
print(json.dumps(summary, indent=2))
raise SystemExit(0 if not failures else 1)
