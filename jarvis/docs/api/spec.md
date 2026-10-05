# JARVIS — API Specification (OpenAPI 3.1, versioned)

**Base:** `/api/v1`  **Auth:** Bearer JWT **and/or** `HttpOnly` cookie `jarvis_token`.  
**Content:** `application/json` unless noted.  
**Versioning:** URL prefix (`/api/v1`). Breaking changes bump to `/api/v2` with deprecation headers.

## Health & Meta

```http
GET /api/v1/health
→ 200 { status: "ok", version, db: "ok", redis: "ok|degraded", llm: "ok|offline", timestamp }
GET /api/v1/openapi.json   (served by FastAPI)
GET /api/v1/docs            (Swagger)
```

## Auth

```http
POST /api/v1/auth/signup   { email, password, display_name? } → { user, token }
POST /api/v1/auth/login    { email, password } → { user, token } (also Set-Cookie)
POST /api/v1/auth/logout   → 204 (clears cookie, revokes session)
GET  /api/v1/auth/me       (auth) → { user, preferences }
PUT  /api/v1/auth/me       (auth) { display_name, locale, timezone, personality, trust_level }
```

Errors: `400` validation, `401` bad creds, `409` email taken, `429` rate-limited.

## Chat (Text Interface)

```http
POST /api/v1/chat                          (auth)
  Body: { message: string, conversation_id?: uuid, attachments?: [{type,url}] }
  → 200 { conversation_id, message: {role:assistant, content}, intent, plan, execution_id }

GET  /api/v1/conversations                 (auth) → { conversations: [...] }
GET  /api/v1/conversations/{id}           (auth) → { conversation, messages: [...] }
DELETE /api/v1/conversations/{id}         (auth) → 204

POST /api/v1/chat/stream                  (auth) SSE or WS upgrade — streams tokens
  Event: data: {"type":"token","content":"Hello"}
  Event: data: {"type":"tool","tool":"calendar.get_today","status":"running"}
  Event: data: {"type":"approval_required","approval":{...}}
```

## Agents

```http
GET  /api/v1/agents                       → { agents: [{id,name,description,allowed_tools,enabled}] }
POST /api/v1/agents/{id}/execute          (auth) { goal, context? } → { execution }
GET  /api/v1/agents/executions            (auth) → paginated executions
GET  /api/v1/agents/executions/{id}       (auth) → { execution, steps }
POST /api/v1/agents/executions/{id}/cancel (auth) → { status: "cancelled" }
```

## Tools

```http
GET  /api/v1/tools                        → { tools: [{name,description,category,risk,parameters_schema}] }
POST /api/v1/tools/execute                (auth)
  Body: { tool: "system.cpu_status", arguments: {} }
  → 200 { result, execution_id, audit_id }
  → 202 { approval_required: true, approval_id }  // if L3/L4
GET  /api/v1/tools/history                (auth) → audit logs paginated
```

## Memory

```http
POST   /api/v1/memory                     (auth) { kind, content, importance?, expires_at? } → { memory }
GET    /api/v1/memory                     (auth) ?kind=&q=&limit=&offset= → { memories, total }
GET    /api/v1/memory/{id}                (auth) → { memory }
PATCH  /api/v1/memory/{id}                (auth) { content?, importance? } → { memory }
DELETE /api/v1/memory/{id}                (auth) → 204
POST   /api/v1/memory/search              (auth) { query, kinds?, limit? } → { results: [{memory,score}] }
POST   /api/v1/memory/controls            (auth) { action: "forget" | "remember"|"show"|"delete_all", target? }
```

## Tasks & Reminders

```http
POST   /api/v1/tasks                      (auth) { title, description?, priority?, deadline? } → { task }
GET    /api/v1/tasks                      (auth) ?status=&q= → { tasks }
PATCH  /api/v1/tasks/{id}                (auth) { status, priority } → { task }
DELETE /api/v1/tasks/{id}                (auth) → 204

POST   /api/v1/reminders                  (auth) { text, run_at, recurrence? } → { reminder }
GET    /api/v1/reminders                  (auth) → { reminders }
DELETE /api/v1/reminders/{id}             (auth) → 204
```

## System

```http
GET  /api/v1/system/status                (auth) → { cpu, gpu, ram, disk, network, processes, uptime }
GET  /api/v1/system/diagnostics           (auth) → health checks for each subsystem
POST /api/v1/system/emergency-stop        (auth) → 202 { stopped: true }
```

## Approvals

```http
GET  /api/v1/approvals                    (auth) ?status=pending → { approvals }
POST /api/v1/approvals/{id}/resolve       (auth) { decision: "granted"|"denied" } → { approval }
```

## Notifications

```http
GET  /api/v1/notifications                (auth) ?unread_only= → { notifications }
POST /api/v1/notifications/{id}/read      (auth) → 204
POST /api/v1/notifications/read-all       (auth) → 204
```

## Devices

```http
GET  /api/v1/devices                      (auth) → { devices }
POST /api/v1/devices/register             (auth) { name, platform, public_key? } → { device }
DELETE /api/v1/devices/{id}               (auth) → 204
POST /api/v1/devices/{id}/command         (auth) { command } → { accepted: true }
```

## Automations & Scheduler

```http
GET  /api/v1/automations                  (auth) → { workflows }
POST /api/v1/automations                  (auth) { name, trigger, actions } → { workflow }
PATCH /api/v1/automations/{id}            (auth) → { workflow }
DELETE /api/v1/automations/{id}           (auth) → 204
POST /api/v1/automations/{id}/run         (auth) → { execution_id }
```

## WebSockets & SSE

```http
GET /api/v1/stream              (auth via query ?token= or cookie)  SSE: text/event-stream
GET /api/v1/stream/{conversation_id}
GET /ws                          (auth)  WebSocket — JSON {type,payload}
  Client sends: {type:"USER_MESSAGE", content:"..."}
  Server emits: PING, USER_MESSAGE, INTENT_CREATED, PLAN_CREATED, TOOL_STARTED,
                TOOL_COMPLETED, APPROVAL_REQUIRED, MEMORY_CREATED, etc.
```

## Error Format
```json
{ "error": "Human readable", "code": "VALIDATION_ERROR", "details": {...} }
```
Codes: `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`, `RATE_LIMITED`, `CONFLICT`, `INTERNAL_ERROR`.

## Pagination
`?limit=20&offset=0` → `Max limit 100`. Responses include `{ items, total, limit, offset }` where applicable.

## Rate Limiting
Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`. Defaults: 60 req/min per user, 10/min for auth endpoints.

## Security Headers (gateway)
`X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY` (except embedded previews), `Content-Security-Policy`.
