"""AgentOrchestrator — dispatches plan steps to agents with limits."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from apps.gateway.db import Approval, AuditLog, Execution, get_sessionmaker
from apps.gateway.events import bus
from packages.common.types import Plan
from packages.security.security import hash_args, sanitize_for_log
from packages.tools.registry import get_tool, execute_tool
from services.core.permission_engine import permission_engine

# Limits per agent (from AgentRecord)
DEFAULT_LIMITS = {"max_runtime_s": 120, "max_tool_calls": 20, "max_tokens": 8000}

class Orchestrator:
    async def run(self, plan: Plan, user_id: str, trust_level: str = "balanced") -> dict[str, Any]:
        from sqlalchemy.orm import Session
        db: Session = get_sessionmaker()()
        exec_id = uuid.uuid4().hex
        try:
            execution = Execution(id=exec_id, user_id=user_id, plan_id=plan.plan_id, goal=plan.goal, status="running", steps=[s.model_dump() for s in plan.steps], progress=0.0)
            db.add(execution)
            db.commit()
        finally:
            db.close()

        bus.publish({"type":"PLAN_CREATED","plan_id":plan.plan_id,"goal":plan.goal,"user_id":user_id})

        results: list[dict[str, Any]] = []
        total_steps = len(plan.steps)
        for idx, step in enumerate(plan.steps):
            # handle safety deterministic
            if step.tool is None:
                # pure reasoning step
                results.append({"step": step.description, "result": "acknowledged"})
                bus.publish({"type":"TOOL_COMPLETED","tool": None, "description": step.description})
                continue

            # permission check
            try:
                tool = get_tool(step.tool)
            except KeyError as e:
                results.append({"step": step.description, "error": str(e)})
                continue

            # map tool risk to permission
            decision = permission_engine.check_tool(tool.risk, tool.requires_approval, trust_level)
            if decision.requires_approval:
                # create approval record
                db2 = get_sessionmaker()()
                try:
                    appr = Approval(
                        execution_id=exec_id,
                        user_id=user_id,
                        tool=tool.name,
                        what=f"Execute {tool.name}",
                        why=f"Plan step: {step.description}",
                        target=str(step.arguments),
                        risk=decision.reason,
                        status="pending"
                    )
                    db2.add(appr)
                    # mark execution awaiting
                    execution2 = db2.query(Execution).filter(Execution.id == exec_id).first()
                    if execution2:
                        execution2.status = "awaiting_approval"
                    db2.commit()
                    bus.publish({"type":"APPROVAL_REQUIRED","approval_id":appr.id,"tool":tool.name,"user_id":user_id})
                    # For Phase 1 we auto-deny if not explicitly approved via API, but we return pending
                    results.append({"step": step.description, "approval_required": True, "approval_id": appr.id, "tool": tool.name})
                    # do not execute
                    continue
                finally:
                    db2.close()
            # execute
            bus.publish({"type":"TOOL_STARTED","tool": tool.name,"user_id": user_id})
            start = time.time()
            try:
                # enforce file sandbox etc inside tool
                out = await asyncio.wait_for(execute_tool(tool.name, step.arguments, user_id=user_id), timeout=30)
                duration = int((time.time()-start)*1000)
                # audit
                self._audit(user_id, None, tool.name, step.arguments, "success", decision.level, None, duration, None)
                bus.publish({"type":"TOOL_COMPLETED","tool": tool.name,"result": out.get("result"),"user_id": user_id})
                results.append({"step": step.description, "tool": tool.name, "result": out.get("result") or out.get("error"), "duration_ms": duration})
            except asyncio.TimeoutError:
                self._audit(user_id, None, tool.name, step.arguments, "failed", decision.level, None, int((time.time()-start)*1000), "timeout")
                results.append({"step": step.description, "error": "tool timeout"})
            except PermissionError as e:
                self._audit(user_id, None, tool.name, step.arguments, "failed", decision.level, None, int((time.time()-start)*1000), str(e))
                results.append({"step": step.description, "error": str(e)})
            except Exception as e:
                self._audit(user_id, None, tool.name, step.arguments, "failed", decision.level, None, int((time.time()-start)*1000), str(e))
                results.append({"step": step.description, "error": str(e)})

        # finalize execution
        db3 = get_sessionmaker()()
        try:
            from datetime import datetime, timezone
            ex = db3.query(Execution).filter(Execution.id == exec_id).first()
            if ex:
                # if any pending approval, status remains awaiting_approval else succeeded
                pending = any(r.get("approval_required") for r in results)
                ex.status = "awaiting_approval" if pending else "succeeded"
                ex.progress = 1.0
                ex.finished_at = datetime.now(timezone.utc)
                # store results in steps? keep original
                db3.commit()
        finally:
            db3.close()

        # if all succeeded and at least one tool was suppressed for approval, we surface pending
        pending_approvals = [r for r in results if r.get("approval_required")]
        return {"execution_id": exec_id, "plan": plan.model_dump(), "results": results, "pending_approvals": pending_approvals}

    def _audit(self, user_id, agent, tool, args, status, risk_level, approval_id, duration_ms, error):
        from sqlalchemy.orm import Session
        db: Session = get_sessionmaker()()
        try:
            # don't store raw args if sensitive; store hash
            h = hash_args(args) if args else None
            db.add(AuditLog(user_id=user_id, agent=agent, tool=tool, arguments_hash=h, result_status=status, risk_level=risk_level or 0, approval_id=approval_id, duration_ms=duration_ms, error=str(error)[:500] if error else None))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def emergency_stop(self, user_id: str):
        db = get_sessionmaker()()
        try:
            # cancel all running/queued executions for user
            from apps.gateway.db import Execution
            for ex in db.query(Execution).filter(Execution.user_id == user_id, Execution.status.in_(["running","queued","awaiting_approval"])).all():
                ex.status = "cancelled"
            db.commit()
            bus.publish({"type":"SECURITY_ALERT","reason":"emergency_stop","user_id":user_id})
        finally:
            db.close()

orchestrator = Orchestrator()
