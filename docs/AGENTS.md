# Agents

## Contract
Every agent is an `AgentDefinition` (agents/contracts.py): id, name, role, capabilities, framework, source, execution_mode, entrypoint, input/output schema, tools, **permissions**, dependencies, required credentials, risk level, version, license, source URL, commit hash and a **contract** (inputs, task, constraints, tools, expected output, quality criteria, do-not list).

Agents return `AgentResult` (status, summary, artifacts, structured_output, logs, errors, recommendations, tools, confidence).

## Built-in team (17)
Project Manager, Business Analyst, Researcher, UX Designer, UI Designer, Solution Architect, Content Writer, SEO Specialist, Database Engineer, Backend Developer, Frontend Developer, QA Engineer, Accessibility Specialist, Performance Engineer, Security Engineer, Technical Writer, DevOps Engineer. Plus the Requirements Agent, Review Agent and Change Analyst inside the orchestration layer.

Handoffs are machine-readable: `sitemap.json` + `wireframes.json` → `design-system.json` → `content.json` + `seo-plan.json` → site; `architecture.json` + `database-schema.sql` → API + `api-spec.yaml`.

## Permissions (least privilege)
`ROLE_PERMISSIONS` in contracts.py. For example, the Content Writer gets `READ_PROJECT, WRITE_ARTIFACT` and the Frontend Developer adds `WRITE_CODE, RUN_TESTS`. Only DevOps holds `DEPLOY`. Custom prompt agents can never receive DEPLOY/EXECUTE/EMAIL/GITHUB.

## 500-AI-Agents-Projects importer
Inspected repository facts (commit recorded at import):
- `agents/01…21-*` are runnable CLI agents. Each has `metadata.yaml`, `requirements.txt` and `agent.py` (argparse). Frameworks: LangGraph, LangChain, CrewAI, LlamaIndex, other. Most need `OPENAI_API_KEY`; some need `TAVILY_API_KEY`, `NEWS_API_KEY` or `GITHUB_TOKEN`.
- The README tables list ~112 more use cases that link to **other** repositories (crewAI-examples, AutoGen notebooks, LangGraph tutorials…). These are catalogue entries, never executed, with licence "verify upstream".
- Repository licence: MIT.

`import_catalogue()` clones or pulls the repo, then for each agent records the framework, entrypoint, CLI flags (as input schema), dependencies, env vars, risky calls (subprocess, network, file writes, eval) and licence. It upserts the agent **disabled** with health `WARNING` pending admin review. The repository is re-scanned on every sync. Changed agents keep their enabled/disabled state, and changed code still requires admin re-enablement through the health check.

Running an imported agent: admin enables it, `AGENCYOS_ENABLE_EXTERNAL_AGENTS=true`, Docker is available, an image `agencyos-agent-<id>` is pre-built from the agent's requirements, and credentials are injected only for the variables the agent declares.

## Adding agents (no platform rewrite)
- **Prompt agent**: Agents → Custom agent (UI) → Test → Enable. Give it a `role` to make it routable.
- **New built-in role**: add a runner to `BUILTIN_RUNNERS`, a spec to `BUILTIN_SPECS`, a row to `planner.TEMPLATE` and a team rule.
- **New runtime** (MCP, remote HTTP agent, Unity, Blender): subclass `AgentAdapter`, register it in `ADAPTERS`, and set `execution_mode`.
