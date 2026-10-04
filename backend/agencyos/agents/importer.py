"""AgentCatalogueImporter — indexes the 500-AI-Agents-Projects repository.

Findings from inspecting the repository (commit recorded per import):
  * agents/NN-name/ — runnable agents, each with metadata.yaml, requirements.txt and a CLI
    agent.py (argparse). Frameworks: langgraph, langchain, crewai, llamaindex, other.
  * README.md tables — ~130 use cases that link to *external* repositories (crewAI examples,
    AutoGen notebooks, LangGraph tutorials…). These are catalogue-only: AgencyOS records them
    but never executes them, and their licences must be verified individually.

Imported executable agents are DISABLED by default and marked WARNING until an admin reviews
the security scan and enables them. They only ever run through ExternalRepoAdapter (Docker).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from ..config import settings
from ..db import db, now
from .contracts import AgentContractSpec, AgentDefinition, Permission
from .registry import upsert

TAG_ROLE = {
    "code-review": "reviewer", "web-search": "researcher", "research": "researcher", "documentation": "technical_writer",
    "testing": "qa_engineer", "unit-tests": "qa_engineer", "competitive-analysis": "researcher", "marketing": "content_writer",
    "social-media": "content_writer", "email": "content_writer", "pii": "security_engineer", "privacy": "security_engineer",
    "sql": "database_engineer", "data-analysis": "data_analyst",
}

RISKY = [(r"\bsubprocess\b|os\.system", "spawns processes"), (r"\brequests\.|httpx|urllib", "network access"),
         (r"open\([^)]*['\"]w", "writes files"), (r"\beval\(|\bexec\(", "dynamic code execution")]

FRAMEWORK_ENV = {"OPENAI": "OPENAI_API_KEY", "TAVILY": "TAVILY_API_KEY", "ANTHROPIC": "ANTHROPIC_API_KEY",
                 "NEWS_API": "NEWS_API_KEY", "GITHUB_TOKEN": "GITHUB_TOKEN", "SERPER": "SERPER_API_KEY"}


def ensure_repo() -> tuple[Path | None, str]:
    s = settings()
    if s.agent_repo_path and s.agent_repo_path.exists():
        return s.agent_repo_path, "local path"
    target = s.data_dir / "agent-sources" / "500-AI-Agents-Projects"
    if (target / ".git").exists():
        r = subprocess.run(["git", "-C", str(target), "pull", "--ff-only", "-q"], capture_output=True, text=True, timeout=120)
        return target, "pulled" if r.returncode == 0 else "cached (pull failed)"
    target.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "clone", "--depth", "1", "-q", s.agent_repo_url, str(target)], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return None, f"clone failed: {r.stderr.strip()[:200]}"
    return target, "cloned"


def _commit(repo: Path) -> str | None:
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or None


def _license(repo: Path) -> str:
    lic = repo / "LICENSE"
    if lic.exists():
        head = lic.read_text(errors="ignore")[:200]
        if "MIT" in head:
            return "MIT"
        return head.splitlines()[0][:60]
    return "unknown"


def scan_agent(d: Path, repo: Path, commit: str | None, lic: str) -> tuple[AgentDefinition, dict]:
    meta = yaml.safe_load((d / "metadata.yaml").read_text()) or {}
    entry = d / (meta.get("entrypoint") or "agent.py")
    code = entry.read_text(errors="ignore") if entry.exists() else ""
    reqs = [l.strip() for l in (d / (meta.get("requirements") or "requirements.txt")).read_text().splitlines()
            if l.strip() and not l.startswith("#")] if (d / (meta.get("requirements") or "requirements.txt")).exists() else []
    env = sorted(set(re.findall(r"os\.(?:getenv|environ(?:\.get)?)\(\s*[\"']([A-Z_]+)", code) +
                     re.findall(r"os\.environ\[\s*[\"']([A-Z_]+)", code)))
    readme = (d / "README.md").read_text(errors="ignore") if (d / "README.md").exists() else ""
    for k, v in FRAMEWORK_ENV.items():
        if (k in code or k in readme or (k == "OPENAI" and "langchain_openai" in code)) and v not in env:
            env.append(v)
    args = re.findall(r"add_argument\(\s*[\"'](--[\w-]+)[\"'](?:[^)]*?help=[\"']([^\"']*))?", code)
    risks = [label for pat, label in RISKY if re.search(pat, code)]
    tags = meta.get("tags") or []
    role = next((TAG_ROLE[t] for t in tags if t in TAG_ROLE), None)
    name = meta.get("title") or d.name
    perms = [Permission.READ_PROJECT, Permission.WRITE_ARTIFACT]
    if "network access" in risks or env:
        perms.append(Permission.ACCESS_WEB)
    defn = AgentDefinition(
        id=f"github.500agents.{name}", name=name.replace("-", " ").title(), role=role,
        description=meta.get("description", ""), capabilities=[t.replace("-", "_") for t in tags],
        industry=meta.get("industry"), category=meta.get("industry"), framework=str(meta.get("framework", "unknown")),
        source="github", execution_mode="sandbox", entrypoint=str(entry),
        input_schema={"cli_args": [{"flag": a, "help": h} for a, h in args], "primary_arg": args[0][0] if args else "--query"},
        output_schema={"stdout": "markdown/text report"}, tools=[t for t in tags if t in ("web-search", "rag", "sql")],
        permissions=perms, dependencies=reqs, environment_requirements=env, required_credentials=env,
        risk_level="high" if "dynamic code execution" in risks or "spawns processes" in risks else "medium",
        version=str(meta.get("version", "0.0.0")), license=lic, commit_hash=commit,
        source_url=f"{settings().agent_repo_url}/tree/main/agents/{d.name}",
        contract=AgentContractSpec(inputs=[a for a, _ in args], task=meta.get("description", ""),
                                   constraints=["Runs only in Docker sandbox", "Credentials injected explicitly"],
                                   expected_output=["stdout report"], do_not=["Access host filesystem", "Read other projects"]),
    )
    return defn, {"risks": risks, "llm": meta.get("llm"), "difficulty": meta.get("difficulty")}


_ROW = re.compile(r"^\|\s*(?P<name>[^|]+?)\s*\|\s*(?P<cat>[^|]+?)\s*\|\s*(?P<desc>[^|]+?)\s*\|\s*(?P<link>[^|]*\]\((?P<url>https?://[^)]+)\)[^|]*)\|")


def scan_catalogue(readme: Path) -> list[dict]:
    rows, section = [], None
    for line in readme.read_text(errors="ignore").splitlines():
        if line.startswith("### ") or line.startswith("## "):
            section = re.sub(r"[^\w\s&-]", "", line.lstrip("# ")).strip()
        m = _ROW.match(line)
        if not m:
            continue
        name = re.sub(r"^[^\w]+", "", m.group("name")).strip()
        if not name or name.lower().startswith(("i want", "framework", "use case")):
            continue
        rows.append({"name": name, "category": m.group("cat").strip(), "description": m.group("desc").strip(),
                     "url": m.group("url"), "section": section})
    return rows


def import_catalogue() -> dict:
    repo, how = ensure_repo()
    if not repo:
        return {"ok": False, "error": how}
    commit, lic = _commit(repo), _license(repo)
    runnable, catalogue = [], 0
    for d in sorted((repo / "agents").glob("*/")):
        if not (d / "metadata.yaml").exists():
            continue
        try:
            defn, info = scan_agent(d, repo, commit, lic)
        except (yaml.YAMLError, OSError) as e:
            runnable.append({"dir": d.name, "error": str(e)})
            continue
        upsert(defn, enabled=False, executable=True, health="WARNING",
               detail="Imported: disabled pending admin security review. Risks: " + (", ".join(info["risks"]) or "none detected"))
        runnable.append({"id": defn.id, "framework": defn.framework, "risks": info["risks"], "credentials": defn.required_credentials})
    for r in scan_catalogue(repo / "README.md"):
        aid = "catalogue." + re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-")
        fw = (r["section"] or "").split()[0] if r["section"] else "unknown"
        defn = AgentDefinition(id=aid, name=r["name"], description=r["description"], category=r["category"],
                               industry=r["category"], framework=fw.lower() if fw.lower() in ("crewai", "autogen", "agno", "langgraph") else "external",
                               source="catalogue", execution_mode="catalogue_only", source_url=r["url"],
                               license="Unknown — verify upstream licence before use", capabilities=[r["category"].lower().replace(" ", "_")],
                               commit_hash=commit)
        upsert(defn, enabled=False, executable=False, health="DISABLED", detail="Catalogue entry linking to an external repository; not executable")
        catalogue += 1
    db().insert("audit_logs", {"action": "agent_catalogue_import", "target": str(repo), "detail": f"{len(runnable)} runnable, {catalogue} catalogue",
                               "created_at": now()})
    return {"ok": True, "source": how, "commit": commit, "license": lic, "runnable": runnable, "catalogue_entries": catalogue}
