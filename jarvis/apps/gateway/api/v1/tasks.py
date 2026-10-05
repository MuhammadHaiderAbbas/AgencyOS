from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.gateway.api.v1.auth import current_user_dep, get_db
from apps.gateway.db import Task, Reminder, User

router = APIRouter(prefix="/tasks", tags=["tasks"])

class TaskIn(BaseModel):
    title: str
    description: str | None = None
    priority: str = "medium"
    deadline: str | None = None

@router.post("")
def create_task(data: TaskIn, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    t = Task(user_id=user.id, title=data.title, description=data.description, priority=data.priority)
    if data.deadline:
        try:
            t.deadline = datetime.fromisoformat(data.deadline.replace("Z","+00:00"))
        except Exception:
            pass
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"task": {"id": t.id, "title": t.title, "priority": t.priority, "status": t.status, "created_at": t.created_at.isoformat() if t.created_at else None}}

@router.get("")
def list_tasks(status: str | None = None, q: str | None = None, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    query = db.query(Task).filter(Task.user_id == user.id)
    if status:
        query = query.filter(Task.status == status)
    if q:
        query = query.filter(Task.title.ilike(f"%{q}%"))
    items = query.order_by(Task.created_at.desc()).limit(100).all()
    return {"tasks": [{"id": t.id, "title": t.title, "priority": t.priority, "status": t.status, "deadline": t.deadline.isoformat() if t.deadline else None, "created_at": t.created_at.isoformat() if t.created_at else None} for t in items]}

@router.patch("/{tid}")
def patch_task(tid: str, data: dict, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    t = db.query(Task).filter(Task.id == tid, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Not found")
    if "status" in data:
        t.status = data["status"]
    if "priority" in data:
        t.priority = data["priority"]
    t.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"task": {"id": t.id, "status": t.status}}

@router.delete("/{tid}")
def delete_task(tid: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    t = db.query(Task).filter(Task.id == tid, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Not found")
    db.delete(t)
    db.commit()
    return {"ok": True}

# reminders

class ReminderIn(BaseModel):
    text: str
    run_at: str
    recurrence: str | None = None

@router.post("/reminders")
def create_reminder(data: ReminderIn, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    try:
        run_at = datetime.fromisoformat(data.run_at.replace("Z","+00:00"))
    except Exception:
        raise HTTPException(400, "Invalid run_at")
    r = Reminder(user_id=user.id, text=data.text, run_at=run_at, recurrence=data.recurrence)
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"reminder": {"id": r.id, "text": r.text, "run_at": r.run_at.isoformat(), "status": r.status}}

@router.get("/reminders")
def list_reminders(user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    items = db.query(Reminder).filter(Reminder.user_id == user.id).order_by(Reminder.run_at.asc()).limit(100).all()
    return {"reminders": [{"id": r.id, "text": r.text, "run_at": r.run_at.isoformat() if r.run_at else None, "status": r.status} for r in items]}

@router.delete("/reminders/{rid}")
def delete_reminder(rid: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    r = db.query(Reminder).filter(Reminder.id == rid, Reminder.user_id == user.id).first()
    if not r:
        raise HTTPException(404, "Not found")
    db.delete(r)
    db.commit()
    return {"ok": True}
