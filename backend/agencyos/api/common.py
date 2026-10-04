"""Shared API helpers: JSON responses, auth, tenancy checks, rate limiting."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from functools import wraps
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..db import db, jload
from ..security import decode_token

COOKIE = "agencyos_session"


class HTTPError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail


def ok(data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


async def body(request: Request, model: type[BaseModel]) -> Any:
    try:
        raw = await request.json()
    except ValueError:
        raise HTTPError(400, "Invalid JSON body")
    try:
        return model.model_validate(raw)
    except ValidationError as e:
        raise HTTPError(422, "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:5]))


def current_user(request: Request, allow_cookie: bool = False) -> dict:
    token = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
    elif allow_cookie:  # cookies only for safe GETs (iframe previews, downloads) — CSRF-safe
        token = request.cookies.get(COOKIE) or request.query_params.get("token")
    if not token:
        raise HTTPError(401, "Not authenticated")
    claims = decode_token(token)
    if not claims:
        raise HTTPError(401, "Session expired")
    u = db().q1("SELECT id, email, name, is_admin, created_at FROM users WHERE id = ? AND deleted_at IS NULL", (claims["sub"],))
    if not u:
        raise HTTPError(401, "User not found")
    m = db().q1("SELECT role FROM memberships WHERE org_id = ? AND user_id = ?", (claims["org"], u["id"]))
    if not m:
        raise HTTPError(403, "Not a member of this workspace")
    u["org_id"], u["org_role"] = claims["org"], m["role"]
    u["is_admin"] = bool(u["is_admin"])
    return u


def auth(allow_cookie: bool = False, roles: set[str] | None = None, admin: bool = False):
    def deco(fn: Callable):
        @wraps(fn)
        async def wrapper(request: Request):
            user = current_user(request, allow_cookie)
            if roles and user["org_role"] not in roles:
                raise HTTPError(403, "Insufficient role")
            if admin and not user["is_admin"]:
                raise HTTPError(403, "Admin only")
            request.state.user = user
            return await fn(request, user)
        return wrapper
    return deco


def project_for(user: dict, project_id: str) -> dict:
    """Tenant isolation: a project is only visible inside its organisation."""
    p = db().q1("SELECT * FROM projects WHERE id = ? AND org_id = ?", (project_id, user["org_id"]))
    if not p:
        raise HTTPError(404, "Project not found")
    return p


def artifact_for(user: dict, artifact_id: str) -> dict:
    a = db().q1("SELECT a.* FROM artifacts a JOIN projects p ON p.id = a.project_id WHERE a.id = ? AND p.org_id = ?",
                (artifact_id, user["org_id"]))
    if not a:
        raise HTTPError(404, "Artifact not found")
    return a


def require_writer(user: dict) -> None:
    if user["org_role"] == "viewer":
        raise HTTPError(403, "Viewers cannot modify projects")


_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(key: str, limit: int, window: float) -> None:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPError(429, "Too many requests — please wait a moment")
    q.append(now)


def project_public(p: dict) -> dict:
    out = dict(p)
    out["archived"] = bool(p["archived"])
    out["is_demo"] = bool(p["is_demo"])
    agg = db().q1("SELECT COUNT(*) total, SUM(CASE WHEN status IN ('COMPLETED','APPROVED') THEN 1 ELSE 0 END) done, "
                  "SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) running FROM tasks WHERE project_id = ?", (p["id"],))
    out["tasks_total"] = agg["total"] or 0
    out["tasks_done"] = agg["done"] or 0
    out["agents_active"] = agg["running"] or 0
    team = db().q1("SELECT COUNT(DISTINCT role) n FROM tasks WHERE project_id = ? AND kind != 'approval'", (p["id"],))
    out["team_size"] = team["n"] if team else 0
    last = db().q1("SELECT created_at, message FROM project_events WHERE project_id = ? ORDER BY id DESC LIMIT 1", (p["id"],))
    out["last_activity"] = last["created_at"] if last else p["updated_at"]
    out["last_activity_message"] = last["message"] if last else None
    dep = db().q1("SELECT url FROM deployments WHERE project_id = ? AND status = 'SUCCEEDED' ORDER BY created_at DESC LIMIT 1", (p["id"],))
    out["live_url"] = dep["url"] if dep else None
    return out


def message_public(m: dict) -> dict:
    return {**m, "meta": jload(m.get("meta"), {})}
