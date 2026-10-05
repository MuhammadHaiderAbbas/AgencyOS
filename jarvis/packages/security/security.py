"""Auth helpers: password hashing, JWT, CSRF, secrets masking."""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from packages.config.config import settings

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

COOKIE_NAME = "jarvis_token"
CSRF_COOKIE = "jarvis_csrf"
CSRF_HEADER = "x-csrf-token"

def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_token(user_id: str, role: str = "user", ttl_minutes: int | None = None) -> str:
    s = settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes or s.token_ttl_minutes)
    payload = {"sub": user_id, "role": role, "iat": int(time.time()), "exp": int(exp.timestamp()), "jti": uuid.uuid4().hex}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")

def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None

def hash_args(args: dict) -> str:
    import json
    raw = json.dumps(args, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()

def mask_secret(v: str) -> str:
    if not v or len(v) <= 4:
        return "***"
    return v[:2] + "***" + v[-2:]

def is_sensitive_key(k: str) -> bool:
    low = k.lower()
    return any(s in low for s in ["password","token","secret","key","auth","credential"])

def sanitize_for_log(args: dict) -> dict:
    out = {}
    for k, v in args.items():
        if is_sensitive_key(k):
            out[k] = "***REDACTED***"
        else:
            out[k] = v
    return out

def generate_csrf() -> str:
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:32]
