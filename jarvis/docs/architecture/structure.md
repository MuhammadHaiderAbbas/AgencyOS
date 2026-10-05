# JARVIS — Repository Structure

```
jarvis/
├── apps/
│   ├── gateway/            # FastAPI gateway: api, db, events, middleware
│   │   ├── app.py          # create_app() factory
│   │   ├── main.py         # CLI entry
│   │   ├── config.py       # (re-export packages/config)
│   │   ├── db.py           # SQLAlchemy models + init
│   │   ├── events.py       # EventBus
│   │   └── api/v1/         # versioned routers
│   │       ├── auth.py
│   │       ├── chat.py
│   │       ├── tools.py
│   │       ├── memory.py
│   │       ├── tasks.py
│   │       ├── system.py
│   │       ├── agents.py
│   │       ├── notifications.py
│   │       ├── devices.py
│   │       └── ws.py       # SSE + WebSocket
│   ├── web/                # React + TS + Vite + Tailwind
│   ├── desktop/            # Electron/Tauri shell (Phase 12)
│   └── mobile/             # RN companion (Phase 12)
├── services/
│   ├── core/               # Core runtime
│   │   ├── input_manager.py
│   │   ├── context_engine.py
│   │   ├── intent_engine.py
│   │   ├── planner.py
│   │   ├── orchestrator.py
│   │   └── permission_engine.py
│   ├── agent/              # registry + builtin defs
│   ├── memory/             # PG+pgvector + controls
│   ├── voice/              # VAD/STT/TTS (stub)
│   ├── vision/             # OCR/screen (stub)
│   ├── automation/         # workflows
│   ├── notifications/      # center
│   └── scheduler/          # cron/interval
├── packages/
│   ├── schemas/            # Event/Intent/Plan types
│   ├── tools/              # registry + builtin handlers
│   ├── security/           # JWT, hashing, secrets
│   ├── logging/            # JSON logger
│   ├── config/             # centralized settings
│   └── common/             # shared types
├── infrastructure/
│   ├── docker/             # Dockerfiles
│   ├── database/           # schema.md + migrations
│   ├── redis/              # redis config
│   └── deployment/         # deploy manifests
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── agent/
│   └── end_to_end/
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── security/
│   ├── deployment/
│   └── development/
├── scripts/
│   └── dev-start.sh
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Conventions

- **Python imports:** `PYTHONPATH` includes `jarvis/`; use absolute imports `from packages.config.config import settings`.
- **Phase isolation:** each `services/*` has its own README and stub adapter when not yet implemented; interfaces defined upfront.
- **Tests:** `pytest` discovers `tests/`; `apps/web` tested via `npm run build` + Playwright (Phase 13).
- **Frontend dist:** `apps/web/dist` is git-ignored in dev, copied into Docker image.
