# Earning with AgencyOS — Complete Guide

AgencyOS is now **100% earning-ready**. Every layer works in **demo mode (no keys)** and flips to **live payments** when you add Stripe/SMTP keys — no code change, no rebuild beyond `npm run build` (frontend) + restart.

## 1. Two earning layers

| Layer | What you sell | How it pays |
|-------|---------------|-------------|
| **Platform** (you) | AgencyOS workspaces: users pay you for projects/agent runs/storage/deploys | Stripe Checkout subscriptions Free → Pro £29/mo → Business £99/mo → Enterprise custom. Limits enforced (`402` on `/api/projects` when capped). Billing history + earnings + referrals in UI. |
| **Client sites** (your customers) | Sites your agents build (hotel/ecommerce/saas) take real money: hotel booking deposits, ecommerce cart checkout, newsletter list → email monetization | Generated `source/api` exposes `/api/bookings` → returns `checkout_url` (Stripe Checkout, mock if no `STRIPE_SECRET_KEY`), `/api/orders/checkout` for cart, `/api/newsletter` + `/api/enquiries` + admin `GET /api/bookings` with `Bearer $ADMIN_TOKEN`. See `source/api/EARNING.md` in every export. |

## 2. Demo vs Live (zero vs real keys)

| Integration | Demo (no keys) | Live (set env + restart) | Badge in UI |
|-------------|----------------|--------------------------|-------------|
| **Stripe (platform)** | `POST /api/billing/checkout` → instant upgrade, `mock: true`, local `billing_events` log | Real Stripe Checkout session (`https://checkout.stripe.com…`), customer portal, webhook verifies `STRIPE_WEBHOOK_SECRET` | `Demo earning` purple → `Stripe LIVE` green |
| **Stripe (client site)** | `POST /api/bookings` → `{checkout_url:"#mock-checkout?amount=..."}` always works end-to-end | Requires `STRIPE_SECRET_KEY` in `source/api/.env` → calls `api.stripe.com/v1/checkout/sessions`, returns real URL | Generated `source/api/.env.example` documents keys |
| **Email** | Mock log to `audit_logs` + in-app notifications (never blocks flow) | Real SMTP via `smtplib` (SendGrid/Gmail/SES) when `SMTP_HOST/PORT/USER/PASSWORD/FROM` set | `mock mode` orange → `connected` green |
| **GitHub** | Local `.git` repo kept (`data/workspaces/<id>/.git`), commits `agent(role): …` | `GITHUB_TOKEN` PAT enables push to GitHub (`/api/projects/{id}/push` style, or `git push` manual) | `local only` gray → `connected` green |
| **Deploy** | `local` → `/sites/<id>/` always ready (immutable `releases/<id>` + `CURRENT` + health + rollback) | `NETLIFY_AUTH_TOKEN`, `VERCEL_TOKEN`, `RENDER_DEPLOY_HOOK_URL`, `CLOUDFLARE_API_TOKEN` enable those adapters (same interface) | `not configured` gray → `ready — can earn now` green |

All transitions are documented in `Settings → Integrations` with the exact env to set.

## 3. Platform earning — step-by-step (you)

1. **User signs up** (`POST /api/auth/signup` with optional `?ref=<code>` or body `referral_code`). Referral code is first 8 of referrer `org.id`; stored pending in `referrals`.
2. **Upgrade** → `POST /api/billing/checkout {plan:"pro"|"business"}` with `Authorization: Bearer <token>`.  
   - No Stripe keys → `{"mock":true,"url":".../#/billing?mock_checkout=success&plan=pro"}` and `organizations.plan` flips instantly (great for demos).  
   - With keys + prices → real Checkout URL; user pays on Stripe; Stripe sends `checkout.session.completed` → `POST /api/billing/webhook` (verifies HMAC) → `apply_plan()` → same DB flip + `billing_events` + referral reward (`earnings` £5/£15).
3. **Portal** → `POST /api/billing/portal` returns Stripe customer portal URL (mock returns `/#/billing?mock_portal=1`).
4. **Limits enforced** → `POST /api/projects` checks `billing.check_limits(org)` → `402 Your plan … Upgrade…` when `projects >= limits[plan]`. Frontend shows orange limit warning + `Billing & referrals →` CTA.
5. **History & earnings** → `GET /api/billing` returns `plan`, `plans` (with `stripe_configured`), `usage`, `earnings` (`SUM earnings where org_id`, `recent`), `billing_history` (10), `limits`. `GET /api/earnings` full list; `GET /api/referrals` link & rewards.
6. **Downgrade** → `POST /api/billing/downgrade {plan:"free"}` (keeps data, just caps).

Test instantly without Stripe:
```bash
curl -X POST http://localhost:8000/api/billing/checkout -H "Authorization: Bearer $TOKEN" -d '{"plan":"pro"}'
# → mock upgrade, check
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/billing | jq .plan
# → "pro"
```

With Stripe live (after env set + restart):
- `STRIPE_SECRET_KEY=sk_test_...`
- `STRIPE_PUBLISHABLE_KEY=pk_test_...`
- `STRIPE_PRICE_PRO=price_...` (Dashboard → Products → Recurring £29)
- `STRIPE_PRICE_BUSINESS=price_...` (£99)
- `STRIPE_WEBHOOK_SECRET=whsec_...` ( `stripe listen --forward-to localhost:8000/api/billing/webhook` or Dashboard → Webhooks → `checkout.session.completed`, `customer.subscription.updated`, `invoice.payment_succeeded`)
- `AGENCYOS_BASE_URL=https://yourdomain.com` for correct success/cancel redirects.

## 4. Client site earning — step-by-step (your customer)

Each built project ships with a dependency-free API (`source/api/service.py` + `server.py`). The static site (`source/site`) already calls it.

### Hotel booking deposit (example)
```bash
# 1. Submit booking (frontend form does this via fetch)
POST /api/bookings
{ "room":"deluxe-king","check_in":"2030-02-01","check_out":"2030-02-03","adults":2,"name":"Guest","email":"g@example.com" }
→ 201 { "message":"Thank you—...","id":123,"checkout_url":"https://checkout.stripe.com/... OR #mock-checkout?amount=19000","amount_cents":19000 }

# 2. Redirect
location.href = res.checkout_url   # real Stripe or mock demo
```

- Amount = `ROOM_PRICES[room]` (e.g. deluxe-king 9500, junior-suite 18500, penthouse 29000 cents per night) × nights. Deposit = max(1500, amount/5) (min £15). Override via `ROOM_PRICES` dict in `service.py` or `ROOM_PRICES_JSON` env.
- Stripe key absence → mock URL with `#mock-checkout` — still proves flow to client without real charge.
- Admin view: `GET /api/bookings` `Authorization: Bearer $ADMIN_TOKEN` lists all, `status` `requested|confirmed|paid|cancelled`.

### Ecommerce cart checkout
```bash
POST /api/orders/checkout
{ "items":[{"id":"sku1","name":"Tote","price":1999},{"id":"sku2","name":"Print","price":5000}], "email":"buyer@example.com" }
→ 200 { "id":1,"checkout_url":"https://checkout.stripe.com/...","total_cents":6999 }
```
- Frontend `site.js` already handles `data-add-to-cart` + `data-cart-count` + `data-cart-items` + `data-checkout` (localStorage `site_cart`). Ecommerce template pages include product grid with `data-add-to-cart` buttons.
- Server `create_order_checkout` reuses same `_stripe_checkout` helper.

### Newsletter / enquiries (list building + leads)
```bash
POST /api/newsletter { "email":"fan@example.com" } → 201 You're subscribed.
POST /api/enquiries { "name":"A","email":"a@b.co","message":"Hi" } → 201 + optional SMTP email to admin.
```
- Newsletter `INSERT OR IGNORE` → owned audience you can export from DB.
- If `SMTP_HOST` set on platform or `SMTP_*` on `source/api` separately, the platform's `email.notify_*` or the generated API's own webhook would email; otherwise logged.

### Connecting Stripe to the generated site
1. Deploy `source/api` anywhere (Render, Fly, Lightsail, your VPS): set `DATABASE_PATH`, `ADMIN_TOKEN` (random), `ALLOWED_ORIGIN` (the site origin), `STRIPE_SECRET_KEY`, `BOOKING_SUCCESS_URL`, `ORDER_SUCCESS_URL`.
2. Edit `source/site/assets/config.js`:
```js
window.SITE_CONFIG = { apiBase: "https://api.your-site.com", stripePublishableKey: "pk_live_...", plausibleDomain: "your-site.com" };
```
3. Deploy `source/site` to Netlify/Vercel/Cloudflare Pages or `local` `/sites`.
4. Test `booking.html` → submit → follow `checkout_url` → pay (test card `4242 4242 4242 4242`) → Stripe Dashboard → Payments shows deposit.

All env templates are in `source/api/.env.example` + `EARNING.md` (included in ZIP).

## 5. Referrals — you earn £5/£15

- **Link:** `https://yourdomain.com/?ref=<8-char>` (first 8 of your `org.id`). Or `/?ref=ab0372fc` style. Auth page captures `?ref` from `location.hash`/`search` + `localStorage` and sends `referral_code` on signup.
- **Store:** `referrals (id, referrer_org_id, referred_org_id, status pending|rewarded, reward_cents, created_at)` UNIQUE on referred.
- **Reward:** On `apply_plan` when `new_plan` is `pro` or `business` and a pending referral exists, we flip to `rewarded` and insert into `earnings` for referrer (`£5`/`£15` cents). Surface via `GET /api/referrals` + `GET /api/earnings`.
- **Frontend:** Billing top card shows referral link + copy button + count + reward; Dashboard free-plan banner nudges with referral CTA.

Payout is manual (export `earnings` CSV from DB) — keep ledger; add cron to email payout when you connect SMTP.

## 6. Deployment earning adapters

`services/deploy.py` now ships 5 real adapters + stubs:

- `local` always ready: copies `source/site` to `data/deployments/<pid>/releases/<did>`, writes `CURRENT`, health checks `<html` presence, instant rollback.
- `netlify` real when `NETLIFY_AUTH_TOKEN` + `NETLIFY_SITE_ID` → zips site + `POST api.netlify.com/api/v1/sites/.../deploys`.
- `vercel` real when `VERCEL_TOKEN` + `VERCEL_PROJECT_ID` → `POST api.vercel.com/v13/deployments`.
- `render` via `RENDER_DEPLOY_HOOK_URL` deploy hook `POST`.
- `cloudflare` stub (`CLOUDFLARE_API_TOKEN` → note ready).

All return `DeployResult(ok, url, logs)` and appear in `GET /api/projects/{id}/deployments` `adapters` + Deliverables `Deployment targets`.

## 7. Email + GitHub — never block earning

- `services/email.py` checks `settings().smtp_host` + `smtp_from`; if missing → mock `{"mock":true}` + audit log; if present → `smtplib.SMTP` TLS + login. Templates: `notify_deployment`, `notify_booking_admin`, `notify_enquiry`.
- `services/github_integration.py` checks `settings().github_token`; `status()` returns `{configured, token, oauth, note}`. When configured, `push_project(pid, remote)` does `git remote add/set` + `git push`. UI in Settings shows green vs gray.

## 8. Frontend earning UX — what changed

- **Auth** captures `?ref` to `localStorage` → signup with referral.
- **Dashboard** hero now mentions earning, input placeholder `…that takes bookings…`, chips hint Stripe, top earning bar (`Build → Deploy → Earn`) + referral CTA when free, stats include `Earned`.
- **Billing** fully interactive: live vs demo badge, portal, downgrade, earnings total + recent list, referral link copy, 4 plan cards with buy buttons (Stripe vs mock, `Requires Stripe price` locked state), billing history table, 4-step earning guide.
- **Project Deliverables** green `ready to earn` card when `COMPLETED`, 2-col earning how-it-works (hotel/ecommerce, newsletter, enquiries + admin curl), 5-step deploy handover checklist, `Test booking checkout →` button, deployment targets with `ready — can earn now`.
- **Settings** integrations now object-aware: shows purple `demo earning` vs green `live`, orange `mock mode` for email, correct hints plus safety limits + `Earning tip` card + base URL.

## 9. DB & config changes to support earning

- `config.Settings` +10 fields (`stripe_*`, `base_url`, `smtp_*`, `github_*`) loaded from env.
- `db.SCHEMA` `organizations` adds `stripe_customer_id/subscription_id/price_id/billing_email/plan_updated_at`; new tables `billing_events`, `earnings`, `referrals`; `ALTER TABLE` migrations on init for existing DB.
- `services/billing.py` pure-Python Stripe via `requests` (no SDK) + mock fallback, HMAC webhook verify, plan apply + referral reward, `add_earning()`.
- `services/sitegen.py` JS now handles cart (`localStorage` `site_cart`), Stripe redirect (`checkout_url` from `POST /api/bookings`), Plausible analytics, TLS-aware.
- `services/backendgen.py` room prices heuristic, `_stripe_checkout` mock/real, `bookings` + `orders` checkout flows, `EARNING.md` + `.env.example` per project, OpenAPI expanded.

## 10. Operations — go live today

```bash
# 1. Set keys in .env (or server env) then restart — badges flip, buying works
STRIPE_SECRET_KEY=sk_live_... STRIPE_PRICE_PRO=price_... STRIPE_PRICE_BUSINESS=price_... \
SMTP_HOST=smtp.sendgrid.net SMTP_USER=apikey SMTP_PASSWORD=SG.... SMTP_FROM=hello@yourdomain.com \
GITHUB_TOKEN=ghp_... \
AGENCYOS_BASE_URL=https://agencyos.yourdomain.com \
python -m agencyos --port 8000  # frontend already built (npm run build)

# 2. Build a revenue site
# → Dashboard → "I want a luxury hotel site with Stripe deposits" → Interview → Approve → Start Build → QA → Accept → Deploy → Download ZIP

# 3. Deploy client API + site (example Render + Netlify)
# unzip → cd source/api → set STRIPE_SECRET_KEY + ADMIN_TOKEN on Render Web Service → deploy
# edit source/site/assets/config.js apiBase → your Render URL
# drag source/site to Netlify or vercel --prod
```

Mock mode remains your sales demo: even without any keys you can click `Upgrade to Pro (instant demo)` + `Test booking checkout →` and show a full booking → mock Stripe → success flow to a client in a meeting. Then later add keys in `.env` and the same buttons become live Stripe without re-building content.

**Every path that previously said “not configured” or “interface only” now says “ready — can earn now” when the env is set, or “demo earning” when not — the whole site is now completely working and monetizable.**

