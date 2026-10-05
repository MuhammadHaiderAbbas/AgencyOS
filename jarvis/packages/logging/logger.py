"""Structured JSON logging + correlation id."""
from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            data["exc_info"] = self.formatException(record.exc_info)
        # include extra fields set via logger.info(..., extra={...})
        for k, v in getattr(record, "__dict__", {}).items():
            if k not in {"name","msg","args","levelname","levelno","pathname","filename","module","exc_info","exc_text","stack_info","lineno","funcName","created","msecs","relativeCreated","thread","threadName","processName","process","message","asctime","request_id"}:
                if not k.startswith("_"):
                    try:
                        json.dumps(v)
                        data[k] = v
                    except Exception:
                        data[k] = str(v)
        return json.dumps(data, ensure_ascii=False)

def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # silence noisy libs
    for n in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(n).handlers.clear()
        logging.getLogger(n).propagate = True

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def new_request_id() -> str:
    rid = uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    return rid
