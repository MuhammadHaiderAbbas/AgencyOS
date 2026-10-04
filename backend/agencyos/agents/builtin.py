"""Built-in specialist agents.

Each agent: `run(ctx: AgentContext) -> AgentResult`. They consume approved upstream
artifacts (never reinterpret the raw idea), produce structured artifacts, and use the
LLM client for language-heavy work with validated JSON + deterministic fallback.
"""
from __future__ import annotations

import json
from typing import Callable

from ..services import backendgen, blueprints, qa, websearch
from ..services.design import build_palette, style_key
from ..services.sitegen import SiteBuilder
from .contracts import AgentContext, AgentResult, ArtifactOut, Permission


def _avoid_from_memory(ctx: AgentContext) -> list[str]:
    out = []
    for m in ctx.memory:
        if m["kind"] == "preference" and m["key"].startswith("avoid_color:"):
            out.append(m["key"].split(":", 1)[1])
    return out


def _style_from_memory(ctx: AgentContext) -> str | None:
    for m in ctx.memory:
        if m["kind"] == "preference" and m["key"] == "style":
            return m["value"]
    return None


def _result(ctx: AgentContext, summary: str, arts: list[ArtifactOut], **kw) -> AgentResult:
    prov = [u for u in ctx.llm.usage]
    real = [u for u in prov if u.provider != "mock"]
    r = AgentResult(status="success", summary=summary, artifacts=arts, **kw)
    if real:
        r.provider, r.model = real[-1].provider, real[-1].model
    return r


# ------------------------------------------------------------------ business analyst
def business_analyst(ctx: AgentContext) -> AgentResult:
    req = ctx.requirements
    md = ["# Requirements — " + req["project_name"], "", f"_Version approved by client. Type: {req['project_type']}, industry: {req['industry']}._", ""]
    for k in ("business_goal", "target_users", "location", "authentication", "payments", "database", "admin_requirements", "deadline", "domain"):
        if req.get(k):
            md.append(f"- **{k.replace('_', ' ').title()}:** {req[k]}")
    md += ["", "## Pages", *[f"- {p}" for p in req["pages"]], "", "## Features", *([f"- {f}" for f in req["features"]] or ["- (none)"]),
           "", "## Non-functional", *[f"- {x}" for x in req["security"] + req["performance"] + req["accessibility"]],
           "", "## Assumptions", *([f"- {a}" for a in req["assumptions"]] or ["- none"]),
           "", "## Open questions", *([f"- {u}" for u in req["unknown_requirements"]] or ["- none"])]

    def fallback():
        stories = [{"as": "visitor", "want": "understand what makes this place special within 5 seconds", "so_that": "I keep exploring",
                    "acceptance": ["Hero states the offer and location", "Primary CTA visible without scrolling"]}]
        if "booking" in req["features"]:
            stories.append({"as": "guest", "want": "request a room for specific dates", "so_that": "I can secure my stay",
                            "acceptance": ["Past dates rejected", "Check-out must be after check-in", "Double bookings prevented", "Confirmation shown"]})
        if "payments" in req["features"]:
            stories.append({"as": "guest", "want": "pay securely online", "so_that": "my booking is guaranteed",
                            "acceptance": ["Card data never touches our servers (Stripe Checkout)"]})
        if "admin_dashboard" in req["features"]:
            stories.append({"as": "hotel manager", "want": "see and manage booking requests", "so_that": "I can confirm them",
                            "acceptance": ["Admin endpoints require a token", "Bookings listed by check-in date"]})
        stories.append({"as": "visitor", "want": "send a question", "so_that": "I get an answer before deciding",
                        "acceptance": ["Form validates email", "Friendly confirmation message"]})
        return {"stories": stories}

    def validate(v):
        if not isinstance(v, dict) or not isinstance(v.get("stories"), list) or not v["stories"]:
            return ["must be an object with a non-empty 'stories' list"]
        return [f"story {i} missing fields" for i, s in enumerate(v["stories"]) if not all(k in s for k in ("as", "want", "acceptance"))]

    res = ctx.llm.generate_json(purpose="user_stories", tier="fast", system="You are a senior business analyst. Write user stories with acceptance criteria. Only use facts present in the requirements.",
                                prompt="Requirements JSON:\n" + json.dumps(req)[:6000] + '\n\nReturn {"stories":[{"as":"","want":"","so_that":"","acceptance":[""]}]}',
                                fallback=fallback, validate=validate)
    return _result(ctx, f"Documented requirements and {len(res.value['stories'])} user stories",
                   [ArtifactOut("requirements.md", "requirements", "\n".join(md), "text/markdown"),
                    ArtifactOut("user-stories.json", "user_stories", res.value)], logs=res.notes)


# ------------------------------------------------------------------ researcher
def researcher(ctx: AgentContext) -> AgentResult:
    req = ctx.requirements
    claims, notes, tools = [], [], []
    subject = f"{req.get('business_subtype') or ''} {req['industry']} website {req.get('location') or ''}".strip()
    if websearch.configured() and Permission.ACCESS_WEB.value in ctx.permissions:
        tools.append("web_search")
        try:
            for q in (f"best {subject} examples", f"{req['industry']} website booking conversion best practices"):
                for r in websearch.search(q, 4):
                    claims.append({"claim": r["title"], "source": r["source"], "evidence": r["evidence"], "date": r["date"], "confidence": 0.6})
        except websearch.SearchUnavailable as e:
            notes.append(str(e))
    else:
        notes.append("Web search provider not configured: competitor research was not performed. Set TAVILY_API_KEY to enable it.")
    heuristics = [
        ("Mobile visitors are the majority for hospitality browsing; booking must work one-handed.", 0.7),
        ("Clear pricing/availability and a single primary CTA reduce booking abandonment.", 0.7),
        ("Real photography is the strongest trust signal; placeholders should be replaced before launch.", 0.8),
    ] if req["industry"] == "hospitality" else [
        ("A single clear call to action per page improves conversion.", 0.7),
        ("Fast mobile load times reduce bounce.", 0.8),
    ]
    for c, conf in heuristics:
        claims.append({"claim": c, "source": "AgencyOS design heuristics (not externally verified)", "evidence": "internal guideline",
                       "date": None, "confidence": conf})
    return _result(ctx, f"Research complete: {len(claims)} claims ({'with' if tools else 'without'} live web sources)",
                   [ArtifactOut("research.json", "research", {"subject": subject, "claims": claims, "notes": notes,
                                                               "policy": "Unsupported claims are never promoted to requirements."})],
                   tools_used=tools, recommendations=notes, confidence=0.75 if tools else 0.5)


# ------------------------------------------------------------------ UX
def ux_designer(ctx: AgentContext) -> AgentResult:
    req = ctx.requirements
    smap = blueprints.sitemap(req)
    wf = blueprints.wireframes(req, smap)
    flows = blueprints.user_flows(req)
    return _result(ctx, f"Sitemap with {len(smap['pages'])} pages, {len(flows['flows'])} user flows and wireframes",
                   [ArtifactOut("sitemap.json", "sitemap", smap), ArtifactOut("user-flows.json", "user_flows", flows),
                    ArtifactOut("wireframes.json", "wireframes", wf)])


# ------------------------------------------------------------------ UI
def ui_designer(ctx: AgentContext) -> AgentResult:
    req = ctx.requirements
    dp = req["design_preferences"]
    style = _style_from_memory(ctx) or dp.get("style")
    avoid = sorted(set((dp.get("avoid_colors") or []) + _avoid_from_memory(ctx)))
    colors = [c for c in (dp.get("colors") or []) if c not in avoid]
    for fb in ctx.feedback:
        if "luxur" in fb.lower() or "elegan" in fb.lower():
            style = "Luxury & elegant"
    palette, fonts, decisions = build_palette(style, colors, avoid)
    ds = {
        "name": f"{req.get('business_name') or 'Project'} design system", "style": style_key(style),
        "colors": palette,
        "typography": {"heading": fonts["heading"], "body": fonts["body"], "base_size": 17,
                       "scale": {"h1": "4rem", "h2": "2.6rem", "h3": "1.35rem"}},
        "spacing": {"unit": 8, "scale": [4, 8, 12, 16, 24, 32, 48, 72]},
        "radius": {"sm": "6px", "md": "12px" if style_key(style) != "luxury" else "4px", "lg": "20px"},
        "layout": {"max_width": 1180, "grid": "auto-fit minmax(240px,1fr)"},
        "breakpoints": {"mobile": 375, "tablet": 768, "desktop": 1280},
        "components": {"button": {"min_height": 46, "variants": ["primary", "ghost"]}, "card": {"border": "1px", "padding": 24},
                       "form_field": {"min_height": 46, "label": "visible, above field"}},
        "decisions": decisions, "avoid_colors": avoid,
    }
    return _result(ctx, f"Design system '{ds['style']}' — primary {palette['primary']}" + (f", avoiding {', '.join(avoid)}" if avoid else ""),
                   [ArtifactOut("design-system.json", "design_system", ds)])


# ------------------------------------------------------------------ architect
def architect(ctx: AgentContext) -> AgentResult:
    req = ctx.requirements
    backend = backendgen.entities(req) if any(f in req["features"] for f in ("booking", "payments", "accounts", "admin_dashboard", "newsletter")) or req["project_type"] != "website" else []
    stack = {"frontend": "Static HTML/CSS/JS (no framework; fastest load, zero build step)",
             "backend": "Python stdlib JSON API + SQLite (portable to PostgreSQL)" if backend else "None — forms post to a hosted form endpoint",
             "payments": "Stripe Checkout (hosted, PCI scope minimised)" if "payments" in req["features"] else None,
             "hosting": "Static hosting/CDN for the site; small container for the API" if backend else "Static hosting/CDN"}
    md = f"""# Architecture — {req['project_name']}

## Context
{req['business_goal']}. Users: {req['target_users']}.

## Decisions
- **Frontend:** {stack['frontend']}
- **Backend:** {stack['backend']}
- **Payments:** {stack['payments'] or 'not in scope'}
- **Hosting:** {stack['hosting']}

## Components
- `source/site` — public website generated from the approved design system and content.
{'- `source/api` — JSON API: ' + ', '.join(backend) + ' (validation, double-booking prevention, admin token).' if backend else ''}

## Security
- No secrets in the client. Admin endpoints require a bearer token from the environment.
- Strict Content-Security-Policy, no third-party scripts, parameterised SQL, request size limits.

## Why this stack
The client needs a fast, low-maintenance {req['project_type']}. A static site + small API keeps hosting cheap,
removes framework upgrade churn and scores well on Core Web Vitals. The API layer can move to FastAPI/PostgreSQL
without changing the site because the contract is the OpenAPI spec.
"""
    return _result(ctx, "Architecture defined: " + ("static site + JSON API" if backend else "static site"),
                   [ArtifactOut("architecture.md", "architecture", md, "text/markdown"),
                    ArtifactOut("architecture.json", "architecture_spec", {"stack": stack, "entities": backend})])


# ------------------------------------------------------------------ content
def content_writer(ctx: AgentContext) -> AgentResult:
    req = ctx.requirements
    smap, wf, ds = ctx.artifacts["sitemap.json"], ctx.artifacts["wireframes.json"], ctx.artifacts.get("design-system.json", {})
    base = blueprints.content(req, smap, wf, ds.get("style", "modern"))

    def validate(v):
        errs = []
        for k in ("hero", "intro", "highlights"):
            if k not in v:
                errs.append(f"missing {k}")
        if "hero" in v and not all(isinstance(v["hero"].get(x), str) and v["hero"].get(x) for x in ("title", "subtitle")):
            errs.append("hero.title/subtitle must be non-empty strings")
        if isinstance(v.get("highlights"), list) and len(v["highlights"]) != len(base["highlights"]):
            errs.append(f"highlights must have exactly {len(base['highlights'])} items")
        return errs

    res = ctx.llm.generate_json(
        purpose="website_copy", tier="fast",
        system=("You are a conversion copywriter. Improve the hero, intro and highlights copy. Never invent facts "
                "(awards, star ratings, prices, years, amenities) that are not in the requirements. Keep placeholders in [brackets]."),
        prompt="Requirements:\n" + json.dumps({k: req[k] for k in ("business_name", "location", "business_subtype", "industry", "features", "design_preferences")})
        + "\nCurrent copy:\n" + json.dumps({k: base[k] for k in ("hero", "intro", "highlights")}) + "\nReturn the same JSON shape.",
        fallback=lambda: {k: base[k] for k in ("hero", "intro", "highlights")}, validate=validate)
    base.update(res.value)
    return _result(ctx, f"Wrote copy for {len(base['pages'])} pages; {len(base['claims_to_confirm'])} facts flagged for client confirmation",
                   [ArtifactOut("content.json", "content", base)], recommendations=[f"Confirm: {c}" for c in base["claims_to_confirm"]], logs=res.notes)


def seo_specialist(ctx: AgentContext) -> AgentResult:
    plan = blueprints.seo_plan(ctx.requirements, ctx.artifacts["sitemap.json"], ctx.artifacts["content.json"])
    return _result(ctx, f"SEO plan: {len(plan['pages'])} page titles/descriptions, structured data, sitemap.xml, robots.txt",
                   [ArtifactOut("seo-plan.json", "seo_plan", plan)])


# ------------------------------------------------------------------ database / backend
def database_engineer(ctx: AgentContext) -> AgentResult:
    ctx.require(Permission.WRITE_CODE)
    sql = backendgen.schema_sql(ctx.requirements)
    api = ctx.workspace / "source" / "api"
    api.mkdir(parents=True, exist_ok=True)
    (api / "schema.sql").write_text(sql)
    return _result(ctx, f"Database schema for {', '.join(backendgen.entities(ctx.requirements))}",
                   [ArtifactOut("database-schema.sql", "database_schema", sql, "text/x-sql")],
                   structured_output={"files": ["source/api/schema.sql"], "commit": "add database schema"})


def backend_developer(ctx: AgentContext) -> AgentResult:
    ctx.require(Permission.WRITE_CODE)
    req = ctx.requirements
    content = ctx.artifacts.get("content.json") or {}
    room_ids = [r["id"] for r in content.get("rooms", [])]
    api = ctx.workspace / "source" / "api"
    files = backendgen.write_backend(api, req, room_ids)
    if not (api / "schema.sql").exists():
        (api / "schema.sql").write_text(backendgen.schema_sql(req))
    spec = backendgen.openapi(req, room_ids)
    msg = "fix failing backend checks" if ctx.feedback else "implement JSON API"
    return _result(ctx, f"Implemented API ({', '.join(backendgen.entities(req))}) with unit tests",
                   [ArtifactOut("api-spec.yaml", "api_spec", spec, "application/yaml")],
                   structured_output={"files": files, "commit": msg}, tools_used=["code_writer"])


# ------------------------------------------------------------------ frontend
def frontend_developer(ctx: AgentContext) -> AgentResult:
    ctx.require(Permission.WRITE_CODE)
    site = ctx.workspace / "source" / "site"
    bug_issues = ctx.params.get("issues") or []
    if bug_issues and site.exists():
        changes = qa.apply_fixes(ctx.workspace, bug_issues, ctx.artifacts.get("seo-plan.json"))
        rebuild_needed = any(i["code"] in ("PAGE_MISSING", "JS_SYNTAX") for i in bug_issues)
        if not rebuild_needed:
            return _result(ctx, f"Fixed {len(bug_issues)} QA issues: " + "; ".join(changes)[:300],
                           [], structured_output={"files": [], "commit": "fix QA issues: " + ", ".join(sorted({i['code'] for i in bug_issues}))},
                           tools_used=["code_fixer"])
    b = SiteBuilder(ctx.requirements, ctx.artifacts["sitemap.json"], ctx.artifacts["wireframes.json"],
                    ctx.artifacts["design-system.json"], ctx.artifacts["content.json"], ctx.artifacts.get("seo-plan.json") or {"pages": []})
    files = b.build(site)
    manifest = {"entry": "source/site/index.html", "files": ["source/site/" + f for f in files],
                "consumed": ["sitemap.json", "wireframes.json", "design-system.json", "content.json", "seo-plan.json"]}
    return _result(ctx, f"Built {sum(1 for f in files if f.endswith('.html'))} pages from approved design system and content",
                   [ArtifactOut("source-manifest.json", "source_manifest", manifest)],
                   structured_output={"files": manifest["files"], "commit": "implement website pages" if not ctx.feedback else "apply design revision"},
                   tools_used=["code_writer"])


# ------------------------------------------------------------------ QA / specialists
def qa_engineer(ctx: AgentContext) -> AgentResult:
    ctx.require(Permission.RUN_TESTS)
    report = qa.run_qa(ctx.workspace, ctx.artifacts["sitemap.json"], ctx.artifacts.get("design-system.json"),
                       visual=ctx.params.get("visual", True))
    return _result(ctx, f"QA {report['status']}: {len(report['passed'])} checks passed, {len(report['failed'])} issues",
                   [ArtifactOut("qa-report.json", "qa_report", report)], structured_output={"report": report},
                   tools_used=["html_checker", "node --check", "unittest (sandbox)", "playwright"])


def accessibility_specialist(ctx: AgentContext) -> AgentResult:
    report = qa.run_accessibility(ctx.workspace, ctx.artifacts.get("design-system.json") or {})
    return _result(ctx, f"Accessibility {report['status']}: {len(report['failed'])} issues",
                   [ArtifactOut("accessibility-report.json", "accessibility_report", report)], structured_output={"report": report})


def performance_engineer(ctx: AgentContext) -> AgentResult:
    report = qa.run_performance(ctx.workspace)
    tot = max((p["total_bytes"] for p in report["pages"]), default=0)
    return _result(ctx, f"Performance {report['status']}: heaviest page {tot // 1024} KB",
                   [ArtifactOut("performance-report.json", "performance_report", report)], structured_output={"report": report})


def security_engineer(ctx: AgentContext) -> AgentResult:
    report = qa.run_security(ctx.workspace)
    return _result(ctx, f"Security {report['status']}: {report['summary']['critical']} critical, {report['summary']['high']} high",
                   [ArtifactOut("security-report.json", "security_report", report)], structured_output={"report": report},
                   tools_used=["secret_scanner", "static_analysis"])


def technical_writer(ctx: AgentContext) -> AgentResult:
    req = ctx.requirements
    has_api = (ctx.workspace / "source" / "api").exists()
    readme = f"""# {req['project_name']}

Built by AgencyOS from approved requirements.

## Structure
- `source/site/` — the website (static HTML/CSS/JS). Open `index.html` or serve the folder.
{'- `source/api/` — JSON API (Python 3.10+, no dependencies). `cd source/api && python server.py`' if has_api else ''}
- `requirements/`, `design/`, `architecture/`, `reports/` — approved artifacts and QA/security reports.

## Running locally
```bash
cd source/site && python3 -m http.server 8000
{'cd source/api && cp .env.example .env && python3 server.py   # API on :8080' if has_api else ''}
```
Set `window.SITE_CONFIG.apiBase` in `source/site/assets/config.js` to the API origin.

## Tests
{'`cd source/api && python3 -m unittest discover -s tests -t .`' if has_api else 'Static site — see reports/qa-report.json'}

## Before launch
""" + "\n".join(f"- [ ] Confirm: {c}" for c in (ctx.artifacts.get("content.json") or {}).get("claims_to_confirm", [])) + """
- [ ] Replace photo placeholders with real photography
- [ ] Configure production secrets (never commit them)
"""
    (ctx.workspace / "README.md").write_text(readme)
    guide = "# User guide\n\nEdit text in `source/site/*.html`. Colours live in `source/site/assets/styles.css` (`:root` variables).\n"
    (ctx.workspace / "deployment" / "USER_GUIDE.md").write_text(guide)
    return _result(ctx, "Wrote README and user guide", [ArtifactOut("documentation.md", "documentation", readme, "text/markdown")],
                   structured_output={"files": ["README.md", "deployment/USER_GUIDE.md"], "commit": "add documentation"})


def devops_engineer(ctx: AgentContext) -> AgentResult:
    req = ctx.requirements
    plan = f"""# Deployment plan — {req['project_name']}

1. Build: static site has no build step; API is pure Python.
2. Gate: QA, security (0 critical/high) and client acceptance must pass.
3. Deploy site to the selected adapter (local preview host by default; Netlify when configured).
4. Health check: index.html served and parseable.
5. Rollback: previous immutable release can be re-activated instantly.
6. Production API (if any): run `source/api/server.py` behind HTTPS with `ADMIN_TOKEN` set; set `ALLOWED_ORIGIN`.
"""
    return _result(ctx, "Deployment plan prepared", [ArtifactOut("deployment-plan.md", "deployment_plan", plan, "text/markdown")])


def project_manager(ctx: AgentContext) -> AgentResult:
    tasks = ctx.params.get("tasks", [])
    phases: dict[str, list[dict]] = {}
    for t in tasks:
        phases.setdefault(t["phase"], []).append(t)
    md = [f"# Project plan — {ctx.requirements['project_name']}", "", f"Team: {', '.join(ctx.params.get('team', []))}", ""]
    for ph, ts in phases.items():
        md.append(f"## {ph.title()}")
        md += [f"- [{t['role']}] {t['title']}" for t in ts]
        md.append("")
    return _result(ctx, f"Plan: {len(tasks)} tasks in {len(phases)} phases", [ArtifactOut("project-plan.md", "project_plan", "\n".join(md), "text/markdown")])


BUILTIN_RUNNERS: dict[str, Callable[[AgentContext], AgentResult]] = {
    "project_manager": project_manager, "business_analyst": business_analyst, "researcher": researcher,
    "ux_designer": ux_designer, "ui_designer": ui_designer, "architect": architect, "content_writer": content_writer,
    "seo_specialist": seo_specialist, "database_engineer": database_engineer, "backend_developer": backend_developer,
    "frontend_developer": frontend_developer, "qa_engineer": qa_engineer, "accessibility_specialist": accessibility_specialist,
    "performance_engineer": performance_engineer, "security_engineer": security_engineer, "technical_writer": technical_writer,
    "devops_engineer": devops_engineer,
}
