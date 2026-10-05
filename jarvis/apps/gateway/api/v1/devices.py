from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.gateway.api.v1.auth import current_user_dep, get_db
from apps.gateway.db import Device, User

router = APIRouter(prefix="/devices", tags=["devices"])

class RegisterIn(BaseModel):
    name: str
    platform: str = "desktop"
    public_key: str | None = None

@router.get("")
def list_devices(user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    devs = db.query(Device).filter(Device.user_id == user.id).all()
    return {"devices": [{"id": d.id, "name": d.name, "platform": d.platform, "status": d.status, "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None} for d in devs]}

@router.post("/register")
def register(data: RegisterIn, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    d = Device(user_id=user.id, name=data.name, platform=data.platform, public_key=data.public_key, status="online")
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"device": {"id": d.id, "name": d.name, "platform": d.platform}}

@router.delete("/{did}")
def delete_device(did: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    d = db.query(Device).filter(Device.id == did, Device.user_id == user.id).first()
    if d:
        db.delete(d)
        db.commit()
    return {"ok": True}

@router.post("/{did}/command")
def send_command(did: str, data: dict, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    d = db.query(Device).filter(Device.id == did, Device.user_id == user.id).first()
    if not d:
        from fastapi import HTTPException
        raise HTTPException(404, "Device not found")
    # stub: just publish event
    from apps.gateway.events import bus
    bus.publish({"type":"DEVICE_COMMAND","device_id": did, "command": data.get("command"), "user_id": user.id})
    return {"accepted": True}
