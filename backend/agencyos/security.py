"""Password hashing, access tokens and secret encryption."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken

from .config import settings

PBKDF2_ROUNDS = 390_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt_b64, hash_b64 = encoded.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(rounds))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def create_token(user_id: str, org_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings().access_token_ttl_minutes)
    return jwt.encode({"sub": user_id, "org": org_id, "exp": exp}, settings().secret_key, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _fernet() -> Fernet:
    key = hashlib.sha256(("agencyos-secrets:" + settings().secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str | None:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None


def mask(value: str | None) -> str | None:
    if not value:
        return None
    return value[:4] + "…" + value[-4:] if len(value) > 10 else "••••"
