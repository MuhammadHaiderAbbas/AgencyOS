# Architecture

```
frontend/ (React + TS, esbuild)  ──HTTP/JSON + SSE──▶  backend/agencyos/api (Starlette)
                                                            │
             ┌──────────────────────────────────────────────┼─────────────────────────────┐
             ▼                                              ▼                             ▼
 orchestration/project_service.py              orchestration/engine.py            events.py (EventBus)
  Requirements Agent (interview.py)             Orchestrator: queue + workers      persisted + fanned out
  PM planning (planner.py, teams.py)            run_task → adapter → review        to SSE / WebSockets
  chat commands, change requests (changes.py)   QA loop, gates, deploy, guards
             │                                              │
             ▼                                              ▼
 agents/registry.py  ◀── agents/importer.py (500-AI-Agents-Projects)   agents/adapters.py
   AgentDefinition + contract + metrics              BuiltinAdapter · PromptAgentAdapter · ExternalRepoAdapter(Docker)
             │                                              │
             ▼                                              ▼
 llm/router.py (LLMClient, model tiers)        services/: artifacts (versioned) · workspace (git) · sitegen ·
   AnthropicProvider · OpenAIProvider · Mock     backendgen · blueprints · design · qa · sandbox · deploy · websearch
             │
             ▼
          db.py (SQLite, portable SQL)  ·  data/workspaces/<project>/ (git)  ·  data/deployments/<project>/releases/
```

## Separation of concerns (§137)
| Concern | Module | Adding something new |
|---|---|---|
| Agent capability | `AgentDefinition` in the registry | insert a definition (importer, admin UI, or `BUILTIN_SPECS`) |
| Agent execution | `agents/adapters.py` | new `AgentAdapter` subclass for a new runtime (MCP, remote API, Unity, Blender…) |
| Orchestration | `orchestration/engine.py` | unchanged when agents are added |
| Project management | `planner.py` (`TEMPLATE`), `teams.py` | add a task row / role rule |
| Project state | `db.py` tables + `events.py` | — |
| UI | `frontend/src` | reads only the API |

## Request flow
HTTP handlers never run agents. They write state and call `orchestrator.enqueue(project_id)`. Worker threads advance the DAG until a gate, completion, or block. Every state change publishes an event. Events are stored (activity feed, audit) and pushed to subscribers (`/api/stream/*` SSE, `/ws/*`).

## Context engine (§95)
`Orchestrator.build_context` gives each agent only the artifacts listed in its task's `inputs` (plus the shared design inputs), the relevant project memory and its own review feedback. The structured DB is authoritative. A vector index can be added behind `build_context` without changing agents.

## Swapping infrastructure
- **PostgreSQL**: `db.Database` is the only SQL execution point. Switch placeholders (`?`→`%s`), `AUTOINCREMENT`→`GENERATED ALWAYS AS IDENTITY`, and `INSERT … ON CONFLICT` is already portable.
- **Redis/Celery**: replace `Orchestrator.enqueue/_loop` with a Celery task calling `orchestrator.advance(project_id)`. The engine is already idempotent per project.
- **Object storage**: `services/workspace.py` and `services/deploy.py` own file I/O.
