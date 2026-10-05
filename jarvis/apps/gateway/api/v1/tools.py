from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.gateway.api.v1.auth import current_user_dep, get_db
from apps.gateway.db import Approval, AuditLog, User, get_sessionmaker
from apps.gateway.events import bus
from packages.tools.registry import REGISTRY, get_tool, list_tools, execute_tool
from services.core.permission_engine import permission_engine

router = APIRouter(prefix="/tools", tags=["tools"])

@router.get("")
def list_tools_ep(user: User = Depends(current_user_dep)):
    return {"tools": [{"name": t.name, "description": t.description, "category": t.category, "risk": t.risk, "parameters_schema": t.parameters_schema, "requires_approval": t.requires_approval} for t in list_tools()]}

class ExecuteIn(BaseModel):
    tool: str
    arguments: dict = {}

@router.post("/execute")
async def execute(data: ExecuteIn, user: User = Depends(current_user_dep)):
    try:
        tool = get_tool(data.tool)
    except KeyError:
        raise HTTPException(404, f"Tool not found: {data.tool}")
    # permission
    decision = permission_engine.check_tool(tool.risk, tool.requires_approval, user.trust_level)
    if decision.requires_approval:
        # create approval
        db = get_sessionmaker()()
        try:
            appr = Approval(user_id=user.id, tool=tool.name, what=f"Execute {tool.name}", why="Direct tool execution", target=str(data.arguments), risk=decision.reason, status="pending")
            db.add(appr)
            db.commit()
            db.refresh(appr)
            bus.publish({"type":"APPROVAL_REQUIRED","approval_id": appr.id, "tool": tool.name, "user_id": user.id})
            return {"approval_required": True, "approval_id": appr.id, "reason": decision.reason}
        finally:
            db.close()
    # validate + execute
    try:
        tool.validate(data.arguments)
    except ValueError as e:
        raise HTTPException(400, str(e))
    start = time.time()
    bus.publish({"type":"TOOL_STARTED","tool": tool.name, "user_id": user.id})
    try:
        result = await execute_tool(tool.name, data.arguments, user_id=user.id)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    duration = int((time.time()-start)*1000)
    # audit
    db2 = get_sessionmaker()()
    try:
        from packages.security.security import hash_args
        h = hash_args(data.arguments)
        db2.add(AuditLog(user_id=user.id, tool=tool.name, arguments_hash=h, result_status="success" if "error" not in result else "failed", risk_level=decision.level, duration_ms=duration, error=result.get("error")))
        db2.commit()
    finally:
        db2.close()
    bus.publish({"type":"TOOL_COMPLETED","tool": tool.name, "user_id": user.id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return {"tool": tool.name, "result": result.get("result"), "duration_ms": duration}

@router.get("/history")
def history(limit: int = 20, offset: int = 0, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    q = db.query(AuditLog).filter(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    total = db.query(AuditLog).filter(AuditLog.user_id == user.id).count()
    return {"items": [{"id": a.id, "tool": a.tool, "status": a.result_status, "risk_level": a.risk_level, "duration_ms": a.duration_ms, "error": a.error, "created_at": a.created_at.isoformat() if a.created_at else None} for a in q], "total": total, "limit": limit, "offset": offset}
