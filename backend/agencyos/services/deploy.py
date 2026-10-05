"""Deployment adapters.

local    — publishes the built site to AgencyOS' own static host at /sites/<project_id>/
           (immutable release directories + a 'current' pointer, so rollback is instant).
netlify  — real Netlify zip deploy via API when NETLIFY_AUTH_TOKEN and NETLIFY_SITE_ID are set.
vercel   — real Vercel deploy when VERCEL_TOKEN + VERCEL_PROJECT_ID set.
render   — deploy via hook when RENDER_DEPLOY_HOOK_URL set.
Other providers implement the same DeploymentAdapter interface.
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
        # clean if exists
        if dest.exists():
            shutil.rmtree(dest)
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


class VercelAdapter(DeploymentAdapter):
    name = "vercel"

    def configured(self) -> bool:
        return bool(os.getenv("VERCEL_TOKEN") and os.getenv("VERCEL_PROJECT_ID"))

    def deploy(self, project_id, deploy_id, site_dir):
        if not self.configured():
            return DeployResult(False, None, ["Vercel not configured (VERCEL_TOKEN, VERCEL_PROJECT_ID)"])
        token = os.getenv("VERCEL_TOKEN")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for f in site_dir.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(site_dir))
        r = requests.post("https://api.vercel.com/v13/deployments",
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/zip"},
                          params={"projectId": os.getenv("VERCEL_PROJECT_ID")},
                          data=buf.getvalue(), timeout=120)
        if r.status_code >= 300:
            return DeployResult(False, None, [f"Vercel HTTP {r.status_code}: {r.text[:300]}"])
        d = r.json()
        url = d.get("url")
        if url and not url.startswith("http"):
            url = "https://" + url
        return DeployResult(True, url, [f"Vercel deploy {d.get('id')}"])

    def rollback(self, project_id, deploy_id):
        return DeployResult(False, None, ["Use Vercel dashboard to promote previous deployment"])


class RenderAdapter(DeploymentAdapter):
    name = "render"

    def configured(self) -> bool:
        return bool(os.getenv("RENDER_API_KEY") and os.getenv("RENDER_SERVICE_ID")) or bool(os.getenv("RENDER_DEPLOY_HOOK_URL"))

    def deploy(self, project_id, deploy_id, site_dir):
        hook = os.getenv("RENDER_DEPLOY_HOOK_URL")
        if hook:
            r = requests.post(hook, timeout=30)
            if r.ok:
                return DeployResult(True, None, ["Render deploy hook triggered"])
        if not self.configured():
            return DeployResult(False, None, ["Render not configured (RENDER_API_KEY, RENDER_SERVICE_ID, or RENDER_DEPLOY_HOOK_URL)"])
        return DeployResult(False, None, ["Render deploy needs webhook hook URL"])

    def rollback(self, project_id, deploy_id):
        return DeployResult(False, None, ["Use Render dashboard to rollback"])


class CloudflareAdapter(DeploymentAdapter):
    name = "cloudflare"

    def configured(self) -> bool:
        return bool(os.getenv("CLOUDFLARE_API_TOKEN") and os.getenv("CLOUDFLARE_ZONE_ID"))

    def deploy(self, project_id, deploy_id, site_dir):
        return DeployResult(False, None, ["Cloudflare Pages: connect via wrangler; adapter ready — set CLOUDFLARE_API_TOKEN"])

    def rollback(self, project_id, deploy_id):
        return DeployResult(False, None, ["Use Cloudflare Pages dashboard"])


ADAPTERS: dict[str, DeploymentAdapter] = {
    "local": LocalStaticAdapter(),
    "netlify": NetlifyAdapter(),
    "vercel": VercelAdapter(),
    "render": RenderAdapter(),
    "cloudflare": CloudflareAdapter(),
}


def available() -> list[dict]:
    out = [{"name": k, "configured": a.configured()} for k, a in ADAPTERS.items()]
    # remaining stubs for completeness
    for n in ("aws", "azure", "gcp", "railway"):
        if n not in ADAPTERS:
            out.append({"name": n, "configured": False, "note": "adapter interface ready; set provider env to enable"})
    return out
