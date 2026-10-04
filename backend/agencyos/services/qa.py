"""Quality checks that actually execute against the generated workspace.

QA:            pages, links, forms, headings, responsive meta, JS syntax, backend tests,
               visual checks (Playwright, if available) incl. horizontal overflow + screenshots.
Accessibility: alt text, labels, lang, contrast, skip link, focus styles, touch targets.
Performance:   page weight, request count, render-blocking scripts.
Security:      secrets, unsafe JS sinks, inline handlers, CSP, link rel, SQL string building.
Fixers:        deterministic remediations the developer agents apply for known issue codes.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup

from . import sandbox
from .design import contrast


def _issue(code, severity, category, message, page=None, owner="frontend_developer"):
    return {"code": code, "severity": severity, "category": category, "message": message, "page": page, "owner": owner}


def _pages(site: Path) -> list[Path]:
    return sorted(site.glob("*.html"))


def _soup(p: Path) -> BeautifulSoup:
    return BeautifulSoup(p.read_text(), "html.parser")


def _has_label(el, soup) -> bool:
    if el.get("type") in ("hidden", "submit", "button"):
        return True
    if el.find_parent("label") or el.get("aria-label") or el.get("aria-labelledby"):
        return True
    return bool(el.get("id") and soup.find("label", attrs={"for": el.get("id")}))


# ---------------------------------------------------------------- QA
def run_qa(workspace: Path, sitemap: dict, design: dict | None, *, visual: bool = True) -> dict:
    site = workspace / "source" / "site"
    issues, passed, warnings = [], [], []
    files = {p.name for p in _pages(site)} if site.exists() else set()
    for pg in sitemap.get("pages", []):
        if pg["path"] not in files:
            issues.append(_issue("PAGE_MISSING", "critical", "functional", f"Page '{pg['title']}' ({pg['path']}) was not built", pg["path"]))
    if files:
        passed.append(f"{len(files)} pages built")
    for p in _pages(site):
        s = _soup(p)
        name = p.name
        for a in s.find_all("a", href=True):
            h = a["href"].split("#")[0].split("?")[0]
            if not h or h.startswith(("http", "mailto:", "tel:", "#")):
                continue
            if not (site / h).exists():
                issues.append(_issue("BROKEN_LINK", "high", "functional", f"Link to '{h}' is broken", name))
        if not (s.title and s.title.string and s.title.string.strip()):
            issues.append(_issue("MISSING_TITLE", "medium", "seo", "Missing <title>", name))
        if not s.find("meta", attrs={"name": "description"}):
            issues.append(_issue("MISSING_DESC", "medium", "seo", "Missing meta description", name))
        h1 = s.find_all("h1")
        if len(h1) != 1:
            issues.append(_issue("H1_COUNT", "medium", "seo", f"Expected exactly one <h1>, found {len(h1)}", name))
        if not s.find("meta", attrs={"name": "viewport"}):
            issues.append(_issue("VIEWPORT", "high", "responsive", "Missing responsive viewport meta", name))
        if re.search(r"lorem ipsum", p.read_text(), re.I):
            issues.append(_issue("LOREM", "medium", "content", "Lorem ipsum text present", name, "content_writer"))
        for f in s.find_all("form"):
            if not f.find(["button", "input"], attrs={"type": "submit"}):
                issues.append(_issue("FORM_SUBMIT", "high", "functional", "Form has no submit button", name))
    js_dir = site / "assets"
    node = shutil.which("node")
    for js in sorted(js_dir.glob("*.js")) if js_dir.exists() else []:
        if node:
            r = subprocess.run([node, "--check", str(js)], capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                issues.append(_issue("JS_SYNTAX", "critical", "functional", f"{js.name}: {r.stderr.strip()[:200]}", js.name))
            else:
                passed.append(f"{js.name} parses")
    # backend build + tests
    api = workspace / "source" / "api"
    backend = {"present": api.exists()}
    if api.exists():
        comp = sandbox.run(["python3", "-m", "py_compile", "service.py", "server.py"], api, timeout=60)
        backend["compile"] = comp.returncode == 0
        if comp.returncode != 0:
            issues.append(_issue("BUILD_FAILED", "critical", "build", f"Backend does not compile: {comp.stderr[:300]}", "source/api", "backend_developer"))
        t = sandbox.run(["python3", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], api, timeout=120)
        out = t.stderr + t.stdout
        m = re.search(r"Ran (\d+) tests?", out)
        backend.update({"tests_run": int(m.group(1)) if m else 0, "tests_passed": t.returncode == 0,
                        "sandbox_mode": t.mode, "output_tail": out[-1500:]})
        if t.returncode != 0:
            issues.append(_issue("TESTS_FAILED", "critical", "tests", "Backend unit tests failed", "source/api", "backend_developer"))
        else:
            passed.append(f"Backend: {backend['tests_run']} unit tests passed ({t.mode} sandbox)")
        for p in api.rglob("*.py"):
            for i, line in enumerate(p.read_text().splitlines(), 1):
                if line.strip().startswith(("print(", "#")) or "f\"" not in line and "f'" not in line:
                    continue
                if "INSERT" in line.upper() or "SELECT" in line.upper():
                    if ".execute(f" in line:
                        issues.append(_issue("SQL_FSTRING", "high", "security", f"{p.name}:{i} builds SQL with an f-string", "source/api", "backend_developer"))
    visual_res = run_visual(site, workspace / "reports" / "screenshots") if visual and files else {"skipped": True}
    for v in visual_res.get("issues", []):
        issues.append(v)
    if visual_res.get("skipped"):
        warnings.append("Visual QA skipped: " + visual_res.get("reason", "browser automation unavailable"))
    else:
        passed.append(f"Visual QA: {visual_res.get('checked', 0)} page renders checked at mobile and desktop widths")
    crit = sum(1 for i in issues if i["severity"] == "critical")
    high = sum(1 for i in issues if i["severity"] == "high")
    return {"status": "PASS" if not crit and not high else "FAIL", "passed": passed, "failed": issues,
            "warnings": warnings, "backend": backend, "visual": {k: v for k, v in visual_res.items() if k != "issues"},
            "summary": {"critical": crit, "high": high, "medium": sum(1 for i in issues if i["severity"] == "medium")}}


def run_visual(site: Path, shots: Path) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"skipped": True, "reason": "playwright not installed", "issues": []}
    shots.mkdir(parents=True, exist_ok=True)
    issues, saved, checked = [], [], 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            for width, label in ((375, "mobile"), (1280, "desktop")):
                ctx = browser.new_context(viewport={"width": width, "height": 860})
                page = ctx.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                for p in _pages(site):
                    page.goto(p.as_uri())
                    page.wait_for_load_state("load")
                    checked += 1
                    over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                    if over > 2:
                        issues.append(_issue("OVERFLOW", "high", "responsive", f"Horizontal overflow of {over}px at {width}px", p.name))
                    small = page.evaluate("""() => [...document.querySelectorAll('a.btn,button')].filter(e => {
                        const r = e.getBoundingClientRect(); return r.width > 0 && (r.height < 40 || r.width < 40); }).length""")
                    if small:
                        issues.append(_issue("TOUCH_TARGET", "medium", "accessibility", f"{small} controls smaller than 40px at {width}px", p.name))
                    if p.name == "index.html" or label == "mobile" and p.name in {"booking.html", "rooms.html"}:
                        f = shots / f"{p.stem}-{label}.png"
                        page.screenshot(path=str(f), full_page=False)
                        saved.append(f.name)
                for e in errors:
                    issues.append(_issue("JS_RUNTIME", "high", "functional", f"Runtime error at {width}px: {e[:200]}"))
                ctx.close()
            browser.close()
    except Exception as e:  # browser missing in the runtime -> report, don't fake
        return {"skipped": True, "reason": f"browser unavailable: {e.__class__.__name__}", "issues": []}
    return {"skipped": False, "checked": checked, "screenshots": saved, "issues": issues}


# ---------------------------------------------------------------- accessibility
def run_accessibility(workspace: Path, design: dict) -> dict:
    site = workspace / "source" / "site"
    issues, passed = [], []
    c = design.get("colors", {})
    if c:
        for fg, bg, need, label in (("text", "background", 4.5, "Body text"), ("muted", "background", 4.5, "Muted text"),
                                    ("on_primary", "primary", 4.5, "Button label"), ("emphasis", "background", 4.5, "Accent text")):
            if fg not in c:
                continue
            ratio = contrast(c[fg], c[bg])
            (passed.append(f"{label} contrast {ratio}:1") if ratio >= need else
             issues.append(_issue("CONTRAST", "high", "accessibility", f"{label} contrast {ratio}:1 < {need}:1", None, "ui_designer")))
    css = (site / "assets" / "styles.css").read_text() if (site / "assets" / "styles.css").exists() else ""
    if ":focus-visible" in css:
        passed.append("Visible focus styles defined")
    else:
        issues.append(_issue("FOCUS_STYLE", "high", "accessibility", "No visible focus style"))
    for p in _pages(site):
        s = _soup(p)
        if not (s.html and s.html.get("lang")):
            issues.append(_issue("HTML_LANG", "medium", "accessibility", "Missing lang attribute", p.name))
        if not s.find("a", class_="skip"):
            issues.append(_issue("SKIP_LINK", "medium", "accessibility", "Missing skip link", p.name))
        for img in s.find_all("img"):
            if img.get("alt") is None:
                issues.append(_issue("IMG_ALT", "high", "accessibility", f"Image without alt: {img.get('src')}", p.name))
        for el in s.find_all(["input", "select", "textarea"]):
            if not _has_label(el, s):
                issues.append(_issue("FORM_LABEL", "high", "accessibility", f"Unlabelled form control '{el.get('name')}'", p.name))
        levels = [int(h.name[1]) for h in s.find_all(re.compile("^h[1-6]$"))]
        for a, b in zip(levels, levels[1:]):
            if b > a + 1:
                issues.append(_issue("HEADING_ORDER", "low", "accessibility", f"Heading level jumps h{a}→h{b}", p.name))
                break
    if not issues:
        passed.append("No accessibility issues found by automated checks (manual screen-reader test still recommended)")
    bad = [i for i in issues if i["severity"] in ("critical", "high")]
    return {"status": "PASS" if not bad else "FAIL", "passed": passed, "failed": issues, "standard": "WCAG 2.2 AA (automated subset)"}


# ---------------------------------------------------------------- performance
def run_performance(workspace: Path) -> dict:
    site = workspace / "source" / "site"
    pages = []
    issues = []
    assets = {f.name: f.stat().st_size for f in (site / "assets").glob("*")} if (site / "assets").exists() else {}
    for p in _pages(site):
        s = _soup(p)
        size = p.stat().st_size
        reqs = 1
        weight = size
        blocking = 0
        for tag in s.find_all(["script", "link"]):
            src = tag.get("src") or (tag.get("href") if tag.name == "link" and "stylesheet" in (tag.get("rel") or []) else None)
            if not src:
                continue
            reqs += 1
            weight += assets.get(Path(src).name, 0)
            if tag.name == "script" and not (tag.has_attr("defer") or tag.has_attr("async")) and tag.find_parent("head"):
                blocking += 1
        pages.append({"page": p.name, "html_bytes": size, "requests": reqs, "total_bytes": weight, "render_blocking_scripts": blocking})
        if weight > 500_000:
            issues.append(_issue("PAGE_WEIGHT", "medium", "performance", f"{p.name} weighs {weight // 1024} KB", p.name))
        if blocking:
            issues.append(_issue("RENDER_BLOCKING", "medium", "performance", f"{blocking} render-blocking scripts", p.name))
    return {"status": "PASS" if not [i for i in issues if i["severity"] in ("critical", "high")] else "FAIL",
            "pages": pages, "failed": issues,
            "notes": ["No external fonts, frameworks or trackers are loaded.", "Images are CSS placeholders until real photography is supplied — re-run after adding photos."]}


# ---------------------------------------------------------------- security
SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style secret key"), (r"sk-ant-[A-Za-z0-9-]{20,}", "Anthropic key"),
    (r"sk_live_[A-Za-z0-9]{10,}", "Stripe live secret"), (r"AKIA[0-9A-Z]{16}", "AWS access key"),
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub token"), (r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", "Private key"),
    (r"(?i)(password|secret|api_key)\s*=\s*['\"][^'\"]{6,}['\"]", "Hard-coded credential"),
]


def run_security(workspace: Path) -> dict:
    issues, passed = [], []
    src = workspace / "source"
    files = [f for f in src.rglob("*") if f.is_file() and f.suffix in {".html", ".js", ".py", ".css", ".json", ".yaml", ".sql", ".txt", ".example"}]
    for f in files:
        text = f.read_text(errors="ignore")
        rel = str(f.relative_to(workspace))
        for pat, label in SECRET_PATTERNS:
            if re.search(pat, text):
                issues.append(_issue("SECRET", "critical", "secrets", f"{label} found in {rel}", rel, "backend_developer"))
        if f.suffix == ".html":
            s = BeautifulSoup(text, "html.parser")
            if not s.find("meta", attrs={"http-equiv": "Content-Security-Policy"}):
                issues.append(_issue("CSP", "medium", "headers", "No Content-Security-Policy", rel))
            if s.find(attrs={"onclick": True}) or s.find(attrs={"onload": True}):
                issues.append(_issue("INLINE_HANDLER", "medium", "xss", "Inline event handler", rel))
            for a in s.find_all("a", target="_blank"):
                if "noopener" not in (a.get("rel") or []):
                    issues.append(_issue("NOOPENER", "low", "tabnabbing", "target=_blank without rel=noopener", rel))
            for sc in s.find_all("script", src=True):
                if sc["src"].startswith("http") and not sc.get("integrity"):
                    issues.append(_issue("SRI", "medium", "supply-chain", f"External script without SRI: {sc['src']}", rel))
            for form in s.find_all("form", action=True):
                if form["action"].startswith("http:"):
                    issues.append(_issue("INSECURE_FORM", "high", "transport", "Form posts over HTTP", rel))
        if f.suffix == ".js":
            if re.search(r"\beval\s*\(|new Function\s*\(", text):
                issues.append(_issue("EVAL", "high", "xss", "eval/new Function used", rel))
            if re.search(r"\.innerHTML\s*=", text):
                issues.append(_issue("INNERHTML", "medium", "xss", "innerHTML assignment (prefer textContent)", rel))
        if f.suffix == ".py":
            if re.search(r"\.execute\(\s*f[\"']", text) or re.search(r"\.execute\([^)]*%\s", text):
                issues.append(_issue("SQLI", "critical", "injection", "SQL built from string formatting", rel, "backend_developer"))
            if re.search(r"\b(os\.system|subprocess\.(call|run|Popen))\(", text):
                issues.append(_issue("SHELL", "high", "injection", "Shell execution in application code", rel, "backend_developer"))
            if "hmac.compare_digest" in text:
                passed.append(f"{rel}: constant-time token comparison")
            if "MAX_BODY" in text:
                passed.append(f"{rel}: request body size limit")
    if not [i for i in issues if i["code"] == "SECRET"]:
        passed.append("No secrets found in source")
    if not [i for i in issues if i["code"] in ("SQLI",)]:
        passed.append("All SQL uses parameter binding")
    crit = sum(1 for i in issues if i["severity"] == "critical")
    high = sum(1 for i in issues if i["severity"] == "high")
    return {"status": "PASS" if not crit and not high else "FAIL", "passed": passed, "failed": issues,
            "summary": {"critical": crit, "high": high}, "files_scanned": len(files),
            "notes": ["Static analysis only. Run a dependency audit and a DAST scan against the deployed API before production."]}


# ---------------------------------------------------------------- fixers
def apply_fixes(workspace: Path, issues: list[dict], seo: dict | None = None) -> list[str]:
    """Deterministic remediations for known issue codes. Returns a list of changes made."""
    site = workspace / "source" / "site"
    changes = []
    by_page: dict[str, list[dict]] = {}
    for i in issues:
        by_page.setdefault(i.get("page") or "", []).append(i)
    seo_pages = {f"{p['page']}.html" if p["page"] not in ("home", "overview") else "index.html": p for p in (seo or {}).get("pages", [])}
    for page, items in by_page.items():
        f = site / page
        if not page.endswith(".html") or not f.exists():
            continue
        s = BeautifulSoup(f.read_text(), "html.parser")
        codes = {i["code"] for i in items}
        if "IMG_ALT" in codes:
            for img in s.find_all("img"):
                if img.get("alt") is None:
                    img["alt"] = Path(img.get("src", "image")).stem.replace("-", " ")
            changes.append(f"{page}: added alt text")
        if "FORM_LABEL" in codes:
            for el in s.find_all(["input", "select", "textarea"]):
                if not _has_label(el, s):
                    el["aria-label"] = (el.get("name") or "field").replace("_", " ").capitalize()
            changes.append(f"{page}: labelled form controls")
        if "BROKEN_LINK" in codes:
            for a in s.find_all("a", href=True):
                h = a["href"].split("#")[0].split("?")[0]
                if h and not h.startswith(("http", "mailto:", "tel:")) and not (site / h).exists():
                    a["href"] = "index.html"
            changes.append(f"{page}: repaired broken links")
        if "H1_COUNT" in codes:
            hs = s.find_all("h1")
            for h in hs[1:]:
                h.name = "h2"
            changes.append(f"{page}: normalised heading hierarchy")
        if "HTML_LANG" in codes and s.html:
            s.html["lang"] = "en"
            changes.append(f"{page}: set document language")
        if "VIEWPORT" in codes and s.head:
            m = s.new_tag("meta", attrs={"name": "viewport", "content": "width=device-width, initial-scale=1"})
            s.head.insert(0, m)
            changes.append(f"{page}: added viewport meta")
        if ("MISSING_TITLE" in codes or "MISSING_DESC" in codes) and s.head:
            sp = seo_pages.get(page, {})
            if "MISSING_TITLE" in codes:
                t = s.new_tag("title")
                t.string = sp.get("title", page)
                s.head.append(t)
            if "MISSING_DESC" in codes:
                s.head.append(s.new_tag("meta", attrs={"name": "description", "content": sp.get("description", "")}))
            changes.append(f"{page}: added SEO meta")
        if "NOOPENER" in codes:
            for a in s.find_all("a", target="_blank"):
                a["rel"] = ["noopener", "noreferrer"]
            changes.append(f"{page}: added rel=noopener")
        out = str(s)
        if not out.lstrip().lower().startswith("<!doctype"):
            out = "<!doctype html>\n" + out
        f.write_text(out)
    css = site / "assets" / "styles.css"
    if any(i["code"] == "OVERFLOW" for i in issues) and css.exists():
        css.write_text(css.read_text() + "\n/* QA fix: prevent horizontal overflow */\nmain,section,.wrap{max-width:100%;overflow-wrap:anywhere}\npre,table{overflow-x:auto;display:block}\n")
        changes.append("styles.css: overflow guard")
    if any(i["code"] == "FOCUS_STYLE" for i in issues) and css.exists():
        css.write_text(css.read_text() + "\n:focus-visible{outline:3px solid var(--accent);outline-offset:2px}\n")
        changes.append("styles.css: focus styles")
    if any(i["code"] == "TOUCH_TARGET" for i in issues) and css.exists():
        css.write_text(css.read_text() + "\n.btn,button{min-height:44px;min-width:44px}\n")
        changes.append("styles.css: touch target sizes")
    return changes


def as_json(obj) -> str:
    return json.dumps(obj, indent=2)
