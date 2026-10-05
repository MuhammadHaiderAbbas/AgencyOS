# JARVIS — Development Roadmap

## Overview
15 phases, each independently testable. No phase proceeds with failing tests.

| Phase | Goal | Key Deliverables | Estimated Scope |
|---|---|---|---|
| **0 — Architecture** | Docs + structure | All models, schema, spec, TDR, roadmap, repo skeleton | This document set |
| **1 — Core Runtime** | HTTP + Event + Auth + Permission + Tool stubs | Gateway, health, config, logging, bus, auth, permission engine, tool registry stub, memory stub | ✅ Next (current build achieves this) |
| 2 — AI Reasoning | Provider abstraction | LLMProvider, ModelRouter, streaming, fallback, intent via LLM |  |
| 3 — Tool System | Plugin architecture | Registry, 20+ tools, validation, audit, categories |  |
| 4 — Memory | Persistent intelligence | PG+pgvector, working/episodic/semantic, search, controls |  |
| 5 — Text Interface | First usable Jarvis | Chat, dashboard, approvals, command history |  |
| 6 — Voice | Speak/listen | VAD, STT, TTS, wake-word, interruption, indicators |  |
| 7 — Computer Control | OS integration | App launch, window mgmt, screenshot, browser, sandboxed shell |  |
| 8 — Vision | See screen/camera | OCR, UI detection, VQA, gestures, face (opt) |  |
| 9 — Automation | Workflows | Scheduler, triggers, conditions, approvals, visual builder |  |
| 10 — Dashboard | Polish | Dark glass UI, holographic mode, avatar states |  |
| 11 — Security | Harden | Audit, pen tests, injection, sandbox, secret protection |  |
| 12 — Multi-device | Ecosystem | Device registry, mobile app, sync |  |
| 13 — Testing | Coverage | Unit/integration/security/agent/E2E/load |  |
| 14 — Deployment | Prod readiness | CI/CD, HTTPS, backups, restore, updates |  |
| 15 — Advanced | Extras | Smart home (Matter/MQTT), research/dev agents, marketplace |  |

### Phase 1 Exit Gate (Definition of Minimal Usable)
- `POST /api/v1/auth/signup`, `/login`, `/me` works; JWT + cookie
- `GET /api/v1/health` returns DB + Redis + LLM status
- `POST /api/v1/chat` → Intent → Plan → Permission check → Tool audit → response (even if tools stubbed)
- `GET /api/v1/tools` lists registry, `POST /api/v1/tools/execute` respects permission levels
- `GET /api/v1/memory` CRUD + search stub
- WebSocket `/api/v1/ws` and SSE `/api/v1/stream` functional
- Permission Engine unit tests for L0-L4
- EventBus publishes `TOOL_STARTED/COMPLETED`, `APPROVAL_REQUIRED`
- Logs are JSON structured, audit_logs table populated
- `docker compose up` starts, `scripts/dev-start.sh` runs

### Detailed Milestones

**Weeks 1-2:** Phases 0-1 (this release).  
**Weeks 3-4:** Phases 2-4 (brain + memory).  
**Weeks 5-6:** Phases 5-6 (chat/voice).  
**Weeks 7-8:** Phases 7-8 (control/vision).  
**Weeks 9-10:** Phases 9-10 (automation/UI).  
**Weeks 11-12:** Phases 11-15 (hardening/deployment).

### Branching
`main` ← `arena/ab316116-agencyos` as integration branch for this environment. Future work uses feature branches `jarvis/phase-*`.

### Risks & Mitigations
- **STT/TTS cost:** default to local Whisper/Piper, cloud opt-in.
- **Tool permission bypass:** every execute path goes through PermissionEngine; tests fuzz bypass.
- **Prompt injection:** retrieved content tagged `unverified_data`, never as instructions; injection test suite.
- **Scope creep:** gate each phase with tests; refuse “build everything at once”.
