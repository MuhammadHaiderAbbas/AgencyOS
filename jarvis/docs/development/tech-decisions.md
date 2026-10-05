# JARVIS — Technology Decision Record (TDR)

## Decision 1 — Backend: Python 3.12 + FastAPI

**Options:** Node/NestJS, Go, Python/FastAPI, Rust/Axum  
**Chosen:** Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0  
**Rationale:** Best ecosystem for AI (LLM SDKs, embeddings, pgvector, voice), async native, OpenAPI auto-gen, type hints, easy plugin authoring. FastAPI is mature, SSE/WS friendly.  
**Consequences:** Need to enforce strict typing/linting (mypy, ruff). GIL not a concern for IO-bound orchestration.

## Decision 2 — Frontend: React + TypeScript + Vite + Tailwind

**Options:** Next.js, Svelte, React+Vite  
**Chosen:** React+Vite+TS+Tailwind (+ Electron/Tauri for desktop)  
**Rationale:** Fast HMR, minimal config, Tailwind for glass/dark UI, React ecosystem for WebSockets, WebRTC. Vite builds to `dist` served by gateway.  
**Consequences:** No SSR needed; SPA with file-based routing.

## Decision 3 — Database: PostgreSQL + pgvector, SQLite for dev

**Options:** Postgres, MySQL, SQLite-only, Mongo  
**Chosen:** Postgres 16 + pgvector extension (prod), SQLite/WAL (dev/test with same SQLAlchemy models).  
**Rationale:** Strongest for structured + vector, JSONB, migrations via Alembic. SQLite zero-ops for `docker compose up` and CI.  
**Consequences:** Parameter style abstracted (`?` vs `%s` handled by SQLAlchemy), need Alembic initially.

## Decision 4 — Cache/Queue: Redis + APScheduler (dev) → Celery/RQ (prod)

**Options:** Redis, RabbitMQ, SQS, in-memory  
**Chosen:** Redis 7 for cache, pubsub, job queue. APScheduler for scheduler service; Celery optional for scale-out.  
**Rationale:** Single infra for caching, events, scheduler; familiar. EventBus falls back to in-process if Redis unavailable (offline mode).  
**Consequences:** Need graceful degradation when Redis down.

## Decision 5 — AI Provider Abstraction

**Interface:** `LLMProvider { generate, stream, embed, vision, health_check }`  
**Providers:** OpenAI-compatible, Anthropic-compatible, Google, Ollama, llama.cpp  
**Routing:** ModelRouter classifies tasks (simple/medium/complex/vision/code/speech) and picks cheapest model meeting latency/cost/privacy constraints.  
**Fallback:** primary → secondary → local → deterministic. Never hard-code to one vendor.

## Decision 6 — Vector Search: pgvector first

**Rationale:** Keep vector in PG to avoid extra service (Qdrant/Weaviate) until needed. 1536-dim, HNSW index.  
**Future:** Swap with Qdrant adapter if scale demands.

## Decision 7 — Auth: OAuth2/OIDC-compatible JWT, HttpOnly cookie + Bearer

**Chosen:** JWT (HS256 dev, RS256 prod), Pydantic validation, RBAC, refresh via `HttpOnly Secure SameSite=Lax` cookie, CSRF double-submit.  
**Rationale:** Works for web, desktop (Bearer), mobile (Bearer). Compatible with future OIDC (Auth0, Google).  
**Consequences:** Secrets via `JARVIS_SECRET_KEY` env, session table for revocation.

## Decision 8 — Secrets: env vars (dev) → OS keychain / Vault (prod)

**Rationale:** 12-factor for containers, but must support OS secret store abstraction. `packages/config` loads env + `.env` + Vault adapter.

## Decision 9 — Observability: structured JSON logs + OpenTelemetry

**Stack:** structlog → JSON → stdout, OpenTelemetry SDK + OTLP, Prometheus metrics, health checks `/api/v1/health`.  
**Rationale:** Docker/K8s log aggregation, trace across Intent→Agent→Tool.

## Decision 10 — Containerization: Docker + docker-compose

**Services:** `gateway`, `web` (built), `postgres`, `redis`, `worker`, `scheduler`, `ollama` (optional). Healthchecks on all.  
**CI:** GitHub Actions lint/test/build.

## Decision 11 — Voice Pipeline

**Components:** VAD (webrtcvad/Silero), STT (Whisper local, cloud STT abstraction), TTS (Piper local, cloud TTS), Wake-word (openWakeWord/Mycroft precise).  
**Design:** Always local VAD/wake-word, configurable STT/TTS (local vs cloud). No continuous mic upload without consent. Interruption via VAD + energy detection.

## Decision 12 — Computer Control

**Primary:** OS accessibility APIs (AT-SPI/Linux, UIA/Win, AX macOS) via `pyautogui`/`pynput` fallback, browser CDP (Playwright). Sandbox terminal with allowlist. Prefer structured APIs over raw clicks.

## Decision 13 — Testing Pyramid

**Unit** (pytest, 80%+), **Integration** (API + DB), **Security** (injection suite), **Agent** (mock LLM, fixture intents), **E2E** (Playwright). Benchmark suite 10 scenarios (calendar, blender, search, etc.).

## Decision 14 — I18n

**Library:** `i18next` (frontend), Python `babel` (backend). All UI strings via translation keys, no hard-coded English.
