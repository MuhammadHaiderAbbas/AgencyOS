"""SQLAlchemy models + init. SQLite for dev, Postgres for prod."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, create_engine, text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from packages.config.config import settings as cfg_settings

def _now():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

# JSON type that works on both SQLite and Postgres
try:
    from sqlalchemy import JSON as SA_JSON
    JSONType = SA_JSON
except Exception:
    JSONType = Text

# Helpers for id default
def uid() -> str:
    return uuid.uuid4().hex

# ---------------- Models ----------------

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")  # user/admin
    locale: Mapped[str] = mapped_column(String(10), default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    personality: Mapped[str] = mapped_column(String(32), default="professional")
    trust_level: Mapped[str] = mapped_column(String(20), default="balanced")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferences: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(32), default="desktop")
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    permissions: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="offline")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(String(32), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    role: Mapped[str] = mapped_column(String(20))  # user/assistant/system/tool
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="episodic")  # working/episodic/semantic
    content: Mapped[str] = mapped_column(Text)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    source: Mapped[str] = mapped_column(String(64), default="user")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

class MemoryEmbedding(Base):
    __tablename__ = "memory_embeddings"
    memory_id: Mapped[str] = mapped_column(String(32), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[str] = mapped_column(Text)  # JSON array for SQLite, vector for PG
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    text: Mapped[str] = mapped_column(String(500))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recurrence: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")

class ToolRecord(Base):
    __tablename__ = "tools"
    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32))
    risk: Mapped[str] = mapped_column(String(20), default="low")
    parameters_schema: Mapped[dict] = mapped_column(JSONType)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class AgentRecord(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text)
    allowed_tools: Mapped[dict] = mapped_column(JSONType)  # list
    system_prompt: Mapped[str] = mapped_column(Text)
    model_tier: Mapped[str] = mapped_column(String(20), default="standard")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued/running/awaiting_approval/succeeded/failed/cancelled
    steps: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    execution_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("executions.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tool: Mapped[str] = mapped_column(String(128))
    what: Mapped[str] = mapped_column(Text)
    why: Mapped[str] = mapped_column(Text)
    target: Mapped[str] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/granted/denied
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    arguments_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_status: Mapped[str] = mapped_column(String(20), default="success")
    risk_level: Mapped[int] = mapped_column(Integer, default=0)
    approval_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), default="info")  # info/warning/approval/security/system/calendar/message/automation
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    trigger: Mapped[dict] = mapped_column(JSONType)
    actions: Mapped[dict] = mapped_column(JSONType)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

# ---------------- Engine / Session ----------------

_engine = None
_SessionLocal = None
_last_url = None

def get_engine():
    global _engine, _last_url, _SessionLocal
    url = cfg_settings().database_url
    if _engine is not None and _last_url == url:
        return _engine
    # url changed -> recreate
    if _engine is not None and _last_url != url:
        try:
            _engine.dispose()
        except Exception:
            pass
        _engine = None
        _SessionLocal = None
    # ensure data dir exists for sqlite
    if url.startswith("sqlite"):
        # url like sqlite:///./data/jarvis.sqlite3
        path = url.split("///")[-1]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False}, echo=False, future=True)
    else:
        _engine = create_engine(url, echo=False, future=True, pool_pre_ping=True)
    _last_url = url
    return _engine

def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return _SessionLocal

def reset_db():
    global _engine, _SessionLocal, _last_url
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _SessionLocal = None
    _last_url = None

def init_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    # seed tools/agents if empty
    from sqlalchemy.orm import Session
    db: Session = get_sessionmaker()()
    try:
        if db.query(AgentRecord).count() == 0:
            seed_agents(db)
        if db.query(ToolRecord).count() == 0:
            seed_tools(db)
        db.commit()
    finally:
        db.close()

def seed_agents(db):
    defaults = [
        ("general", "General Assistant", "General reasoning fallback", ["system.cpu_status","system.ram_status","system.disk_status","files.search","files.read","search.web"], "You are JARVIS, a helpful AI operating layer.", "standard"),
        ("research", "Research Agent", "Web research and summarization", ["search.web","browser.open","browser.search"], "You are a research specialist.", "advanced"),
        ("computer", "Computer Agent", "Computer control", ["computer.open_application","computer.close_application","computer.screenshot","system.diagnostics"], "You control the computer.", "standard"),
        ("file", "File Agent", "File operations", ["files.read","files.write","files.search","files.list"], "You manage files.", "standard"),
        ("developer", "Developer Agent", "Code analysis", ["files.read","files.search","system.diagnostics"], "You are a developer assistant.", "code"),
        ("communication", "Communication Agent", "Email and messaging", ["email.draft","email.send","messaging.send"], "You handle communications.", "standard"),
        ("scheduling", "Scheduling Agent", "Calendar and reminders", ["calendar.get_today","calendar.create_event","tasks.create","tasks.list"], "You manage schedules.", "small"),
        ("automation", "Automation Agent", "Workflows", ["automation.run_workflow"], "You run automations.", "standard"),
        ("vision", "Vision Agent", "Image analysis", ["vision.analyze_image","computer.screenshot"], "You analyze images.", "vision"),
        ("system", "System Agent", "Diagnostics", ["system.cpu_status","system.ram_status","system.disk_status","system.diagnostics"], "You monitor system.", "small"),
        ("security", "Security Agent", "Security monitoring", ["system.diagnostics"], "You enforce security.", "standard"),
    ]
    for name, disp, desc, tools, prompt, tier in defaults:
        db.add(AgentRecord(id=name, name=disp, description=desc, allowed_tools=tools, system_prompt=prompt, model_tier=tier))

def seed_tools(db):
    import json
    tools = [
        ("system.cpu_status", "Get CPU usage", "system", "low", {"type":"object","properties":{},"additionalProperties":False}, False),
        ("system.ram_status", "Get RAM usage", "system", "low", {"type":"object","properties":{},"additionalProperties":False}, False),
        ("system.disk_status", "Get disk usage", "system", "low", {"type":"object","properties":{},"additionalProperties":False}, False),
        ("system.diagnostics", "Run diagnostics", "system", "low", {"type":"object","properties":{},"additionalProperties":False}, False),
        ("computer.open_application", "Open an installed application", "computer", "low", {"type":"object","properties":{"application":{"type":"string"}},"required":["application"]}, False),
        ("computer.close_application", "Close an application", "computer", "moderate", {"type":"object","properties":{"application":{"type":"string"}},"required":["application"]}, False),
        ("computer.screenshot", "Take a screenshot", "computer", "low", {"type":"object","properties":{},"additionalProperties":False}, False),
        ("files.read", "Read a file", "files", "low", {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}, False),
        ("files.write", "Write a file", "files", "moderate", {"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}, False),
        ("files.search", "Search files", "files", "low", {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, False),
        ("files.list", "List directory", "files", "low", {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}, False),
        ("calendar.get_today", "Get today's calendar", "calendar", "low", {"type":"object","properties":{},"additionalProperties":False}, False),
        ("calendar.create_event", "Create calendar event", "calendar", "low", {"type":"object","properties":{"title":{"type":"string"},"when":{"type":"string"}},"required":["title","when"]}, False),
        ("tasks.create", "Create a task", "tasks", "low", {"type":"object","properties":{"title":{"type":"string"},"priority":{"type":"string"}},"required":["title"]}, False),
        ("tasks.list", "List tasks", "tasks", "low", {"type":"object","properties":{},"additionalProperties":False}, False),
        ("search.web", "Search the web", "search", "low", {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, False),
        ("browser.open", "Open URL in browser", "browser", "low", {"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}, False),
        ("browser.search", "Search via browser", "browser", "low", {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, False),
        ("email.draft", "Draft an email", "email", "low", {"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}, False),
        ("email.send", "Send an email", "email", "high", {"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}, True),
        ("vision.analyze_image", "Analyze an image", "vision", "low", {"type":"object","properties":{"image_url":{"type":"string"}},"required":["image_url"]}, False),
        ("automation.run_workflow", "Run a workflow", "automation", "moderate", {"type":"object","properties":{"workflow_id":{"type":"string"}},"required":["workflow_id"]}, False),
    ]
    for name, desc, cat, risk, schema, appr in tools:
        db.add(ToolRecord(name=name, description=desc, category=cat, risk=risk, parameters_schema=schema, requires_approval=appr))
