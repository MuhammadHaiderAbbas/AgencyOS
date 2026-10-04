"""Browser end-to-end walkthrough (Playwright). Start the server first, then:
    B=http://localhost:8000 python tests/e2e_browser.py
It signs up, runs the hotel interview, approves every gate, requests a change and screenshots each step."""
import time, sys
from playwright.sync_api import sync_playwright
import os; B=os.environ.get("B","http://localhost:8765"); S=os.environ.get("SHOTS","./e2e-shots/"); os.makedirs(S, exist_ok=True)
errs=[]
with sync_playwright() as pw:
    br=pw.chromium.launch(args=["--no-sandbox"])
    pg=br.new_page(viewport={"width":1536,"height":1000})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type=="error" and errs.append(m.text))
    pg.goto(B); pg.wait_for_selector("text=Create your workspace")
    pg.screenshot(path=S+"01-auth.png")
    pg.fill("input[autocomplete=name]","Alex Carter"); pg.fill("input[type=email]",f"alex{int(time.time())}@company.com"); pg.fill("input[type=password]","correct-horse-1")
    pg.click("button:has-text('Start building')")
    pg.wait_for_selector("text=Describe your idea."); time.sleep(0.5)
    pg.screenshot(path=S+"02-dashboard-empty.png")
    pg.fill(".idea-box input","I want a website for my hotel"); pg.click(".idea-box .go")
    pg.wait_for_selector("text=What is the name of your hotel?")
    answers=["The Grand Vista Hotel","Lisbon, Portugal"]
    for a in answers:
        pg.fill(".composer textarea",a); pg.keyboard.press("Enter"); time.sleep(0.35)
    # use option chips for the rest
    for chip in ["Luxury","Online booking"]:
        pg.click(f".opts .chip:has-text('{chip}')"); time.sleep(0.35)
    pg.fill(".composer textarea","Deluxe King, Junior Suite, Penthouse"); pg.keyboard.press("Enter"); time.sleep(0.35)
    for chip in ["Pay online","Guest checkout is fine","Yes"]:
        pg.click(f".opts .chip:has-text('{chip}')"); time.sleep(0.35)
    pg.fill(".composer textarea","Gallery, Guest reviews, FAQ"); pg.keyboard.press("Enter"); time.sleep(0.35)
    pg.fill(".composer textarea","English"); pg.keyboard.press("Enter"); time.sleep(0.35)
    pg.click(".opts .chip:has-text('Logo only')"); time.sleep(0.35)
    pg.click(".opts .chip:has-text('Luxury & elegant')"); time.sleep(0.35)
    pg.fill(".composer textarea","dark green and gold"); pg.keyboard.press("Enter"); time.sleep(0.35)
    for _ in range(3):
        pg.click(".opts .chip:has-text('Skip')"); time.sleep(0.35)
    pg.wait_for_selector("text=Approve Project")
    pg.screenshot(path=S+"03-summary.png")
    pg.click("button:has-text('Approve Project')")
    try:
        pg.wait_for_selector("text=START BUILD", timeout=8000)
    except Exception:
        pg.screenshot(path=S+"fail.png"); print("PAGEERR", errs); raise
    time.sleep(0.5)
    pg.screenshot(path=S+"04-plan.png")
    pg.click("button:has-text('START BUILD')")
    time.sleep(2.5)
    pg.screenshot(path=S+"05-building.png")
    pg.wait_for_selector("text=Review & approve", timeout=60000); time.sleep(1)
    url=pg.url; pid=url.split("/projects/")[1].split("/")[0]
    pg.goto(f"{B}/#/projects/{pid}/approvals"); pg.wait_for_selector("text=Design & architecture"); time.sleep(0.5)
    pg.screenshot(path=S+"06-approval.png")
    pg.click("button:has-text('Approve')")
    time.sleep(3)
    pg.goto(f"{B}/#/projects/{pid}/progress"); time.sleep(1.5)
    pg.screenshot(path=S+"07-progress.png")
    pg.goto(f"{B}/#/projects/{pid}/approvals"); pg.wait_for_selector("text=built and tested", timeout=90000); time.sleep(0.5)
    pg.screenshot(path=S+"08-uat.png")
    pg.click("button:has-text('Approve')"); time.sleep(1.5)
    pg.wait_for_selector("text=Authorise deployment"); pg.click("button:has-text('Approve')"); time.sleep(2)
    pg.goto(f"{B}/#/projects/{pid}/deliverables"); time.sleep(1.2); pg.screenshot(path=S+"09-deliverables.png")
    pg.goto(f"{B}/#/projects/{pid}/preview"); time.sleep(2); pg.screenshot(path=S+"10-preview.png")
    pg.goto(f"{B}/#/projects/{pid}/artifacts"); time.sleep(1); pg.click(".list-item:has-text('design-system.json')"); time.sleep(1); pg.screenshot(path=S+"11-artifacts.png")
    pg.goto(f"{B}/#/projects/{pid}/trace"); time.sleep(1); pg.screenshot(path=S+"12-trace.png")
    pg.goto(f"{B}/#/projects/{pid}/chat"); time.sleep(1)
    pg.fill(".composer textarea","I don't want gold anymore"); pg.keyboard.press("Enter"); time.sleep(1)
    pg.screenshot(path=S+"13-change.png")
    pg.click("button:has-text('Apply change')"); time.sleep(4)
    pg.goto(f"{B}/#/dashboard"); time.sleep(2); pg.screenshot(path=S+"14-dashboard.png")
    pg.goto(f"{B}/#/marketplace"); time.sleep(1); pg.click("button:has-text('Sync GitHub catalogue')"); time.sleep(4); pg.screenshot(path=S+"15-marketplace.png")
    pg.goto(f"{B}/#/settings"); time.sleep(1.5); pg.screenshot(path=S+"16-settings.png", full_page=True)
    m=br.new_page(viewport={"width":390,"height":844}); m.goto(f"{B}/#/projects/{pid}/chat")
    m.evaluate("t=>localStorage.setItem('agencyos.token',t)", pg.evaluate("localStorage.getItem('agencyos.token')")); m.reload(); time.sleep(2)
    m.screenshot(path=S+"17-mobile.png")
    print("PID", pid)
    br.close()
print("ERRORS", errs)
