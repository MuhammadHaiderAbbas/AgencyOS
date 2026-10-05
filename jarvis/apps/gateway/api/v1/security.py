from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.gateway.api.v1.auth import current_user_dep, get_db
from apps.gateway.db import Approval, AuditLog, User

router = APIRouter(prefix="/security", tags=["security"])

@router.get("/approvals")
def list_approvals(status: str | None = None, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    q = db.query(Approval).filter(Approval.user_id == user.id)
    if status:
        q = q.filter(Approval.status == status)
    items = q.order_by(Approval.requested_at.desc()).limit(100).all()
    return {"approvals": [{"id": a.id, "tool": a.tool, "what": a.what, "why": a.why, "target": a.target, "risk": a.risk, "status": a.status, "requested_at": a.requested_at.isoformat() if a.requested_at else None} for a in items]}

@router.post("/approvals/{aid}/resolve")
def resolve(aid: str, data: dict, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    a = db.query(Approval).filter(Approval.id == aid, Approval.user_id == user.id).first()
    if not a:
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")
    decision = data.get("decision")
    if decision not in ("granted","denied"):
        raise HTTPException(400, "decision must be granted|denied")
    a.status = decision
    a.resolved_at = datetime.now(timezone.utc)
    # also update execution status?
    if a.execution_id:
        from apps.gateway.db import Execution
        ex = db.query(Execution).filter(Execution.id == a.execution_id).first()
        if ex and decision == "granted":
            ex.status = "queued"
        elif ex and decision == "denied":
            ex.status = "cancelled"
    db.commit()
    # publish event
    from apps.gateway.events import bus
    bus.publish({"type": "APPROVAL_GRANTED" if decision=="granted" else "APPROVAL_DENIED", "approval_id": a.id, "user_id": user.id})
    return {"approval": {"id": a.id, "status": a.status}}

@router.get("/audit")
def audit(limit: int = 50, offset: int = 0, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    q = db.query(AuditLog).filter(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    total = db.query(AuditLog).filter(AuditLog.user_id == user.id).count()
    return {"items": [{"id": a.id, "tool": a.tool, "status": a.result_status, "risk": a.risk_level, "error": a.error, "created_at": a.created_at.isoformat() if a.created_at else None} for a in q], "total": total}

@router.get("/health")
def sec_health(user: User = Depends(current_user_dep)):
    return {"sessions": "ok", "permissions": "ok"}
