# JARVIS — Architecture Document

**Version:** 0.1.0  **Status:** Phase 0 — Foundation  **Date:** 2026-10-05

## 1. Vision Summary

JARVIS is an **AI operating layer**, not a chatbot. It sits between the user (voice/text/vision/gesture) and the operating system, tools, devices, and cloud services. The fundamental loop:

```
PERCEIVE → UNDERSTAND → REMEMBER → PLAN → ASK PERMISSION IF REQUIRED → ACT → VERIFY → REPORT → LEARN
```

Principles: security, privacy, reliability, modularity, extensibility, local-first, human approval for sensitive actions, observability, excellent UX, agent orchestration, voice, multimodal, automation, long-term memory, cross-platform.

## 2. High-Level Architecture

```
                ┌─────────────────────┐
                │       USER          │
                └──────────┬──────────┘
                           │
              Voice / Text / Vision / Gesture / System Events
                           │
                           ▼
                ┌─────────────────────┐
                │   INPUT MANAGER     │  Normalizes every input into canonical Event
                └──────────┬──────────┘
                           ▼
                ┌─────────────────────┐
                │   CONTEXT ENGINE    │◄─── Memory (working / episodic / semantic)
                └──────────┬──────────┘     + Environmental (time, device, system)
                           ▼
                ┌─────────────────────┐
                │   INTENT ENGINE     │  Natural language → structured Intent
                └──────────┬──────────┘  (goal, slots, tools, risk, ambiguity)
                           ▼
                ┌─────────────────────┐
                │      PLANNER        │  Goal → ExecutionPlan {steps, risk, approvals}
                └──────────┬──────────┘
                           ▼
                ┌─────────────────────┐
                │ AGENT ORCHESTRATOR  │  Dispatches to specialized agents w/ scoped tools
                └──────────┬──────────┘
                           ▼
                ┌─────────────────────┐
                │ PERMISSION ENGINE   │  0 SAFE → 4 CRITICAL (always confirm L4)
                └──────────┬──────────┘
                   ┌───────┴────────┐
                   │                │
              Safe action      Confirmation required
                   │                ▼
               ┌───────┐       ┌──────────┐
               │ TOOLS │◄──────│  USER    │
               └───┬───┘       │ APPROVAL │
                   │           └────┬─────┘
                   └───────┬────────┘
                           ▼
                      EXECUTION
                           │
                           ▼
                      VERIFICATION → RESULT → AUDIT LOG → EVENT BUS → UI/SPEECH
```

## 3. Service Topology

| Layer | Service | Tech | Responsibility |
|---|---|---|---|
| Interaction | `apps/web` | React+TS+Vite+Tailwind | Chat, dashboard, approval UX, system indicators |
| Interaction | `apps/desktop` | Electron/Tauri (phase 12) | Native OS control, systray, global hotkeys |
| Interaction | `apps/mobile` | RN/Flutter | Remote chat/voice/approvals |
| Gateway | `apps/gateway` | FastAPI + WS + SSE | API, auth, event fan-out, static serving |
| Core | `services/core` | Python | InputMgr, Context, Intent, Planner, Orchestrator, Permission, ToolRouter |
| Memory | `services/memory` | PG+pgvector + Redis | Working/episodic/semantic + embeddings + controls |
| Agent | `services/agent` | Python | Agent definitions, routing, execution, visualization |
| Voice | `services/voice` | Python | VAD → STT → Intent → TTS → speaker, wake-word, interruption |
| Vision | `services/vision` | Python | Screenshot, OCR, UI detection, camera, gestures |
| Automation | `services/automation` + `services/scheduler` | Python+Redis+Celery/APScheduler | Triggers, workflows, visual builder |
| Notifications | `services/notifications` | Python | Center: info/warning/approval/security/system |
| System | Tool adapters | Python | `computer.*`, `browser.*`, `files.*`, `system.*` etc. |

Each service is independently testable and communicates via:
- **HTTP** (versioned REST `/api/v1/*`)
- **Event Bus** (in-proc PubSub → Redis PubSub in prod)
- **WebSockets/SSE** (streaming, tool progress, notifications)

## 4. Data Flow Example — "Prepare my morning briefing"

1. Input Manager receives `voice` event: `{event_id, source:voice, content:"Prepare my morning briefing", user_id}`
2. Context Engine loads: recent conversation, preferences, calendar/tasks/reminder count, system health.
3. Intent Engine → `intent: briefing, risk: low, requires_confirmation:false`
4. Planner → plan with 9 steps (time, calendar, tasks, reminders, notifications, system, news, summarize, present)
5. Orchestrator → assigns `GeneralAssistant` + `SchedulingAgent` + `SystemAgent` + `ResearchAgent`
6. Permission Engine → all steps L0/L1 → no confirmation
7. Tool Router executes `calendar.get_today`, `tasks.list`, `system.status`, `notifications.list`, `search.news` (stubbed), then LLM summarize
8. Verification: check each tool succeeded, latch failures with graceful degradation message
9. Report: stream response "Good morning. You have 3 meetings..." + dashboard update, audit log write, event `BRIEFING_COMPLETED`

## 5. Modularity Rules

- No giant application. Every capability is a **Tool** with schema `{name, description, params, risk, permissions}`.
- Agents receive only the tools they need (least privilege).
- Adding a new tool/agent = new file + registry entry, no core modification.
- Fallback chain: primary LLM → secondary → local → deterministic command router (for STOP/LOCK/etc).

## 6. Deployment Topology

```
Developer: docker compose up  (backend, frontend, postgres, redis, worker, scheduler)
Production: Docker Swarm / K8s, HTTPS via Caddy/Traefik, Postgres managed, Redis managed
Offline: local LLM via Ollama, local STT/VAD, file/computer control works, cloud features show "Internet required"
```

## 7. Phases & Gates

| Phase | Name | Exit Criteria |
|---|---|---|
| 0 | Architecture | This doc + TDR + DB schema + API spec + security/agent/tool/permission/event/memory models + roadmap |
| 1 | Core Runtime | FastAPI gateway, auth, config, logging, event bus, health, Intent/Planner/Permission/Tool stubs, tests |
| 2 | AI Reasoning | Provider abstraction, model router, streaming, fallback |
| 3 | Tool System | Plugin registry, 20+ tools, audit |
| 4 | Memory | PG+pgvector, working/episodic/semantic, controls |
| 5 | Text Interface | Chat + dashboard + approvals |
| 6 | Voice | Wake-word, VAD, STT/TTS, interruption |
| 7 | Computer Control | App launch, screenshot, keyboard/mouse, browser |
| 8 | Vision | OCR, screen QA, camera, gestures |
| 9 | Automation | Scheduler, workflows, visual builder |
| 10 | Dashboard | Polished dark glass UI, holographic mode |
| 11 | Security | Hardening, pen tests, injection suite |
| 12 | Multi-device | Device identities, sync, mobile |
| 13-15 | Testing/Deploy/Advanced | E2E, benchmarks, docs, one-command install |

## 8. Non-Functional Requirements

- **Latency:** intent <200ms, tool dispatch <50ms, streaming first token <500ms.
- **Reliability:** circuit breakers, retries, graceful degradation, never crash on single tool failure.
- **Observability:** structured JSON logs, OpenTelemetry traces, metrics (latency, error rate, tokens, cost).
- **Privacy:** local-first where possible, explicit consent for memory/camera/mic, mic/camera indicators.
- **Security:** RBAC, least privilege, encrypted secrets, no shell without sandbox, audit everything.

## 9. Future Extension Points

- Plugin marketplace, integrations page, MCP adapter, Blender/Unreal adapters, Home Assistant/Matter.

## 10. Diagram — Module Dependencies

```
apps/gateway  depends on  services/core, packages/security, packages/logging, packages/config
services/core depends on  packages/schemas, packages/tools, services/memory, services/agent
services/agent depends on packages/tools, services/memory, LLM router
packages/* depend on nothing (pure)
```

No circular dependencies. `packages/common` holds shared types (Event, Intent, Plan, ToolDef, PermissionLevel).
