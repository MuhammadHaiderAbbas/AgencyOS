"""Change Request Engine: user request -> impact analysis -> PM -> affected tasks re-run.

User requests never modify code directly. They update requirements/memory, then the
affected tasks (and everything downstream) are re-queued with the request as feedback.
"""
from __future__ import annotations

import copy
import re

from ..db import db, jdump, jload, new_id, now
from ..events import bus
from .interview import FEATURE_LABELS, finalize, parse_change, public_requirements
from .planner import downstream

DESIGN_WORDS = re.compile(r"\b(design|colou?r|look|style|luxur|elegan|modern|minimal|font|typography|dark|light|bold|warm|brand|button)", re.I)
COPY_WORDS = re.compile(r"\b(text|copy|wording|headline|title|tagline|description|content|write)", re.I)
LAYOUT_WORDS = re.compile(r"\b(page|section|layout|homepage|menu|navigation)", re.I)
STYLE_MAP = {"luxurious": "Luxury & elegant", "luxury": "Luxury & elegant", "elegant": "Luxury & elegant",
             "minimal": "Modern & minimal", "modern": "Modern & minimal", "bold": "Bold & vibrant",
             "warm": "Warm & welcoming", "playful": "Bold & vibrant"}
BACKEND_FEATURES = {"booking", "payments", "accounts", "admin_dashboard", "newsletter"}


# Upstream producers are only re-run when the change targets them directly.
NO_CASCADE = {"research", "architecture", "ui_design_system", "ba_requirements", "ux_structure", "db_schema", "backend"}


def impacted(project_id: str, keys: list[str], tasks: dict[str, dict]) -> set[str]:
    ids = {tasks[k]["id"] for k in keys if k in tasks}
    by_id = {t["id"]: t for t in tasks.values()}
    return ids | {d for d in downstream(project_id, ids) if by_id[d]["key"] not in NO_CASCADE}


def analyze(project_id: str, text: str) -> dict:
    from .engine import current_requirements
    req = current_requirements(project_id)
    pc = parse_change(text)
    keys: list[str] = []
    notes: list[str] = []
    contradictions = []
    adds = []
    for f in pc["add"]:
        if f in req.get("features", []):
            continue
        if req.get("_explicit", {}).get(f) is False:
            contradictions.append(f"You previously asked for no {FEATURE_LABELS.get(f, f)}. Should I update the requirements to include it?")
        adds.append(f)
    pc["add"] = adds
    pc["remove"] = [f for f in pc["remove"] if f in req.get("features", [])]
    req_change = bool(pc["add"] or pc["remove"])
    if req_change:
        keys += ["ba_requirements", "ux_structure", "content", "frontend"]
        if set(pc["add"] + pc["remove"]) & BACKEND_FEATURES:
            keys += ["architecture", "db_schema", "backend"]
    if pc["colors"] or pc["avoid_colors"] or pc["style"] or DESIGN_WORDS.search(text):
        keys += ["ui_design_system", "frontend"]
        if pc["style"]:
            keys.append("content")
    if COPY_WORDS.search(text):
        keys += ["content", "frontend"]
    if LAYOUT_WORDS.search(text) and not keys:
        keys += ["ux_structure", "frontend"]
    existing = {t["key"]: t for t in db().q("SELECT * FROM tasks WHERE project_id = ?", (project_id,))}
    keys = [k for k in dict.fromkeys(keys) if k in existing]
    if not keys:
        return {"understood": False, "summary": "I couldn't map that to a specific change. Could you say what should change (e.g. a colour, a page, a feature)?"}
    hit = impacted(project_id, keys, existing)
    affected = [t for t in existing.values() if t["id"] in hit]
    roles = sorted({t["role"] for t in affected if t["kind"] != "approval"})
    work = [t for t in affected if t["kind"] in ("work", "check", "fix")]
    parts = []
    if pc["add"]:
        parts.append("add " + ", ".join(FEATURE_LABELS.get(f, f) for f in pc["add"]))
    if pc["remove"]:
        parts.append("remove " + ", ".join(FEATURE_LABELS.get(f, f) for f in pc["remove"]))
    if pc["avoid_colors"]:
        parts.append("avoid " + ", ".join(pc["avoid_colors"]))
    if pc["colors"]:
        parts.append("use " + ", ".join(pc["colors"]))
    if pc["style"]:
        parts.append(f"make the design more {pc['style']}")
    if not parts:
        parts.append("revise " + ("design" if "ui_design_system" in keys else "content" if "content" in keys else "structure"))
    return {"understood": True, "id": new_id(), "text": text, "parsed": pc, "summary": "; ".join(parts),
            "requirement_change": req_change, "contradictions": contradictions + notes,
            "affected_tasks": [t["title"] for t in affected], "affected_task_keys": keys,
            "affected_agents": roles, "affected_components": sorted({t["phase"] for t in affected}),
            "estimated_tasks": len(work), "estimated_minutes": max(1, round(len(work) * 0.25)),
            "estimated_cost_usd": 0.0 if _is_mock(project_id) else round(len(work) * 0.02, 2),
            "requires_reapproval": ["gate_uat", "gate_deploy"]}


def _is_mock(project_id: str) -> bool:
    from ..llm.router import resolve_provider
    p = db().q1("SELECT org_id FROM projects WHERE id = ?", (project_id,))
    return resolve_provider(p["org_id"] if p else None)[0].name == "mock"


def remember(project_id: str, kind: str, key: str, value: str, source: str) -> None:
    db().ex("INSERT INTO project_memory (id, project_id, kind, key, value, source, created_at) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(project_id, kind, key) DO UPDATE SET value = excluded.value, source = excluded.source",
            (new_id(), project_id, kind, key, value, source, now()))


def apply_change(project_id: str, text: str, user_id: str, source_gate: str | None = None, analysis: dict | None = None) -> dict:
    from .engine import current_requirements, orchestrator, post_agent_message
    a = analysis or analyze(project_id, text)
    if not a.get("understood"):
        if source_gate:  # a rejected gate with vague feedback: re-run that gate's producers with the note as feedback
            a = {"understood": True, "parsed": parse_change(""), "summary": text, "requirement_change": False,
                 "affected_task_keys": {"design": ["ui_design_system", "ux_structure"], "uat": ["frontend"]}.get(source_gate, ["frontend"])}
        else:
            return a
    pc = a["parsed"]
    req = current_requirements(project_id)
    if a.get("requirement_change") or pc["colors"] or pc["avoid_colors"] or pc["style"]:
        new = copy.deepcopy(req)
        for f in pc["add"]:
            if f not in new["features"]:
                new["features"].append(f)
            new.setdefault("_explicit", {})[f] = True
            if f == "payments" and "Stripe" not in new["integrations"]:
                new["integrations"].append("Stripe")
        for f in pc["remove"]:
            if f in new["features"]:
                new["features"].remove(f)
            new.setdefault("_explicit", {})[f] = False
        dp = new["design_preferences"]
        dp["avoid_colors"] = sorted(set(dp.get("avoid_colors") or []) | set(pc["avoid_colors"]))
        dp["colors"] = [c for c in (pc["colors"] or dp.get("colors") or []) if c not in dp["avoid_colors"]]
        if pc["style"]:
            dp["style"] = STYLE_MAP.get(pc["style"], dp.get("style"))
        new = finalize(new)
        v = (db().q1("SELECT MAX(version) v FROM requirement_versions WHERE project_id = ?", (project_id,))["v"] or 0) + 1
        db().insert("requirement_versions", {"id": new_id(), "project_id": project_id, "version": v, "data": jdump(new),
                                             "status": "APPROVED", "change_note": text[:500], "created_at": now()})
        bus.publish(type="REQUIREMENT_UPDATED", project_id=project_id, actor="Change Analyst", message=f"Requirements v{v}: {a['summary']}")
        from .planner import extend_plan
        added = extend_plan(project_id, new)
        a["affected_task_keys"] = list(a["affected_task_keys"]) + added
    for c in pc["avoid_colors"]:
        remember(project_id, "preference", f"avoid_color:{c}", "true", text[:200])
    if pc["style"]:
        remember(project_id, "preference", "style", STYLE_MAP.get(pc["style"], pc["style"]), text[:200])
    remember(project_id, "decision", f"change:{now()}", a["summary"], text[:200])
    # reset affected + downstream tasks
    tasks = {t["key"]: t for t in db().q("SELECT * FROM tasks WHERE project_id = ?", (project_id,))}
    ids = {tasks[k]["id"] for k in a["affected_task_keys"] if k in tasks}
    all_ids = impacted(project_id, a["affected_task_keys"], tasks)
    keep_gate = source_gate != "design" and not a.get("requirement_change")
    reset = 0
    for t in tasks.values():
        if t["id"] not in all_ids:
            continue
        if t["key"] == "gate_design" and keep_gate:
            continue
        if t["key"].startswith(("fix_", "rebuild_")):
            continue
        fb = [text] if t["id"] in ids else []
        db().update("tasks", {"id": t["id"]}, {"status": "BACKLOG", "feedback": jdump(fb), "review_status": None,
                                               "revision_count": 0, "attempt_count": 0, "completed_at": None})
        reset += 1
    db().ex("UPDATE approvals SET status = 'SUPERSEDED' WHERE project_id = ? AND status = 'PENDING'", (project_id,))
    db().update("projects", {"id": project_id}, {"status": "DEVELOPMENT", "updated_at": now()})
    bus.publish(type="CHANGE_REQUEST", project_id=project_id, actor="Project Manager",
                message=f"Change request applied: {a['summary']} — {reset} task(s) re-queued", data={"analysis": {k: v for k, v in a.items() if k != 'parsed'}})
    post_agent_message(project_id, "Project Manager",
                       f"Change accepted: **{a['summary']}**. I've re-queued {reset} task(s) for "
                       f"{', '.join(sorted({tasks[k]['role'].replace('_', ' ') for k in a['affected_task_keys'] if k in tasks}))}. "
                       "You'll be asked to review the result before anything is redeployed.", {"type": "change_applied"})
    orchestrator.enqueue(project_id)
    return {**a, "reset_tasks": reset}
