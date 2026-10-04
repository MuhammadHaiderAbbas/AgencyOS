"""Deployment adapters.

local    — publishes the built site to AgencyOS' own static host at /sites/<project_id>/
           (immutable release directories + a 'current' pointer, so rollback is instant).
netlify  — real Netlify zip deploy via API when NETLIFY_AUTH_TOKEN and NETLIFY_SITE_ID are set.
Other providers implement the same `DeploymentAdapter` interface.
"""
from __future__ import annotations

import io
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from ..config import settings


@dataclass
class DeployResult:
    ok: bool
    url: str | None
    logs: list[str]


class DeploymentAdapter:
    name = "base"

    def configured(self) -> bool:
        return False

    def deploy(self, project_id: str, deploy_id: str, site_dir: Path) -> DeployResult:
        raise NotImplementedError

    def rollback(self, project_id: str, deploy_id: str) -> DeployResult:
        raise NotImplementedError


class LocalStaticAdapter(DeploymentAdapter):
    name = "local"

    def configured(self) -> bool:
        return True

    def _root(self, project_id: str) -> Path:
        return settings().deployments_dir / project_id

    def deploy(self, project_id, deploy_id, site_dir):
        logs = [f"Build output: {site_dir}"]
        if not (site_dir / "index.html").exists():
            return DeployResult(False, None, logs + ["index.html missing — refusing to deploy"])
        dest = self._root(project_id) / "releases" / deploy_id
        shutil.copytree(site_dir, dest)
        logs.append(f"Copied {sum(1 for _ in dest.rglob('*') if _.is_file())} files to release {deploy_id[:8]}")
        (self._root(project_id) / "CURRENT").write_text(deploy_id)
        logs.append("Activated release")
        ok = self.health(project_id)
        logs.append("Health check: " + ("index.html served" if ok else "FAILED"))
        return DeployResult(ok, f"/sites/{project_id}/", logs)

    def rollback(self, project_id, deploy_id):
        if not (self._root(project_id) / "releases" / deploy_id).exists():
            return DeployResult(False, None, ["release not found"])
        (self._root(project_id) / "CURRENT").write_text(deploy_id)
        return DeployResult(True, f"/sites/{project_id}/", [f"Rolled back to release {deploy_id[:8]}"])

    def health(self, project_id) -> bool:
        cur = self.current_dir(project_id)
        return bool(cur and (cur / "index.html").exists() and b"<html" in (cur / "index.html").read_bytes()[:500].lower())

    def current_dir(self, project_id: str) -> Path | None:
        ptr = self._root(project_id) / "CURRENT"
        if not ptr.exists():
            return None
        return self._root(project_id) / "releases" / ptr.read_text().strip()


class NetlifyAdapter(DeploymentAdapter):
    name = "netlify"

    def configured(self) -> bool:
        return bool(os.getenv("NETLIFY_AUTH_TOKEN") and os.getenv("NETLIFY_SITE_ID"))

    def deploy(self, project_id, deploy_id, site_dir):
        if not self.configured():
            return DeployResult(False, None, ["Netlify not configured (NETLIFY_AUTH_TOKEN, NETLIFY_SITE_ID)"])
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for f in site_dir.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(site_dir))
        r = requests.post(f"https://api.netlify.com/api/v1/sites/{os.environ['NETLIFY_SITE_ID']}/deploys",
                          headers={"Authorization": f"Bearer {os.environ['NETLIFY_AUTH_TOKEN']}", "Content-Type": "application/zip"},
                          data=buf.getvalue(), timeout=120)
        if r.status_code >= 300:
            return DeployResult(False, None, [f"Netlify HTTP {r.status_code}: {r.text[:200]}"])
        d = r.json()
        return DeployResult(True, d.get("ssl_url") or d.get("url"), [f"Netlify deploy {d.get('id')} state={d.get('state')}"])

    def rollback(self, project_id, deploy_id):
        return DeployResult(False, None, ["Use Netlify's 'Publish deploy' on a previous deploy"])


ADAPTERS: dict[str, DeploymentAdapter] = {"local": LocalStaticAdapter(), "netlify": NetlifyAdapter()}


def available() -> list[dict]:
    return [{"name": k, "configured": a.configured()} for k, a in ADAPTERS.items()] + [
        {"name": n, "configured": False, "note": "adapter interface ready; not implemented in this build"}
        for n in ("vercel", "aws", "azure", "gcp", "render", "railway")]
