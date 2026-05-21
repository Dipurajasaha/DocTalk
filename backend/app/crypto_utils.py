import os
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

def generate_rsa_key_pair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return public_pem.decode('utf-8'), private_pem.decode('utf-8')

def encrypt_private_key(private_key_pem: str, password: str) -> str:
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(password.encode())
    
    cipher = AES.new(key, AES.MODE_GCM)
    ct_bytes, tag = cipher.encrypt_and_digest(private_key_pem.encode())
    
    payload = salt + cipher.nonce + tag + ct_bytes
    return base64.b64encode(payload).decode('utf-8')

def decrypt_private_key(encrypted_payload_b64: str, password: str) -> str:
    payload = base64.b64decode(encrypted_payload_b64)
    salt = payload[:16]
    nonce = payload[16:32]
    tag = payload[32:48]
    ct_bytes = payload[48:]
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(password.encode())
    
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    pt_bytes = cipher.decrypt_and_verify(ct_bytes, tag)
    return pt_bytes.decode('utf-8')

def encrypt_file_key(file_key: bytes, public_key_pem: str) -> str:
    public_key = serialization.load_pem_public_key(
        public_key_pem.encode('utf-8'),
        backend=default_backend()
    )
    encrypted = public_key.encrypt(
        file_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_file_key(encrypted_file_key_b64: str, private_key_pem: str) -> bytes:
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None,
        backend=default_backend()
    )
    encrypted = base64.b64decode(encrypted_file_key_b64)
    decrypted = private_key.decrypt(
        encrypted,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return decrypted

def generate_aes_key() -> bytes:
    return get_random_bytes(32)

def encrypt_file_content(data: bytes, aes_key: bytes) -> tuple[bytes, bytes, bytes]:
    cipher = AES.new(aes_key, AES.MODE_GCM)
    ct_bytes, auth_tag = cipher.encrypt_and_digest(data)
    return ct_bytes, cipher.nonce, auth_tag

def decrypt_file_content(encrypted_data: bytes, aes_key: bytes, nonce: bytes, auth_tag: bytes) -> bytes:
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(encrypted_data, auth_tag)
