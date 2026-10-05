"""Billing & monetization service.

Stripe is optional. When env STRIPE_SECRET_KEY is absent we run in *mock demo mode*:
 - Checkout instantly upgrades the org locally and logs a billing_event.
 - Portal returns a mock URL.
 - Webhook verification is skipped.

This keeps the whole site earning-capable even without keys, while wiring
real Stripe when keys are present. Uses only `requests` (no stripe SDK needed)
to keep the existing pure-Python constraint.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

import requests

from ..config import settings
from ..db import db, new_id, now

PLANS = [
    {"id": "free", "name": "Free", "price": "£0", "price_cents": 0, "interval": "month",
     "limits": {"projects": 3, "agent_executions": 500, "storage_mb": 200, "deployments": 3},
     "features": ["3 projects", "500 agent runs / mo", "Community support", "Local deployments"]},
    {"id": "pro", "name": "Pro", "price": "£29/mo", "price_cents": 2900, "interval": "month",
     "limits": {"projects": 20, "agent_executions": 10_000, "storage_mb": 5_000, "deployments": 50},
     "features": ["20 projects", "10k runs / mo", "5 GB storage", "Netlify + Vercel deploy", "Email support", "Stripe checkout for client sites"]},
    {"id": "business", "name": "Business", "price": "£99/mo", "price_cents": 9900, "interval": "month",
     "limits": {"projects": 100, "agent_executions": 50_000, "storage_mb": 50_000, "deployments": 500},
     "features": ["100 projects", "50k runs / mo", "50 GB storage", "All deploy targets", "SMTP email", "GitHub push", "Priority support"]},
    {"id": "enterprise", "name": "Enterprise", "price": "Contact us", "price_cents": 0, "interval": "custom",
     "limits": {},
     "features": ["Unlimited projects", "Custom limits", "SSO + audit", "Dedicated sandbox", "SLA"]},
]

PLAN_BY_ID = {p["id"]: p for p in PLANS}


def stripe_configured() -> bool:
    s = settings()
    return bool(s.stripe_secret_key)


def publishable_key() -> str | None:
    return settings().stripe_publishable_key


def get_plans() -> list[dict[str, Any]]:
    s = settings()
    cfg = stripe_configured()
    out = []
    for p in PLANS:
        q = dict(p)
        q["stripe_configured"] = cfg
        q["has_price"] = False
        if p["id"] == "pro":
            q["has_price"] = bool(s.stripe_price_pro or not cfg)  # in mock mode pro is always purchasable
        elif p["id"] == "business":
            q["has_price"] = bool(s.stripe_price_business or not cfg)
        out.append(q)
    return out


def _price_for(plan: str) -> str | None:
    s = settings()
    if plan == "pro":
        return s.stripe_price_pro
    if plan == "business":
        return s.stripe_price_business
    return None


def _base_url() -> str:
    return settings().base_url


def check_limits(org_id: str) -> dict[str, Any]:
    """Return usage vs limits for enforcement; does not block reads."""
    org = db().q1("SELECT plan FROM organizations WHERE id = ?", (org_id,))
    plan_id = org["plan"] if org else "free"
    limits = PLAN_BY_ID.get(plan_id, PLAN_BY_ID["free"])["limits"]
    since_30d = time.time() - 30*24*3600  # not used directly, we query by ISO
    import datetime
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).isoformat()
    from ..services import workspace as ws
    projects = db().q1("SELECT COUNT(*) n FROM projects WHERE org_id = ?", (org_id,))["n"]
    execs = db().q1("SELECT COUNT(*) n FROM agent_executions e JOIN projects p ON p.id=e.project_id WHERE p.org_id=? AND e.started_at >= ?", (org_id, since))["n"]
    storage_mb = round(sum(f.stat().st_size for p in db().q("SELECT id FROM projects WHERE org_id=?", (org_id,)) for f in ws.path_for(p["id"]).rglob("*") if f.is_file())/1e6, 2) if True else 0
    out = {"plan": plan_id, "limits": limits, "usage": {"projects": projects, "agent_executions": execs, "storage_mb": storage_mb}}
    out["can_create_project"] = (plan_id == "enterprise") or (projects < limits.get("projects", 999999))
    return out


def apply_plan(org_id: str, new_plan: str, stripe_event_id: str | None = None, stripe_price_id: str | None = None,
               stripe_customer_id: str | None = None, stripe_subscription_id: str | None = None, amount_cents: int | None = None):
    if new_plan not in PLAN_BY_ID:
        raise ValueError("unknown plan")
    patch: dict[str, Any] = {"plan": new_plan, "plan_updated_at": now()}
    if stripe_price_id:
        patch["stripe_price_id"] = stripe_price_id
    if stripe_customer_id:
        patch["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id:
        patch["stripe_subscription_id"] = stripe_subscription_id
    db().update("organizations", {"id": org_id}, patch)
    # log billing event
    try:
        db().insert("billing_events", {
            "id": new_id(), "org_id": org_id, "kind": "plan_change",
            "plan": new_plan, "amount_cents": amount_cents or PLAN_BY_ID[new_plan].get("price_cents", 0),
            "currency": "gbp", "stripe_event_id": stripe_event_id, "status": "succeeded", "created_at": now()
        })
    except Exception:
        pass
    # also audit
    try:
        db().insert("audit_logs", {"org_id": org_id, "action": "plan_changed", "target": new_plan, "detail": f"stripe:{stripe_event_id or 'mock'}", "created_at": now()})
    except Exception:
        pass
    # referral reward: if referred and this is first upgrade past free, reward referrer
    try:
        ref = db().q1("SELECT * FROM referrals WHERE referred_org_id=? AND status='pending'", (org_id,))
        if ref and new_plan in ("pro","business"):
            reward = 500 if new_plan == "pro" else 1500  # cents
            db().update("referrals", {"id": ref["id"]}, {"status": "rewarded", "reward_cents": reward})
            # credit earnings to referrer
            db().insert("earnings", {"id": new_id(), "org_id": ref["referrer_org_id"], "source": "referral", "amount_cents": reward, "currency": "gbp", "description": f"Referral reward: {org_id} → {new_plan}", "created_at": now()})
    except Exception:
        pass


def create_checkout_session(org_id: str, plan: str, customer_email: str | None = None, origin: str | None = None) -> dict[str, Any]:
    if plan not in ("pro","business"):
        raise ValueError("checkout only for pro/business; enterprise = Contact us, free = downgrade")
    s = settings()
    if not s.stripe_secret_key or not _price_for(plan):
        # Mock mode: instant upgrade – demo earning works without Stripe
        apply_plan(org_id, plan, amount_cents=PLAN_BY_ID[plan]["price_cents"])
        # fake url that redirects back to billing with success
        base = origin or _base_url()
        return {"url": f"{base}/#/billing?mock_checkout=success&plan={plan}", "id": f"mock_{new_id()[:12]}", "mock": True}

    price_id = _price_for(plan)
    base = origin or _base_url()
    success_url = f"{base}/#/billing?checkout=success&plan={plan}&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/#/billing?checkout=cancel"
    data = {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": org_id,
        "allow_promotion_codes": "true",
        "billing_address_collection": "auto",
    }
    if customer_email:
        data["customer_email"] = customer_email
    # if org already has a customer, pass it (Stripe will ignore if customer_email also set? prefer existing)
    org = db().q1("SELECT stripe_customer_id FROM organizations WHERE id=?", (org_id,))
    if org and org["stripe_customer_id"]:
        data["customer"] = org["stripe_customer_id"]
        data.pop("customer_email", None)

    r = requests.post("https://api.stripe.com/v1/checkout/sessions",
                      headers={"Authorization": f"Bearer {s.stripe_secret_key}"},
                      data=data, timeout=20)
    if r.status_code >= 300:
        raise RuntimeError(f"Stripe {r.status_code}: {r.text[:300]}")
    j = r.json()
    # record pending billing event
    try:
        db().insert("billing_events", {"id": new_id(), "org_id": org_id, "kind": "checkout_created", "plan": plan,
                                       "amount_cents": PLAN_BY_ID[plan]["price_cents"], "currency": "gbp",
                                       "stripe_event_id": j.get("id"), "status": "pending", "created_at": now()})
    except Exception:
        pass
    return {"url": j.get("url"), "id": j.get("id")}


def create_customer_portal(org_id: str, return_url: str | None = None) -> dict[str, Any]:
    s = settings()
    org = db().q1("SELECT stripe_customer_id FROM organizations WHERE id=?", (org_id,))
    if not s.stripe_secret_key or not org or not org["stripe_customer_id"]:
        # mock portal
        base = return_url or _base_url()
        return {"url": f"{base}/#/billing?mock_portal=1", "mock": True}
    r = requests.post("https://api.stripe.com/v1/billing_portal/sessions",
                      headers={"Authorization": f"Bearer {s.stripe_secret_key}"},
                      data={"customer": org["stripe_customer_id"], "return_url": return_url or _base_url()},
                      timeout=15)
    if r.status_code >= 300:
        raise RuntimeError(f"Stripe portal {r.status_code}: {r.text[:300]}")
    return {"url": r.json().get("url")}


def _verify_stripe_signature(payload: bytes, sig: str, secret: str) -> bool:
    # Stripe signature: t=timestamp,v1=hmac(payload), optionally v0
    # header like "t=167...,v1=abc...,v0=..."
    try:
        parts = dict(p.split("=") for p in sig.split(",") if "=" in p)
        t = parts.get("t")
        v1 = parts.get("v1")
        if not t or not v1:
            return False
        signed_payload = f"{t}.{payload.decode()}".encode()
        expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, v1)
    except Exception:
        return False


def handle_webhook_raw(payload: bytes, sig_header: str | None) -> dict[str, Any]:
    s = settings()
    if s.stripe_webhook_secret and sig_header:
        if not _verify_stripe_signature(payload, sig_header, s.stripe_webhook_secret):
            raise ValueError("invalid stripe signature")
    import json as _j
    event = _j.loads(payload)
    etype = event.get("type")
    data_obj = event.get("data", {}).get("object", {})
    # handle checkout.session.completed, customer.subscription.* , invoice.payment_succeeded
    org_id = data_obj.get("client_reference_id") or data_obj.get("metadata", {}).get("org_id")
    # try to find org via customer
    if not org_id and data_obj.get("customer"):
        row = db().q1("SELECT id FROM organizations WHERE stripe_customer_id=?", (data_obj["customer"],))
        if row:
            org_id = row["id"]
    # idempotency guard
    eid = event.get("id")
    if eid and db().q1("SELECT id FROM billing_events WHERE stripe_event_id=?", (eid,)):
        return {"ok": True, "duplicate": True}

    if etype == "checkout.session.completed" and org_id:
        plan = None
        # try line_items price -> map to plan
        # For simplicity, check subscription items via price; fallback: metadata plan
        price_id = None
        try:
            # checkout session has display_items or line_items not expanded; we rely on metadata or price mapping
            price_id = data_obj.get("metadata", {}).get("plan")  # if we set
        except Exception:
            pass
        # map price_id if we have Stripe price expansion would need retrieval; fallback to subscription retrieval
        subscription = data_obj.get("subscription")
        customer = data_obj.get("customer")
        # Determine plan by price; if env price matches, choose
        # Simple: if customer and plan not known, try fetch subscription details (requires API call)
        if not plan:
            # heuristic: try to fetch subscription if secret available
            sub_plan = data_obj.get("metadata", {}).get("plan")
            if sub_plan in ("pro","business"):
                plan = sub_plan
            else:
                # attempt to call Stripe to expand subscription
                if s.stripe_secret_key and subscription:
                    try:
                        r = requests.get(f"https://api.stripe.com/v1/subscriptions/{subscription}",
                                         headers={"Authorization": f"Bearer {s.stripe_secret_key}"}, timeout=10)
                        if r.ok:
                            sj = r.json()
                            items = sj.get("items", {}).get("data", [])
                            if items:
                                pid = items[0].get("price", {}).get("id")
                                if pid == s.stripe_price_business:
                                    plan = "business"
                                elif pid == s.stripe_price_pro:
                                    plan = "pro"
                    except Exception:
                        pass
                if not plan:
                    # default to pro if unknown (safe)
                    plan = "pro"
        apply_plan(org_id, plan, stripe_event_id=eid, stripe_price_id=price_id or _price_for(plan),
                   stripe_customer_id=customer, stripe_subscription_id=subscription,
                   amount_cents=PLAN_BY_ID[plan]["price_cents"])
        return {"ok": True, "plan": plan}

    if etype in ("customer.subscription.updated", "customer.subscription.created") and org_id:
        status = data_obj.get("status")
        price_id = None
        try:
            price_id = data_obj.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
        except Exception:
            pass
        plan = None
        if price_id == s.stripe_price_business:
            plan = "business"
        elif price_id == s.stripe_price_pro:
            plan = "pro"
        if status in ("active","trialing") and plan:
            apply_plan(org_id, plan, stripe_event_id=eid, stripe_price_id=price_id,
                       stripe_subscription_id=data_obj.get("id"), stripe_customer_id=data_obj.get("customer"))
            return {"ok": True, "plan": plan}
        if status in ("canceled","unpaid","incomplete_expired") and org_id:
            # downgrade to free on cancel – keep data, just limit
            apply_plan(org_id, "free", stripe_event_id=eid)
            return {"ok": True, "plan": "free"}

    if etype == "invoice.payment_succeeded" and org_id and data_obj.get("paid"):
        # record earning for platform (optional)
        amount = data_obj.get("amount_paid") or data_obj.get("amount_due")
        try:
            db().insert("billing_events", {"id": new_id(), "org_id": org_id, "kind": "invoice_paid",
                                           "plan": db().q1("SELECT plan FROM organizations WHERE id=?", (org_id,))["plan"] if org_id else None,
                                           "amount_cents": amount, "currency": data_obj.get("currency","gbp"),
                                           "stripe_event_id": eid, "status": "succeeded", "created_at": now()})
        except Exception:
            pass
        return {"ok": True}

    # unhandled: log
    try:
        db().insert("billing_events", {"id": new_id(), "org_id": org_id or "unknown", "kind": f"webhook:{etype}", "plan": None,
                                       "amount_cents": 0, "currency": "gbp", "stripe_event_id": eid, "status": "ignored", "created_at": now()})
    except Exception:
        pass
    return {"ok": True, "ignored": etype}


# earnings helpers for generated sites / marketplace

def add_earning(org_id: str, amount_cents: int, source: str = "project", project_id: str | None = None, description: str | None = None, currency: str = "gbp"):
    db().insert("earnings", {"id": new_id(), "org_id": org_id, "project_id": project_id, "source": source,
                             "amount_cents": amount_cents, "currency": currency, "description": description or source, "created_at": now()})


def org_earnings_summary(org_id: str) -> dict[str, Any]:
    row = db().q1("SELECT COALESCE(SUM(amount_cents),0) total_cents, COUNT(*) n FROM earnings WHERE org_id=?", (org_id,))
    by_source = db().q("SELECT source, SUM(amount_cents) total, COUNT(*) n FROM earnings WHERE org_id=? GROUP BY source", (org_id,))
    return {"total_cents": row["total_cents"], "count": row["n"], "by_source": by_source}
