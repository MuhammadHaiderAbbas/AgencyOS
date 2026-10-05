"""Shared types: Event, Intent, Plan, ToolDef, PermissionLevel."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import IntEnum, Enum
from typing import Any

from pydantic import BaseModel, Field

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def new_id() -> str:
    return uuid.uuid4().hex

class PermissionLevel(IntEnum):
    SAFE = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    CRITICAL = 4

class Event(BaseModel):
    event_id: str = Field(default_factory=new_id)
    type: str
    source: str = "text"
    timestamp: str = Field(default_factory=_now)
    user_id: str | None = None
    session_id: str | None = None
    device_id: str | None = None
    content: str = ""
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None

class Intent(BaseModel):
    intent: str
    goal: str
    actions: list[dict[str, Any]] = Field(default_factory=list)
    slots: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    risk_level: int = 0
    confidence: float = 0.9
    raw: str = ""

class PlanStep(BaseModel):
    id: str = Field(default_factory=new_id)
    tool: str | None = None
    description: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    agent: str | None = None
    risk_level: int = 0
    requires_approval: bool = False

class Plan(BaseModel):
    plan_id: str = Field(default_factory=new_id)
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    risk_level: int = 0
    requires_confirmation: bool = False
    reasoning: str = ""

class ApprovalRequest(BaseModel):
    what: str
    why: str
    target: str
    risk: str

class ToolCategory(str, Enum):
    computer = "computer"
    browser = "browser"
    files = "files"
    system = "system"
    calendar = "calendar"
    email = "email"
    messaging = "messaging"
    media = "media"
    developer = "developer"
    database = "database"
    search = "search"
    vision = "vision"
    audio = "audio"
    automation = "automation"
    smart_home = "smart_home"
    tasks = "tasks"
