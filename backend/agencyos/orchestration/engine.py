"""Agent Orchestrator + task engine.

Long-running work never happens in an HTTP request: the API enqueues a project, a worker
thread advances its task graph until it reaches a human gate, finishes, or blocks.

Per task:  select agent -> build least-context -> adapter.run (sandboxed where needed)
           -> validate + review -> artifacts (versioned) + git commit -> next.
Failures:  retry -> alternate compatible agent -> escalate to PM/user. Never silent.
QA loop:   failed checks -> bug-fix tasks for the owning role -> re-test, bounded.
Guards:    max retries, max revisions, max executions per project, project budget.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
from typing import Any

from ..agents import registry
from ..agents.adapters import adapter_for
from ..agents.contracts import AgentContext, AgentResult
from ..config import settings
from ..db import db, jdump, jload, new_id, now
from ..events import bus
from ..llm.router import LLMClient
from ..services import artifacts as art_store
from ..services import deploy as deploy_svc
from ..services import workspace
from .planner import PHASE_STATUS, downstream
from .review import review
from .teams import ROLE_LABELS

log = logging.getLogger("agencyos.engine")
DONE = ("COMPLETED", "APPROVED")
COMMIT_SCOPE = {"business_analyst": "analyst", "technical_writer": "docs", "project_manager": "pm", "ux_designer": "ux",
                "ui_designer": "ui", "content_writer": "content", "seo_specialist": "seo", "frontend_developer": "frontend",
                "backend_developer": "backend", "database_engineer": "database", "qa_engineer": "qa", "security_engineer": "security",
                "performance_engineer": "performance", "accessibility_specialist": "a11y", "devops_engineer": "devops",
                "researcher": "research", "architect": "architecture"}


def label(role: str) -> str:
    return ROLE_LABELS.get(role, role.replace("_", " ").title())


def notify(project_id: str, kind: str, title: str, body: str = "") -> None:
    p = db().q1("SELECT created_by, org_id FROM projects WHERE id = ?", (project_id,))
    if not p:
        return
    db().insert("notifications", {"id": new_id(), "user_id": p["created_by"], "project_id": project_id, "kind": kind,
                                  "title": title, "body": body, "read": 0, "created_at": now()})
    bus.publish(type="NOTIFICATION", project_id=project_id, actor="AgencyOS", message=title, data={"kind": kind, "body": body})


def current_requirements(project_id: str) -> dict:
    r = db().q1("SELECT data FROM requirement_versions WHERE project_id = ? ORDER BY version DESC LIMIT 1", (project_id,))
    return jload(r["data"], {}) if r else {}


def project_memory(project_id: str) -> list[dict]:
    return db().q("SELECT kind, key, value FROM project_memory WHERE project_id = ? ORDER BY created_at", (project_id,))


def post_agent_message(project_id: str, author: str, content: str, meta: dict | None = None) -> None:
    db().insert("chat_messages", {"id": new_id(), "project_id": project_id, "role": "agent", "author": author,
                                  "content": content, "meta": jdump(meta or {}), "created_at": now()})
    bus.publish(type="AGENT_MESSAGE", project_id=project_id, actor=author, message=content[:200], data=meta or {})


class Orchestrator:
    def __init__(self, workers: int = 2):
        self.q: queue.Queue[str] = queue.Queue()
        self._running: set[str] = set()
        self._again: set[str] = set()
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self.workers = workers
        self.sync = False  # tests: run inline

    # ---------------------------------------------------------------- queue
    def start(self) -> None:
        for i in range(self.workers):
            t = threading.Thread(target=self._loop, name=f"agency-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()

    def queue_size(self) -> int:
        return self.q.qsize()

    def status(self) -> dict:
        return {"workers": len([t for t in self._threads if t.is_alive()]), "queue": self.q.qsize(), "running": sorted(self._running)}

    def enqueue(self, project_id: str) -> None:
        if self.sync:
            self.advance(project_id)
            return
        with self._lock:
            if project_id in self._running:
                self._again.add(project_id)
                return
        self.q.put(project_id)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                pid = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            with self._lock:
                if pid in self._running:
                    self._again.add(pid)
                    continue
                self._running.add(pid)
            try:
                self.advance(pid)
            except Exception:  # never let a worker die silently
                log.error("advance failed: %s", traceback.format_exc())
                bus.publish(type="PROJECT_BLOCKED", project_id=pid, actor="Orchestrator", message="Orchestrator error — see admin logs")
            finally:
                with self._lock:
                    self._running.discard(pid)
                    again = pid in self._again
                    self._again.discard(pid)
                if again:
                    self.q.put(pid)

    # ---------------------------------------------------------------- graph helpers
    def tasks(self, project_id: str) -> list[dict]:
        return db().q("SELECT * FROM tasks WHERE project_id = ? ORDER BY position, created_at", (project_id,))

    def deps(self, task_id: str) -> list[dict]:
        return db().q("SELECT t.* FROM task_dependencies d JOIN tasks t ON t.id = d.depends_on WHERE d.task_id = ?", (task_id,))

    def ready_tasks(self, project_id: str) -> list[dict]:
        out = []
        for t in self.tasks(project_id):
            if t["status"] == "READY":
                out.append(t)
            elif t["status"] == "BACKLOG" and all(d["status"] in DONE for d in self.deps(t["id"])):
                out.append(t)
        return out

    def set_status(self, task: dict, status: str, **extra) -> None:
        vals = {"status": status, **extra}
        if status == "IN_PROGRESS":
            vals["started_at"] = now()
        if status in DONE or status == "FAILED":
            vals["completed_at"] = now()
        db().update("tasks", {"id": task["id"]}, vals)
        task.update(vals)

    # ---------------------------------------------------------------- main loop
    def advance(self, project_id: str) -> None:
        s = settings()
        while True:
            p = db().q1("SELECT * FROM projects WHERE id = ?", (project_id,))
            if not p or p["status"] in ("CANCELLED", "COMPLETED", "DISCOVERY", "REQUIREMENTS", "PLANNING") or p["archived"]:
                return
            execs = db().q1("SELECT COUNT(*) n FROM agent_executions WHERE project_id = ?", (project_id,))["n"]
            if execs >= s.max_project_executions:
                self._block(project_id, "Execution limit reached for this project (loop protection).")
                return
            if p["cost_usd"] >= s.max_project_budget_usd:
                self._block(project_id, f"Project AI budget of ${s.max_project_budget_usd:.2f} reached.")
                return
            ready = self.ready_tasks(project_id)
            if not ready:
                self.refresh_project(project_id)
                return
            task = ready[0]
            if task["kind"] == "approval":
                self._open_gate(p, task)
                continue
            if task["kind"] == "deploy":
                self._deploy(p, task)
                continue
            self.run_task(p, task)
            self.refresh_project(project_id)
            if s.step_delay:
                time.sleep(s.step_delay)

    def _block(self, project_id: str, reason: str) -> None:
        db().update("projects", {"id": project_id}, {"status": "BLOCKED", "updated_at": now()})
        bus.publish(type="PROJECT_BLOCKED", project_id=project_id, actor="Project Manager", message=reason)
        post_agent_message(project_id, "Project Manager", f"I've paused the project: {reason} I need your decision before continuing.",
                           {"type": "escalation"})
        notify(project_id, "blocked", "Project paused", reason)

    # ---------------------------------------------------------------- task execution
    def build_context(self, p: dict, task: dict, defn) -> AgentContext:
        req = current_requirements(p["id"])
        names = jload(task["inputs"], []) + [
            "sitemap.json", "wireframes.json", "design-system.json", "content.json", "seo-plan.json"]
        arts = {}
        for n in dict.fromkeys(names):  # retrieval: only artifacts this task can use
            v = art_store.latest(p["id"], n)
            if v is not None:
                arts[n] = v
        fb = jload(task["feedback"], [])
        params: dict[str, Any] = {}
        if task["kind"] == "fix":
            params["issues"] = [f for f in fb if isinstance(f, dict)]
        feedback = [f if isinstance(f, str) else f.get("message", "") for f in fb]
        return AgentContext(project=p, requirements=req, task=task, artifacts=arts, memory=project_memory(p["id"]),
                            feedback=feedback, workspace=workspace.ensure(p["id"]),
                            llm=LLMClient(p["org_id"], p["id"]), permissions={x.value if hasattr(x, "value") else x for x in defn.permissions},
                            params=params)

    def run_task(self, p: dict, task: dict) -> None:
        s = settings()
        agent_id = task["assigned_agent"] or registry.select_agent(task["role"])
        if not agent_id:
            self.set_status(task, "FAILED")
            self._escalate(p, task, f"No enabled agent can perform the role '{label(task['role'])}'.")
            return
        defn = registry.get(agent_id)
        adapter = adapter_for(defn)
        self.set_status(task, "IN_PROGRESS", assigned_agent=agent_id, attempt_count=task["attempt_count"] + 1)
        verb = "fixing" if task["kind"] == "fix" else "revising" if task["revision_count"] else "started"
        bus.publish(type="TASK_STARTED", project_id=p["id"], actor=label(task["role"]),
                    message=f"{label(task['role'])} {verb}: {task['title']}", data={"task_id": task["id"], "role": task["role"]})
        exec_id = new_id()
        db().insert("agent_executions", {"id": exec_id, "project_id": p["id"], "task_id": task["id"], "agent_id": agent_id,
                                         "role": task["role"], "status": "RUNNING", "input_summary": f"{task['title']} | inputs: {', '.join(jload(task['inputs'], []))}",
                                         "started_at": now()})
        t0 = time.monotonic()
        ctx = self.build_context(p, task, defn)
        ctx.llm.execution_id = exec_id
        try:
            result: AgentResult = adapter.run(defn, ctx) if adapter else AgentResult("failed", "no adapter", errors=["No adapter for execution mode"])
        except PermissionError as e:
            result = AgentResult("failed", "permission denied", errors=[str(e)])
        except Exception as e:  # agent crash
            result = AgentResult("failed", f"Agent crashed: {e.__class__.__name__}", errors=[traceback.format_exc()[-1500:]])
        dur = int((time.monotonic() - t0) * 1000)
        cost = round(sum(u.cost_usd for u in ctx.llm.usage), 6)
        tin = sum(u.tokens_in for u in ctx.llm.usage)
        tout = sum(u.tokens_out for u in ctx.llm.usage)
        provider = next((u.provider for u in reversed(ctx.llm.usage) if u.provider != "mock"), "mock")
        model = next((u.model for u in reversed(ctx.llm.usage) if u.provider != "mock"), "deterministic")
        ok = result.status == "success"
        db().update("agent_executions", {"id": exec_id}, {
            "status": "SUCCEEDED" if ok else "FAILED", "output_summary": result.summary[:1000], "tools_used": jdump(result.tools_used),
            "logs": jdump(result.logs[-20:]), "errors": jdump(result.errors[-5:]), "provider": provider, "model": model,
            "tokens_in": tin, "tokens_out": tout, "cost_usd": cost, "duration_ms": dur, "confidence": result.confidence, "finished_at": now()})
        db().ex("UPDATE projects SET cost_usd = cost_usd + ?, updated_at = ? WHERE id = ?", (cost, now(), p["id"]))
        registry.record_run(agent_id, ok, dur, cost)
        if not ok:
            self._handle_failure(p, task, agent_id, result)
            return
        # persist artifacts (versioned) and code (git)
        for a in result.artifacts:
            art_store.save(p["id"], a.name, a.type, a.content, a.content_type, label(task["role"]), task["id"], a.note)
        commit_msg = result.structured_output.get("commit") or f"{task['title'].lower()}"
        scope = COMMIT_SCOPE.get(task["role"], task["role"])
        sha = workspace.commit(p["id"], scope, commit_msg)
        if sha:
            bus.publish(type="BUILD_SUCCEEDED" if task["role"].endswith("developer") else "ARTIFACT_UPDATED", project_id=p["id"],
                        actor=label(task["role"]), message=f"Committed {sha}: agent({scope}): {commit_msg}",
                        data={"commit": sha})
        if task["kind"] == "check":
            self._handle_check(p, task, result)
            return
        if task["kind"] == "fix":
            self.set_status(task, "COMPLETED", review_status="APPROVED")
            bus.publish(type="TASK_COMPLETED", project_id=p["id"], actor=label(task["role"]), message=f"{label(task['role'])} completed: {result.summary}",
                        data={"task_id": task["id"]})
            return
        # review every structured deliverable
        req = ctx.requirements
        all_issues: list[str] = []
        for a in result.artifacts:
            if a.content_type in ("application/json", "text/markdown"):
                passed, issues = review(a.name, a.content, req, ctx.memory, ctx.llm)
                art_store.set_review(p["id"], a.name, "APPROVED" if passed else "REJECTED")
                all_issues += issues
        db().insert("reviews", {"id": new_id(), "project_id": p["id"], "task_id": task["id"], "reviewer": "Review Agent",
                                "verdict": "APPROVED" if not all_issues else "REVISION_REQUIRED", "issues": jdump(all_issues),
                                "summary": result.summary[:500], "created_at": now()})
        registry.record_review(agent_id, not all_issues)
        if all_issues:
            bus.publish(type="REVIEW_FAILED", project_id=p["id"], actor="Review Agent",
                        message=f"Review requested changes to {task['title']}: {all_issues[0]}", data={"issues": all_issues, "task_id": task["id"]})
            if task["revision_count"] + 1 > s.max_revisions:
                self.set_status(task, "FAILED", review_status="REJECTED")
                self._escalate(p, task, f"{task['title']} failed review {s.max_revisions} times: {all_issues[0]}")
                return
            self.set_status(task, "READY", review_status="REVISION_REQUIRED", revision_count=task["revision_count"] + 1,
                            feedback=jdump(all_issues))
            bus.publish(type="TASK_REVISION", project_id=p["id"], actor="Project Manager",
                        message=f"Project Manager sent {task['title']} back to {label(task['role'])} for revision", data={"task_id": task["id"]})
            return
        bus.publish(type="REVIEW_PASSED", project_id=p["id"], actor="Review Agent", message=f"Review passed: {task['title']}",
                    data={"task_id": task["id"]})
        self.set_status(task, "COMPLETED", review_status="APPROVED", feedback=None)
        bus.publish(type="TASK_COMPLETED", project_id=p["id"], actor=label(task["role"]),
                    message=f"{label(task['role'])} completed: {result.summary}", data={"task_id": task["id"], "role": task["role"]})

    def _handle_failure(self, p, task, agent_id, result) -> None:
        s = settings()
        err = (result.errors or [result.summary])[0][-300:]
        bus.publish(type="AGENT_FAILED", project_id=p["id"], actor=label(task["role"]), message=f"{label(task['role'])} failed: {result.summary}",
                    data={"task_id": task["id"], "error": err})
        if task["attempt_count"] <= s.max_task_retries:
            self.set_status(task, "READY", feedback=jdump([f"Previous attempt failed: {err}"]))
            return
        alt = registry.select_agent(task["role"], exclude={agent_id})
        if alt:
            self.set_status(task, "READY", assigned_agent=alt, attempt_count=0)
            bus.publish(type="TASK_REVISION", project_id=p["id"], actor="Project Manager",
                        message=f"Project Manager reassigned {task['title']} to an alternative agent", data={"task_id": task["id"], "agent": alt})
            return
        self.set_status(task, "FAILED")
        self._escalate(p, task, f"{task['title']} failed after {task['attempt_count']} attempts: {err}")

    def _handle_check(self, p, task, result) -> None:
        s = settings()
        report = result.structured_output.get("report", {})
        failing = [i for i in report.get("failed", []) if i["severity"] in ("critical", "high")]
        if not failing:
            self.set_status(task, "COMPLETED", review_status="APPROVED", feedback=None)
            bus.publish(type="TASK_COMPLETED", project_id=p["id"], actor=label(task["role"]),
                        message=f"{label(task['role'])} completed: {result.summary}", data={"task_id": task["id"]})
            return
        bus.publish(type="BUG_REPORTED", project_id=p["id"], actor=label(task["role"]),
                    message=f"{label(task['role'])} found {len(failing)} blocking issue(s): {failing[0]['message']}",
                    data={"task_id": task["id"], "issues": failing})
        if task["revision_count"] + 1 > s.max_revisions:
            self.set_status(task, "FAILED", review_status="REJECTED")
            notify(p["id"], "qa_failed", f"{task['title']} still failing", failing[0]["message"])
            self._escalate(p, task, f"{task['title']} still reports {len(failing)} blocking issue(s) after {s.max_revisions} fix rounds.",
                           decision=True)
            return
        by_owner: dict[str, list[dict]] = {}
        team_roles = {t["role"] for t in self.tasks(p["id"])}
        for i in failing:
            owner = i.get("owner") or "frontend_developer"
            if owner not in team_roles:
                owner = "frontend_developer"
            by_owner.setdefault(owner, []).append(i)
        n = task["revision_count"] + 1
        fix_ids = []
        for owner, issues in by_owner.items():
            fid = self._add_task(p["id"], f"fix_{task['key']}_{owner}_{n}", task["phase"], f"Fix {len(issues)} issue(s) from {task['title']}",
                                 owner, "fix" if owner in ("frontend_developer", "backend_developer") else "work", issues)
            fix_ids.append(fid)
            if owner not in ("frontend_developer", "backend_developer"):
                # design/content changes must be re-implemented by the frontend developer
                rid = self._add_task(p["id"], f"rebuild_{task['key']}_{n}", task["phase"], "Rebuild pages with revised design/content",
                                     "frontend_developer", "work", [], depends=[fid])
                db().update("tasks", {"id": rid}, {"inputs": jdump(["sitemap.json", "wireframes.json", "design-system.json", "content.json", "seo-plan.json"]),
                                                   "outputs": jdump(["source-manifest.json"])})
                fix_ids.append(rid)
        for fid in fix_ids:
            db().insert("task_dependencies", {"task_id": task["id"], "depends_on": fid})
        self.set_status(task, "BACKLOG", review_status="REVISION_REQUIRED", revision_count=n, feedback=jdump(failing))
        bus.publish(type="TASK_REVISION", project_id=p["id"], actor="Project Manager",
                    message=f"Project Manager created {len(fix_ids)} bug-fix task(s); {task['title']} will re-run after the fix",
                    data={"task_id": task["id"]})

    def _add_task(self, project_id, key, phase, title, role, kind, feedback, depends=None) -> str:
        tid = new_id()
        pos = (db().q1("SELECT MAX(position) m FROM tasks WHERE project_id = ?", (project_id,))["m"] or 0)
        db().insert("tasks", {"id": tid, "project_id": project_id, "key": key, "phase": phase, "title": title,
                              "description": title, "role": role, "kind": kind, "status": "BACKLOG", "priority": 1,
                              "inputs": jdump(["sitemap.json", "seo-plan.json"]), "outputs": jdump([]), "feedback": jdump(feedback),
                              "position": pos, "created_at": now()})
        for d in depends or []:
            db().insert("task_dependencies", {"task_id": tid, "depends_on": d})
        bus.publish(type="TASK_CREATED", project_id=project_id, actor="Project Manager", message=f"Task created: {title} → {label(role)}",
                    data={"task_id": tid})
        return tid

    def _escalate(self, p, task, reason: str, decision: bool = True) -> None:
        bus.publish(type="ESCALATION", project_id=p["id"], actor="Project Manager", message=reason, data={"task_id": task["id"]})
        if decision:
            self._create_approval(p["id"], "decision", "I need your decision", task["id"], what=reason,
                                  why="The team could not resolve this automatically within the safety limits.",
                                  impact="Approve = accept and continue with known issues. Request changes = let the team try again.")
        post_agent_message(p["id"], "Project Manager", f"I need your decision: {reason}", {"type": "escalation", "task_id": task["id"]})
        notify(p["id"], "input_required", "Your decision is needed", reason)

    # ---------------------------------------------------------------- approvals
    def _create_approval(self, project_id, gate, title, task_id, what="", why="", impact="", preview=None) -> str:
        existing = db().q1("SELECT id FROM approvals WHERE project_id = ? AND task_id = ? AND status = 'PENDING'", (project_id, task_id))
        if existing:
            return existing["id"]
        aid = new_id()
        db().insert("approvals", {"id": aid, "project_id": project_id, "gate": gate, "title": title, "what_changed": what, "why": why,
                                  "impact": impact, "preview": jdump(preview or {}), "status": "PENDING", "task_id": task_id, "created_at": now()})
        bus.publish(type="APPROVAL_REQUIRED", project_id=project_id, actor="Project Manager", message=f"Approval needed: {title}",
                    data={"approval_id": aid, "gate": gate})
        return aid

    def _open_gate(self, p, task) -> None:
        gate = task["key"].replace("gate_", "")
        info = {
            "design": ("Design & architecture are ready for your review",
                       "Sitemap, wireframes, design system" + (" and architecture" if art_store.latest(p["id"], "architecture.md") else ""),
                       "Developers only build from approved designs.", "Approving starts development.",
                       {"artifacts": ["sitemap.json", "wireframes.json", "design-system.json", "architecture.md"]}),
            "uat": ("Your website is built and tested — please review it",
                    "Complete site, API (if any), QA, accessibility, performance and security reports",
                    "You decide whether the build meets your expectations.", "Approving moves to deployment authorisation.",
                    {"preview_url": f"/api/projects/{p['id']}/preview/index.html", "artifacts": ["qa-report.json", "security-report.json"]}),
            "deploy": ("Authorise deployment", "Publish the approved build to the hosting target",
                       "Nothing is deployed without your explicit authorisation.", "The site becomes publicly reachable at the deployment URL.",
                       {"target": "local"}),
        }.get(gate, (task["title"], "", "", "", {}))
        self._create_approval(p["id"], gate, info[0], task["id"], info[1], info[2], info[3], info[4])
        self.set_status(task, "BLOCKED")
        post_agent_message(p["id"], "Project Manager", f"**{info[0]}.** {info[2]} Open *Approvals* or reply here.",
                           {"type": "approval", "gate": gate})
        notify(p["id"], "approval", info[0], info[3])
        self.refresh_project(p["id"])

    def decide(self, approval_id: str, decision: str, user_id: str, note: str | None = None) -> dict:
        a = db().q1("SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if not a or a["status"] != "PENDING":
            raise ValueError("approval is not pending")
        status = {"approve": "APPROVED", "reject": "REJECTED", "changes": "CHANGES_REQUESTED"}[decision]
        db().update("approvals", {"id": approval_id}, {"status": status, "decided_by": user_id, "decision_note": note, "decided_at": now()})
        bus.publish(type="APPROVAL_DECIDED", project_id=a["project_id"], actor="Client", message=f"{a['title']}: {status.replace('_', ' ').lower()}",
                    data={"approval_id": approval_id, "decision": status})
        task = db().q1("SELECT * FROM tasks WHERE id = ?", (a["task_id"],)) if a["task_id"] else None
        if task:
            if a["gate"] == "decision":
                if status == "APPROVED":
                    self.set_status(task, "COMPLETED", review_status="ACCEPTED_WITH_ISSUES")
                else:
                    self.set_status(task, "READY", revision_count=0, attempt_count=0)
                db().update("projects", {"id": a["project_id"]}, {"status": "DEVELOPMENT", "updated_at": now()})
            elif status == "APPROVED":
                self.set_status(task, "APPROVED")
                if a["gate"] == "design":
                    for n in ("sitemap.json", "wireframes.json", "design-system.json", "architecture.md"):
                        art_store.set_review(a["project_id"], n, "APPROVED")
            else:
                from .changes import apply_change
                self.set_status(task, "BACKLOG")
                apply_change(a["project_id"], note or "Client requested changes", user_id, source_gate=a["gate"])
        self.enqueue(a["project_id"])
        return {"status": status}

    # ---------------------------------------------------------------- deployment
    def _deploy(self, p, task) -> None:
        self.set_status(task, "IN_PROGRESS")
        db().update("projects", {"id": p["id"]}, {"status": "DEPLOYING", "updated_at": now()})
        bus.publish(type="DEPLOYMENT_STARTED", project_id=p["id"], actor="DevOps Engineer", message="DevOps Engineer started deployment")
        res = run_deployment(p["id"], "local")
        if res["ok"]:
            self.set_status(task, "COMPLETED", review_status="APPROVED")
        else:
            self.set_status(task, "FAILED")
            self._escalate(p, task, "Deployment failed: " + "; ".join(res["logs"][-2:]))
        self.refresh_project(p["id"])

    # ---------------------------------------------------------------- status
    def refresh_project(self, project_id: str) -> dict:
        p = db().q1("SELECT * FROM projects WHERE id = ?", (project_id,))
        ts = self.tasks(project_id)
        if not ts or p["status"] in ("DISCOVERY", "REQUIREMENTS", "PLANNING", "CANCELLED"):
            return p
        done = sum(1 for t in ts if t["status"] in DONE)
        progress = round(done / len(ts) * 100, 1)
        pending = db().q1("SELECT gate FROM approvals WHERE project_id = ? AND status = 'PENDING' ORDER BY created_at DESC LIMIT 1", (project_id,))
        running = [t for t in ts if t["status"] == "IN_PROGRESS"]
        if done == len(ts):
            status = "COMPLETED"
        elif pending:
            status = {"design": "DESIGN", "uat": "USER_ACCEPTANCE", "deploy": "READY_TO_DEPLOY"}.get(pending["gate"], "BLOCKED")
        elif any(t["status"] == "FAILED" for t in ts):
            status = "BLOCKED"
        elif running:
            status = "DEPLOYING" if running[0]["kind"] == "deploy" else PHASE_STATUS.get(running[0]["phase"], "DEVELOPMENT")
        else:
            nxt = self.ready_tasks(project_id)
            status = PHASE_STATUS.get(nxt[0]["phase"], p["status"]) if nxt else p["status"]
        changed = status != p["status"] or abs(progress - p["progress"]) > 0.01
        if changed:
            db().update("projects", {"id": project_id}, {"status": status, "progress": progress, "updated_at": now()})
            bus.publish(type="PROJECT_UPDATED", project_id=project_id, actor="Project Manager", message=f"Status {status} · {progress:.0f}%",
                        data={"status": status, "progress": progress})
            if status == "COMPLETED" and p["status"] != "COMPLETED":
                bus.publish(type="PROJECT_COMPLETED", project_id=project_id, actor="Project Manager", message="Project complete")
                post_agent_message(project_id, "Project Manager", "**Project complete.** Your deliverables are ready under *Deliverables*.",
                                   {"type": "complete"})
                notify(project_id, "complete", "Project complete", "All gates passed and the site is deployed.")
        p.update(status=status, progress=progress)
        return p


def run_deployment(project_id: str, provider: str) -> dict:
    adapter = deploy_svc.ADAPTERS.get(provider)
    if not adapter or not adapter.configured():
        return {"ok": False, "logs": [f"Deployment provider '{provider}' is not configured"]}
    site = workspace.path_for(project_id) / "source" / "site"
    did = new_id()
    db().insert("deployments", {"id": did, "project_id": project_id, "provider": provider, "status": "RUNNING",
                                "commit_hash": workspace.head(project_id), "created_at": now()})
    res = adapter.deploy(project_id, did, site)
    db().update("deployments", {"id": did}, {"status": "SUCCEEDED" if res.ok else "FAILED", "url": res.url, "logs": jdump(res.logs),
                                             "finished_at": now()})
    bus.publish(type="DEPLOYMENT_COMPLETED" if res.ok else "DEPLOYMENT_FAILED", project_id=project_id, actor="DevOps Engineer",
                message=("Deployed to " + str(res.url)) if res.ok else "Deployment failed", data={"deployment_id": did, "url": res.url})
    return {"ok": res.ok, "url": res.url, "logs": res.logs, "id": did}


orchestrator = Orchestrator()
