# JARVIS — Event Model

## Canonical Event

All inputs normalized to:

```json
{
  "event_id": "uuid",
  "type": "USER_MESSAGE",
  "source": "voice|text|vision|gesture|system|scheduled|application|device",
  "timestamp": "ISO8601",
  "user_id": "uuid",
  "session_id": "uuid",
  "device_id": "uuid?",
  "content": "raw text or payload",
  "attachments": [{ "type": "image|file|audio", "url": "...", "meta": {} }],
  "metadata": { "app": "Chrome", "screen": "...", "location": "if permitted" },
  "trace_id": "uuid"
}
```

## Internal Event Types (EventBus)

| Type | When |
|---|---|
| USER_MESSAGE | InputManager received |
| VOICE_DETECTED | VAD triggered |
| INTENT_CREATED | IntentEngine done: `{intent, confidence}` |
| PLAN_CREATED | Planner done: `{plan}` |
| AGENT_STARTED / AGENT_COMPLETED / AGENT_FAILED | Orchestrator |
| TOOL_STARTED / TOOL_COMPLETED / TOOL_FAILED | ToolRouter |
| APPROVAL_REQUIRED / APPROVAL_GRANTED / APPROVAL_DENIED | PermissionEngine |
| MEMORY_CREATED / UPDATED | Memory store |
| AUTOMATION_TRIGGERED | Scheduler |
| SECURITY_ALERT | Security agent |
| DEVICE_CONNECTED / DISCONNECTED | Device registry |
| NOTIFICATION_CREATED | Notifications service |
| SYSTEM_HEALTH_CHANGED | System monitor |

## Bus Implementation

- **Dev:** `asyncio.Queue` per subscriber (in-process). `EventBus.subscribe(loop, org_id?, project_id?) → Queue`, `publish(event)` fans out, persisted to `audit_logs` where relevant.
- **Prod:** Redis PubSub (`redis.asyncio`), with in-proc fallback if Redis down.
- **Delivery:** At-least-once, persisted history in DB `events` table (optional) for replay.
- **Web exposure:** SSE `/api/v1/stream` and WS `/ws` emit filtered by user/org.

## Example Flow

```python
bus.publish({"type":"USER_MESSAGE","content":"Open Blender","user_id":u.id})
# → IntentEngine subscribes → publishes INTENT_CREATED
# → Planner → PLAN_CREATED
# → Orchestrator → TOOL_STARTED (computer.open_application)
# → frontend receives via SSE
```
