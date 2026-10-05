"""GitHub integration for earning work.

When GITHUB_TOKEN is set we can push the per-project isolated git repo to GitHub
and open PRs. Otherwise we report not configured but keep local git.

Uses only `requests` + subprocess git.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import requests

from ..config import settings
from ..services import workspace as ws


def configured() -> bool:
    return bool(settings().github_token)


def status() -> dict:
    s = settings()
    token = bool(s.github_token)
    oauth = bool(s.github_client_id and s.github_client_secret)
    return {"token": token, "oauth": oauth, "configured": token or oauth,
            "note": "Set GITHUB_TOKEN (PAT) to enable push" if not token else "Ready to push"}


def push_project(project_id: str, remote_url: str, branch: str = "main") -> dict:
    """Push local project workspace git to remote_url (https with token). Requires GITHUB_TOKEN env or token in URL."""
    if not configured() and "github_token" not in remote_url:
        return {"ok": False, "error": "GitHub not configured — set GITHUB_TOKEN"}
    repo = ws.path_for(project_id)
    if not (repo / ".git").exists():
        return {"ok": False, "error": "No git repo for project"}
    # ensure remote
    try:
        subprocess.check_output(["git", "-C", str(repo), "remote", "get-url", "origin"], stderr=subprocess.STDOUT)
        subprocess.check_call(["git", "-C", str(repo), "remote", "set-url", "origin", remote_url])
    except subprocess.CalledProcessError:
        subprocess.check_call(["git", "-C", str(repo), "remote", "add", "origin", remote_url])
    # push
    try:
        out = subprocess.check_output(["git", "-C", str(repo), "push", "-u", "origin", f"HEAD:{branch}"], stderr=subprocess.STDOUT, text=True, timeout=60)
        return {"ok": True, "logs": out.splitlines()[-10:]}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": e.output[:500] if hasattr(e, "output") else str(e)}


def create_repo(token: str, name: str, private: bool = True) -> dict:
    r = requests.post("https://api.github.com/user/repos", headers={"Authorization": f"Bearer {token}"}, json={"name": name, "private": private}, timeout=15)
    if r.status_code >= 300:
        return {"ok": False, "error": f"GitHub {r.status_code}: {r.text[:300]}"}
    return {"ok": True, "data": r.json(), "clone_url": r.json().get("clone_url")}
