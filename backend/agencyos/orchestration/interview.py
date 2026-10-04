"""Requirements Agent: adaptive interview -> structured Project Requirements Document.

The interviewer is a small state machine over a question bank. Each question has an
applicability rule, so a brochure site never gets asked about payments. Free-text
answers are parsed deterministically; when a real LLM is configured it additionally
extracts any extra facts the user volunteered so the same question isn't asked twice.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .teams import INDUSTRY_NOUN, detect_industry, detect_project_type

YES = re.compile(r"^\s*(y|yes|yeah|yep|sure|definitely|of course|please|ok|okay|correct|absolutely|i do|we do)\b", re.I)
NO = re.compile(r"^\s*(n|no|nope|not really|none|nah|don'?t|do not|we don'?t|i don'?t|no thanks)\b", re.I)
SKIP = re.compile(r"\b(skip|not sure|don'?t know|unsure|later|no idea|n/?a|tbd)\b", re.I)

COLOR_WORDS = ["black", "white", "gold", "green", "dark green", "navy", "blue", "red", "burgundy", "purple",
               "pink", "orange", "yellow", "teal", "turquoise", "grey", "gray", "beige", "cream", "brown",
               "silver", "emerald", "charcoal", "sand", "terracotta", "olive"]


def empty_requirements(idea: str) -> dict:
    ptype = detect_project_type(idea)
    industry = detect_industry(idea)
    return {
        "idea": idea, "project_name": None, "project_type": ptype, "industry": industry,
        "business_name": None, "business_subtype": None, "location": None, "target_users": None,
        "business_goal": None, "features": [], "pages": [], "platforms": ["web"] if ptype != "mobile_app" else [],
        "design_preferences": {"style": None, "colors": [], "avoid_colors": []},
        "branding": {"has_logo": None}, "content_requirements": {}, "technical_requirements": {},
        "integrations": [], "authentication": None, "payments": None, "database": None,
        "admin_requirements": None, "hosting": None, "domain": None, "security": ["https", "input validation"],
        "performance": ["Core Web Vitals pass on mobile"], "accessibility": ["WCAG 2.2 AA"],
        "seo": ptype in {"website", "ecommerce", "saas"}, "analytics": None, "languages": ["English"],
        "deadline": None, "budget": None, "constraints": [], "known_assets": {}, "contact": {},
        "room_types": [], "product_categories": [], "core_features": [], "data_sources": [],
        "unknown_requirements": [], "assumptions": [], "risks": [],
        "_answered": [], "_explicit": {},
    }


@dataclass
class Question:
    id: str
    text: str | Callable[[dict], str]
    kind: str  # text | choice | multi | bool
    options: list[str] = field(default_factory=list)
    when: Callable[[dict], bool] = lambda r: True
    required: bool = True
    parse: Callable[[str, dict], dict] | None = None

    def render(self, r: dict) -> str:
        return self.text(r) if callable(self.text) else self.text


def _noun(r: dict) -> str:
    return INDUSTRY_NOUN.get(r.get("industry") or "", "business")


def _has(r: dict, feat: str) -> bool:
    return feat in (r.get("features") or [])


def _add_feature(r: dict, feat: str, on: bool) -> None:
    f = list(r.get("features") or [])
    if on and feat not in f:
        f.append(feat)
    if not on and feat in f:
        f.remove(feat)
    r["features"] = f
    r["_explicit"][feat] = on


def _match_options(answer: str, options: list[str]) -> list[str]:
    a = answer.lower()
    hits = [o for o in options if o.lower() in a or o.lower().split(" ")[0] in a.split()]
    if not hits:
        nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", a)]
        hits = [options[n - 1] for n in nums if 1 <= n <= len(options)]
    return hits


def _list_items(answer: str) -> list[str]:
    parts = re.split(r",|\band\b|\n|;|/", answer)
    return [p.strip(" .-•*").strip() for p in parts if p.strip(" .-•*").strip()]


def _bool(answer: str) -> bool | None:
    if YES.search(answer):
        return True
    if NO.search(answer):
        return False
    return None


def parse_colors(answer: str) -> tuple[list[str], list[str]]:
    a = answer.lower()
    avoid: list[str] = []
    use: list[str] = []
    for c in sorted(COLOR_WORDS, key=len, reverse=True):
        for m in re.finditer(r"\b" + re.escape(c) + r"\b", a):
            before = a[max(0, m.start() - 25):m.start()]
            target = avoid if re.search(r"(no|not|avoid|without|hate|don'?t (want|like)|except|anything but)\s+(\w+\s+)?$", before) else use
            if c not in target and not any(c in x for x in use + avoid):
                target.append(c)
    hexes = re.findall(r"#[0-9a-fA-F]{6}\b", answer)
    return use + hexes, avoid


# ---------------------------------------------------------------- parsers
def p_name(a, r):
    name = re.sub(r"^(it'?s|it is|the name is|called|we are|we're|name:)\s+", "", a.strip(), flags=re.I).strip(" .\"'")
    return {"business_name": name[:80], "project_name": f"{name[:60]} {'Website' if r['project_type'] == 'website' else PROJECT_TITLES.get(r['project_type'], 'Project')}"}


def p_location(a, r):
    return {"location": re.sub(r"^(it'?s |we'?re |located )?(in|at)\s+", "", a.strip(), flags=re.I).strip(" .")}


def p_subtype(a, r):
    q = QUESTIONS_BY_ID["business_subtype"]
    hits = _match_options(a, q.options)
    return {"business_subtype": hits[0] if hits else a.strip()[:40]}


def p_scope(a, r):
    out: dict[str, Any] = {}
    al = a.lower()
    booking = any(w in al for w in ("book", "reserv", "online", "2")) and not any(w in al for w in ("brochure", "simple", "just info", "1"))
    _add_feature(r, "booking", booking)
    if not booking:
        r["assumptions"].append("Brochure site: enquiries via contact form; no online booking engine.")
        _add_feature(r, "contact_form", True)
    return out


def p_rooms(a, r):
    items = [i for i in _list_items(a) if len(i) < 40]
    m = re.search(r"\b(\d{1,2})\b", a)
    if m and len(items) <= 1:
        n = int(m.group(1))
        items = ["Standard Room", "Deluxe Room", "Junior Suite", "Executive Suite", "Family Room", "Penthouse"][:max(1, min(n, 6))]
        r["assumptions"].append(f"{n} room types; names are placeholders until confirmed.")
    return {"room_types": items}


def p_products(a, r):
    return {"product_categories": [i for i in _list_items(a) if len(i) < 40][:12]}


def p_payments(a, r):
    b = _bool(a)
    al = a.lower()
    if b is None:
        b = any(w in al for w in ("online", "card", "stripe", "deposit", "pay now"))
        if "hotel" in al or "arrival" in al or "at the" in al:
            b = False
    _add_feature(r, "payments", b)
    if b:
        ints = list(r["integrations"])
        if "Stripe" not in ints:
            ints.append("Stripe")
        r["integrations"] = ints
    return {"payments": "Online card payments (Stripe)" if b else "Pay on arrival / offline"}


def p_bool_feature(feat: str, label: str):
    def _p(a, r):
        b = _bool(a)
        if b is None:
            b = not SKIP.search(a) and len(a.strip()) > 0 and "no" not in a.lower().split()
        _add_feature(r, feat, b)
        return {}
    return _p


def p_accounts(a, r):
    al = a.lower()
    on = ("account" in al and "guest" not in al) or (_bool(a) is True and "guest" not in al)
    _add_feature(r, "accounts", on)
    return {}


def p_extras(a, r):
    q = QUESTIONS_BY_ID["extras"]
    hits = _match_options(a, q.options)
    if NO.search(a):
        hits = []
    for h in hits:
        _add_feature(r, EXTRA_FEATURES[h], True)
    return {}


def p_languages(a, r):
    if NO.search(a) or a.strip().lower() in {"english", "english only", "just english"}:
        return {"languages": ["English"]}
    langs = [l.title() for l in _list_items(a) if l.isalpha() or " " in l]
    if not any(l.lower() == "english" for l in langs):
        langs.insert(0, "English")
    if len(langs) > 1:
        _add_feature(r, "multilingual", True)
    return {"languages": langs[:6]}


def p_assets(a, r):
    al = a.lower()
    logo = "logo" in al or "both" in al or (_bool(a) is True)
    photos = "photo" in al or "both" in al or "image" in al or (_bool(a) is True)
    if "neither" in al or _bool(a) is False:
        logo = photos = False
    if not photos:
        r["assumptions"].append("No photography supplied: tasteful placeholders are used and flagged for replacement.")
    if not logo:
        r["assumptions"].append("No logo supplied: a typographic wordmark is generated from the business name.")
    return {"branding": {"has_logo": logo}, "known_assets": {"logo": logo, "photos": photos}}


def p_style(a, r):
    q = QUESTIONS_BY_ID["style"]
    hits = _match_options(a, q.options)
    dp = dict(r["design_preferences"])
    dp["style"] = hits[0] if hits else a.strip()[:60]
    return {"design_preferences": dp}


def p_colors(a, r):
    use, avoid = parse_colors(a)
    dp = dict(r["design_preferences"])
    if not (NO.search(a) or SKIP.search(a)) or use or avoid:
        dp["colors"], dp["avoid_colors"] = use, avoid
    return {"design_preferences": dp}


def p_contact(a, r):
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", a)
    phone = re.search(r"\+?[\d][\d\s().-]{6,}\d", a)
    c = {}
    if email:
        c["email"] = email.group(0)
    if phone:
        c["phone"] = phone.group(0).strip()
    if not c:
        r["assumptions"].append("Contact details not provided: placeholders shown and flagged before launch.")
    return {"contact": c}


def p_deadline(a, r):
    return {"deadline": None if SKIP.search(a) or NO.search(a) else a.strip()[:60]}


def p_domain(a, r):
    b = _bool(a)
    dom = re.search(r"\b[\w-]+\.(com|co\.uk|net|org|io|uk|hotel|travel|pt|es|fr|de)\b", a.lower())
    return {"domain": dom.group(0) if dom else ("Existing domain (to confirm)" if b else "Needs a domain"),
            "hosting": "AgencyOS managed hosting (preview) — production provider chosen at deployment"}


def p_text(fieldname: str, maxlen: int = 200, as_list: bool = False):
    def _p(a, r):
        if SKIP.search(a):
            r["unknown_requirements"].append(fieldname)
            return {}
        return {fieldname: _list_items(a)[:12] if as_list else a.strip()[:maxlen]}
    return _p


PROJECT_TITLES = {"website": "Website", "ecommerce": "Store", "saas": "Platform", "mobile_app": "App",
                  "chatbot": "Assistant", "dashboard": "Dashboard", "game": "Game", "automation": "Automation"}

EXTRA_FEATURES = {"Gallery": "gallery", "Guest reviews": "reviews", "Blog": "blog", "Restaurant & dining": "dining",
                  "Spa & wellness": "spa", "Events & weddings": "events", "FAQ": "faq", "Newsletter": "newsletter",
                  "Special offers": "offers", "Testimonials": "reviews", "Team page": "team", "Pricing page": "pricing"}

_WEB = {"website", "ecommerce", "saas"}

QUESTIONS: list[Question] = [
    Question("business_name", lambda r: f"What is the name of your {_noun(r)}?" if r["industry"] != "general"
             else "What is the name of the business or product?", "text", parse=p_name),
    Question("location", "Where is it located? (city and country is enough)", "text",
             when=lambda r: r["industry"] in {"hospitality", "restaurant", "health", "fitness", "beauty", "real_estate", "legal"},
             parse=p_location),
    Question("business_subtype", "What type of hotel is it?", "choice",
             ["Luxury", "Boutique", "Resort", "Business", "Budget", "Other"],
             when=lambda r: r["industry"] == "hospitality", parse=p_subtype),
    Question("scope", lambda r: ("Should guests be able to book rooms online, or do you want a simple brochure site with an enquiry form?"
                                 if r["industry"] == "hospitality" else
                                 "Do customers need to book or reserve online, or is a simple informational site enough?"),
             "choice", ["Online booking", "Brochure site"],
             when=lambda r: r["project_type"] == "website" and r["industry"] in {"hospitality", "restaurant", "health", "fitness", "beauty"},
             parse=p_scope),
    Question("room_types", "Which room types do you offer? (e.g. Deluxe King, Junior Suite, Penthouse — or just how many)",
             "text", when=lambda r: r["industry"] == "hospitality" and _has(r, "booking"), parse=p_rooms),
    Question("product_categories", "What will you sell? List your main product categories.", "text",
             when=lambda r: r["project_type"] == "ecommerce", parse=p_products),
    Question("payments", lambda r: ("Should guests pay online when they book, or pay at the hotel?"
                                    if r["industry"] == "hospitality" else "Do you want to take payments online?"),
             "choice", ["Pay online", "Pay on arrival"],
             when=lambda r: _has(r, "booking") or r["project_type"] in {"ecommerce", "saas"}, parse=p_payments),
    Question("accounts", "Do customers need their own accounts (to see bookings/orders), or is guest checkout fine?",
             "choice", ["Yes, accounts", "Guest checkout is fine"],
             when=lambda r: _has(r, "booking") or r["project_type"] == "ecommerce",
             parse=p_accounts),
    Question("admin_dashboard", "Do you want an admin dashboard to manage bookings, content and enquiries?", "bool",
             ["Yes", "No"], when=lambda r: _has(r, "booking") or r["project_type"] in {"ecommerce", "saas"},
             parse=p_bool_feature("admin_dashboard", "Admin dashboard")),
    Question("core_features", "What are the 3–5 core things users must be able to do?", "text",
             when=lambda r: r["project_type"] in {"saas", "mobile_app", "chatbot", "game", "automation"},
             parse=p_text("core_features", as_list=True)),
    Question("target_users", "Who are the main users?", "text",
             when=lambda r: r["project_type"] in {"saas", "mobile_app", "chatbot", "dashboard"},
             parse=p_text("target_users")),
    Question("data_sources", "Where does the data come from? (e.g. CSV exports, Google Sheets, a database, an API)", "text",
             when=lambda r: r["project_type"] == "dashboard", parse=p_text("data_sources", as_list=True)),
    Question("extras", "Which of these would you like? (pick any)", "multi",
             ["Gallery", "Guest reviews", "Blog", "Restaurant & dining", "Spa & wellness", "Events & weddings", "FAQ", "Newsletter", "Special offers"],
             when=lambda r: r["industry"] == "hospitality", parse=p_extras),
    Question("extras_generic", "Which extra sections would you like? (pick any)", "multi",
             ["Gallery", "Testimonials", "Blog", "FAQ", "Newsletter", "Team page", "Pricing page"],
             when=lambda r: r["project_type"] in _WEB and r["industry"] != "hospitality", parse=lambda a, r: _extras_generic(a, r)),
    Question("languages", "Which languages should the site support?", "text", when=lambda r: r["project_type"] in _WEB | {"mobile_app"},
             parse=p_languages),
    Question("assets", "Do you already have a logo and photos?", "choice", ["Both", "Logo only", "Photos only", "Neither"],
             when=lambda r: r["project_type"] in _WEB | {"mobile_app"}, parse=p_assets),
    Question("style", "Which style fits best?", "choice",
             ["Luxury & elegant", "Modern & minimal", "Warm & welcoming", "Bold & vibrant"], parse=p_style),
    Question("colors", "Any brand colours you'd like to use — or avoid?", "text", required=False, parse=p_colors),
    Question("contact", "Which contact email and phone number should appear? (you can say skip)", "text",
             required=False, when=lambda r: r["project_type"] in _WEB, parse=p_contact),
    Question("deadline", "Do you have a target launch date?", "text", required=False, parse=p_deadline),
    Question("domain", "Do you already have a domain name?", "text", required=False,
             when=lambda r: r["project_type"] in _WEB, parse=p_domain),
]
QUESTIONS_BY_ID = {q.id: q for q in QUESTIONS}


def _extras_generic(a, r):
    q = QUESTIONS_BY_ID["extras_generic"]
    for h in ([] if NO.search(a) else _match_options(a, q.options)):
        _add_feature(r, EXTRA_FEATURES[h], True)
    return {}


# ---------------------------------------------------------------- pre-extraction from the idea
def preextract(idea: str, r: dict) -> None:
    i = idea.lower()
    if re.search(r"\b(book|booking|reservation|reserve)\b", i):
        _add_feature(r, "booking", True)
        r["_answered"].append("scope")
    if re.search(r"\bbrochure|simple (site|website)\b", i):
        _add_feature(r, "booking", False)
        r["_answered"].append("scope")
    for sub in ("luxury", "boutique", "resort", "budget"):
        if sub in i and r["industry"] == "hospitality":
            r["business_subtype"] = sub.title()
            r["_answered"].append("business_subtype")
    m = re.search(r"\b(?:called|named)\s+[\"']?([A-Z][\w&' -]{2,40}?)[\"']?(?:[,.]| in | for |$)", idea)
    if m:
        r.update(p_name(m.group(1), r))
        r["_answered"].append("business_name")
    m = re.search(r"\bin ([A-Z][a-zA-Z]+(?:,? [A-Z][a-zA-Z]+)?)", idea)
    if m:
        r["location"] = m.group(1)
        r["_answered"].append("location")


# ---------------------------------------------------------------- interview engine
def next_question(r: dict) -> Question | None:
    for q in QUESTIONS:
        if q.id in r["_answered"]:
            continue
        if not q.when(r):
            continue
        return q
    return None


def detect_contradictions(before: dict, after: dict) -> list[dict]:
    out = []
    for feat, val in after.get("_explicit", {}).items():
        prev = before.get("_explicit", {}).get(feat)
        if prev is not None and prev != val:
            out.append({"feature": feat, "previous": prev, "new": val})
    return out


FEATURE_LABELS = {
    "booking": "online booking", "payments": "online payments", "accounts": "customer accounts",
    "admin_dashboard": "an admin dashboard", "gallery": "a gallery", "reviews": "reviews", "blog": "a blog",
    "dining": "a dining page", "spa": "a spa page", "events": "an events page", "faq": "an FAQ",
    "newsletter": "a newsletter signup", "offers": "special offers", "multilingual": "multiple languages",
    "contact_form": "a contact form", "team": "a team page", "pricing": "a pricing page",
}


def apply_answer(r: dict, qid: str, answer: str) -> dict:
    q = QUESTIONS_BY_ID[qid]
    if SKIP.search(answer) and not q.required:
        r["_answered"].append(qid)
        return r
    if SKIP.search(answer) and q.required:
        r["unknown_requirements"].append(qid)
        r["assumptions"].append(f"'{qid.replace('_', ' ')}' left open by the client; a sensible default is used and flagged.")
    updates = q.parse(answer, r) if q.parse else {}
    r.update(updates)
    if qid not in r["_answered"]:
        r["_answered"].append(qid)
    return r


def derive_pages(r: dict) -> list[str]:
    t, ind, f = r["project_type"], r["industry"], set(r.get("features") or [])
    if t == "ecommerce":
        pages = ["Home", "Shop", "Product Details", "Cart", "Checkout", "About", "Contact"]
        if "accounts" in f:
            pages.append("My Account")
    elif t == "saas":
        pages = ["Home", "Features", "Pricing", "Sign up", "Log in", "App Dashboard", "Contact"]
    elif t == "dashboard":
        pages = ["Overview", "Reports", "Data Sources", "Settings"]
    elif t == "chatbot":
        pages = ["Home", "Chat", "Knowledge Base", "Admin"]
    elif t in {"mobile_app", "game", "automation"}:
        pages = ["Home", "Core Flow", "Settings"]
    elif ind == "hospitality":
        pages = ["Home", "Rooms"]
        if "booking" in f:
            pages += ["Room Details", "Booking"]
        pages += ["About", "Contact"]
    else:
        pages = ["Home", "Services", "About", "Contact"]
    extra = {"gallery": "Gallery", "blog": "Blog", "dining": "Dining", "spa": "Spa & Wellness", "events": "Events",
             "faq": "FAQ", "offers": "Offers", "team": "Team", "pricing": "Pricing", "reviews": "Reviews"}
    for k, v in extra.items():
        if k in f and v not in pages:
            pages.insert(-1, v)
    if "admin_dashboard" in f and "Admin" not in pages:
        pages.append("Admin")
    return pages


def finalize(r: dict) -> dict:
    r["pages"] = derive_pages(r)
    if not r.get("project_name"):
        r["project_name"] = (r.get("business_name") or "New") + " " + PROJECT_TITLES.get(r["project_type"], "Project")
    f = set(r["features"])
    r["authentication"] = "Customer accounts (email + password)" if "accounts" in f else (
        "Admin login only" if "admin_dashboard" in f else "None (public site)")
    if "booking" in f or r["project_type"] in {"ecommerce", "saas"}:
        r["database"] = "Relational database (bookings/orders/content)"
    if "admin_dashboard" in f:
        r["admin_requirements"] = "Manage bookings/orders, content and enquiries"
    if r["industry"] == "hospitality" and r["location"]:
        if "Google Maps" not in r["integrations"]:
            r["integrations"].append("Google Maps")
    if "multilingual" in f and not any("translation" in a for a in r["assumptions"]):
        r["assumptions"].append(f"Launch copy is written in English; {', '.join(r['languages'][1:])} translations to be supplied or commissioned.")
    if "contact_form" in f or "booking" in f:
        if "Email" not in r["integrations"]:
            r["integrations"].append("Email")
    if r.get("analytics") is None:
        r["analytics"] = "Privacy-friendly analytics (cookie-less) — assumed"
    if not r.get("business_goal"):
        r["business_goal"] = {
            "hospitality": "Increase direct bookings and present the property attractively",
            "restaurant": "Drive reservations and showcase the menu",
            "retail": "Sell products online", "portfolio": "Showcase work and win clients",
        }.get(r["industry"], "Establish an online presence and convert visitors into customers")
    if not r.get("target_users"):
        r["target_users"] = {"hospitality": "Leisure and business travellers researching and booking stays",
                             "restaurant": "Local diners and visitors"}.get(r["industry"], "Prospective customers")
    risks = []
    if "payments" in f:
        risks.append("Payment processing requires a Stripe account and PCI-compliant hosted checkout.")
    if not r["known_assets"].get("photos"):
        risks.append("Placeholder imagery reduces conversion until real photography is supplied.")
    if "booking" in f:
        risks.append("Availability must not double-book; integrate with the hotel PMS/channel manager later if one exists.")
    r["risks"] = risks
    r["unknown_requirements"] = sorted(set(r["unknown_requirements"]))
    r["assumptions"] = list(dict.fromkeys(r["assumptions"]))
    return r


def summary_markdown(r: dict) -> str:
    def li(xs):
        return "\n".join(f"- {x}" for x in xs) if xs else "- (none)"
    labels = [FEATURE_LABELS.get(f, f.replace("_", " ")) for f in r["features"]]
    dp = r["design_preferences"]
    lines = [
        f"**Project:** {r['project_name']}",
        f"**Type:** {r['project_type'].replace('_', ' ').title()} · **Industry:** {r['industry'].replace('_', ' ').title()}"
        + (f" · **Location:** {r['location']}" if r.get("location") else ""),
        f"**Goal:** {r['business_goal']}",
        "", "**Pages**", li(r["pages"]), "", "**Features**", li([l[0].upper() + l[1:] for l in labels]),
        "", "**Design**", f"- Style: {dp.get('style') or 'to be proposed'}",
        f"- Colours: {', '.join(dp.get('colors') or []) or 'designer to propose'}"
        + (f" (avoid: {', '.join(dp['avoid_colors'])})" if dp.get("avoid_colors") else ""),
        "", "**Integrations**", li(r["integrations"]),
    ]
    if r.get("room_types"):
        lines += ["", "**Room types**", li(r["room_types"])]
    if r["assumptions"]:
        lines += ["", "**Assumptions**", li(r["assumptions"])]
    if r["risks"]:
        lines += ["", "**Risks**", li(r["risks"])]
    return "\n".join(lines)


def public_requirements(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith("_")}


# ---------------------------------------------------------------- free-text change parsing
CHANGE_FEATURE_WORDS = {
    "blog": "blog", "gallery": "gallery", "reviews": "reviews", "faq": "faq", "newsletter": "newsletter",
    "booking": "booking", "book": "booking", "reservation": "booking", "reserve": "booking", "payment": "payments", "stripe": "payments",
    "pay online": "payments", "account": "accounts", "login": "accounts", "admin": "admin_dashboard",
    "spa": "spa", "dining": "dining", "restaurant": "dining", "events": "events", "offers": "offers",
    "pricing": "pricing", "team": "team",
}


def parse_change(text: str) -> dict:
    """Very small intent parser for requirement edits: add/remove features, colour prefs, style."""
    t = text.lower()
    add, remove = [], []
    negative = bool(re.search(r"\b(remove|drop|delete|no longer|don'?t want|do not want|without|get rid of|no)\b", t))
    positive = bool(re.search(r"\b(add|include|want|need|enable|also|allow|let)\b", t))
    for word, feat in CHANGE_FEATURE_WORDS.items():
        if re.search(r"\b" + re.escape(word), t):
            (remove if negative and not (positive and not re.search(r"(remove|drop|delete|no longer|don'?t want)", t)) else add).append(feat)
    use, avoid = parse_colors(text)
    style = None
    for s in ("luxurious", "luxury", "minimal", "modern", "bold", "warm", "elegant", "playful"):
        if s in t:
            style = s
    return {"add": sorted(set(add)), "remove": sorted(set(remove)), "colors": use, "avoid_colors": avoid, "style": style}
