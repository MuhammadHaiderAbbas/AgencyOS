# JARVIS — Tool Model

## Definition

Every capability is a **Tool**. Tools are plugins with a declarative schema and a handler.

```json
{
  "name": "computer.open_application",
  "description": "Open an installed application",
  "category": "computer",
  "risk": "low",
  "parameters": {
    "type": "object",
    "properties": { "application": { "type": "string" } },
    "required": ["application"],
    "additionalProperties": false
  },
  "requires_approval": false
}
```

### ToolDef dataclass

```python
@dataclass
class ToolDef:
    name: str            # dot.namespaced
    description: str
    category: str        # computer/browser/files/system/calendar/email/messaging/media/developer/database/search/vision/audio/automation/smart_home
    risk: Literal["low","moderate","high","critical"]  # maps to PermissionLevel 0-3/4
    parameters_schema: dict
    requires_approval: bool
    handler: Callable    # (user, args, context) -> result
    enabled: bool = True
```

## Registry

`packages/tools/registry.py` holds `TOOL_REGISTRY: dict[str, ToolDef]`.

- Registration is explicit list, not filesystem scanning (deterministic, auditable).
- `list_tools()` → for `/api/v1/tools`
- `get_tool(name)` → raises 404 if unknown/disabled
- `execute(user, name, args)` → validates via JSON Schema → PermissionEngine → handler → audit

## Categories & Examples (Phase 1 minimal, expands per phase)

| Category | Tools (initial) |
|---|---|
| computer | `computer.open_application`, `computer.close_application`, `computer.screenshot` |
| system | `system.cpu_status`, `system.ram_status`, `system.disk_status`, `system.diagnostics` |
| files | `files.read`, `files.write`, `files.search`, `files.list` (scoped) |
| calendar | `calendar.get_today`, `calendar.create_event` |
| tasks | `tasks.create`, `tasks.list` |
| search | `search.web` (Tavily adapter stub) |
| browser | `browser.open`, `browser.search` |
| email | `email.draft`, `email.send` (L3) |
| automation | `automation.run_workflow` |
| vision | `vision.analyze_image` |

High-risk tools set `requires_approval=True` or risk `high/critical` → PermissionEngine gate.

## Handler Contract

```python
async def handle_cpu_status(user, args: {}, context) -> dict:
    import psutil
    return {"cpu_percent": psutil.cpu_percent(), "cores": psutil.cpu_count()}
```

- Handlers MUST validate args with schema before use.
- MUST NOT log secrets.
- MUST return JSON-serializable dict (or raise `ToolError`).
- MUST respect file scope: `files.*` checks `context.allowed_roots`.

## Adding a Tool

1. Write handler in `packages/tools/builtin/{category}.py`
2. Define `ToolDef` with `risk` and `parameters_schema`
3. Append to `TOOL_REGISTRY` in `registry.py`
4. Add unit test in `tests/unit/test_tools.py`
5. Document in `docs/api/spec.md` if public

## Audit

Every invocation writes to `audit_logs` regardless of success. `arguments_hash` stored; raw args omitted if sensitive.
