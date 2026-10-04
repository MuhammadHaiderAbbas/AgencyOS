"""Versioned artifact store. Never overwrites: every save is a new version.

Artifacts are mirrored into the project workspace (e.g. design/design-system.json) and
committed to git by the authoring agent's role, so the repo history mirrors the store.
"""
from __future__ import annotations

import difflib
import json
from typing import Any

from ..db import db, jdump, new_id, now
from ..events import bus
from . import workspace

TYPE_DIR = {
    "requirements": "requirements", "user_stories": "requirements", "research": "research", "sitemap": "design",
    "user_flows": "design", "wireframes": "design", "design_system": "design", "architecture": "architecture",
    "architecture_spec": "architecture", "content": "design", "seo_plan": "design", "database_schema": "architecture",
    "api_spec": "architecture", "qa_report": "reports", "accessibility_report": "reports", "performance_report": "reports",
    "security_report": "reports", "deployment_plan": "deployment", "project_plan": "requirements",
    "documentation": "deployment", "source_manifest": "artifacts", "custom": "artifacts", "external_output": "artifacts",
}

PHASE_OF = {
    "requirements": "requirements", "user_stories": "requirements", "project_plan": "planning", "research": "research",
    "sitemap": "ux", "user_flows": "ux", "wireframes": "ux", "design_system": "ui", "architecture": "architecture",
    "architecture_spec": "architecture", "content": "content", "seo_plan": "content", "database_schema": "development",
    "api_spec": "development", "source_manifest": "development", "qa_report": "testing", "accessibility_report": "testing",
    "performance_report": "testing", "security_report": "security", "documentation": "documentation", "deployment_plan": "deployment",
}


def _serialise(content: Any, content_type: str) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, indent=2, ensure_ascii=False)


def save(project_id: str, name: str, type_: str, content: Any, content_type: str, author: str,
         task_id: str | None = None, note: str | None = None, mirror: bool = True) -> dict:
    text = _serialise(content, content_type)
    art = db().q1("SELECT * FROM artifacts WHERE project_id = ? AND name = ?", (project_id, name))
    ts = now()
    if art:
        last = db().q1("SELECT content FROM artifact_versions WHERE artifact_id = ? AND version = ?", (art["id"], art["current_version"]))
        if last and last["content"] == text:
            return {**art, "unchanged": True}
        version = art["current_version"] + 1
        db().update("artifacts", {"id": art["id"]}, {"current_version": version, "status": "IN_REVIEW", "updated_at": ts,
                                                     "author_agent": author})
        aid = art["id"]
        evt = "ARTIFACT_UPDATED"
    else:
        aid, version = new_id(), 1
        db().insert("artifacts", {"id": aid, "project_id": project_id, "name": name, "type": type_, "phase": PHASE_OF.get(type_),
                                  "current_version": 1, "approved_version": None, "status": "IN_REVIEW", "author_agent": author,
                                  "created_at": ts, "updated_at": ts})
        evt = "ARTIFACT_CREATED"
    db().insert("artifact_versions", {"id": new_id(), "artifact_id": aid, "version": version, "content": text,
                                      "content_type": content_type, "author_agent": author, "task_id": task_id, "note": note,
                                      "review_status": "PENDING", "created_at": ts})
    if mirror:
        p = workspace.ensure(project_id) / TYPE_DIR.get(type_, "artifacts") / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    bus.publish(type=evt, project_id=project_id, actor=author,
                message=f"{author} {'created' if version == 1 else 'updated'} {name} (v{version})",
                data={"artifact_id": aid, "name": name, "version": version})
    return {"id": aid, "name": name, "version": version}


def latest(project_id: str, name: str, approved_only: bool = False) -> Any:
    art = db().q1("SELECT * FROM artifacts WHERE project_id = ? AND name = ?", (project_id, name))
    if not art:
        return None
    v = art["approved_version"] if approved_only and art["approved_version"] else art["current_version"]
    row = db().q1("SELECT content, content_type FROM artifact_versions WHERE artifact_id = ? AND version = ?", (art["id"], v))
    if not row:
        return None
    if row["content_type"] == "application/json":
        try:
            return json.loads(row["content"])
        except ValueError:
            return row["content"]
    return row["content"]


def set_review(project_id: str, name: str, status: str) -> None:
    art = db().q1("SELECT * FROM artifacts WHERE project_id = ? AND name = ?", (project_id, name))
    if not art:
        return
    db().ex("UPDATE artifact_versions SET review_status = ? WHERE artifact_id = ? AND version = ?", (status, art["id"], art["current_version"]))
    if status == "APPROVED":
        db().update("artifacts", {"id": art["id"]}, {"status": "APPROVED", "approved_version": art["current_version"], "updated_at": now()})
    elif status == "REJECTED":
        db().update("artifacts", {"id": art["id"]}, {"status": "REVISION_REQUIRED", "updated_at": now()})


def approve_version(artifact_id: str, version: int, actor: str) -> None:
    art = db().q1("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
    db().update("artifacts", {"id": artifact_id}, {"approved_version": version, "status": "APPROVED", "updated_at": now()})
    db().ex("UPDATE artifact_versions SET review_status = 'APPROVED' WHERE artifact_id = ? AND version = ?", (artifact_id, version))
    bus.publish(type="ARTIFACT_APPROVED", project_id=art["project_id"], actor=actor, message=f"{art['name']} v{version} approved",
                data={"artifact_id": artifact_id, "version": version})


def restore(artifact_id: str, version: int, actor: str) -> dict:
    art = db().q1("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
    row = db().q1("SELECT * FROM artifact_versions WHERE artifact_id = ? AND version = ?", (artifact_id, version))
    if not art or not row:
        raise KeyError("version not found")
    res = save(art["project_id"], art["name"], art["type"], row["content"], row["content_type"], actor,
               note=f"Restored from v{version}")
    bus.publish(type="ARTIFACT_RESTORED", project_id=art["project_id"], actor=actor,
                message=f"{art['name']} restored from v{version}", data={"artifact_id": artifact_id})
    workspace.commit(art["project_id"], "user", f"restore {art['name']} v{version}")
    return res


def diff(artifact_id: str, a: int, b: int) -> str:
    rows = {r["version"]: r["content"] for r in db().q(
        "SELECT version, content FROM artifact_versions WHERE artifact_id = ? AND version IN (?, ?)", (artifact_id, a, b))}
    return "".join(difflib.unified_diff(rows.get(a, "").splitlines(True), rows.get(b, "").splitlines(True), f"v{a}", f"v{b}"))
