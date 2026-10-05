from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.gateway.api.v1.auth import current_user_dep, get_db
from apps.gateway.db import AgentRecord, Execution, User

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("")
def list_agents(user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    agents = db.query(AgentRecord).filter(AgentRecord.enabled == True).all()
    return {"agents": [{"id": a.id, "name": a.name, "description": a.description, "allowed_tools": a.allowed_tools, "model_tier": a.model_tier, "enabled": a.enabled} for a in agents]}

@router.get("/executions")
def list_executions(limit: int = 20, offset: int = 0, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    q = db.query(Execution).filter(Execution.user_id == user.id).order_by(Execution.created_at.desc()).offset(offset).limit(limit).all()
    total = db.query(Execution).filter(Execution.user_id == user.id).count()
    return {"items": [{"id": e.id, "goal": e.goal, "status": e.status, "progress": e.progress, "created_at": e.created_at.isoformat() if e.created_at else None} for e in q], "total": total}

@router.get("/executions/{eid}")
def get_execution(eid: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    e = db.query(Execution).filter(Execution.id == eid, Execution.user_id == user.id).first()
    if not e:
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")
    return {"execution": {"id": e.id, "goal": e.goal, "status": e.status, "steps": e.steps, "progress": e.progress, "created_at": e.created_at.isoformat() if e.created_at else None}}

@router.post("/executions/{eid}/cancel")
def cancel(eid: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    e = db.query(Execution).filter(Execution.id == eid, Execution.user_id == user.id).first()
    if not e:
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")
    e.status = "cancelled"
    db.commit()
    return {"ok": True}
