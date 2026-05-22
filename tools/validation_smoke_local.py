import sys
import os
import tempfile
from pathlib import Path

# Ensure project root is on sys.path for local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.services.report_service import ReportService
from backend.services.safety_service import medical_safety_service
from fastapi import HTTPException

print('Running local validation checks...')

rs = ReportService()
root = rs.upload_root
print('upload_root:', root)

# Path traversal check
try:
    bad = '../../etc/passwd'
    try:
        p = rs._resolve_disk_path(bad)
        print('ERROR: traversal allowed, resolved to', p)
    except HTTPException as exc:
        print('OK: traversal blocked ->', exc.detail)
except Exception as e:
    print('Exception during path traversal test:', e)

# File validation
with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    good_png = tdp / 'good.png'
    bad_png = tdp / 'bad.png'
    # create good image
    from PIL import Image
    img = Image.new('RGB', (10,10), 'white')
    img.save(good_png)
    # create corrupt file
    bad_png.write_bytes(b'not a png')

    try:
        rs._validate_saved_file(good_png, '.png', 'image/png')
        print('OK: valid image accepted')
    except Exception as e:
        print('ERROR: valid image rejected', e)

    try:
        rs._validate_saved_file(bad_png, '.png', 'image/png')
        print('ERROR: corrupt image accepted')
    except HTTPException as e:
        print('OK: corrupt image rejected ->', e.detail)
    except Exception as e:
        print('OK: corrupt image rejected (other) ->', type(e), e)

# Safety fallback
fb = medical_safety_service.fallback_response('test', 'simulated error', {'warnings': ['prior']})
print('fallback success value:', fb.get('success'))
print('fallback warnings:', fb.get('warnings'))

print('Local validation complete.')
