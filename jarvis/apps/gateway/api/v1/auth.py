from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from apps.gateway.db import User, get_sessionmaker
from packages.security.security import create_token, decode_token, hash_password, verify_password, COOKIE_NAME, CSRF_COOKIE, generate_csrf
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["auth"])

class SignupIn(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

def _user_to_dict(u: User):
    return {"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role, "locale": u.locale, "timezone": u.timezone, "personality": u.personality, "trust_level": u.trust_level, "created_at": u.created_at.isoformat() if u.created_at else None}

def get_db():
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()

def current_user_dep(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME) or (request.headers.get("authorization") or "").replace("Bearer ","")
    # also support query token for SSE/WS
    if not token:
        token = request.query_params.get("token") or ""
    claims = decode_token(token) if token else None
    if not claims:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == claims["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.post("/signup")
def signup(data: SignupIn, response: Response, db: Session = Depends(get_db)):
    from packages.config.config import settings
    if not settings().allow_signup and db.query(User).count() > 0:
        raise HTTPException(400, "Signup disabled")
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(409, "Email already registered")
    is_first = db.query(User).count() == 0
    user = User(email=data.email.lower(), password_hash=hash_password(data.password), display_name=data.display_name or data.email.split("@")[0], role="admin" if is_first else "user")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id, user.role)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=False, max_age=60*60*24)
    csrf = generate_csrf()
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, samesite="lax", secure=False)
    return {"user": _user_to_dict(user), "token": token, "csrf": csrf}

@router.post("/login")
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    # update last_login
    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_token(user.id, user.role)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=False, max_age=60*60*24)
    csrf = generate_csrf()
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, samesite="lax", secure=False)
    return {"user": _user_to_dict(user), "token": token, "csrf": csrf}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    response.delete_cookie(CSRF_COOKIE)
    return {"ok": True}

@router.get("/me")
def me(user: User = Depends(current_user_dep)):
    return {"user": _user_to_dict(user)}

class UpdateMeIn(BaseModel):
    display_name: str | None = None
    locale: str | None = None
    timezone: str | None = None
    personality: str | None = None
    trust_level: str | None = None

@router.put("/me")
def update_me(data: UpdateMeIn, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user.id).first()
    if data.display_name is not None:
        u.display_name = data.display_name
    if data.locale is not None:
        u.locale = data.locale
    if data.timezone is not None:
        u.timezone = data.timezone
    if data.personality is not None:
        u.personality = data.personality
    if data.trust_level is not None:
        if data.trust_level not in ("conservative","balanced","autonomous"):
            raise HTTPException(400, "Invalid trust_level")
        u.trust_level = data.trust_level
    db.commit()
    db.refresh(u)
    return {"user": _user_to_dict(u)}
