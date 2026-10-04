"""ASGI application: REST API + WebSockets + static frontend."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..agents.registry import seed_builtins
from ..config import load_settings, settings
from ..db import db, init_db, now
from ..events import bus
from ..orchestration.engine import orchestrator
from ..security import decode_token
from .common import COOKIE, HTTPError
from .routes import routes

log = logging.getLogger("agencyos")


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if not request.url.path.startswith(("/api/projects/", "/sites/")):
            resp.headers.setdefault("X-Frame-Options", "DENY")
        return resp


async def http_error(request: Request, exc: HTTPError):
    return JSONResponse({"error": exc.detail}, status_code=exc.status)


async def server_error(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse({"error": "Internal server error"}, status_code=500)


# ---------------------------------------------------------------- websockets
async def _ws(websocket: WebSocket, project_id: str | None, types: tuple[str, ...] | None = None):
    token = websocket.query_params.get("token") or websocket.cookies.get(COOKIE)
    claims = decode_token(token) if token else None
    if not claims or not db().q1("SELECT 1 FROM memberships WHERE org_id = ? AND user_id = ?", (claims["org"], claims["sub"])):
        await websocket.close(code=4401)
        return
    if project_id and not db().q1("SELECT 1 FROM projects WHERE id = ? AND org_id = ?", (project_id, claims["org"])):
        await websocket.close(code=4404)
        return
    await websocket.accept()
    q = bus.subscribe(asyncio.get_running_loop(), org_id=claims["org"], project_id=project_id)
    try:
        while True:
            try:
                evt = await asyncio.wait_for(q.get(), timeout=25)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "PING"})
                continue
            if types and not evt["type"].startswith(types):
                continue
            await websocket.send_json(evt)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        bus.unsubscribe(q)


async def ws_project(websocket: WebSocket):
    await _ws(websocket, websocket.path_params["pid"])


async def ws_org(websocket: WebSocket):
    await _ws(websocket, None)


async def ws_tasks(websocket: WebSocket):
    await _ws(websocket, None, ("TASK_",))


async def ws_agents(websocket: WebSocket):
    await _ws(websocket, None, ("AGENT_", "TASK_STARTED", "TASK_COMPLETED"))


async def ws_notifications(websocket: WebSocket):
    await _ws(websocket, None, ("NOTIFICATION", "APPROVAL_REQUIRED"))


# ---------------------------------------------------------------- server-sent events (works without a WS library)
async def _sse(request: Request, project_id: str | None):
    import json as _json
    from sse_starlette.sse import EventSourceResponse
    from .common import current_user, project_for
    user = current_user(request, allow_cookie=True)
    if project_id:
        project_for(user, project_id)
    q = bus.subscribe(asyncio.get_running_loop(), org_id=user["org_id"], project_id=project_id)

    async def gen():
        try:
            yield {"event": "ready", "data": "{}"}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    continue
                yield {"event": "message", "data": _json.dumps(evt)}
        finally:
            bus.unsubscribe(q)

    return EventSourceResponse(gen(), ping=15, headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


async def sse_org(request: Request):
    return await _sse(request, None)


async def sse_project(request: Request):
    return await _sse(request, request.path_params["pid"])


# ---------------------------------------------------------------- lifecycle
def recover() -> None:
    """After a restart: tasks that were mid-flight are re-queued (never silently lost)."""
    stuck = db().q("SELECT id, project_id FROM tasks WHERE status = 'IN_PROGRESS'")
    for t in stuck:
        db().update("tasks", {"id": t["id"]}, {"status": "READY"})
    db().ex("UPDATE agent_executions SET status = 'FAILED', errors = '[\"interrupted by server restart\"]', finished_at = ? WHERE status = 'RUNNING'", (now(),))
    for p in db().q("SELECT id FROM projects WHERE status NOT IN ('DISCOVERY','REQUIREMENTS','PLANNING','COMPLETED','CANCELLED','BLOCKED') AND archived = 0"):
        orchestrator.enqueue(p["id"])


def create_app(**overrides) -> Starlette:
    load_settings(**overrides)
    init_db(settings().database_path)
    seed_builtins()

    @contextlib.asynccontextmanager
    async def lifespan(app):
        if not orchestrator.sync:
            orchestrator.start()
            recover()
        yield
        orchestrator.stop()

    dist = settings().frontend_dist
    extra = []
    if dist.exists():
        async def spa(request):
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
        extra = [Mount("/assets", StaticFiles(directory=dist / "assets"), name="assets"), Route("/{path:path}", spa)]

    async def site_root(request):
        return RedirectResponse(f"/sites/{request.path_params['pid']}/")

    app = Starlette(
        routes=[Route("/api/stream/org", sse_org), Route("/api/stream/projects/{pid}", sse_project),
                *routes, Route("/sites/{pid}", site_root),
                WebSocketRoute("/ws/projects/{pid}", ws_project), WebSocketRoute("/ws/org", ws_org),
                WebSocketRoute("/ws/tasks", ws_tasks), WebSocketRoute("/ws/agents", ws_agents),
                WebSocketRoute("/ws/notifications", ws_notifications), *extra],
        middleware=[Middleware(SecurityHeaders)],
        exception_handlers={HTTPError: http_error, Exception: server_error},
        lifespan=lifespan,
    )
    return app
