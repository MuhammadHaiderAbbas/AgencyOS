"""FastAPI factory — versioned API, middleware, lifecycle."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from apps.gateway.api.v1.auth import router as auth_router
from apps.gateway.api.v1.chat import router as chat_router
from apps.gateway.api.v1.tools import router as tools_router
from apps.gateway.api.v1.memory import router as memory_router
from apps.gateway.api.v1.tasks import router as tasks_router
from apps.gateway.api.v1.system import router as system_router
from apps.gateway.api.v1.security import router as security_router
from apps.gateway.api.v1.agents import router as agents_router
from apps.gateway.api.v1.notifications import router as notifications_router
from apps.gateway.api.v1.devices import router as devices_router
from apps.gateway.api.v1.ws import router as ws_router
from apps.gateway.db import init_db, get_sessionmaker
from apps.gateway.events import bus
from packages.config.config import load_settings, settings
from packages.logging.logger import setup_logging, new_request_id, request_id_var

logger = logging.getLogger("jarvis")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings().log_level)
    init_db()
    # try redis
    try:
        from packages.config.config import settings as cfg
        await bus.init_redis(cfg().redis_url)
    except Exception as e:
        logger.warning("Bus redis init failed: %s", e)
    logger.info("JARVIS gateway started env=%s db=%s", settings().env, settings().database_url)
    yield
    logger.info("JARVIS gateway stopping")

def create_app(**overrides) -> FastAPI:
    load_settings(**overrides)
    setup_logging(settings().log_level)

    app = FastAPI(title="JARVIS", version="0.1.0", description="AI Operating Layer — Just Another Rather Very Intelligent System", lifespan=lifespan)

    # middleware: request id + logging
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or new_request_id()
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response

    # CORS for dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # security headers
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if not request.url.path.startswith("/api/"):
            resp.headers.setdefault("X-Frame-Options", "DENY")
        return resp

    # health (no auth)
    @app.get("/api/v1/health", tags=["health"])
    def health():
        # check db
        try:
            db = get_sessionmaker()()
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
            db.close()
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {e}"
        redis_status = "ok" if bus._redis else "degraded (in-process)"
        llm = "local" if not settings().anthropic_api_key and not settings().openai_api_key else "configured"
        return {"status": "ok" if db_status=="ok" else "degraded", "version": app.version, "db": db_status, "redis": redis_status, "llm": llm}

    # mount versioned routers
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(tools_router, prefix="/api/v1")
    app.include_router(memory_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(system_router, prefix="/api/v1")
    app.include_router(security_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(devices_router, prefix="/api/v1")
    # WS/SSE are top-level /api/v1/stream and /api/v1/ws
    app.include_router(ws_router, prefix="/api/v1")

    # frontend static
    dist = settings().frontend_dist
    if dist.exists():
        # serve assets if built
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            # if requesting api assets already handled, else serve index
            fp = dist / path
            if path.startswith("api/"):
                return JSONResponse({"error":"Not found"}, status_code=404)
            if fp.exists() and fp.is_file():
                return FileResponse(fp)
            return FileResponse(dist / "index.html")
    else:
        @app.get("/", tags=["root"])
        def root():
            return {"name":"JARVIS", "version": app.version, "status":"ok", "docs":"/docs", "frontend":"not built — run `cd apps/web && npm install && npm run build`"}

    return app
