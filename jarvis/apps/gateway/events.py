"""EventBus — in-process fanout with optional Redis."""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

log = logging.getLogger("jarvis.bus")

class EventBus:
    def __init__(self):
        self._subs: set[asyncio.Queue] = set()
        self._redis = None
        self._history: list[dict[str, Any]] = []
        self._max_history = 500

    async def init_redis(self, url: str | None):
        if not url:
            return
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(url, decode_responses=True)
            await self._redis.ping()
            log.info("Redis connected for EventBus")
        except Exception as e:
            log.warning("Redis unavailable, using in-process bus: %s", e)
            self._redis = None

    def subscribe(self, loop: asyncio.AbstractEventLoop | None = None) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subs.discard(q)

    def publish(self, event: dict[str, Any]):
        # persist history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        # fanout to subscribers
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("Subscriber queue full, dropping event %s", event.get("type"))
        # optional redis publish
        if self._redis:
            try:
                asyncio.create_task(self._redis.publish("jarvis:events", json.dumps(event)))
            except Exception:
                pass

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._history[-limit:]

bus = EventBus()
