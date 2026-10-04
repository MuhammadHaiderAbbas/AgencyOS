"""Deterministic UX + content blueprints.

These are the rule-based implementations the UX Designer, Content Writer and SEO
agents use when no LLM is configured (and as the validated fallback when one is).
Content never invents business facts: unknown facts are emitted as clearly marked
placeholders and listed in `claims_to_confirm`.
"""
from __future__ import annotations

import re


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "page"


PAGE_SECTIONS: dict[str, list[str]] = {
    "Home": ["hero", "intro", "highlights", "featured_rooms", "reviews", "cta"],
    "Rooms": ["page_header", "room_list", "amenities", "cta"],
    "Room Details": ["page_header", "room_detail", "amenities", "cta"],
    "Booking": ["page_header", "booking_form", "policies"],
    "About": ["page_header", "story", "highlights", "cta"],
    "Contact": ["page_header", "contact_form", "contact_details", "map"],
    "Gallery": ["page_header", "gallery_grid"],
    "Blog": ["page_header", "blog_list"],
    "Dining": ["page_header", "story", "highlights", "cta"],
    "Spa & Wellness": ["page_header", "story", "highlights", "cta"],
    "Events": ["page_header", "story", "highlights", "contact_form"],
    "FAQ": ["page_header", "faq"],
    "Offers": ["page_header", "offers"],
    "Reviews": ["page_header", "reviews"],
    "Services": ["page_header", "highlights", "cta"],
    "Team": ["page_header", "team"],
    "Pricing": ["page_header", "pricing_table", "faq"],
    "Shop": ["page_header", "product_grid"],
    "Product Details": ["page_header", "product_detail"],
    "Cart": ["page_header", "cart"],
    "Checkout": ["page_header", "checkout_form"],
    "My Account": ["page_header", "login_form"],
    "Features": ["page_header", "highlights", "cta"],
    "Sign up": ["page_header", "signup_form"],
    "Log in": ["page_header", "login_form"],
    "App Dashboard": ["page_header", "dashboard_stats"],
    "Overview": ["page_header", "dashboard_stats"],
    "Reports": ["page_header", "dashboard_stats"],
    "Data Sources": ["page_header", "story"],
    "Settings": ["page_header", "story"],
    "Chat": ["page_header", "chat_widget"],
    "Knowledge Base": ["page_header", "faq"],
    "Admin": ["page_header", "admin_panel"],
    "Core Flow": ["page_header", "highlights", "cta"],
}


def sitemap(req: dict) -> dict:
    pages = []
    for title in req["pages"]:
        pid = slug(title)
        path = "index.html" if title in ("Home", "Overview") else f"{pid}.html"
        pages.append({"id": pid, "title": title, "path": path,
                      "purpose": _purpose(title, req), "in_nav": title not in {"Room Details", "Product Details", "Cart", "Checkout", "Admin", "Log in", "Sign up"}})
    return {"pages": pages, "primary_cta": _cta(req)}


def _cta(req: dict) -> dict:
    f = set(req["features"])
    if "booking" in f:
        return {"label": "Book your stay" if req["industry"] == "hospitality" else "Book now", "target": "booking"}
    if req["project_type"] == "ecommerce":
        return {"label": "Shop now", "target": "shop"}
    if req["project_type"] == "saas":
        return {"label": "Start free", "target": "sign-up"}
    return {"label": "Get in touch", "target": "contact"}


def _purpose(title: str, req: dict) -> str:
    noun = req.get("business_name") or "the business"
    return {
        "Home": f"Introduce {noun}, build desire and route visitors to the primary action.",
        "Rooms": "Compare room types quickly and move to details or booking.",
        "Room Details": "Give everything needed to choose a specific room.",
        "Booking": "Capture a valid booking request with dates, guests and contact details.",
        "About": "Build trust through story and values.",
        "Contact": "Make it effortless to ask a question or find the location.",
        "Gallery": "Showcase the atmosphere visually.",
        "FAQ": "Answer pre-booking questions to reduce friction.",
    }.get(title, f"Present {title.lower()} information clearly.")


def wireframes(req: dict, smap: dict) -> dict:
    screens = []
    for p in smap["pages"]:
        secs = list(PAGE_SECTIONS.get(p["title"], ["page_header", "story"]))
        if p["title"] == "Home":
            f = set(req["features"])
            if req["industry"] != "hospitality" or not req.get("room_types"):
                secs = [s for s in secs if s != "featured_rooms"]
            if "reviews" not in f:
                secs = [s for s in secs if s != "reviews"]
            if "newsletter" in f:
                secs.insert(-1, "newsletter")
            if "offers" in f:
                secs.insert(3, "offers")
        if p["title"] == "Contact" and not req.get("location"):
            secs = [s for s in secs if s != "map"]
        screens.append({"page": p["id"], "sections": [{"type": s, "layout": _layout(s)} for s in secs]})
    return {"breakpoints": ["mobile 375", "tablet 768", "desktop 1280"], "screens": screens}


def _layout(s: str) -> str:
    return {"hero": "full-bleed image, headline, subhead, primary CTA", "room_list": "card grid 1/2/3 columns",
            "booking_form": "single column form with summary aside on desktop", "gallery_grid": "masonry 2/3 columns",
            "reviews": "3 quote cards", "highlights": "icon + text grid 1/2/4 columns"}.get(s, "stacked content block")


def user_flows(req: dict) -> dict:
    flows = [{"name": "Discover", "steps": ["Land on Home", "Scan highlights", "Open Rooms/Services", "Contact or Book"]}]
    if "booking" in req["features"]:
        steps = ["Open Rooms", "Choose a room", "Select dates and guests", "Enter contact details"]
        steps += ["Pay securely (Stripe)"] if "payments" in req["features"] else ["Submit request"]
        steps += ["See confirmation", "Receive confirmation email"]
        flows.append({"name": "Book a stay", "steps": steps})
    flows.append({"name": "Ask a question", "steps": ["Open Contact", "Fill form", "Submit", "See thank-you message"]})
    return {"flows": flows}


# ---------------------------------------------------------------- content
STYLE_VOICE = {
    "luxury": ("Refined", "timeless", "unhurried elegance"),
    "warm": ("Welcoming", "genuine", "a home from home"),
    "bold": ("Vivid", "confident", "energy"),
    "modern": ("Clear", "considered", "effortless simplicity"),
}

ROOM_COPY = [
    "A calm, light-filled room designed for restful nights.",
    "Extra space to unwind, with a seating area and generous bed.",
    "A separate living area for longer, more comfortable stays.",
    "Our most spacious option, ideal for special occasions.",
    "Room for the whole family, with flexible sleeping arrangements.",
    "Top-floor retreat with the finest finishes.",
]


def content(req: dict, smap: dict, wf: dict, style_key: str) -> dict:
    name = req.get("business_name") or "Your Business"
    loc = req.get("location")
    adj, adj2, phrase = STYLE_VOICE.get(style_key, STYLE_VOICE["modern"])
    sub = (req.get("business_subtype") or "").lower()
    ind = req["industry"]
    claims: list[str] = []
    noun = {"hospitality": f"{sub + ' ' if sub and sub != 'other' else ''}hotel"}.get(ind, "business")

    hero_title = {
        "hospitality": f"{adj} stays{(' in ' + loc) if loc else ''}",
        "restaurant": f"{adj} food{(' in ' + loc) if loc else ''}, made with care",
    }.get(ind, f"{name}: {phrase}")
    pages: dict[str, dict] = {}
    contact = req.get("contact") or {}
    if not contact.get("email"):
        claims.append("Contact email (placeholder shown)")
    if not contact.get("phone"):
        claims.append("Contact phone (placeholder shown)")
    rooms = []
    for i, r in enumerate(req.get("room_types") or []):
        rooms.append({"id": slug(r), "name": r, "summary": ROOM_COPY[i % len(ROOM_COPY)],
                      "price_from": None, "occupancy": 2 if i < 2 else 4,
                      "features": ["Free Wi-Fi", "Air conditioning", "Ensuite bathroom"]})
    if rooms:
        claims.append("Room prices, sizes and amenities (placeholders until confirmed)")
    highlights = {
        "hospitality": [("Prime location", f"Explore {loc or 'the area'} from your doorstep."),
                        ("Thoughtful service", "A team on hand to make every stay easy."),
                        ("Restful rooms", "Designed for comfort and quiet nights."),
                        ("Book direct", "The simplest way to reserve and manage your stay.")],
    }.get(ind, [("Quality", "Work delivered with care and attention to detail."),
                ("Experience", "A team that understands what you need."),
                ("Support", "Friendly help whenever you need it."),
                ("Value", "Clear, fair pricing with no surprises.")])
    for p in smap["pages"]:
        pages[p["id"]] = {"title": p["title"], "heading": p["title"] if p["title"] != "Home" else hero_title,
                          "intro": _page_intro(p["title"], name, noun, loc, adj2)}
    copy = {
        "brand": {"name": name, "tagline": f"{adj} {noun}{(' in ' + loc) if loc else ''}".strip()},
        "hero": {"title": hero_title,
                 "subtitle": f"Welcome to {name} — {phrase}{(' in the heart of ' + loc) if loc else ''}.",
                 "cta": smap["primary_cta"]["label"]},
        "intro": {"title": f"Welcome to {name}",
                  "body": f"{name} is a {noun} built around {phrase}. Every detail is designed to make your time with us easy and memorable."},
        "story": {"title": "Our story",
                  "body": f"[Client to supply: the story of {name} — when it opened, what makes it special, and the people behind it.]"},
        "highlights": [{"title": t, "body": b} for t, b in highlights],
        "rooms": rooms,
        "amenities": ["Free Wi-Fi", "24-hour reception", "Daily housekeeping", "Air conditioning", "Luggage storage", "Concierge"]
        if ind == "hospitality" else [],
        "reviews": [{"quote": "[Real guest review to be added]", "author": "Verified guest"} for _ in range(3)],
        "faq": _faq(req),
        "offers": [{"title": "Stay longer, save more", "body": "[Offer terms to be confirmed by the client]"}],
        "cta": {"title": "Ready when you are", "body": f"Plan your visit to {name} today.", "button": smap["primary_cta"]["label"]},
        "policies": ["Check-in from 15:00, check-out by 11:00 [confirm]", "Free cancellation up to 48 hours before arrival [confirm]",
                     "Payment is taken securely online" if "payments" in req["features"] else "Payment is taken at the property"]
        if ind == "hospitality" else [],
        "contact": {"email": contact.get("email") or "hello@example.com", "phone": contact.get("phone") or "+00 000 000 000",
                    "address": req.get("location") or "[Address to be confirmed]"},
        "blog": [{"title": f"Things to do near {name}", "excerpt": "[Draft — to be written once the local guide is confirmed]"}],
        "pages": pages,
        "footer": f"© {name}. All rights reserved.",
    }
    if any(r.startswith("[") for r in [copy["story"]["body"]]):
        claims.append("Business story / history")
    if "reviews" in req["features"]:
        claims.append("Guest reviews must be real — placeholders are never published as genuine")
    if "offers" in req["features"]:
        claims.append("Offer terms")
    copy["claims_to_confirm"] = claims
    return copy


def _page_intro(title, name, noun, loc, adj2) -> str:
    return {
        "Rooms": f"Choose the room that suits your stay at {name}.",
        "Booking": "Tell us your dates and we'll take care of the rest.",
        "About": f"The people, place and ideas behind {name}.",
        "Contact": "We usually reply within one working day.",
        "Gallery": f"A glimpse of {name}.",
        "FAQ": "Answers to the questions we hear most often.",
    }.get(title, f"{title} at {name}.")


def _faq(req):
    items = [("How do I get in touch?", "Use the contact form or call us — details are on the Contact page.")]
    if req["industry"] == "hospitality":
        items = [("What time is check-in?", "Check-in is from 15:00 and check-out by 11:00 [confirm]."),
                 ("Is parking available?", "[Client to confirm parking arrangements.]"),
                 ("Can I cancel my booking?", "[Client to confirm cancellation policy.]")] + items
    return [{"q": q, "a": a} for q, a in items]


def seo_plan(req: dict, smap: dict, copy: dict) -> dict:
    name = copy["brand"]["name"]
    loc = req.get("location")
    kw_base = {"hospitality": ["hotel", "boutique hotel", "hotel rooms", "book hotel"]}.get(req["industry"], [req["project_type"]])
    keywords = [f"{k} {loc}".strip() if loc else k for k in kw_base]
    pages = []
    for p in smap["pages"]:
        t = f"{p['title']} | {name}" if p["title"] != "Home" else f"{name}{' — ' + copy['brand']['tagline'] if copy['brand']['tagline'] else ''}"
        d = copy["pages"][p["id"]]["intro"]
        if p["title"] == "Home":
            d = copy["hero"]["subtitle"]
        pages.append({"page": p["id"], "title": t[:60], "description": d[:155], "h1": copy["pages"][p["id"]]["heading"]})
    sd = {"@context": "https://schema.org", "@type": "Hotel" if req["industry"] == "hospitality" else "LocalBusiness",
          "name": name}
    if loc:
        sd["address"] = loc
    return {"keywords": keywords, "pages": pages, "structured_data": sd, "robots": "index, follow",
            "sitemap_xml": True, "canonical_base": "https://" + (req.get("domain") if req.get("domain") and "." in str(req.get("domain")) and " " not in str(req.get("domain")) else "example.com")}
