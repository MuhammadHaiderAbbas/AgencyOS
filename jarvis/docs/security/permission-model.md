# JARVIS — Permission Model

## Levels

| Level | Name | Risk | Confirm | Example |
|---|---|---|---|---|
| 0 | SAFE | low | never | answer Q, calc, read public page, open calculator |
| 1 | LOW | low | no | create reminder, create draft, organize files (non-destructive) |
| 2 | MODERATE | moderate | trust-dependent | move file, delete temp file, send message, edit doc |
| 3 | HIGH | high | yes (default) | financial tx, delete important, install software, privileged exec |
| 4 | CRITICAL | critical | always | disable antivirus, change auth, delete large dataset, modify security |

Mapping: Tool `risk: low → 0`, `moderate → 2`, `high → 3`, `critical → 4`.

## Engine

```python
class PermissionEngine:
    def check(self, user, tool: ToolDef, args: dict, trust_level: str) -> PermissionDecision:
        # returns { allowed: bool, requires_approval: bool, level: int, reason: str }
```

### Trust Levels

| Trust | Behavior |
|---|---|
| conservative | confirm L2+ |
| balanced | confirm L3+ (default) |
| autonomous | confirm L4 only (L4 always) |

User can set via `PUT /auth/me {trust_level}`.

## Deterministic Safety Commands

These bypass AI and execute via trusted handler (no LLM):

- STOP / CANCEL / PAUSE
- LOCK / DISABLE MICROPHONE / DISABLE CAMERA
- EMERGENCY STOP — kills all executions, revokes temps, blocks tools, does NOT destroy data.

## Approval Object

```json
{
  "id": "uuid",
  "execution_id": "uuid",
  "tool": "files.delete",
  "what": "Delete 184 files from Downloads",
  "why": "User said 'clean up downloads'",
  "target": "/home/user/Downloads",
  "risk": "Deleting cannot be undone. 184 files affected.",
  "status": "pending"
}
```

UI: `[Cancel] [Review] [Confirm]`.

## Enforcement Points

1. `ToolRouter.execute` — before handler.
2. `Orchestrator` — before dispatching step.
3. `Scheduler` — scheduled jobs also check at execution time.

Every agent only gets `allowed_tools` intersection with permission grant.

## Tests

- Unit: L0 allowed, L4 always requires approval, trust levels respected.
- Security: attempt bypass via direct handler call fails; forged approval rejected (must be owned by user, pending).
