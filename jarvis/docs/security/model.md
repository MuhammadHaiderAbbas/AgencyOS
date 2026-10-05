# JARVIS — Security Model

## 1. Threat Model

| Threat | Mitigation |
|---|---|
| Prompt injection (web/email/docs overriding instructions) | Retrieved content tagged `role:data` never as system; PolicyEngine strips instruction patterns; test suite fuzzes injections |
| Tool permission bypass | Every `tool.execute` path calls `PermissionEngine.check(user, tool, args)`; agents scoped to allowed_tools; fails closed |
| Command injection | No `shell: true` without allowlist; sandboxed terminal with command allowlist; input validation by Pydantic; parameterized queries only |
| Path traversal | File tools enforce scope `JARVIS_ROOT` (`~/Jarvis/` by default); `..` resolved and rejected if outside; tests cover `../../etc/passwd` |
| Privilege escalation | RBAC (user/admin), least privilege, token revocation, device permissions |
| Credential leakage | Secrets never logged/prompted/stored in memory; masked in API (`***`); env-only; no frontend exposure |
| XSS/CSRF | CSP + escaped rendering, CSRF double-submit for cookie auth, SameSite=Lax |
| SQLi | SQLAlchemy ORM + parameterized queries, never string interpolation |
| SSRF | URL allowlist, no internal metadata endpoints, SSRF tests |
| Session hijacking | HttpOnly+Secure cookies, short JWT TTL (24h), refresh rotation, IP/UA binding, revoke-all |
| Unsafe plugins | Manifest permissions, sandbox, user approval, code scan |

## 2. Authentication & Sessions

- **Password storage:** bcrypt (rounds=12).
- **JWT:** HS256 (dev) / RS256 (prod), payload `{sub:user_id, org?:null, role, iat, exp}`, TTL 24h (configurable).
- **Cookies:** `jarvis_token=JWT; HttpOnly; Secure (prod); SameSite=Lax; Path=/`.
- **CSRF:** For cookie auth, require `X-CSRF-Token` header matching `csrf_token` cookie (double-submit).
- **Rate limit:** 10 login attempts/min/IP, CAPTCHA after 5 failures (future).
- **Sessions table:** tracks refresh, revocation, device, IP, UA. `REVOKE ALL` operation.

## 3. Authorization (RBAC)

| Role | Capabilities |
|---|---|
| `user` | Own memories, tasks, conversations, tools L0-L3 (L3 needs approval), devices |
| `admin` | Above + user management, global tool config, integrations, security dashboard, kill switch |

Tool-scoped permissions stored per user (jsonb) + per-agent allowed_tools. Enforcement is in PermissionEngine, not in handler logic.

## 4. Permission Levels (Risk Tiers)

| Level | Label | Requires Confirm | Examples |
|---|---|---|---|
| 0 | SAFE | never | answer, calc, read public, open calculator, read non-sensitive file |
| 1 | LOW | no | create reminder, draft, organize files |
| 2 | MODERATE | maybe (config) | move files, send message, edit doc |
| 3 | HIGH | yes (default) |  financial, delete important, install software, privileged exec, send sensitive |
| 4 | CRITICAL | always | disable security, change auth, delete large datasets, modify security controls |

Trust settings: `conservative` (confirm L2+), `balanced` (L3+), `autonomous` (L4 only). L4 always requires explicit user confirmation regardless of trust.

## 5. Human Confirmation Flow

When `PermissionEngine` returns `requires_approval=true`:
1. Execution paused (`awaiting_approval`), Approval record created with `WHAT/WHY/TARGET/RISK`.
2. Notification + WS/SSE `APPROVAL_REQUIRED`.
3. UI shows `[Cancel] [Review] [Confirm]` modal.
4. User resolves via `POST /approvals/{id}/resolve`.
5. If granted, tool executes; if denied, execution cancelled and logged.

Emergency stop: `POST /system/emergency-stop` or phrase “Jarvis, emergency stop” (deterministic router) immediately cancels all running executions, revokes temp permissions, stops speech/automation.

## 6. Secrets & PII

- Secrets (`ANTHROPIC_API_KEY`, DB creds, tokens) from env only in dev; prod uses OS keychain/Vault adapter (`packages/security/secrets.py`).
- Never into logs/LLM prompts/frontend/error messages/memory embeddings.
- PII minimization: collect only permitted context; memory controls allow `show/forget/delete_all`.
- Audit logs store `arguments_hash` (SHA256) not raw args if arg contains `password|token|key`.

## 7. Network & Transport

- TLS terminating at gateway (Caddy/Traefik) in prod; HSTS.
- Internally, services talk over localhost/docker network only.
- No public exposure of desktop without secure reverse tunnel + auth.

## 8. Audit Logging

Every tool execution writes to `audit_logs`:
`{ timestamp, user_id, agent, tool, arguments_hash, result_status, risk_level, approval_id, duration_ms, error }`
- Structured JSON logs also emitted with `request_id` correlation.
- Endpoints: `GET /tools/history`, `GET /security/audit` (admin).

## 9. Secure Defaults

- `ALLOW_REMOTE_ACCESS=false` by default.
- Plugin execution sandboxed (Docker) if external.
- Offline graceful degradation message: “Internet required”.

## 10. Testing

`tests/security/` covers: injection, path traversal, privilege escalation, credential leak, unsafe file access, SSRF, CSRF, agent permission bypass, tool risk enforcement. Must pass before phase promotion.
