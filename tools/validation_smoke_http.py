import uuid
import requests
from pathlib import Path
from tempfile import TemporaryDirectory
import json

BASE = 'http://127.0.0.1:8001'
TIMEOUT = 10
session = requests.Session()

def record(name, resp=None):
    entry = {'name': name}
    if resp is not None:
        entry['status_code'] = getattr(resp, 'status_code', None)
        try:
            entry['json'] = resp.json()
        except Exception:
            entry['text'] = getattr(resp, 'text', '')[:500]
    print(json.dumps(entry, indent=2))
    return entry


def mime_for(path):
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        return 'application/pdf'
    if suffix in {'.jpg', '.jpeg'}:
        return 'image/jpeg'
    if suffix == '.png':
        return 'image/png'
    return 'text/plain'


def signup_patient(username):
    resp = session.post(f'{BASE}/api/auth/patient/signup', json={'username': username, 'name': username, 'password': 'Password123!'}, timeout=TIMEOUT)
    record('signup_patient', resp)
    resp.raise_for_status()
    return resp.json()['access_token']


try:
    # health
    h = session.get(f'{BASE}/health', timeout=TIMEOUT)
    record('health', h)
except Exception as exc:
    print('HTTP validation aborted: backend unreachable or timed out:', exc)
    raise SystemExit(1)

with TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    png = tmp / 'xray.png'
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (128,128), 'white')
    draw = ImageDraw.Draw(img)
    draw.ellipse((32,32,96,96), outline='black', width=4)
    img.save(png)

    patient = f'valp_{uuid.uuid4().hex[:6]}'
    patient2 = f'valq_{uuid.uuid4().hex[:6]}'
    patient_token = signup_patient(patient)
    patient2_token = signup_patient(patient2)

    # upload image
    with png.open('rb') as fh:
        resp = session.post(f'{BASE}/api/medical_images/upload', headers={'Authorization': f'Bearer {patient_token}'}, data={'patient_id': patient}, files={'file': ('xray.png', fh, mime_for(png))}, timeout=TIMEOUT)
    record('upload_image', resp)
    if resp.status_code not in (200,201):
        print('Image upload failed; aborting HTTP validation')
        raise SystemExit(1)
    asset_id = resp.json().get('id')

    # process xray
    proc = session.post(f'{BASE}/api/processing/analyze-xray', headers={'Authorization': f'Bearer {patient_token}'}, json={'asset_id': asset_id, 'language': 'en'}, timeout=30)
    record('process_xray', proc)
    if proc.status_code == 200:
        body = proc.json()
        print('process_xray success:', body.get('success'))
    else:
        print('process_xray status', proc.status_code)
    # Upload a corrupted image and ensure processing returns 422
    corrupt = tmp / 'corrupt.png'
    corrupt.write_bytes(b'not a real png')
    with corrupt.open('rb') as fh:
        resp2 = session.post(f'{BASE}/api/medical_images/upload', headers={'Authorization': f'Bearer {patient_token}'}, data={'patient_id': patient}, files={'file': ('corrupt.png', fh, mime_for(corrupt))}, timeout=TIMEOUT)
    record('upload_corrupt', resp2)
    if resp2.status_code not in (200,201):
        print('Corrupt upload rejected at upload time with', resp2.status_code)
    else:
        corrupt_id = resp2.json().get('id')
        corrupt_proc = session.post(f'{BASE}/api/processing/analyze-xray', headers={'Authorization': f'Bearer {patient_token}'}, json={'asset_id': corrupt_id, 'language': 'en'}, timeout=30)
        record('process_corrupt_xray', corrupt_proc)
        print('corrupt process status', corrupt_proc.status_code)

print('HTTP validation complete')
