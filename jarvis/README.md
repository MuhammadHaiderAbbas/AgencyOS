# JARVIS — Just Another Rather Very Intelligent System

> An AI operating layer, not a chatbot. Local-first, modular, secure, observable.

**This is a clean, independent build** — no dependency on AgencyOS or any previous project. See `docs/architecture/README.md` for the full spec.

## Architecture at a Glance

```
User (voice/text/vision) → Input Manager → Context Engine → Intent Engine
  → Planner → Agent Orchestrator → Permission Engine → Tools → Verification → Response
```

- **Backend:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, PostgreSQL+pgvector, Redis
- **Frontend:** React + TypeScript + Vite + Tailwind (dark glass UI)
- **AI:** Provider abstraction (OpenAI/Anthropic/Google/Ollama/llama.cpp), Model Router, fallback
- **Security:** 5-level permissions (L0 SAFE → L4 CRITICAL always confirm), RBAC, audit, sandboxed tools

## Repository Structure (spec-compliant)

```
jarvis/
├── apps/
│   ├── gateway/        # FastAPI gateway (API + WS/SSE + static)
│   ├── web/            # React dashboard
│   ├── desktop/        # Electron/Tauri shell (phase 12)
│   └── mobile/         # RN companion (phase 12)
├── services/
│   ├── core/           # Intent, Planner, Orchestrator, Permission, Context, Input
│   ├── agent/          # Specialized agents
│   ├── memory/         # Working/episodic/semantic + vector
│   ├── voice/          # VAD/STT/TTS/wake-word
│   ├── vision/         # OCR/screen/camera
│   ├── automation/     # Workflows
│   ├── notifications/  # Notification center
│   └── scheduler/      # Cron/interval/event triggers
├── packages/
│   ├── schemas/        # Event/Intent/Plan/ToolDef types
│   ├── tools/          # Plugin tool registry
│   ├── security/       # Secrets, RBAC, headers
│   ├── logging/        # Structured JSON + OTEL
│   ├── config/         # Centralized config
│   └── common/         # Shared utilities
├── infrastructure/
│   ├── docker/         # Dockerfiles & compose
│   ├── database/       # Schema & migrations
│   ├── redis/          # Redis config
│   └── deployment/     # Deploy manifests
├── tests/
└── docs/
```

## Quick Start (Development)

```bash
# 1. Clone and enter
cd jarvis

# 2. One-command start (backend + frontend)
./scripts/dev-start.sh
# or: docker compose up --build

# 3. Manual
pip install -r requirements.txt
cd apps/web && npm install && npm run build && cd ../..
python -m apps.gateway.main --port 8000
# open http://localhost:8000
```

First account you create becomes `admin`.

## Environment

Copy `.env.example` → `.env` and set `JARVIS_SECRET_KEY` (auto-generated in `data/` if unset) and any LLM/API keys.

- `JARVIS_DATABASE_URL` — `sqlite:///./data/jarvis.sqlite3` (dev) or `postgresql+psycopg://...` (prod)
- `JARVIS_REDIS_URL` — optional; falls back to in-process bus if unavailable
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` — if unset, deterministic local mode
- `TAVILY_API_KEY` — for web research (optional)

## API

Versioned under `/api/v1`: `/auth`, `/chat`, `/agents`, `/tools`, `/memory`, `/tasks`, `/system`, `/notifications`, `/devices`, `/health`. See `docs/api/spec.md` and Swagger at `http://localhost:8000/docs`.

## Development Procedure (per spec)

After each phase: **Run tests → Start system → Verify health → Inspect logs → Fix → Document → Continue.** No untested batch.

## Status — Phase 1 (Core Runtime) ✅

- [x] Architecture docs (12 artifacts)
- [x] Repository structure
- [x] Gateway: FastAPI, auth (JWT+cookie), health, middleware, versioned API
- [x] Packages: config, logging (JSON), security, schemas, event bus
- [x] Services: InputManager, ContextEngine, IntentEngine (rule-based + LLM stub), Planner, PermissionEngine (L0-L4), ToolRegistry, Memory stub
- [x] Agent registry (11 agents), Orchestrator with limits
- [x] Tools: 15 built-in (`system.*`, `computer.*`, `files.*`, `calendar.*`, `tasks.*`, `search.*`)
- [x] Audit logging, RBAC, CSRF, rate limit
- [x] Frontend: dashboard shell (glass UI), chat, approvals, system status, notifications
- [x] Docker + scripts + tests

See `docs/development/roadmap.md` for next phases.

## Honest Limits of This Phase

- Tools execute against host sandbox (safe roots) — real computer control needs OS adapters (Phase 7)
- Voice/vision/automation are interfaces with placeholder adapters — documented where
- Vector memory uses brute cosine on SQLite; pgvector in prod
- No brain magic: if LLM unreachable, deterministic intent + local mode still answers

## License

MIT — see LICENSE.
