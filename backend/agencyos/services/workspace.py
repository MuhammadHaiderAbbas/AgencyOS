"""Per-project isolated workspace + git repository."""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from ..config import settings

LAYOUT = ["requirements", "research", "design", "architecture", "source", "tests", "deployment",
          "artifacts", "reports"]

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "AgencyOS", "GIT_AUTHOR_EMAIL": "agents@agencyos.local",
    "GIT_COMMITTER_NAME": "AgencyOS", "GIT_COMMITTER_EMAIL": "agents@agencyos.local",
}


def path_for(project_id: str) -> Path:
    if not project_id.isalnum():
        raise ValueError("invalid project id")
    return settings().workspaces_dir / project_id


def ensure(project_id: str) -> Path:
    p = path_for(project_id)
    if not p.exists():
        p.mkdir(parents=True)
        for d in LAYOUT:
            (p / d).mkdir()
            (p / d / ".gitkeep").touch()
        (p / ".gitignore").write_text(".env\n*.sqlite3\n__pycache__/\nreports/screenshots/\n")
        _git(p, "init", "-q", "-b", "main")
        _git(p, "add", "-A")
        _git(p, "commit", "-q", "-m", "chore: initialise AgencyOS project workspace")
        _git(p, "branch", "develop")
    return p


def _git(p: Path, *args: str) -> str:
    env = {**os.environ, **_GIT_ENV}
    r = subprocess.run(["git", *args], cwd=p, env=env, capture_output=True, text=True, timeout=60)
    if r.returncode != 0 and args[0] not in {"commit"}:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def commit(project_id: str, role: str, message: str) -> str | None:
    p = ensure(project_id)
    _git(p, "add", "-A")
    status = _git(p, "status", "--porcelain")
    if not status:
        return None
    _git(p, "commit", "-q", "-m", f"agent({role}): {message}")
    return _git(p, "rev-parse", "--short", "HEAD")


def log(project_id: str, limit: int = 50) -> list[dict]:
    p = path_for(project_id)
    if not p.exists():
        return []
    out = _git(p, "log", f"-n{limit}", "--pretty=format:%h\x1f%s\x1f%cI")
    rows = []
    for line in out.splitlines():
        h, s, d = line.split("\x1f")
        rows.append({"hash": h, "message": s, "date": d})
    return rows


def revert_last(project_id: str) -> str:
    p = ensure(project_id)
    _git(p, "revert", "--no-edit", "HEAD")
    return _git(p, "rev-parse", "--short", "HEAD")


def head(project_id: str) -> str | None:
    p = path_for(project_id)
    if not p.exists():
        return None
    return _git(p, "rev-parse", "--short", "HEAD")


def tree(project_id: str) -> list[dict]:
    p = path_for(project_id)
    if not p.exists():
        return []
    files = []
    for f in sorted(p.rglob("*")):
        if ".git" in f.parts or f.name == ".gitkeep" or not f.is_file():
            continue
        files.append({"path": str(f.relative_to(p)), "size": f.stat().st_size})
    return files


def read_file(project_id: str, rel: str, max_bytes: int = 400_000) -> str:
    p = path_for(project_id)
    target = (p / rel).resolve()
    if not str(target).startswith(str(p.resolve()) + os.sep) or ".git" in target.parts:
        raise PermissionError("path outside workspace")
    return target.read_bytes()[:max_bytes].decode("utf-8", errors="replace")


def export_zip(project_id: str) -> bytes:
    p = ensure(project_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in p.rglob("*"):
            if f.is_file() and ".git" not in f.parts and f.name not in {".env"} and "screenshots" not in f.parts:
                z.write(f, f.relative_to(p))
    return buf.getvalue()


def delete(project_id: str) -> None:
    p = path_for(project_id)
    if p.exists():
        shutil.rmtree(p)
