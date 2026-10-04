"""Static site generator used by the Frontend Developer agent.

Consumes ONLY approved machine-readable artifacts (sitemap, wireframes, design system,
content, seo plan) and writes a responsive, accessible, dependency-free site into
`<workspace>/source/site`. No external scripts, fonts are system fallbacks unless the
client hosts their own.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

E = html.escape


def _css(ds: dict) -> str:
    c, t, sp = ds["colors"], ds["typography"], ds["spacing"]
    radius = ds.get("radius", {}).get("md", "10px")
    return f""":root{{--bg:{c['background']};--surface:{c['surface']};--primary:{c['primary']};--on-primary:{c['on_primary']};
--accent:{c['accent']};--emphasis:{c.get('emphasis', c['text'])};--text:{c['text']};--muted:{c['muted']};--border:{c['border']};
--font-heading:{t['heading']};--font-body:{t['body']};--radius:{radius};--space:{sp['unit']}px;--maxw:{ds['layout']['max_width']}px}}
*,*::before,*::after{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-body);font-size:{t['base_size']}px;line-height:1.6}}
img{{max-width:100%;display:block}}
a{{color:inherit}}
h1,h2,h3{{font-family:var(--font-heading);line-height:1.15;margin:0 0 calc(var(--space)*2)}}
h1{{font-size:clamp(2.1rem,5vw,{t['scale']['h1']})}} h2{{font-size:clamp(1.6rem,3.2vw,{t['scale']['h2']})}} h3{{font-size:{t['scale']['h3']}}}
p{{margin:0 0 calc(var(--space)*2)}}
.skip{{position:absolute;left:-999px;top:0;background:var(--primary);color:var(--on-primary);padding:8px 12px;z-index:10}}
.skip:focus{{left:8px}}
:focus-visible{{outline:3px solid var(--emphasis);outline-offset:2px}}
.wrap{{max-width:var(--maxw);margin:0 auto;padding:0 calc(var(--space)*2.5)}}
header.site{{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--border)}}
header.site .wrap{{display:flex;align-items:center;justify-content:space-between;min-height:68px;gap:16px}}
.brand{{font-family:var(--font-heading);font-size:1.35rem;font-weight:700;text-decoration:none;letter-spacing:.02em}}
nav.main ul{{list-style:none;display:flex;gap:22px;margin:0;padding:0;align-items:center}}
nav.main a{{text-decoration:none;color:var(--muted);font-weight:500;padding:10px 2px;display:inline-block}}
nav.main a[aria-current=page],nav.main a:hover{{color:var(--text)}}
nav.main a.nav-cta{{display:inline-flex;padding:0 18px;color:var(--on-primary);min-height:42px}}
.menu-btn{{display:none;background:none;border:1px solid var(--border);color:var(--text);border-radius:8px;min-height:44px;min-width:44px}}
.btn{{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:0 22px;border-radius:var(--radius);
background:var(--primary);color:var(--on-primary);text-decoration:none;font-weight:600;border:0;cursor:pointer;font-size:1rem}}
.btn.ghost{{background:transparent;color:var(--text);border:1px solid var(--border)}}
section{{padding:calc(var(--space)*9) 0}}
.hero{{min-height:72vh;display:flex;align-items:flex-end;padding-bottom:calc(var(--space)*10);
background:linear-gradient(180deg,transparent 0%,var(--bg) 96%),radial-gradient(1200px 500px at 70% 20%,color-mix(in srgb,var(--accent) 55%,transparent),transparent),
linear-gradient(135deg,var(--surface),color-mix(in srgb,var(--primary) 25%,var(--bg)))}}
.hero>.wrap{{width:100%}}
.hero p.lead{{font-size:1.2rem;color:var(--muted);max-width:640px}}
.eyebrow{{text-transform:uppercase;letter-spacing:.18em;font-size:.78rem;color:var(--emphasis);font-weight:600;margin-bottom:12px;display:block}}
.page-header{{padding:calc(var(--space)*8) 0 calc(var(--space)*3);border-bottom:1px solid var(--border)}}
.grid{{display:grid;gap:calc(var(--space)*3);grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:calc(var(--space)*3);overflow:hidden}}
.ph{{aspect-ratio:4/3;border-radius:calc(var(--radius) - 2px);margin:-8px -8px 16px;display:flex;align-items:flex-end;padding:10px;font-size:.75rem;color:var(--on-primary);
background:linear-gradient(135deg,color-mix(in srgb,var(--primary) 70%,var(--bg)),color-mix(in srgb,var(--accent) 70%,var(--bg)))}}
.muted{{color:var(--muted)}}
.quote{{font-family:var(--font-heading);font-size:1.15rem}}
form.form{{display:grid;gap:16px;max-width:640px}}
.row2{{display:grid;gap:16px;grid-template-columns:1fr 1fr}}
label{{display:grid;gap:6px;font-weight:500}}
input,select,textarea{{font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;min-height:46px}}
.notice{{border:1px solid var(--border);border-left:4px solid var(--primary);padding:12px 16px;border-radius:8px;background:var(--surface)}}
.notice[hidden]{{display:none}}
details{{border-bottom:1px solid var(--border);padding:14px 0}} summary{{cursor:pointer;font-weight:600}}
footer.site{{border-top:1px solid var(--border);padding:calc(var(--space)*5) 0;color:var(--muted);font-size:.92rem}}
footer.site .wrap{{display:flex;flex-wrap:wrap;justify-content:space-between;gap:16px}}
@media (max-width:820px){{
  .menu-btn{{display:inline-flex;align-items:center;justify-content:center}}
  nav.main{{display:none;position:absolute;left:0;right:0;top:68px;background:var(--bg);border-bottom:1px solid var(--border)}}
  nav.main.open{{display:block}}
  nav.main ul{{flex-direction:column;align-items:stretch;gap:0;padding:8px 20px 16px}}
  .row2{{grid-template-columns:1fr}}
  section{{padding:calc(var(--space)*6) 0}}
}}
@media (prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}}}
"""


JS = r"""(function(){
  var btn=document.querySelector('.menu-btn'),nav=document.querySelector('nav.main');
  if(btn&&nav){btn.addEventListener('click',function(){var o=nav.classList.toggle('open');btn.setAttribute('aria-expanded',o?'true':'false');});}
  var API=(window.SITE_CONFIG&&window.SITE_CONFIG.apiBase)||'';
  function show(el,msg){el.textContent=msg;el.hidden=false;el.focus&&el.focus();}
  document.querySelectorAll('form[data-endpoint]').forEach(function(f){
    f.addEventListener('submit',function(ev){
      ev.preventDefault();
      var out=f.querySelector('.notice');
      if(!f.checkValidity()){f.reportValidity();return;}
      var data={};new FormData(f).forEach(function(v,k){data[k]=v;});
      if(data.check_in&&data.check_out){
        var today=new Date().toISOString().slice(0,10);
        if(data.check_in<today){return show(out,'Check-in cannot be in the past.');}
        if(data.check_out<=data.check_in){return show(out,'Check-out must be after check-in.');}
      }
      if(!API){return show(out,'This preview is not connected to the live API yet, so nothing was sent. Your details were valid.');}
      fetch(API+f.getAttribute('data-endpoint'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
        .then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
        .then(function(res){show(out,res.ok?(res.j.message||'Thank you — we have received your request.'):(res.j.error||'Something went wrong.'));if(res.ok)f.reset();})
        .catch(function(){show(out,'We could not reach the server. Please try again or contact us directly.');});
    });
  });
  var y=document.getElementById('year'); if(y) y.textContent=new Date().getFullYear();
})();
"""


class SiteBuilder:
    def __init__(self, req, smap, wf, ds, copy, seo):
        self.req, self.smap, self.wf, self.ds, self.copy, self.seo = req, smap, wf, ds, copy, seo
        self.pages = {p["id"]: p for p in smap["pages"]}
        self.seo_pages = {p["page"]: p for p in seo.get("pages", [])}

    def _href(self, pid: str) -> str:
        p = self.pages.get(pid)
        return p["path"] if p else "index.html"

    def nav(self, current: str) -> str:
        items = []
        for p in self.smap["pages"]:
            if not p.get("in_nav", True):
                continue
            cur = ' aria-current="page"' if p["id"] == current else ""
            items.append(f'<li><a href="{p["path"]}"{cur}>{E(p["title"])}</a></li>')
        cta = self.smap["primary_cta"]
        if cta["target"] in self.pages:
            items.append(f'<li><a class="btn nav-cta" href="{self._href(cta["target"])}">{E(cta["label"])}</a></li>')
        return "".join(items)

    def page(self, p: dict, sections_html: str) -> str:
        s = self.seo_pages.get(p["id"], {})
        title = s.get("title") or f"{p['title']} | {self.copy['brand']['name']}"
        desc = s.get("description") or self.copy["pages"][p["id"]]["intro"]
        canonical = self.seo.get("canonical_base", "https://example.com").rstrip("/") + "/" + ("" if p["path"] == "index.html" else p["path"])
        sd = ""
        if p["path"] == "index.html" and self.seo.get("structured_data"):
            sd = f'<script type="application/ld+json">{json.dumps(self.seo["structured_data"])}</script>'
        lang = "en"
        return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta name="robots" content="{E(self.seo.get('robots', 'index, follow'))}">
<link rel="canonical" href="{E(canonical)}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:type" content="website">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src *; form-action 'self'">
<link rel="stylesheet" href="assets/styles.css">
{sd}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap">
<a class="brand" href="index.html">{E(self.copy['brand']['name'])}</a>
<button class="menu-btn" type="button" aria-expanded="false" aria-controls="primary-nav">Menu</button>
<nav class="main" id="primary-nav" aria-label="Main"><ul>{self.nav(p['id'])}</ul></nav>
</div></header>
<main id="main">
{sections_html}
</main>
<footer class="site"><div class="wrap">
<span>© <span id="year">2026</span> {E(self.copy['brand']['name'])}</span>
<span>{E(self.copy['contact']['email'])} · {E(self.copy['contact']['phone'])}</span>
</div></footer>
<script src="assets/config.js" defer></script>
<script src="assets/site.js" defer></script>
</body>
</html>
"""

    # ------------------------------------------------------------ sections
    def section(self, kind: str, p: dict) -> str:
        c = self.copy
        pc = c["pages"][p["id"]]
        cta = self.smap["primary_cta"]
        cta_href = self._href(cta["target"])
        w = '<div class="wrap">'
        if kind == "hero":
            return (f'<section class="hero" aria-label="Introduction">{w}<span class="eyebrow">{E(c["brand"]["tagline"])}</span>'
                    f'<h1>{E(c["hero"]["title"])}</h1><p class="lead">{E(c["hero"]["subtitle"])}</p>'
                    f'<p><a class="btn" href="{cta_href}">{E(c["hero"]["cta"])}</a> '
                    f'<a class="btn ghost" href="{self._href("about") if "about" in self.pages else "#main"}">Discover more</a></p></div></section>')
        if kind == "page_header":
            return f'<div class="page-header">{w}<h1>{E(pc["heading"])}</h1><p class="muted">{E(pc["intro"])}</p></div></div>'
        if kind == "intro":
            return f'<section>{w}<h2>{E(c["intro"]["title"])}</h2><p class="muted" style="max-width:720px">{E(c["intro"]["body"])}</p></div></section>'
        if kind == "story":
            return f'<section>{w}<h2>{E(c["story"]["title"])}</h2><p class="muted" style="max-width:720px">{E(c["story"]["body"])}</p></div></section>'
        if kind == "highlights":
            cards = "".join(f'<div class="card"><h3>{E(h["title"])}</h3><p class="muted">{E(h["body"])}</p></div>' for h in c["highlights"])
            return f'<section>{w}<h2>Why stay with us</h2><div class="grid">{cards}</div></div></section>' if self.req["industry"] == "hospitality" \
                else f'<section>{w}<h2>What we offer</h2><div class="grid">{cards}</div></div></section>'
        if kind in ("featured_rooms", "room_list"):
            rooms = c["rooms"][:3] if kind == "featured_rooms" else c["rooms"]
            if not rooms:
                return ""
            det = self._href("room-details")
            cards = "".join(
                f'<article class="card"><div class="ph" role="img" aria-label="Photo placeholder: {E(r["name"])}">Photo placeholder</div>'
                f'<h3>{E(r["name"])}</h3><p class="muted">{E(r["summary"])}</p><p class="muted">Sleeps {r["occupancy"]}</p>'
                f'<a class="btn ghost" href="{det}#{r["id"]}">View {E(r["name"])}</a></article>' for r in rooms)
            title = "Our rooms" if kind == "featured_rooms" else "Rooms & suites"
            return f'<section>{w}<h2>{title}</h2><div class="grid">{cards}</div></div></section>'
        if kind == "room_detail":
            blocks = "".join(
                f'<article class="card" id="{r["id"]}" style="margin-bottom:24px"><div class="ph" role="img" aria-label="Photo placeholder: {E(r["name"])}">Photo placeholder</div>'
                f'<h2>{E(r["name"])}</h2><p>{E(r["summary"])}</p><ul>{"".join(f"<li>{E(x)}</li>" for x in r["features"])}</ul>'
                f'<p class="muted">Sleeps {r["occupancy"]} · Rates shown at booking</p><a class="btn" href="{cta_href}?room={r["id"]}">Book {E(r["name"])}</a></article>'
                for r in c["rooms"])
            return f'<section>{w}{blocks}</div></section>'
        if kind == "amenities" and c["amenities"]:
            lis = "".join(f'<li>{E(a)}</li>' for a in c["amenities"])
            return f'<section>{w}<h2>Amenities</h2><ul class="grid" style="list-style:none;padding:0">{lis}</ul></div></section>'
        if kind == "reviews":
            cards = "".join(f'<figure class="card"><blockquote class="quote">{E(r["quote"])}</blockquote><figcaption class="muted">— {E(r["author"])}</figcaption></figure>' for r in c["reviews"])
            return f'<section>{w}<h2>What guests say</h2><div class="grid">{cards}</div></div></section>'
        if kind == "cta":
            return (f'<section>{w}<div class="card" style="text-align:center;padding:48px"><h2>{E(c["cta"]["title"])}</h2>'
                    f'<p class="muted">{E(c["cta"]["body"])}</p><a class="btn" href="{cta_href}">{E(c["cta"]["button"])}</a></div></div></section>')
        if kind == "booking_form":
            opts = "".join(f'<option value="{r["id"]}">{E(r["name"])}</option>' for r in c["rooms"]) or '<option value="standard">Standard room</option>'
            pay = "payments" in self.req["features"]
            return f"""<section>{w}<form class="form" data-endpoint="/api/bookings" novalidate>
<label>Room<select name="room" required>{opts}</select></label>
<div class="row2"><label>Check-in<input type="date" name="check_in" required></label><label>Check-out<input type="date" name="check_out" required></label></div>
<div class="row2"><label>Adults<input type="number" name="adults" min="1" max="8" value="2" required></label><label>Children<input type="number" name="children" min="0" max="8" value="0"></label></div>
<label>Full name<input type="text" name="name" autocomplete="name" required></label>
<div class="row2"><label>Email<input type="email" name="email" autocomplete="email" required></label><label>Phone<input type="tel" name="phone" autocomplete="tel"></label></div>
<label>Special requests<textarea name="requests" rows="3"></textarea></label>
<p class="muted">{'You will be taken to secure Stripe checkout to pay.' if pay else 'No payment is taken now — pay at the property.'}</p>
<button class="btn" type="submit">{'Continue to payment' if pay else 'Request booking'}</button>
<p class="notice" role="status" tabindex="-1" hidden></p>
</form></div></section>"""
        if kind == "policies" and c["policies"]:
            return f'<section>{w}<h2>Good to know</h2><ul>{"".join(f"<li>{E(x)}</li>" for x in c["policies"])}</ul></div></section>'
        if kind == "contact_form":
            return f"""<section>{w}<h2>Send us a message</h2><form class="form" data-endpoint="/api/enquiries" novalidate>
<div class="row2"><label>Name<input type="text" name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label></div>
<label>Message<textarea name="message" rows="5" required></textarea></label>
<button class="btn" type="submit">Send message</button><p class="notice" role="status" tabindex="-1" hidden></p></form></div></section>"""
        if kind == "contact_details":
            ct = c["contact"]
            return (f'<section>{w}<h2>Contact details</h2><p>Email: <a href="mailto:{E(ct["email"])}">{E(ct["email"])}</a><br>'
                    f'Phone: <a href="tel:{E(ct["phone"].replace(" ", ""))}">{E(ct["phone"])}</a><br>Address: {E(ct["address"])}</p></div></section>')
        if kind == "map" and self.req.get("location"):
            q = E(self.req["location"].replace(" ", "+"))
            return f'<section>{w}<h2>Find us</h2><p><a class="btn ghost" href="https://www.google.com/maps/search/?api=1&amp;query={q}" target="_blank" rel="noopener noreferrer">Open in Google Maps</a></p></div></section>'
        if kind == "gallery_grid":
            tiles = "".join(f'<div class="ph" role="img" aria-label="Gallery photo placeholder {i}" style="margin:0">Photo placeholder</div>' for i in range(1, 10))
            return f'<section>{w}<div class="grid">{tiles}</div></div></section>'
        if kind == "faq":
            items = "".join(f'<details><summary>{E(f["q"])}</summary><p class="muted">{E(f["a"])}</p></details>' for f in c["faq"])
            return f'<section>{w}<h2>Frequently asked questions</h2>{items}</div></section>'
        if kind == "offers":
            cards = "".join(f'<div class="card"><h3>{E(o["title"])}</h3><p class="muted">{E(o["body"])}</p></div>' for o in c["offers"])
            return f'<section>{w}<h2>Offers</h2><div class="grid">{cards}</div></div></section>'
        if kind == "newsletter":
            return f"""<section>{w}<div class="card"><h2>Stay in touch</h2><form class="form" data-endpoint="/api/newsletter" novalidate>
<label>Email address<input type="email" name="email" autocomplete="email" required></label><button class="btn" type="submit">Subscribe</button>
<p class="notice" role="status" tabindex="-1" hidden></p></form></div></div></section>"""
        if kind == "blog_list":
            cards = "".join(f'<article class="card"><h3>{E(b["title"])}</h3><p class="muted">{E(b["excerpt"])}</p></article>' for b in c["blog"])
            return f'<section>{w}<div class="grid">{cards}</div></div></section>'
        if kind == "product_grid":
            cats = self.req.get("product_categories") or ["Featured"]
            cards = "".join(f'<article class="card"><div class="ph" role="img" aria-label="Product photo placeholder">Photo placeholder</div><h3>{E(x)}</h3><p class="muted">[Products to be imported]</p></article>' for x in cats)
            return f'<section>{w}<div class="grid">{cards}</div></div></section>'
        if kind in ("login_form", "signup_form"):
            ep = "/api/auth/login" if kind == "login_form" else "/api/auth/signup"
            extra = '<label>Name<input type="text" name="name" autocomplete="name" required></label>' if kind == "signup_form" else ""
            return f"""<section>{w}<form class="form" data-endpoint="{ep}" novalidate>{extra}
<label>Email<input type="email" name="email" autocomplete="email" required></label>
<label>Password<input type="password" name="password" autocomplete="{'new-password' if kind == 'signup_form' else 'current-password'}" minlength="8" required></label>
<button class="btn" type="submit">{'Create account' if kind == 'signup_form' else 'Log in'}</button><p class="notice" role="status" tabindex="-1" hidden></p></form></div></section>"""
        if kind == "admin_panel":
            return f'<section>{w}<div class="notice">The admin dashboard is served by the backend API (see <code>source/api</code>). Sign in there to manage bookings, enquiries and content.</div></div></section>'
        if kind in ("dashboard_stats", "chat_widget", "pricing_table", "team", "product_detail", "cart", "checkout_form"):
            return f'<section>{w}<div class="notice">{E(kind.replace("_", " ").title())}: implemented by the application layer in <code>source/api</code>; this static preview shows layout only.</div></div></section>'
        return ""

    def build(self, out: Path) -> list[str]:
        (out / "assets").mkdir(parents=True, exist_ok=True)
        written = []
        (out / "assets" / "styles.css").write_text(_css(self.ds))
        (out / "assets" / "site.js").write_text(JS)
        (out / "assets" / "config.js").write_text("window.SITE_CONFIG = { apiBase: '' }; // set to your API origin at deployment\n")
        written += ["assets/styles.css", "assets/site.js", "assets/config.js"]
        screens = {s["page"]: s["sections"] for s in self.wf["screens"]}
        for p in self.smap["pages"]:
            secs = "\n".join(self.section(s["type"], p) for s in screens.get(p["id"], []))
            (out / p["path"]).write_text(self.page(p, secs))
            written.append(p["path"])
        base = self.seo.get("canonical_base", "https://example.com").rstrip("/")
        urls = "".join(f"<url><loc>{E(base)}/{'' if p['path'] == 'index.html' else p['path']}</loc></url>" for p in self.smap["pages"])
        (out / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
        (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
        written += ["sitemap.xml", "robots.txt"]
        return written
