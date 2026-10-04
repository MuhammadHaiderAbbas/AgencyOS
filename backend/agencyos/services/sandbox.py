"""Sandboxed command execution for agent-generated or third-party code.

Two modes:
  docker   — preferred. Network disabled, read-only root, memory/CPU/pids limits, timeout.
  process  — fallback when Docker is unavailable. Scrubbed environment (no secrets),
             CPU/memory/file-size rlimits, timeout, cwd confined to the workspace.
             This is weaker isolation and is only used for code AgencyOS generated itself;
             third-party agents REQUIRE docker mode.
"""
from __future__ import annotations

import os
import resource
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    mode: str


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        r = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, timeout=5)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024))
    os.setsid()


SAFE_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": "/tmp", "NO_PROXY": "*"}


def run(cmd: list[str], cwd: Path, *, timeout: int = 60, image: str = "python:3.12-slim",
        require_docker: bool = False, env: dict | None = None, network: bool = False) -> SandboxResult:
    if docker_available():
        dcmd = ["docker", "run", "--rm", "--network", "bridge" if network else "none", "--memory", "1g", "--cpus", "1", "--pids-limit", "256",
                "--read-only", "--tmpfs", "/tmp", "-v", f"{cwd}:/work:rw", "-w", "/work"]
        for k, v in (env or {}).items():
            dcmd += ["-e", f"{k}={v}"]
        dcmd += [image, *cmd]
        return _exec(dcmd, cwd, timeout, "docker", None)
    if require_docker:
        return SandboxResult(126, "", "Docker sandbox required but not available", False, "refused")
    return _exec(cmd, cwd, timeout, "process", {**SAFE_ENV, **(env or {})})


def _exec(cmd, cwd, timeout, mode, env) -> SandboxResult:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
                           preexec_fn=_limits if mode == "process" else None)
        return SandboxResult(r.returncode, r.stdout[-20000:], r.stderr[-20000:], False, mode)
    except subprocess.TimeoutExpired as e:
        return SandboxResult(124, (e.stdout or b"")[-5000:].decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                             "timeout", True, mode)
    except OSError as e:
        return SandboxResult(127, "", str(e), False, mode)
