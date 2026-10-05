"""WS and SSE"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse

from apps.gateway.db import User, get_sessionmaker
from apps.gateway.events import bus
from packages.security.security import decode_token, COOKIE_NAME

router = APIRouter(tags=["stream"])

def _user_from_token(token: str | None):
    claims = decode_token(token) if token else None
    if not claims:
        return None
    db = get_sessionmaker()()
    try:
        u = db.query(User).filter(User.id == claims["sub"]).first()
        return u
    finally:
        db.close()

@router.get("/stream")
async def sse_stream(request: Request):
    token = request.cookies.get(COOKIE_NAME) or request.query_params.get("token") or (request.headers.get("authorization") or "").replace("Bearer ","")
    user = _user_from_token(token)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(401, "Not authenticated")
    q = bus.subscribe(asyncio.get_running_loop())

    async def gen():
        try:
            yield {"event": "ready", "data": json.dumps({"user_id": user.id})}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                # filter by user_id if present
                if evt.get("user_id") and evt["user_id"] != user.id:
                    continue
                yield {"event": "message", "data": json.dumps(evt)}
        finally:
            bus.unsubscribe(q)
    return EventSourceResponse(gen(), ping=15, headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    # accept token via query or cookie
    token = websocket.query_params.get("token") or websocket.cookies.get(COOKIE_NAME)
    if not token and websocket.headers.get("authorization"):
        token = websocket.headers.get("authorization", "").replace("Bearer ","")
    claims = decode_token(token) if token else None
    if not claims:
        await websocket.close(code=4401)
        return
    user_id = claims["sub"]
    await websocket.accept()
    q = bus.subscribe(asyncio.get_running_loop())
    try:
        while True:
            try:
                evt = await asyncio.wait_for(q.get(), timeout=25)
            except asyncio.TimeoutError:
                await websocket.send_json({"type":"PING"})
                continue
            if evt.get("user_id") and evt["user_id"] != user_id:
                continue
            await websocket.send_json(evt)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        bus.unsubscribe(q)
