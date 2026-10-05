"""Database layer.

SQLite (stdlib) with portable SQL. All access goes through `Database`, so moving to
PostgreSQL means swapping this module's connection/placeholder handling only.
JSON columns are stored as TEXT and (de)serialised with `jdump`/`jload`.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  password_hash TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS organizations (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'personal',
  plan TEXT NOT NULL DEFAULT 'free', created_at TEXT NOT NULL,
  stripe_customer_id TEXT, stripe_subscription_id TEXT, stripe_price_id TEXT,
  billing_email TEXT, plan_updated_at TEXT
);
CREATE TABLE IF NOT EXISTS memberships (
  org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (org_id, user_id)
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  created_by TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL, idea TEXT NOT NULL,
  project_type TEXT, industry TEXT, status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
  template TEXT, is_demo INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0, estimated_cost_usd REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_projects_org ON projects(org_id);
CREATE TABLE IF NOT EXISTS requirement_versions (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  version INTEGER NOT NULL, data TEXT NOT NULL, status TEXT NOT NULL,
  change_note TEXT, created_at TEXT NOT NULL, UNIQUE(project_id, version)
);
CREATE TABLE IF NOT EXISTS interview_state (
  project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  data TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_messages (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  role TEXT NOT NULL, author TEXT NOT NULL, content TEXT NOT NULL, meta TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_chat_project ON chat_messages(project_id, created_at);
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT, description TEXT NOT NULL,
  source TEXT NOT NULL, framework TEXT NOT NULL, industry TEXT, category TEXT,
  definition TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
  executable INTEGER NOT NULL DEFAULT 1, health_status TEXT NOT NULL DEFAULT 'HEALTHY',
  health_detail TEXT, version TEXT NOT NULL DEFAULT '1.0.0', license TEXT, source_url TEXT,
  commit_hash TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_metrics (
  agent_id TEXT PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
  runs INTEGER NOT NULL DEFAULT 0, successes INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0, review_passes INTEGER NOT NULL DEFAULT 0,
  review_fails INTEGER NOT NULL DEFAULT 0, total_duration_ms INTEGER NOT NULL DEFAULT 0,
  total_cost_usd REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  key TEXT NOT NULL, phase TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
  role TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'work', status TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 2, assigned_agent TEXT, inputs TEXT, outputs TEXT,
  review_status TEXT, revision_count INTEGER NOT NULL DEFAULT 0, attempt_count INTEGER NOT NULL DEFAULT 0,
  feedback TEXT, position INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
  started_at TEXT, completed_at TEXT, UNIQUE(project_id, key)
);
CREATE INDEX IF NOT EXISTS ix_tasks_project ON tasks(project_id, status);
CREATE TABLE IF NOT EXISTS task_dependencies (
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  depends_on TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  PRIMARY KEY(task_id, depends_on)
);
CREATE TABLE IF NOT EXISTS agent_executions (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL, agent_id TEXT NOT NULL, role TEXT,
  status TEXT NOT NULL, input_summary TEXT, output_summary TEXT, tools_used TEXT, logs TEXT,
  errors TEXT, provider TEXT, model TEXT, tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0, cost_usd REAL NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0, confidence REAL, started_at TEXT NOT NULL, finished_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_exec_project ON agent_executions(project_id, started_at);
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL, type TEXT NOT NULL, phase TEXT, current_version INTEGER NOT NULL DEFAULT 1,
  approved_version INTEGER, status TEXT NOT NULL, author_agent TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(project_id, name)
);
CREATE TABLE IF NOT EXISTS artifact_versions (
  id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
  version INTEGER NOT NULL, content TEXT NOT NULL, content_type TEXT NOT NULL,
  author_agent TEXT NOT NULL, task_id TEXT, note TEXT, review_status TEXT,
  created_at TEXT NOT NULL, UNIQUE(artifact_id, version)
);
CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE, reviewer TEXT NOT NULL,
  verdict TEXT NOT NULL, issues TEXT, summary TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  gate TEXT NOT NULL, title TEXT NOT NULL, what_changed TEXT, why TEXT, impact TEXT,
  preview TEXT, status TEXT NOT NULL, task_id TEXT, decided_by TEXT, decision_note TEXT,
  created_at TEXT NOT NULL, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS project_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
  org_id TEXT, type TEXT NOT NULL, actor TEXT NOT NULL, message TEXT NOT NULL, data TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_project ON project_events(project_id, id);
CREATE INDEX IF NOT EXISTS ix_events_org ON project_events(org_id, id);
CREATE TABLE IF NOT EXISTS project_memory (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, source TEXT,
  created_at TEXT NOT NULL, UNIQUE(project_id, kind, key)
);
CREATE TABLE IF NOT EXISTS llm_usage (
  id TEXT PRIMARY KEY, org_id TEXT, project_id TEXT, execution_id TEXT, provider TEXT NOT NULL,
  model TEXT NOT NULL, purpose TEXT, tokens_in INTEGER NOT NULL, tokens_out INTEGER NOT NULL,
  cost_usd REAL NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deployments (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  provider TEXT NOT NULL, status TEXT NOT NULL, url TEXT, commit_hash TEXT, logs TEXT,
  created_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id TEXT, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT, read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS org_secrets (
  org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, name TEXT NOT NULL,
  ciphertext TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(org_id, name)
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, org_id TEXT, user_id TEXT, action TEXT NOT NULL,
  target TEXT, detail TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS billing_events (
  id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, plan TEXT, amount_cents INTEGER, currency TEXT DEFAULT 'usd',
  stripe_event_id TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS earnings (
  id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id TEXT, source TEXT NOT NULL, amount_cents INTEGER NOT NULL, currency TEXT NOT NULL DEFAULT 'usd',
  description TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_earnings_org ON earnings(org_id, created_at);
CREATE TABLE IF NOT EXISTS referrals (
  id TEXT PRIMARY KEY, referrer_org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  referred_org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending', reward_cents INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, UNIQUE(referred_org_id)
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


def jdump(v: Any) -> str | None:
    return None if v is None else json.dumps(v, default=str)


def jload(v: str | None, default: Any = None) -> Any:
    if v in (None, ""):
        return default
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return default


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(SCHEMA)
        # lightweight migrations for columns added after first release
        for sql in [
            "ALTER TABLE organizations ADD COLUMN stripe_customer_id TEXT",
            "ALTER TABLE organizations ADD COLUMN stripe_subscription_id TEXT",
            "ALTER TABLE organizations ADD COLUMN stripe_price_id TEXT",
            "ALTER TABLE organizations ADD COLUMN billing_email TEXT",
            "ALTER TABLE organizations ADD COLUMN plan_updated_at TEXT",
        ]:
            try:
                self._conn.execute(sql)
            except sqlite3.OperationalError:
                pass

    def q(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return [dict(r) for r in cur.fetchall()]

    def q1(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def ex(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return cur.lastrowid or cur.rowcount

    def insert(self, table: str, row: dict) -> dict:
        cols = ", ".join(row.keys())
        ph = ", ".join("?" for _ in row)
        self.ex(f"INSERT INTO {table} ({cols}) VALUES ({ph})", row.values())
        return row

    def update(self, table: str, where: dict, values: dict) -> int:
        sets = ", ".join(f"{k} = ?" for k in values)
        cond = " AND ".join(f"{k} = ?" for k in where)
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE {table} SET {sets} WHERE {cond}", (*values.values(), *where.values())
            )
            return cur.rowcount

    def transaction(self):
        db = self

        class _Tx:
            def __enter__(self_inner):
                db._lock.acquire()
                db._conn.execute("BEGIN")
                return db

            def __exit__(self_inner, exc_type, *_):
                try:
                    db._conn.execute("ROLLBACK" if exc_type else "COMMIT")
                finally:
                    db._lock.release()

        return _Tx()

    def ping(self) -> bool:
        try:
            self.q("SELECT 1")
            return True
        except sqlite3.Error:
            return False


_db: Database | None = None


def init_db(path: Path | str) -> Database:
    global _db
    _db = Database(path)
    return _db


def db() -> Database:
    if _db is None:
        raise RuntimeError("Database not initialised")
    return _db
