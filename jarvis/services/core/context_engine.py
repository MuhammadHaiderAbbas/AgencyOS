"""ContextEngine — combines short-term, long-term, and environmental context."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from apps.gateway.db import Conversation, Memory, Message, get_sessionmaker

class ContextEngine:
    def build(self, user_id: str, current_message: str, conversation_id: str | None = None) -> dict[str, Any]:
        db: Session = get_sessionmaker()()
        try:
            # short-term: last 10 messages
            recent = []
            if conversation_id:
                msgs = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(10).all()
                recent = [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None} for m in reversed(msgs)]
            # long-term: semantic memories search (naive: top 5 by importance)
            mems = db.query(Memory).filter(Memory.user_id == user_id).order_by(Memory.importance.desc()).limit(5).all()
            long_term = [{"content": m.content, "kind": m.kind, "importance": m.importance} for m in mems]
            # environmental
            env = {
                "time": datetime.now(timezone.utc).isoformat(),
                "date": datetime.now(timezone.utc).date().isoformat(),
            }
            return {"recent_messages": recent, "memories": long_term, "environment": env, "user_id": user_id}
        finally:
            db.close()

context_engine = ContextEngine()
