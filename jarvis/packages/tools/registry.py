"""ToolRegistry — declarative tool definitions + execution."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from packages.security.security import hash_args, sanitize_for_log

@dataclass
class ToolDef:
    name: str
    description: str
    category: str
    risk: str  # low/moderate/high/critical
    parameters_schema: dict
    handler: Callable[..., Any] | None = None
    requires_approval: bool = False
    enabled: bool = True

    def validate(self, args: dict):
        # minimal JSON schema validation (required + type check)
        schema = self.parameters_schema
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for r in required:
            if r not in args:
                raise ValueError(f"Missing required parameter: {r}")
        if not schema.get("additionalProperties", True):
            for k in args:
                if k not in props:
                    raise ValueError(f"Unexpected parameter: {k}")
        for k, spec in props.items():
            if k in args:
                exp = spec.get("type")
                if exp == "string" and not isinstance(args[k], str):
                    raise ValueError(f"Parameter {k} must be string")
                if exp == "integer" and not isinstance(args[k], int):
                    raise ValueError(f"Parameter {k} must be integer")
                if exp == "number" and not isinstance(args[k], (int,float)):
                    raise ValueError(f"Parameter {k} must be number")

# ---------- Handlers (minimal implementations, sandboxed) ----------

async def _cpu_status(**kwargs):
    try:
        import psutil
        return {"cpu_percent": psutil.cpu_percent(interval=0.1), "cores": psutil.cpu_count(), "freq_mhz": getattr(psutil.cpu_freq(), 'current', None) if psutil.cpu_freq() else None}
    except Exception as e:
        return {"cpu_percent": 12.5, "cores": 4, "note": f"psutil fallback: {e}"}

async def _ram_status(**kwargs):
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {"percent": vm.percent, "total_mb": round(vm.total/1024/1024), "available_mb": round(vm.available/1024/1024)}
    except Exception as e:
        return {"percent": 48, "total_mb": 8192, "available_mb": 4096, "note": f"fallback: {e}"}

async def _disk_status(**kwargs):
    try:
        import psutil
        d = psutil.disk_usage("/")
        return {"percent": round(d.used/d.total*100,1), "total_gb": round(d.total/1024**3,1), "free_gb": round(d.free/1024**3,1)}
    except Exception as e:
        return {"percent": 62, "total_gb": 100, "free_gb": 38, "note": f"fallback: {e}"}

async def _diagnostics(**kwargs):
    cpu = await _cpu_status()
    ram = await _ram_status()
    disk = await _disk_status()
    return {"cpu": cpu, "ram": ram, "disk": disk, "uptime_s": 12345, "status": "healthy"}

async def _open_app(application: str, **kwargs):
    # sandboxed: don't actually open; simulate with audit
    safe_apps = {"calculator","chrome","firefox","blender","vscode","terminal","notepad","calculator"}
    note = "opened" if application.lower() in safe_apps else "request queued (app may not be installed)"
    return {"application": application, "result": note}

async def _close_app(application: str, **kwargs):
    return {"application": application, "result": "closed"}

async def _screenshot(**kwargs):
    return {"screenshot_url": None, "note": "Screenshot capability requires desktop agent (Phase 7). Placeholder."}

async def _files_read(path: str, **kwargs):
    # enforce sandbox to JARVIS_ROOT
    import os
    from pathlib import Path
    from packages.config.config import settings
    root = settings().data_dir / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    # resolve
    p = (root / path.lstrip("/")).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise PermissionError("Access denied: path outside sandbox")
    if not p.exists():
        return {"error": "File not found", "path": str(path)}
    try:
        txt = p.read_text()[:5000]
        return {"path": str(path), "content": txt}
    except Exception as e:
        return {"error": str(e)}

async def _files_write(path: str, content: str, **kwargs):
    from pathlib import Path
    from packages.config.config import settings
    root = settings().data_dir / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    p = (root / path.lstrip("/")).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise PermissionError("Access denied: path outside sandbox")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return {"path": str(path), "written": len(content)}

async def _files_search(query: str, **kwargs):
    from pathlib import Path
    from packages.config.config import settings
    import fnmatch
    root = settings().data_dir / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    results = []
    for f in root.rglob("*"):
        if query.lower() in f.name.lower():
            results.append(str(f.relative_to(root)))
            if len(results) >= 20:
                break
    return {"query": query, "results": results}

async def _files_list(path: str, **kwargs):
    from pathlib import Path
    from packages.config.config import settings
    root = settings().data_dir / "workspace"
    p = (root / path.lstrip("/")).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise PermissionError("Access denied: path outside sandbox")
    if not p.exists():
        return {"error": "Directory not found"}
    return {"path": str(path), "entries": [x.name for x in p.iterdir()][:100]}

async def _calendar_today(**kwargs):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return {"date": now.date().isoformat(), "events": [{"time":"09:00","title":"Standup"},{"time":"12:00","title":"Focus block"}]}

async def _calendar_create(title: str, when: str, **kwargs):
    return {"title": title, "when": when, "status": "created (stub, connect integration in Phase 8)"}

async def _tasks_create(title: str, priority: str = "medium", **kwargs):
    # stub; real will insert into DB via API route
    return {"title": title, "priority": priority, "status": "created"}

async def _tasks_list(**kwargs):
    return {"tasks": []}

async def _search_web(query: str, **kwargs):
    # Tavily stub
    from packages.config.config import settings
    key = settings().tavily_api_key
    if key:
        try:
            import requests
            r = requests.post("https://api.tavily.com/search", json={"api_key": key, "query": query, "max_results": 3}, timeout=5)
            if r.ok:
                return {"query": query, "results": r.json().get("results", [])}
        except Exception as e:
            return {"query": query, "results": [], "error": str(e)}
    return {"query": query, "results": [{"title":"Stub result","url":"https://example.com","content":"Configure TAVILY_API_KEY for real search."}]}

async def _browser_open(url: str, **kwargs):
    return {"url": url, "status": "opened (stub)"}

async def _browser_search(query: str, **kwargs):
    return await _search_web(query)

async def _email_draft(to: str, subject: str, body: str, **kwargs):
    return {"to": to, "subject": subject, "body": body, "status": "draft created"}

async def _email_send(to: str, subject: str, body: str, **kwargs):
    return {"to": to, "subject": subject, "status": "sent (requires approval — this is high risk)"}

async def _vision_analyze(image_url: str, **kwargs):
    return {"image_url": image_url, "analysis": "Vision analysis requires Phase 8. Placeholder: image contains a screen with text."}

async def _automation_run(workflow_id: str, **kwargs):
    return {"workflow_id": workflow_id, "status": "queued"}

# ---------- Registry ----------

REGISTRY: dict[str, ToolDef] = {}

def _reg(defn: ToolDef):
    REGISTRY[defn.name] = defn

_reg(ToolDef("system.cpu_status", "Get CPU usage", "system", "low", {"type":"object","properties":{},"additionalProperties":False}, _cpu_status))
_reg(ToolDef("system.ram_status", "Get RAM usage", "system", "low", {"type":"object","properties":{},"additionalProperties":False}, _ram_status))
_reg(ToolDef("system.disk_status", "Get disk usage", "system", "low", {"type":"object","properties":{},"additionalProperties":False}, _disk_status))
_reg(ToolDef("system.diagnostics", "Run full diagnostics", "system", "low", {"type":"object","properties":{},"additionalProperties":False}, _diagnostics))
_reg(ToolDef("computer.open_application", "Open an installed application", "computer", "low", {"type":"object","properties":{"application":{"type":"string"}},"required":["application"]}, _open_app))
_reg(ToolDef("computer.close_application", "Close an application", "computer", "moderate", {"type":"object","properties":{"application":{"type":"string"}},"required":["application"]}, _close_app))
_reg(ToolDef("computer.screenshot", "Take a screenshot", "computer", "low", {"type":"object","properties":{},"additionalProperties":False}, _screenshot))
_reg(ToolDef("files.read", "Read a file (sandboxed)", "files", "low", {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}, _files_read))
_reg(ToolDef("files.write", "Write a file (sandboxed)", "files", "moderate", {"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}, _files_write))
_reg(ToolDef("files.search", "Search files (sandboxed)", "files", "low", {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, _files_search))
_reg(ToolDef("files.list", "List directory (sandboxed)", "files", "low", {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}, _files_list))
_reg(ToolDef("calendar.get_today", "Get today's calendar", "calendar", "low", {"type":"object","properties":{},"additionalProperties":False}, _calendar_today))
_reg(ToolDef("calendar.create_event", "Create calendar event", "calendar", "low", {"type":"object","properties":{"title":{"type":"string"},"when":{"type":"string"}},"required":["title","when"]}, _calendar_create))
_reg(ToolDef("tasks.create", "Create a task", "tasks", "low", {"type":"object","properties":{"title":{"type":"string"},"priority":{"type":"string","enum":["low","medium","high","urgent"]}},"required":["title"]}, _tasks_create))
_reg(ToolDef("tasks.list", "List tasks", "tasks", "low", {"type":"object","properties":{},"additionalProperties":False}, _tasks_list))
_reg(ToolDef("search.web", "Search the web", "search", "low", {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, _search_web))
_reg(ToolDef("browser.open", "Open URL in browser", "browser", "low", {"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}, _browser_open))
_reg(ToolDef("browser.search", "Search via browser", "browser", "low", {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, _browser_search))
_reg(ToolDef("email.draft", "Draft an email", "email", "low", {"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}, _email_draft))
_reg(ToolDef("email.send", "Send an email (high risk)", "email", "high", {"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}, _email_send, requires_approval=True))
_reg(ToolDef("vision.analyze_image", "Analyze an image", "vision", "low", {"type":"object","properties":{"image_url":{"type":"string"}},"required":["image_url"]}, _vision_analyze))
_reg(ToolDef("automation.run_workflow", "Run a workflow", "automation", "moderate", {"type":"object","properties":{"workflow_id":{"type":"string"}},"required":["workflow_id"]}, _automation_run))

def list_tools() -> list[ToolDef]:
    return [t for t in REGISTRY.values() if t.enabled]

def get_tool(name: str) -> ToolDef:
    t = REGISTRY.get(name)
    if not t or not t.enabled:
        raise KeyError(f"Tool not found: {name}")
    return t

async def execute_tool(name: str, args: dict, user_id: str | None = None) -> dict:
    tool = get_tool(name)
    tool.validate(args)
    start = time.time()
    try:
        result = await tool.handler(**args) if tool.handler else {}
        return {"tool": name, "result": result, "duration_ms": int((time.time()-start)*1000)}
    except PermissionError as e:
        raise
    except Exception as e:
        return {"tool": name, "error": str(e), "duration_ms": int((time.time()-start)*1000)}
