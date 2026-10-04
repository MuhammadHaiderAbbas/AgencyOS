"""Demo seed: runs the REAL pipeline for "I want a website for my hotel." with the local
deterministic provider, and marks the project DEMO. Nothing is fabricated: every task,
artifact, test result and deployment comes from an actual execution.
"""
from __future__ import annotations

import secrets

from .agents.registry import seed_builtins
from .config import load_settings, settings
from .db import db, init_db, new_id, now
from .security import hash_password

DEMO_EMAIL = "demo@agencyos.local"
ANSWERS = ["The Grand Vista Hotel", "Lisbon, Portugal", "Luxury", "Online booking", "Deluxe King, Junior Suite, Penthouse",
           "Pay on arrival", "Guest checkout is fine", "Yes", "Gallery, Guest reviews, FAQ", "English", "Logo only",
           "Luxury & elegant", "dark green and gold", "skip", "skip", "skip"]


def seed_demo(password: str | None = None) -> dict:
    load_settings()
    s = settings()
    s.step_delay = 0
    init_db(s.database_path)
    seed_builtins()
    from .orchestration import project_service as ps
    from .orchestration.engine import orchestrator
    orchestrator.sync = True
    u = db().q1("SELECT * FROM users WHERE email = ?", (DEMO_EMAIL,))
    pw = password or secrets.token_urlsafe(9)
    if not u:
        uid, oid = new_id(), new_id()
        first = db().q1("SELECT COUNT(*) n FROM users")["n"] == 0
        db().insert("users", {"id": uid, "email": DEMO_EMAIL, "name": "Demo User", "password_hash": hash_password(pw), "is_admin": int(first), "created_at": now()})
        db().insert("organizations", {"id": oid, "name": "Demo workspace", "kind": "personal", "created_at": now()})
        db().insert("memberships", {"org_id": oid, "user_id": uid, "role": "owner", "created_at": now()})
    else:
        uid = u["id"]
        oid = db().q1("SELECT org_id FROM memberships WHERE user_id = ?", (uid,))["org_id"]
        db().update("users", {"id": uid}, {"password_hash": hash_password(pw)})
    user = {"id": uid, "name": "Demo User"}
    p = ps.create_project(user, oid, "I want a website for my hotel.", demo=True)
    for a in ANSWERS:
        cur = db().q1("SELECT * FROM projects WHERE id = ?", (p["id"],))
        if ps._state(p["id"]).get("awaiting_confirmation"):
            break
        ps.handle_message(cur, user, a)
    ps.approve_requirements(db().q1("SELECT * FROM projects WHERE id = ?", (p["id"],)), user)
    db().update("projects", {"id": p["id"]}, {"name": "[DEMO] The Grand Vista Hotel Website"})
    ps.start_build(db().q1("SELECT * FROM projects WHERE id = ?", (p["id"],)), user)
    a = db().q1("SELECT * FROM approvals WHERE project_id = ? AND gate = 'design' AND status = 'PENDING'", (p["id"],))
    if a:
        ps.decide_approval(a, "approve", user, None)
    orchestrator.sync = False
    return {"email": DEMO_EMAIL, "password": pw, "project_id": p["id"],
            "status": db().q1("SELECT status, progress FROM projects WHERE id = ?", (p["id"],))}
