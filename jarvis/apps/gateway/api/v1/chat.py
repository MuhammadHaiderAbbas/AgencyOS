from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.gateway.api.v1.auth import current_user_dep, get_db
from apps.gateway.db import Conversation, Message, User
from apps.gateway.events import bus
from services.core.context_engine import context_engine
from services.core.input_manager import input_manager
from services.core.intent_engine import intent_engine
from services.core.orchestrator import orchestrator
from services.core.planner import planner

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatIn(BaseModel):
    message: str
    conversation_id: str | None = None
    source: str = "text"

@router.post("")
async def chat(data: ChatIn, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    # ensure conversation
    conv_id = data.conversation_id
    if conv_id:
        conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == user.id).first()
        if not conv:
            conv_id = None
    if not conv_id:
        conv = Conversation(user_id=user.id, title=data.message[:60])
        db.add(conv)
        db.commit()
        db.refresh(conv)
        conv_id = conv.id
    # store user message
    msg = Message(conversation_id=conv_id, user_id=user.id, role="user", content=data.message)
    db.add(msg)
    db.commit()

    # pipeline
    event = input_manager.normalize(content=data.message, source=data.source, user_id=user.id)
    bus.publish({"type":"USER_MESSAGE","content":data.message,"user_id":user.id, "conversation_id": conv_id})

    intent = intent_engine.parse(data.message)
    bus.publish({"type":"INTENT_CREATED","intent": intent.model_dump(),"user_id":user.id})
    ctx = context_engine.build(user_id=user.id, current_message=data.message, conversation_id=conv_id)
    plan = planner.plan(intent)
    bus.publish({"type":"PLAN_CREATED","plan": plan.model_dump(),"user_id":user.id})

    # safety commands: handle instantly
    if intent.intent.startswith("safety"):
        if intent.intent == "safety_emergency_stop":
            orchestrator.emergency_stop(user.id)
            reply = "Emergency stop executed. All active tasks cancelled."
        elif intent.intent == "safety_stop":
            orchestrator.emergency_stop(user.id)
            reply = "Stopped."
        elif intent.intent == "safety_lock":
            reply = "Lock requires desktop integration (Phase 7). Acknowledged."
        else:
            reply = f"Safety command '{intent.intent}' acknowledged."
        # store assistant message
        amsg = Message(conversation_id=conv_id, user_id=None, role="assistant", content=reply)
        db.add(amsg)
        db.commit()
        return {"conversation_id": conv_id, "message": {"role":"assistant","content": reply}, "intent": intent.model_dump(), "plan": plan.model_dump(), "execution": None}

    # orchestrator
    exec_result = await orchestrator.run(plan, user_id=user.id, trust_level=user.trust_level)

    # craft reply
    # handle specific intents for friendly responses even when orchestrator gave "acknowledged"
    low_msg = data.message.lower()
    # direct time query bypass — always answer time
    if intent.intent == "time" or ("what time" in low_msg or "current time" in low_msg):
        from datetime import datetime, timezone
        reply = f"Current time is {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}."
        # store and return early (no orchestrator heavy work already done but we overwrite)
        amsg = Message(conversation_id=conv_id, user_id=None, role="assistant", content=reply, tool_calls=exec_result)
        db.add(amsg)
        from datetime import datetime as dt2, timezone as tz2
        conv_item2 = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if conv_item2:
            conv_item2.updated_at = dt2.now(tz2.utc)
        db.commit()
        return {"conversation_id": conv_id, "message": {"role":"assistant","content": reply}, "intent": intent.model_dump(), "plan": plan.model_dump(), "execution": exec_result}

    if intent.intent == "general":
        if "introduce yourself" in low_msg or low_msg.strip() in ("jarvis", "jarvis.", "hey jarvis", "hello jarvis"):
            reply = (
                "I'm Jarvis — your AI operating layer. I can: open apps, check system status, manage calendar/tasks/reminders, "
                "search files and the web, analyze images, run automations, and remember what you teach me. "
                "I respect permissions (L0-L4), ask before risky actions, and log everything for review. "
                f"Connected: DB {ctx.get('environment',{}).get('date','')}. LLM: {'configured' if intent.confidence else 'local'}. Try: 'Prepare my morning briefing' or 'What's using my RAM?'"
            )
        elif any(k in low_msg for k in ["hello","hi","good morning","good evening","hey"]):
            reply = f"Hello {user.display_name or 'there'}. I'm Jarvis. I can help with your calendar, tasks, files, system status, web search, and more. Try: 'What's using the most RAM?' or 'Prepare my morning briefing.'"
        elif "time" in low_msg:
            from datetime import datetime, timezone
            reply = f"Current time is {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}."
        elif exec_result["results"] and exec_result["results"][0].get("result") == "acknowledged":
            # generic ack -> turn into helpful answer
            reply = f"I heard you: '{data.message}'. I have {len(plan.steps)} step(s) planned. For richer AI, configure an LLM provider. Try a specific command like 'Open calculator' or 'Prepare my morning briefing.'"
        else:
            reply = f"Done: {intent.goal}"
    elif intent.intent == "briefing":
        parts = []
        for r in exec_result["results"]:
            if r.get("approval_required"):
                parts.append(f"⚠️ Approval required for {r['tool']}.")
            elif r.get("error"):
                parts.append(f"Error in {r.get('step')}: {r['error']}")
            elif r.get("result"):
                res = r["result"]
                if isinstance(res, dict):
                    if "cpu_percent" in res:
                        parts.append(f"CPU {res.get('cpu_percent')}% across {res.get('cores')} cores")
                    elif "percent" in res and "total_mb" in res:
                        parts.append(f"RAM {res.get('percent')}% used ({res.get('available_mb')} MB available)")
                    elif "percent" in res and "total_gb" in res:
                        parts.append(f"Disk {res.get('percent')}% used ({res.get('free_gb')} GB free)")
                    else:
                        parts.append(f"{r.get('step')}: {str(res)[:300]}")
                else:
                    parts.append(str(res)[:400])
        reply = "Good morning. Here's your briefing:\n" + "\n".join(f"- {p}" for p in parts) if parts else "Briefing ready (no data)."
        if exec_result["pending_approvals"]:
            reply += f"\n\n{len(exec_result['pending_approvals'])} action(s) need your approval."
    elif exec_result["results"]:
        parts = []
        for r in exec_result["results"]:
            if r.get("approval_required"):
                parts.append(f"⚠️ Approval required for {r['tool']}. Review in Security Center.")
            elif r.get("error"):
                parts.append(f"Error in {r.get('step')}: {r['error']}")
            elif r.get("result"):
                res = r["result"]
                if isinstance(res, dict):
                    if "cpu_percent" in res:
                        parts.append(f"CPU {res.get('cpu_percent')}% across {res.get('cores')} cores")
                    elif "percent" in res and "total_mb" in res:
                        parts.append(f"RAM {res.get('percent')}% used ({res.get('available_mb')} MB available)")
                    elif "percent" in res and "total_gb" in res:
                        parts.append(f"Disk {res.get('percent')}% used ({res.get('free_gb')} GB free)")
                    elif "cpu" in res and "ram" in res:
                        parts.append(f"System: CPU {res['cpu'].get('cpu_percent')}% · RAM {res['ram'].get('percent')}% · Disk {res['disk'].get('percent')}%")
                    else:
                        parts.append(f"{r.get('step')}: {str(res)[:300]}")
                else:
                    parts.append(str(res)[:400])
        reply = "\n".join(parts) if parts else f"Done: {intent.goal}"
        if exec_result["pending_approvals"]:
            reply += f"\n\n{len(exec_result['pending_approvals'])} action(s) need your approval."
    else:
        reply = f"Done: {intent.goal}"
    # store
    amsg = Message(conversation_id=conv_id, user_id=None, role="assistant", content=reply, tool_calls=exec_result)
    db.add(amsg)
    # update conversation timestamp
    conv_item = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if conv_item:
        from datetime import datetime, timezone
        conv_item.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"conversation_id": conv_id, "message": {"role":"assistant","content": reply}, "intent": intent.model_dump(), "plan": plan.model_dump(), "execution": exec_result}

@router.get("/conversations")
def list_conversations(user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    convs = db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()).limit(50).all()
    return {"conversations": [{"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat() if c.updated_at else None, "created_at": c.created_at.isoformat() if c.created_at else None} for c in convs]}

@router.get("/conversations/{cid}")
def get_conversation(cid: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == cid, Conversation.user_id == user.id).first()
    if not conv:
        from fastapi import HTTPException
        raise HTTPException(404, "Conversation not found")
    msgs = db.query(Message).filter(Message.conversation_id == cid).order_by(Message.created_at.asc()).all()
    return {"conversation": {"id": conv.id, "title": conv.title}, "messages": [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None} for m in msgs]}

@router.delete("/conversations/{cid}")
def delete_conversation(cid: str, user: User = Depends(current_user_dep), db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == cid, Conversation.user_id == user.id).first()
    if not conv:
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")
    db.query(Message).filter(Message.conversation_id == cid).delete()
    db.delete(conv)
    db.commit()
    return {"ok": True}
