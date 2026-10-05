from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.gateway.api.v1.auth import current_user_dep, get_db
from apps.gateway.db import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("")
def list_notifs(unread_only: bool = False, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        q = q.filter(Notification.read == False)
    items = q.order_by(Notification.created_at.desc()).limit(50).all()
    return {"notifications": [{"id": n.id, "type": n.type, "title": n.title, "body": n.body, "read": n.read, "created_at": n.created_at.isoformat() if n.created_at else None} for n in items]}

@router.post("/{nid}/read")
def mark_read(nid: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == nid, Notification.user_id == user.id).first()
    if n:
        n.read = True
        db.commit()
    return {"ok": True}

@router.post("/read-all")
def read_all(user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.read == False).update({"read": True})
    db.commit()
    return {"ok": True}
