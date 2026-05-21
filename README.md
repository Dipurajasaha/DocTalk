# HealthCare FastAPI Rebuild

This rebuild now uses separate folders for frontend and backend.

## Project Structure

- backend/ → FastAPI backend
  - app/ → API routes, schemas, data access
  - requirements.txt → backend dependencies
- frontend/ → HTML, CSS, JS frontend

```
HealthCare/
├── backend/                 # FastAPI backend
├── frontend/                # Vite + React frontend
├── data/                    # JSON data storage
└── README.md
```

## Quick Start

1. Create and activate a virtual environment.
2. Install backend dependencies:
   - `pip install -r requirements.txt`
3. Install frontend dependencies:
   - `cd frontend`
   - `npm install`
4. For React development mode (recommended while coding UI):
   - `npm run dev`
5. Build frontend for FastAPI static serving:
   - `npm run build`
6. Run server from the project root:
   - `python -m uvicorn backend.main:api --reload --host 127.0.0.1 --port 8000`
7. Open:
   - `http://127.0.0.1:8000` for the backend or `http://127.0.0.1:5173` for the Vite frontend

---

## 🔒 Advanced Hybrid Encryption (AES + RSA)

This backend enforces **mandatory, end-to-end hybrid encryption** for all patient files and sensitive data. Every user automatically receives encryption keys on login/registration, and all uploads are encrypted—no plaintext fallback exists.

### Clean Architecture Layer
* **`backend/app/crypto_utils.py`**: Low-level cryptographic primitives (AES-256-GCM, RSA-2048-OAEP, key wrapping, password-protected private keys via PBKDF2).
* **`backend/app/file_service.py`**: Service orchestration layer (`FileCryptoService`) for upload/download/share workflows—all encryption/decryption logic lives here.
* **`backend/main.py`**: Route handlers do request validation, auth checks, and persistence only; no direct crypto calls.

### Key Features
* **Automatic Key Bootstrap:** On user login or registration, the system automatically generates an RSA-2048 key pair and securely stores it with PBKDF2-encrypted private key wrapping.
* **File Protection:** All uploads are encrypted with **AES-256-GCM**, ensuring confidentiality (encryption) and authenticity (GCM auth tag).
* **Per-User Key Exchange:** Each user's AES file keys are encrypted with their RSA public key; decryption requires their password-protected private key.
* **Password-Protected Wallet:** Private keys are encrypted at rest using PBKDF2 + AES-GCM, activated on login with user password.
* **Key Mapping Isolation:** File-key pairs stored in `data/file_keys.json` (JSON file store) link authorized users to encrypted assets without exposing plaintext keys.
* **Secure-Only File Access:** Direct `/data` static serving is disabled; all file retrieval goes through `/api/file/{file_id}` with auth + key mapping validation.
* **Mandatory Encryption Policy:** Upload endpoints reject requests from users missing encryption keys; no plaintext files are ever written to disk.

### Cryptographic Workflows
1. **User Key Bootstrap (Login/Registration):**
   - On `/api/login` or `/api/register`, system checks if user has `publicKey` and `encryptedPrivateKey`.
   - If missing, RSA-2048 key pair is auto-generated and stored securely.
   - User's new private key is encrypted with their password via PBKDF2 + AES-GCM.
   - User is then ready to upload/download encrypted files.

2. **Upload & Encrypt (Mandatory):**
   - Route handler receives file bytes and immediately validates user has encryption keys.
   - Delegates to `FileCryptoService.process_upload(...)`.
   - A secure random AES-256 key is generated; file bytes encrypted via AES-GCM (producing ciphertext, nonce, auth tag).
   - AES key is wrapped with uploader's RSA public key.
   - Ciphertext written to disk; key mapping stored in `data/file_keys.json`.
   - Encryption metadata (`algorithm`, `key_id`, `iv`, `auth_tag`) returned with asset record.
   - If user lacks keys, upload **fails with 400 error**—no plaintext fallback.

3. **Download & Decrypt (Secure Access Only):**
   - Client requests file through `/api/file/{file_id}`.
   - System validates: (1) user is authenticated, (2) user has key mapping for file, (3) file has encryption metadata.
   - If missing any requirement, returns **403 Forbidden**.
   - Delegates to `FileCryptoService.process_download(...)`.
   - Service decrypts user's encrypted private key in memory (password required), unwraps AES file key, verifies GCM auth tag, decrypts file, returns plaintext bytes.

4. **Secure Sharing:** 
   - Route delegates to `FileCryptoService.process_share(...)`.
   - Owner's private key decrypts the stored AES key.
   - AES key is re-encrypted for target user using target's RSA public key.
   - File bytes remain on disk unchanged; only key ownership mapping is expanded.

### Verification
To verify encryption is working end-to-end, run:
```bash
cd backend
python internal_encryption_self_test.py
```
This script:
- Registers two test users with auto-generated keys
- Uploads a file with known content
- Confirms content is **not readable** on disk (at-rest ciphertext)
- Downloads file and verifies **exact content match** (decryption success)
- Attempts access from unauthorized user and confirms **denied** (access control)
- Prints `[PASS]` or `[FAIL]` for each step

---

## Data Source

By default, the backend reads and writes JSON data from workspace `data/`.

## Notes

- Frontend was migrated to React + Vite.
- FastAPI serves the built frontend from `frontend/dist`.
- If `frontend/dist` does not exist, `/` returns a setup message until you run `npm run build`.
- `backend/main.py` is the legacy standalone FastAPI entrypoint.
- The Vite frontend proxies `/api` and `/static` to the backend during development.
