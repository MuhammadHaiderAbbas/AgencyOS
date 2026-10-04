"""Project Manager planning: approved requirements -> team -> task graph (DAG)."""
from __future__ import annotations

from ..db import db, jdump, new_id, now
from ..events import bus
from .teams import ROLE_LABELS, build_team


# key, phase, title, role, kind, outputs, inputs, deps, condition(team)
TEMPLATE = [
    ("ba_requirements", "requirements", "Document requirements & user stories", "business_analyst", "work",
     ["requirements.md", "user-stories.json"], [], []),
    ("research", "research", "Research audience & market", "researcher", "work", ["research.json"], [], ["ba_requirements"]),
    ("ux_structure", "ux", "Sitemap, user flows & wireframes", "ux_designer", "work",
     ["sitemap.json", "user-flows.json", "wireframes.json"], ["user-stories.json", "research.json"], ["ba_requirements", "research"]),
    ("ui_design_system", "ui", "Visual design system", "ui_designer", "work", ["design-system.json"], ["sitemap.json"], ["ux_structure"]),
    ("architecture", "architecture", "Solution architecture", "architect", "work", ["architecture.md", "architecture.json"],
     ["requirements.md"], ["ba_requirements"]),
    ("gate_design", "ui", "Client approval: design & architecture", "project_manager", "approval", [], [],
     ["ui_design_system", "architecture"]),
    ("content", "content", "Write website copy", "content_writer", "work", ["content.json"],
     ["sitemap.json", "wireframes.json", "design-system.json"], ["ux_structure", "ui_design_system"]),
    ("seo", "content", "SEO plan & metadata", "seo_specialist", "work", ["seo-plan.json"], ["sitemap.json", "content.json"], ["content"]),
    ("db_schema", "development", "Database schema", "database_engineer", "work", ["database-schema.sql"], ["architecture.json"],
     ["architecture", "gate_design"]),
    ("backend", "development", "Implement API & unit tests", "backend_developer", "work", ["api-spec.yaml"],
     ["architecture.json", "content.json", "database-schema.sql"], ["db_schema", "content"]),
    ("frontend", "development", "Implement website pages", "frontend_developer", "work", ["source-manifest.json"],
     ["sitemap.json", "wireframes.json", "design-system.json", "content.json", "seo-plan.json"], ["gate_design", "content", "seo"]),
    ("qa", "testing", "QA: functional, responsive & visual tests", "qa_engineer", "check", ["qa-report.json"],
     ["sitemap.json", "design-system.json"], ["frontend", "backend"]),
    ("accessibility", "testing", "Accessibility audit", "accessibility_specialist", "check", ["accessibility-report.json"],
     ["design-system.json"], ["frontend"]),
    ("performance", "testing", "Performance audit", "performance_engineer", "check", ["performance-report.json"], [], ["frontend"]),
    ("security", "security", "Security review", "security_engineer", "check", ["security-report.json"], [], ["frontend", "backend"]),
    ("docs", "documentation", "Documentation", "technical_writer", "work", ["documentation.md"], ["content.json"], ["qa"]),
    ("deploy_plan", "deployment", "Deployment plan", "devops_engineer", "work", ["deployment-plan.md"], [], ["security"]),
    ("gate_uat", "uat", "Client acceptance of the build", "project_manager", "approval", [], [],
     ["qa", "accessibility", "performance", "security", "docs", "deploy_plan"]),
    ("gate_deploy", "deployment", "Client authorisation to deploy", "project_manager", "approval", [], [], ["gate_uat"]),
    ("deploy", "deployment", "Deploy & health check", "devops_engineer", "deploy", [], [], ["gate_deploy"]),
]

PHASE_STATUS = {"requirements": "REQUIREMENTS", "research": "RESEARCH", "ux": "DESIGN", "ui": "DESIGN", "architecture": "ARCHITECTURE",
                "content": "DEVELOPMENT", "development": "DEVELOPMENT", "testing": "QA", "security": "SECURITY_REVIEW",
                "documentation": "QA", "uat": "USER_ACCEPTANCE", "deployment": "READY_TO_DEPLOY"}

PHASE_ORDER = ["requirements", "research", "ux", "ui", "architecture", "content", "development", "testing", "security",
               "documentation", "uat", "deployment"]


def create_plan(project_id: str, req: dict) -> dict:
    team = build_team(req)
    keys = {t[0] for t in TEMPLATE if t[3] in team or t[4] in ("approval", "deploy")}
    ids: dict[str, str] = {}
    rows = []
    with db().transaction():
        for pos, (key, phase, title, role, kind, outs, ins, deps) in enumerate(TEMPLATE):
            if key not in keys:
                continue
            tid = new_id()
            ids[key] = tid
            rows.append((tid, key, deps))
            db().insert("tasks", {"id": tid, "project_id": project_id, "key": key, "phase": phase, "title": title,
                                  "description": f"{ROLE_LABELS.get(role, role)}: {title}", "role": role, "kind": kind,
                                  "status": "BACKLOG", "priority": 1 if kind == "approval" else 2, "inputs": jdump(ins),
                                  "outputs": jdump(outs), "position": pos, "created_at": now()})
        for tid, key, deps in rows:
            for d in deps:
                if d in ids:  # skip deps on tasks not in this project's plan
                    db().insert("task_dependencies", {"task_id": tid, "depends_on": ids[d]})
    _assert_acyclic(project_id)
    bus.publish(type="PLAN_CREATED", project_id=project_id, actor="Project Manager",
                message=f"Project Manager created {len(rows)} tasks for a team of {len(team)} specialists",
                data={"tasks": len(rows), "team": team})
    return {"team": team, "tasks": len(rows), "phases": len({t[1] for t in TEMPLATE if t[0] in keys})}


def extend_plan(project_id: str, req: dict) -> list[str]:
    """Add tasks a changed requirement now needs (e.g. booking added to a brochure site)."""
    team = build_team(req)
    existing = {t["key"]: t["id"] for t in db().q("SELECT key, id FROM tasks WHERE project_id = ?", (project_id,))}
    added = []
    for pos, (key, phase, title, role, kind, outs, ins, deps) in enumerate(TEMPLATE):
        if key in existing or role not in team or kind in ("approval", "deploy"):
            continue
        tid = new_id()
        db().insert("tasks", {"id": tid, "project_id": project_id, "key": key, "phase": phase, "title": title,
                              "description": f"{ROLE_LABELS.get(role, role)}: {title}", "role": role, "kind": kind, "status": "BACKLOG",
                              "priority": 2, "inputs": jdump(ins), "outputs": jdump(outs), "position": pos, "created_at": now()})
        existing[key] = tid
        added.append(key)
    if added:
        for key, phase, title, role, kind, outs, ins, deps in TEMPLATE:
            if key not in existing:
                continue
            for d in deps:
                if d in existing and (key in added or d in added):
                    db().ex("INSERT OR IGNORE INTO task_dependencies (task_id, depends_on) VALUES (?, ?)", (existing[key], existing[d]))
        _assert_acyclic(project_id)
        bus.publish(type="PLAN_CREATED", project_id=project_id, actor="Project Manager",
                    message=f"Project Manager added {len(added)} task(s) for the new scope: {', '.join(added)}", data={"added": added})
    return added


def _assert_acyclic(project_id: str) -> None:
    deps = db().q("SELECT d.task_id, d.depends_on FROM task_dependencies d JOIN tasks t ON t.id = d.task_id WHERE t.project_id = ?", (project_id,))
    graph: dict[str, list[str]] = {}
    for d in deps:
        graph.setdefault(d["task_id"], []).append(d["depends_on"])
    state: dict[str, int] = {}

    def visit(n):
        if state.get(n) == 1:
            raise ValueError("circular task dependency detected")
        if state.get(n) == 2:
            return
        state[n] = 1
        for m in graph.get(n, []):
            visit(m)
        state[n] = 2

    for n in list(graph):
        visit(n)


def downstream(project_id: str, task_ids: set[str]) -> set[str]:
    deps = db().q("SELECT d.task_id, d.depends_on FROM task_dependencies d JOIN tasks t ON t.id = d.task_id WHERE t.project_id = ?", (project_id,))
    rev: dict[str, list[str]] = {}
    for d in deps:
        rev.setdefault(d["depends_on"], []).append(d["task_id"])
    out, stack = set(), list(task_ids)
    while stack:
        n = stack.pop()
        for m in rev.get(n, []):
            if m not in out:
                out.add(m)
                stack.append(m)
    return out


def estimate(project_id: str, provider_is_mock: bool) -> dict:
    tasks = db().q("SELECT kind, role FROM tasks WHERE project_id = ?", (project_id,))
    llm_tasks = sum(1 for t in tasks if t["role"] in {"business_analyst", "content_writer", "researcher"})
    cost = 0.0 if provider_is_mock else round(llm_tasks * 0.02 + 0.05, 2)
    work = sum(1 for t in tasks if t["kind"] in ("work", "check"))
    return {"estimated_cost_usd": cost, "estimated_minutes": max(1, round(work * 0.25)),
            "note": "Estimates only. No LLM is used with the local deterministic provider." if provider_is_mock
            else "Estimate based on indicative model prices; actual usage is tracked per call."}
