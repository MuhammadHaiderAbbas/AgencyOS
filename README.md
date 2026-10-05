# AgencyOS

**Turn an idea into a finished product.** A user types *"I want a website for my hotel."* AgencyOS interviews them, writes the spec, builds a specialist team and task graph, and then runs the work end to end: research, UX, UI, architecture, content, SEO, frontend, backend, QA, accessibility, performance, security, docs and deployment. The user approves at each milestone.

```
User idea → Requirements Agent (adaptive interview) → Spec → ✅ client approval
 → Project Manager (team + task DAG) → Orchestrator → specialist agents
 → versioned artifacts + git commits → Review Agent → revision loops
 → ✅ design approval → build → QA / a11y / perf / security → bug-fix loop
 → ✅ acceptance → ✅ deploy authorisation → deploy + health check → done
```

## What's in this build

All of the following runs; none of it is mocked in the UI.

| Area | Status |
|---|---|
| Auth (signup/login, JWT + HttpOnly cookie), organisations, roles, tenant isolation | ✅ |
| Requirements interview: adaptive question bank, contradiction detection, summary, approval | ✅ |
| Dynamic team builder + PM task DAG (cycle check), plan estimate, Start Build | ✅ |
| Orchestrator: worker queue, retries, alternate-agent fallback, escalation, loop/budget guards | ✅ |
| 17 built-in agents with contracts, least-privilege permissions, structured outputs | ✅ |
| Review agent (rule-based, plus model review when an LLM is configured) and revision loop | ✅ |
| Versioned artifact store (diff / restore / approve), mirrored to a per-project git repo | ✅ |
| Real code generation: static site + stdlib Python API, schema and OpenAPI spec | ✅ |
| Real QA: link/page/form checks, `node --check`, backend unit tests in a sandbox, Playwright visual QA and screenshots | ✅ |
| Accessibility, performance and security scanners (secrets, SQLi, XSS sinks, CSP…) | ✅ |
| QA → bug-fix task → developer fix → re-test loop (bounded, then escalates to you) | ✅ |
| Approval gates: requirements, design + architecture, acceptance, deployment, decisions | ✅ |
| Change Request Engine: impact analysis, contradiction prompts, re-plan, memory ("never gold again") | ✅ |
| Deploy to the built-in static host with health check, immutable releases, rollback; Netlify adapter | ✅ |
| LLM providers: Anthropic + OpenAI (switchable), model router (fast/strong/code), usage and cost tracking | ✅ |
| Agent registry + importer for **ashishpatel26/500-AI-Agents-Projects** (21 runnable agents, about 112 catalogue entries) | ✅ |
| Custom prompt agents (admin): create, test, enable | ✅ |
| Realtime UI (Server-Sent Events; WebSocket endpoints too), dashboard, chat, kanban, trace, admin observability | ✅ |
| Export ZIP, clone, archive, delete (confirmed), data export, account deletion | ✅ |
| Billing & earning | **Stripe live + demo mock** — free/pro/business/enterprise, Checkout, customer portal, webhook, referral £5/£15, earnings history; limits enforced 402; mock instant upgrade so **whole site earns demo without keys** |
| GitHub push | ✅ PAT push via `GITHUB_TOKEN` (local git always; `POST /api/projects/{id}/push` when configured) |
| Email notifications | ✅ SMTP (`SMTP_HOST`…) — real booking/enquiry emails when set, mock log + in-app otherwise (never blocks earning) |
| Deploy | ✅ Local immutable + health + rollback (always) + **Netlify, Vercel, Render, Cloudflare** real when tokens set; AWS/Azure/GCP/Railway stubs same interface |
| Client site monetization | ✅ Static site → Stripe Checkout (real with `STRIPE_SECRET_KEY` else mock), cart, newsletter, SEO, Plausible, `source/api/EARNING.md` |

**Without an API key** the platform runs in **local deterministic mode**. Every agent uses its rule-based implementation, so the whole pipeline produces a real, tested website with no LLM. The UI labels these runs "local" and reports $0 AI cost. **With a key**, agents use the model for language work (user stories, copy, extraction, reviews). JSON outputs are schema-validated and retried, with the deterministic implementation as a safe fallback.

## Quick start

```bash
# backend (Python 3.11+)
cd backend
pip install -r requirements.txt
python -m playwright install chromium        # optional: visual QA screenshots

# frontend
cd ../frontend && npm install && npm run build

# run (serves API + UI on :8000)
cd ../backend && python -m agencyos --port 8000
# open http://localhost:8000 — the first account you create becomes platform admin
```

Optional:

```bash
python -m agencyos import-agents      # clone + index the 500-AI-Agents-Projects catalogue
python -m agencyos seed-demo          # runs the full "[DEMO] Grand Vista Hotel" project through the real pipeline
export ANTHROPIC_API_KEY=...          # or OPENAI_API_KEY, or set keys per workspace in Settings
```

Docker: `docker build -t agencyos . && docker run -p 8000:8000 -v agencyos-data:/data agencyos`

## 💰 Earning — entire platform is now monetization-ready

> **Demo earning works with zero keys** — checkout instantly upgrades (mock), client site checkout returns mock URLs — the whole flow is always testable end-to-end. Add Stripe keys to charge real money with no code change.

| How | What | Config |
|-----|------|--------|
| **Platform subscriptions** | Free 3 projects → Pro £29 (20 proj, 10k runs) → Business £99 (100 proj, 50k runs) → Enterprise custom. Limits enforced `402` on `/api/projects`. Billing history + earnings in UI. | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_BUSINESS`, `STRIPE_WEBHOOK_SECRET` + `AGENCYOS_BASE_URL` |
| **Client site bookings/orders** | Every hotel/ecommerce site your agents build includes Stripe Checkout: `POST /api/bookings` → returns `{checkout_url}` (real Stripe when `STRIPE_SECRET_KEY` set in `source/api/.env`, mock otherwise), cart `POST /api/orders/checkout`, nightly rates per room. Docs in `source/api/EARNING.md`. | Generated `source/api/.env.example` already has keys; set them when you deploy `source/api` (e.g. Render, Fly, VPS) |
| **Newsletter & enquiries** | `POST /api/newsletter` builds owned list; `POST /api/enquiries` + `POST /api/bookings` send email notification via SMTP when set, mock log otherwise. | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` |
| **Referrals** | Share `?ref=<your_org[:8]>` — when referred org upgrades, you get £5 (Pro) / £15 (Business) credited to `earnings` automatically. Link & stats in Billing. | No config — auto from signup `?ref=` or localStorage |
| **Deploy & deliver** | Finish project → Deliverables → Deploy (local always + Netlify/Vercel/Render/Cloudflare when tokens set) → hand client Live URL + `ADMIN_TOKEN` | `NETLIFY_AUTH_TOKEN`, `VERCEL_TOKEN`, `RENDER_DEPLOY_HOOK_URL`, `GITHUB_TOKEN` for push |

Test earning now:

\`\`\`bash
# platform (mock, no keys needed)
curl -X POST http://localhost:8000/api/billing/checkout -H "Authorization: Bearer <token>" -d '{"plan":"pro"}' # → mock url + instant upgrade
# client site (after `python -m agencyos seed-demo` + export)
curl -X POST http://localhost:8080/api/bookings -d '{"room":"deluxe-king","check_in":"2030-02-01","check_out":"2030-02-03","adults":2,"name":"Guest","email":"g@example.com"}' # → {checkout_url}
\`\`\`

See `.env.example` for all keys; add them to server env or `Settings → Integrations` (encrypted). **No rebuild needed** — restart and the badges flip from "demo earning" to "live".

## Tests

```bash
cd backend && python -m unittest discover -s tests -t tests     # 31 tests
B=http://localhost:8000 python tests/e2e_browser.py              # full browser walkthrough + screenshots
```

The suite covers auth, CSRF, multi-tenancy, viewer permissions, key encryption and masking, adaptive interview, colour parsing, contradictions, the full hotel build to deployment, "every completed task has a real execution", the QA bug loop, crash, retry and escalate, review rejection with revision, the execution-limit guard, change requests and memory, post-build scope changes that extend the plan, artifact versioning, restore and diff, rollback, delete confirmation, the agent registry and routing, the real repository importer, custom-agent permission limits, LLM invalid-JSON retry, provider outage fallback, the security scanner and path traversal.

## Docs

- [ARCHITECTURE](docs/ARCHITECTURE.md): components, flow, and swapping SQLite→Postgres or the in-process queue→Redis
- [ORCHESTRATION](docs/ORCHESTRATION.md): task graph, reviews, QA loop, gates, change requests, guards
- [AGENTS](docs/AGENTS.md): contracts, adapters, registry and routing, the 500-agents importer, adding new agents
- [SECURITY](docs/SECURITY.md) · [DATABASE](docs/DATABASE.md) · [API](docs/API.md) · [DEPLOYMENT](docs/DEPLOYMENT.md) · [CONTRIBUTING](docs/CONTRIBUTING.md)

## Honest limits of this foundation

- **Code generation scope.** Web projects (website, ecommerce, SaaS, dashboard and chatbot front-ends) produce a real static site plus a Python API. Mobile, game and automation projects get specs plus a web prototype. Native builds need new agents (e.g. a "Unity Game Developer Agent") registered through the same contract.
- **Third-party agents.** Agents from the GitHub repo are indexed with their frameworks, credentials, CLI inputs and risk scan. They are **disabled by default** and only execute inside Docker with a pre-built image (`execution_mode: sandbox`).
- **Scale-out.** This build uses SQLite and an in-process worker pool. The DB layer and `Orchestrator.enqueue` are the only seams to change for PostgreSQL + Redis/Celery.
