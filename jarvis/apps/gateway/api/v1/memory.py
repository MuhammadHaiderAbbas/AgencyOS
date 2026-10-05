from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.gateway.api.v1.auth import current_user_dep, get_db
from apps.gateway.db import Memory, MemoryEmbedding, User

router = APIRouter(prefix="/memory", tags=["memory"])

class MemoryIn(BaseModel):
    kind: str = "episodic"
    content: str
    importance: float = 0.5
    confidence: float = 0.8
    source: str = "user"
    expires_at: str | None = None

@router.post("")
def create_memory(data: MemoryIn, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    if data.kind not in ("working","episodic","semantic"):
        raise HTTPException(400, "Invalid kind")
    m = Memory(user_id=user.id, kind=data.kind, content=data.content, importance=data.importance, confidence=data.confidence, source=data.source)
    if data.expires_at:
        try:
            m.expires_at = datetime.fromisoformat(data.expires_at.replace("Z","+00:00"))
        except Exception:
            pass
    db.add(m)
    db.commit()
    db.refresh(m)
    # naive embedding stub
    db.add(MemoryEmbedding(memory_id=m.id, embedding="[]"))
    db.commit()
    return {"memory": {"id": m.id, "kind": m.kind, "content": m.content, "importance": m.importance, "created_at": m.created_at.isoformat() if m.created_at else None}}

@router.get("")
def list_memory(kind: str | None = None, q: str | None = None, limit: int = 20, offset: int = 0, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    query = db.query(Memory).filter(Memory.user_id == user.id)
    if kind:
        query = query.filter(Memory.kind == kind)
    if q:
        query = query.filter(Memory.content.ilike(f"%{q}%"))
    total = query.count()
    items = query.order_by(Memory.created_at.desc()).offset(offset).limit(limit).all()
    return {"memories": [{"id": m.id, "kind": m.kind, "content": m.content, "importance": m.importance, "created_at": m.created_at.isoformat() if m.created_at else None} for m in items], "total": total, "limit": limit, "offset": offset}

@router.get("/{mid}")
def get_memory(mid: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    m = db.query(Memory).filter(Memory.id == mid, Memory.user_id == user.id).first()
    if not m:
        raise HTTPException(404, "Not found")
    return {"memory": {"id": m.id, "kind": m.kind, "content": m.content, "importance": m.importance, "created_at": m.created_at.isoformat() if m.created_at else None}}

@router.patch("/{mid}")
def patch_memory(mid: str, data: dict, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    m = db.query(Memory).filter(Memory.id == mid, Memory.user_id == user.id).first()
    if not m:
        raise HTTPException(404, "Not found")
    if "content" in data:
        m.content = data["content"]
    if "importance" in data:
        m.importance = float(data["importance"])
    m.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"memory": {"id": m.id, "kind": m.kind, "content": m.content}}

@router.delete("/{mid}")
def delete_memory(mid: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    m = db.query(Memory).filter(Memory.id == mid, Memory.user_id == user.id).first()
    if not m:
        raise HTTPException(404, "Not found")
    db.delete(m)
    db.commit()
    return {"ok": True}

class SearchIn(BaseModel):
    query: str
    kinds: list[str] | None = None
    limit: int = 5

@router.post("/search")
def search(data: SearchIn, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    # naive brute-force contains ranking by importance + substring
    q = db.query(Memory).filter(Memory.user_id == user.id)
    if data.kinds:
        q = q.filter(Memory.kind.in_(data.kinds))
    all_mems = q.all()
    query_low = data.query.lower()
    scored = []
    for m in all_mems:
        score = 0.0
        if query_low in m.content.lower():
            score = 0.8 + 0.2 * m.importance
        # also token overlap naive
        overlap = len(set(query_low.split()) & set(m.content.lower().split())) / max(1, len(query_low.split()))
        score = max(score, overlap * 0.7)
        if score > 0:
            scored.append((m, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    results = [{"memory": {"id": m.id, "kind": m.kind, "content": m.content, "importance": m.importance}, "score": round(s,3)} for m,s in scored[:data.limit]]
    return {"results": results}

class ControlIn(BaseModel):
    action: str
    target: str | None = None

@router.post("/controls")
def controls(data: ControlIn, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    if data.action == "delete_all":
        db.query(MemoryEmbedding).filter(MemoryEmbedding.memory_id.in_(db.query(Memory.id).filter(Memory.user_id == user.id))).delete(synchronize_session=False)
        db.query(Memory).filter(Memory.user_id == user.id).delete()
        db.commit()
        return {"ok": True, "deleted": True}
    if data.action == "forget" and data.target:
        mems = db.query(Memory).filter(Memory.user_id == user.id, Memory.content.ilike(f"%{data.target}%")).all()
        for m in mems:
            db.delete(m)
        db.commit()
        return {"ok": True, "forgotten": len(mems)}
    if data.action == "show":
        total = db.query(Memory).filter(Memory.user_id == user.id).count()
        return {"ok": True, "total_memories": total}
    raise HTTPException(400, "Unknown action")
