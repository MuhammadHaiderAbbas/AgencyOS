# API

All endpoints are JSON and require `Authorization: Bearer <token>` unless noted.

**Auth**: `POST /api/auth/signup` · `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me` · `DELETE /api/auth/me` {confirm: email} · `GET /api/auth/export`

**Projects**: `GET/POST /api/projects` {idea, template?} · `GET/DELETE /api/projects/{id}` · `GET/POST /api/projects/{id}/messages` · `POST …/approve-requirements` · `POST …/start` · `GET …/tasks` · `GET …/artifacts` · `GET …/activity` · `GET …/executions` · `GET …/files` · `GET …/file?path=` · `GET …/preview/{path}`* · `GET …/screenshots/{name}`* · `GET …/export`* · `POST …/clone|archive|unarchive` · `GET …/deployments` · `POST …/deployments/{did}/rollback`

**Artifacts**: `GET /api/artifacts` · `GET /api/artifacts/{id}?version=` · `POST …/approve|restore` {version} · `GET …/diff?a=&b=`

**Work**: `GET /api/tasks?status=` · `GET /api/approvals?status=PENDING|ALL` · `POST /api/approvals/{id}/decide` {decision: approve|reject|changes, note} · `GET /api/activity` · `GET /api/notifications` · `POST /api/notifications/read` · `GET /api/dashboard` · `GET /api/templates`

**Agents**: `GET /api/agents?source=&framework=&industry=&q=` · `GET /api/agents/{id}` · admin: `POST /api/agents/import` · `POST /api/agents/custom` · `POST /api/agents/{id}/enable|disable|health|test`

**Settings / billing / admin**: `GET /api/settings` · `PUT /api/settings/providers` · `GET /api/billing` · `GET /api/admin/observability`

**Realtime**: SSE `GET /api/stream/org`*, `GET /api/stream/projects/{id}`* · WebSocket `/ws/projects/{id}`, `/ws/org`, `/ws/tasks`, `/ws/agents`, `/ws/notifications` (`?token=`; needs the `websockets` package)

**Public**: `GET /api/health` · `GET /sites/{project_id}/…` (local deployments)

\* Also accepts the session cookie (safe GETs only).
