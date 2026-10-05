"""InputManager — normalizes all inputs into canonical Event."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from packages.common.types import Event

class InputManager:
    def normalize(
        self,
        content: str,
        source: str = "text",
        user_id: str | None = None,
        session_id: str | None = None,
        device_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Event:
        return Event(
            event_id=uuid.uuid4().hex,
            type="USER_MESSAGE",
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            session_id=session_id,
            device_id=device_id,
            content=content,
            attachments=attachments or [],
            metadata=metadata or {},
            trace_id=uuid.uuid4().hex,
        )

input_manager = InputManager()
