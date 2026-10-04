"""Project-type routing and dynamic team generation."""
from __future__ import annotations

import re

PROJECT_TYPES = {
    "website": "Web Product Team",
    "ecommerce": "Ecommerce Team",
    "saas": "SaaS Product Team",
    "mobile_app": "Mobile Team",
    "chatbot": "AI Product Team",
    "dashboard": "Data Product Team",
    "game": "Game Development Team",
    "automation": "Automation Team",
}

_TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("ecommerce", ("ecommerce", "e-commerce", "online store", "online shop", "webshop", "sell products", "shopify", "store for")),
    ("mobile_app", ("android", "iphone", "ios app", "mobile app", "app for my phone", "mobile application")),
    ("chatbot", ("chatbot", "chat bot", "ai assistant", "support bot", "virtual assistant")),
    ("dashboard", ("dashboard", "analytics", "report", "kpi", "data visual")),
    ("game", ("game", "unity", "multiplayer", "rpg", "platformer")),
    ("automation", ("automation", "automate", "workflow", "zapier", "scrape", "bot that")),
    ("saas", ("saas", "subscription software", "platform where users", "web app", "crm", "marketplace", "booking platform")),
    ("website", ("website", "web site", "landing page", "site for", "homepage", "portfolio", "blog")),
]

INDUSTRIES: dict[str, tuple[str, ...]] = {
    "hospitality": ("hotel", "resort", "guesthouse", "guest house", "b&b", "bed and breakfast", "hostel", "inn", "villa"),
    "restaurant": ("restaurant", "cafe", "café", "bakery", "bar ", "bistro", "pizzeria", "coffee shop"),
    "health": ("clinic", "dentist", "doctor", "physio", "medical", "pharmacy"),
    "fitness": ("gym", "fitness", "yoga", "personal trainer", "workout"),
    "beauty": ("salon", "barber", "spa ", "beauty", "nail"),
    "real_estate": ("real estate", "estate agent", "property", "realtor", "lettings"),
    "legal": ("law firm", "lawyer", "solicitor", "attorney"),
    "education": ("school", "course", "tutor", "academy", "education", "learning"),
    "retail": ("shop", "store", "boutique", "clothing", "fashion", "jewellery", "jewelry"),
    "portfolio": ("portfolio", "photographer", "artist", "designer", "freelancer"),
    "finance": ("accountant", "finance", "bank", "invest", "trading"),
    "technology": ("software", "startup", "ai ", "tech", "saas"),
}

INDUSTRY_NOUN = {
    "hospitality": "hotel", "restaurant": "restaurant", "health": "practice", "fitness": "gym",
    "beauty": "salon", "real_estate": "agency", "legal": "firm", "education": "school",
    "retail": "store", "portfolio": "portfolio", "finance": "business", "technology": "product",
}


def detect_project_type(text: str) -> str:
    t = " " + text.lower() + " "
    for ptype, kws in _TYPE_RULES:
        if any(k in t for k in kws):
            return ptype
    return "website"


def detect_industry(text: str) -> str:
    t = " " + text.lower() + " "
    for ind, kws in INDUSTRIES.items():
        if any(re.search(r"\b" + re.escape(k.strip()) + r"\b", t) for k in kws):
            return ind
    return "general"


# ---------------------------------------------------------------- team building
ROLE_LABELS = {
    "project_manager": "Project Manager", "business_analyst": "Business Analyst",
    "researcher": "Researcher", "ux_designer": "UX Designer", "ui_designer": "UI Designer",
    "architect": "Solution Architect", "content_writer": "Content Writer", "seo_specialist": "SEO Specialist",
    "frontend_developer": "Frontend Developer", "backend_developer": "Backend Developer",
    "database_engineer": "Database Engineer", "qa_engineer": "QA Engineer",
    "security_engineer": "Security Engineer", "performance_engineer": "Performance Engineer",
    "accessibility_specialist": "Accessibility Specialist", "technical_writer": "Technical Writer",
    "devops_engineer": "DevOps Engineer", "reviewer": "Review Agent", "change_analyst": "Change Analyst",
    "requirements_agent": "Requirements Agent",
}


def needs_backend(req: dict) -> bool:
    f = set(req.get("features") or [])
    return bool(f & {"booking", "payments", "accounts", "admin_dashboard", "cart", "checkout",
                     "user_auth", "api", "reviews_submission", "orders"}) or req.get("project_type") in {
        "ecommerce", "saas", "chatbot", "dashboard"}


def build_team(req: dict) -> list[str]:
    """Return the roles this project needs. Only required specialists are activated."""
    ptype = req.get("project_type", "website")
    team = ["project_manager", "business_analyst", "ux_designer", "ui_designer", "content_writer",
            "frontend_developer", "qa_engineer", "security_engineer"]
    if ptype in {"website", "ecommerce", "saas"}:
        team.append("seo_specialist")
    if ptype not in {"automation"}:
        team.append("researcher")
    if needs_backend(req):
        team += ["architect", "backend_developer", "database_engineer"]
    if ptype in {"saas", "ecommerce", "dashboard", "chatbot", "mobile_app", "game"}:
        team.append("architect")
    team += ["accessibility_specialist", "performance_engineer", "technical_writer", "devops_engineer"]
    seen: list[str] = []
    for r in team:
        if r not in seen:
            seen.append(r)
    return seen
