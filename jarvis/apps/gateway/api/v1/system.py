from __future__ import annotations

import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.gateway.api.v1.auth import current_user_dep, get_db
from apps.gateway.db import User
from packages.tools.registry import execute_tool
from services.core.orchestrator import orchestrator

router = APIRouter(prefix="/system", tags=["system"])

@router.get("/status")
async def system_status(user: User = Depends(current_user_dep)):
    cpu = await execute_tool("system.cpu_status", {})
    ram = await execute_tool("system.ram_status", {})
    disk = await execute_tool("system.disk_status", {})
    return {"cpu": cpu.get("result"), "ram": ram.get("result"), "disk": disk.get("result"), "timestamp": int(time.time())}

@router.get("/diagnostics")
async def diagnostics(user: User = Depends(current_user_dep)):
    diag = await execute_tool("system.diagnostics", {})
    return diag.get("result")

@router.post("/emergency-stop")
def emergency(user: User = Depends(current_user_dep)):
    orchestrator.emergency_stop(user.id)
    return {"stopped": True}
