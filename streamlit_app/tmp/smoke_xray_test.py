import io
import requests
from PIL import Image

BASE = 'http://127.0.0.1:8000'

def signup(username='smoke_test_user', name='Smoke Test', password='TestPass123!'):
    r = requests.post(f'{BASE}/api/auth/patient/signup', json={'username': username, 'name': name, 'password': password}, timeout=10)
    print('signup', r.status_code, r.text)
    if r.ok:
        return r.json()
    # try login if user exists
    if r.status_code == 409:
        lr = requests.post(f'{BASE}/api/auth/patient/login', json={'username': username, 'password': password}, timeout=10)
        print('login', lr.status_code, lr.text)
        return lr.json() if lr.ok else None
    return None

def upload_image(token, patient_id):
    # create small PNG
    img = Image.new('RGB', (10,10), color=(255,0,0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    files = {'file': ('smoke.png', buf, 'image/png')}
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    data = {'patient_id': patient_id}
    r = requests.post(f'{BASE}/api/medical_images/upload', files=files, data=data, headers=headers, timeout=30)
    print('upload', r.status_code, r.text)
    return r.json() if r.ok else None

def analyze(token, asset_id):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    payload = {'asset_id': asset_id, 'language': 'en'}
    r = requests.post(f'{BASE}/api/processing/analyze-xray', json=payload, headers=headers, timeout=240)
    print('analyze', r.status_code, r.text)
    return r.json() if r.ok else None

def main():
    info = signup()
    if not info:
        print('Signup failed')
        return
    token = info.get('access_token')
    user_id = info.get('user_id')
    uploaded = upload_image(token, user_id)
    if not uploaded:
        print('Upload failed')
        return
    asset_id = uploaded.get('id')
    analyze(token, asset_id)

if __name__ == '__main__':
    main()
