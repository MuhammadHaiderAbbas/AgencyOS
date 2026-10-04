"""Event system.

Every state change emits an event. Events are persisted (activity feed, audit) and
fanned out to live subscribers (WebSocket connections). Publishing is thread-safe so
agent workers running in executor threads can emit events.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any

from .db import db, jdump, jload, now

EVENT_TYPES = {
    "PROJECT_CREATED", "PROJECT_UPDATED", "REQUIREMENT_UPDATED", "REQUIREMENTS_APPROVED",
    "PLAN_CREATED", "TASK_CREATED", "TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED", "TASK_BLOCKED",
    "TASK_REVISION", "ARTIFACT_CREATED", "ARTIFACT_UPDATED", "ARTIFACT_APPROVED", "ARTIFACT_RESTORED",
    "REVIEW_PASSED", "REVIEW_FAILED", "AGENT_STARTED", "AGENT_COMPLETED", "AGENT_FAILED",
    "USER_MESSAGE", "AGENT_MESSAGE", "APPROVAL_REQUIRED", "APPROVAL_DECIDED", "CHANGE_REQUEST",
    "BUG_REPORTED", "BUILD_SUCCEEDED", "BUILD_FAILED", "DEPLOYMENT_STARTED", "DEPLOYMENT_COMPLETED",
    "DEPLOYMENT_FAILED", "PROJECT_COMPLETED", "PROJECT_BLOCKED", "ESCALATION", "NOTIFICATION",
}


class EventBus:
    def __init__(self) -> None:
        self._subs: list[tuple[asyncio.Queue, asyncio.AbstractEventLoop, dict]] = []
        self._lock = threading.Lock()

    def subscribe(self, loop: asyncio.AbstractEventLoop, *, org_id: str, project_id: str | None = None):
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        flt = {"org_id": org_id, "project_id": project_id}
        with self._lock:
            self._subs.append((q, loop, flt))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs = [s for s in self._subs if s[0] is not q]

    def publish(self, *, type: str, message: str, project_id: str | None = None,
                org_id: str | None = None, actor: str = "system", data: dict[str, Any] | None = None) -> dict:
        assert type in EVENT_TYPES, f"unknown event type {type}"
        if org_id is None and project_id:
            p = db().q1("SELECT org_id FROM projects WHERE id = ?", (project_id,))
            org_id = p["org_id"] if p else None
        created = now()
        eid = db().ex(
            "INSERT INTO project_events (project_id, org_id, type, actor, message, data, created_at) VALUES (?,?,?,?,?,?,?)",
            (project_id, org_id, type, actor, message, jdump(data or {}), created),
        )
        evt = {"id": eid, "project_id": project_id, "org_id": org_id, "type": type, "actor": actor,
               "message": message, "data": data or {}, "created_at": created}
        with self._lock:
            subs = list(self._subs)
        for q, loop, flt in subs:
            if flt["org_id"] != org_id:
                continue  # tenant isolation for live streams
            if flt["project_id"] and flt["project_id"] != project_id:
                continue
            try:
                loop.call_soon_threadsafe(_put_nowait, q, evt)
            except RuntimeError:
                pass  # loop closed
        return evt


def _put_nowait(q: asyncio.Queue, evt: dict) -> None:
    try:
        q.put_nowait(evt)
    except asyncio.QueueFull:
        pass


bus = EventBus()


def row_to_event(r: dict) -> dict:
    r = dict(r)
    r["data"] = jload(r.get("data"), {})
    return r
