import json
import unittest
from unittest import mock

from helpers import HOTEL_ANSWERS, AgencyTestCase, db

from agencyos.agents import builtin
from agencyos.config import settings
from agencyos.orchestration import interview as iv


class AuthAndTenancy(AgencyTestCase):
    def test_signup_login_me(self):
        h = self.signup()
        me = self.c.get("/api/auth/me", headers=h).json()
        self.assertTrue(me["user"]["is_admin"], "first user bootstraps as admin")
        self.assertEqual(me["llm"]["provider"], "mock")
        r = self.c.post("/api/auth/login", json={"email": "alex@example.com", "password": "wrong-password"})
        self.assertEqual(r.status_code, 401)
        r = self.c.post("/api/auth/login", json={"email": "ALEX@example.com", "password": "correct-horse-1"})
        self.assertEqual(r.status_code, 200)

    def test_requires_auth(self):
        self.assertEqual(self.c.get("/api/projects").status_code, 401)
        self.assertEqual(self.c.get("/api/projects", headers={"Authorization": "Bearer nope"}).status_code, 401)

    def test_cookie_not_accepted_for_writes(self):
        self.signup()  # sets cookie on the client
        r = self.c.post("/api/projects", json={"idea": "a website"})
        self.assertEqual(r.status_code, 401, "state-changing endpoints require the bearer header (CSRF)")

    def test_multi_tenancy_isolation(self):
        a = self.signup("a@example.com")
        b = self.signup("b@example.com")
        pid = self.new_project(a)
        self.assertEqual(self.c.get(f"/api/projects/{pid}", headers=b).status_code, 404)
        self.assertEqual(self.c.get(f"/api/projects/{pid}/messages", headers=b).status_code, 404)
        self.assertEqual(self.c.post(f"/api/projects/{pid}/messages", json={"content": "hi"}, headers=b).status_code, 404)
        self.assertEqual(self.c.get(f"/api/projects/{pid}/export", headers=b).status_code, 404)
        self.assertEqual(self.c.get("/api/projects", headers=b).json(), [])
        art = db().q1("SELECT id FROM artifacts LIMIT 1")
        self.assertEqual(self.c.get("/api/tasks", headers=b).json(), [])
        self.assertEqual(self.c.get("/api/activity", headers=b).json(), [])

    def test_viewer_cannot_modify(self):
        h = self.signup()
        pid = self.new_project(h)
        uid = db().q1("SELECT id FROM users")["id"]
        db().ex("UPDATE memberships SET role = 'viewer' WHERE user_id = ?", (uid,))
        self.assertEqual(self.c.post(f"/api/projects/{pid}/messages", json={"content": "x"}, headers=h).status_code, 403)

    def test_non_admin_cannot_manage_agents(self):
        self.signup("admin@example.com")
        h = self.signup("user@example.com")
        self.assertEqual(self.c.post("/api/agents/builtin.researcher/disable", headers=h).status_code, 403)

    def test_api_keys_encrypted_and_masked(self):
        h = self.signup()
        r = self.c.put("/api/settings/providers", json={"provider": "anthropic", "anthropic_api_key": "sk-ant-test-1234567890abcdef"}, headers=h)
        self.assertEqual(r.status_code, 200)
        row = db().q1("SELECT ciphertext FROM org_secrets WHERE name = 'ANTHROPIC_API_KEY'")
        self.assertNotIn("sk-ant", row["ciphertext"])
        s = self.c.get("/api/settings", headers=h).json()
        self.assertEqual(s["llm"]["provider"], "anthropic")
        self.assertNotIn("1234567890", json.dumps(s))


class Interview(AgencyTestCase):
    def test_adaptive_brochure_skips_payment_questions(self):
        h = self.signup()
        pid = self.new_project(h, "I want a simple brochure website for my hotel")
        self.interview(h, pid, ["Sea Breeze Inn", "Brighton, UK", "Boutique", "Gallery", "English", "Neither", "Warm & welcoming", "skip", "skip", "skip", "skip"])
        msgs = " ".join(m["content"] for m in self.c.get(f"/api/projects/{pid}/messages", headers=h).json())
        self.assertNotIn("pay online", msgs.lower())
        self.assertNotIn("room types", msgs.lower())
        req = self.project(h, pid)["requirements"]
        self.assertNotIn("booking", req["features"])
        self.assertTrue(req["assumptions"])

    def test_hotel_interview_produces_summary(self):
        h = self.signup()
        pid = self.new_project(h)
        self.interview(h, pid)
        p = self.project(h, pid)
        self.assertEqual(p["status"], "REQUIREMENTS")
        self.assertEqual(p["pending_approvals"][0]["gate"], "requirements")
        r = p["requirements"]
        self.assertEqual(r["business_name"], "The Grand Vista Hotel")
        self.assertIn("booking", r["features"])
        self.assertIn("payments", r["features"])
        self.assertNotIn("accounts", r["features"])
        self.assertIn("Stripe", r["integrations"])
        self.assertEqual(r["room_types"], ["Deluxe King", "Junior Suite", "Penthouse"])

    def test_change_before_approval(self):
        h = self.signup()
        pid = self.new_project(h)
        self.interview(h, pid)
        self.say(h, pid, "Please add a blog and avoid gold")
        r = self.project(h, pid)["requirements"]
        self.assertIn("blog", r["features"])
        self.assertIn("gold", r["design_preferences"]["avoid_colors"])

    def test_contradiction_detected(self):
        r = iv.empty_requirements("hotel website")
        iv._add_feature(r, "booking", False)
        before = json.loads(json.dumps(r))
        iv._add_feature(r, "booking", True)
        self.assertEqual(iv.detect_contradictions(before, r)[0]["feature"], "booking")

    def test_colour_parsing(self):
        use, avoid = iv.parse_colors("navy and white please, but no gold")
        self.assertEqual(sorted(use), ["navy", "white"])
        self.assertEqual(avoid, ["gold"])


class Pipeline(AgencyTestCase):
    def test_full_hotel_build(self):
        h = self.signup()
        pid = self.new_project(h)
        self.to_design_gate(h, pid)
        p = self.project(h, pid)
        self.assertEqual(p["status"], "DESIGN", "build must stop at the design approval gate")
        t = self.tasks(h, pid)
        self.assertEqual(t["frontend"]["status"], "BACKLOG", "developers never start before design approval")
        self.approve_pending(h, pid, "design")
        p = self.project(h, pid)
        self.assertEqual(p["status"], "USER_ACCEPTANCE")
        qa_report = db().q1("SELECT v.content FROM artifact_versions v JOIN artifacts a ON a.id = v.artifact_id WHERE a.project_id = ? AND a.name = 'qa-report.json' ORDER BY v.version DESC", (pid,))
        rep = json.loads(qa_report["content"])
        self.assertEqual(rep["status"], "PASS")
        self.assertTrue(rep["backend"]["tests_passed"])
        self.assertGreaterEqual(rep["backend"]["tests_run"], 8)
        self.assertEqual(db().q1("SELECT COUNT(*) n FROM deployments WHERE project_id = ?", (pid,))["n"], 0, "no deploy without authorisation")
        self.approve_pending(h, pid, "uat")
        self.approve_pending(h, pid, "deploy")
        p = self.project(h, pid)
        self.assertEqual(p["status"], "COMPLETED")
        self.assertEqual(p["progress"], 100)
        site = self.c.get(f"/sites/{pid}/")
        self.assertEqual(site.status_code, 200)
        self.assertIn("The Grand Vista Hotel", site.text)
        files = self.c.get(f"/api/projects/{pid}/files", headers=h).json()
        msgs = [c["message"] for c in files["commits"]]
        self.assertTrue(any(m.startswith("agent(frontend):") for m in msgs))
        self.assertTrue(any(m.startswith("agent(backend):") for m in msgs))
        ex = self.c.get(f"/api/projects/{pid}/executions", headers=h).json()
        self.assertTrue(all(e["status"] == "SUCCEEDED" for e in ex))
        zipr = self.c.get(f"/api/projects/{pid}/export", headers=h)
        self.assertEqual(zipr.headers["content-type"], "application/zip")

    def test_every_displayed_status_has_backing_execution(self):
        h = self.signup()
        pid = self.new_project(h)
        self.to_design_gate(h, pid)
        done = [t for t in self.tasks(h, pid).values() if t["status"] == "COMPLETED"]
        for t in done:
            self.assertTrue(db().q1("SELECT 1 FROM agent_executions WHERE task_id = ? AND status = 'SUCCEEDED'", (t["id"],)), t["key"])

    def test_qa_bug_loop_fixes_and_retests(self):
        from agencyos.services import sitegen
        orig = sitegen.SiteBuilder.section
        calls = {"n": 0}

        def buggy(self_, kind, p):
            out = orig(self_, kind, p)
            if kind == "intro":
                calls["n"] += 1
                out += '<a href="does-not-exist.html">broken</a><input name="unlabelled">'
            return out
        h = self.signup()
        pid = self.new_project(h)
        with mock.patch.object(sitegen.SiteBuilder, "section", buggy):
            self.to_design_gate(h, pid)
            self.approve_pending(h, pid, "design")
        t = self.tasks(h, pid)
        fixes = [k for k in t if k.startswith("fix_")]
        self.assertTrue(fixes, "QA failure must create bug-fix tasks")
        self.assertEqual(t["qa"]["status"], "COMPLETED")
        self.assertGreaterEqual(t["qa"]["revision_count"], 1)
        types = [e["type"] for e in self.c.get(f"/api/projects/{pid}/activity", headers=h).json()]
        self.assertIn("BUG_REPORTED", types)
        html = (settings().workspaces_dir / pid / "source" / "site" / "index.html").read_text()
        self.assertNotIn("does-not-exist.html", html)
        self.assertIn('aria-label="Unlabelled"', html)

    def test_agent_failure_retries_then_escalates(self):
        def boom(ctx):
            raise RuntimeError("simulated crash")
        h = self.signup()
        pid = self.new_project(h)
        with mock.patch.dict(builtin.BUILTIN_RUNNERS, {"researcher": boom}):
            self.to_design_gate(h, pid)
        t = self.tasks(h, pid)
        self.assertEqual(t["research"]["status"], "FAILED")
        ex = db().q("SELECT status FROM agent_executions WHERE task_id = ?", (t["research"]["id"],))
        self.assertEqual(len(ex), settings().max_task_retries + 1)
        p = self.project(h, pid)
        self.assertEqual(p["status"], "BLOCKED")
        self.assertEqual(p["pending_approvals"][0]["gate"], "decision")
        # user lets the team try again; with the crash gone it now succeeds
        self.c.post(f"/api/approvals/{p['pending_approvals'][0]['id']}/decide", json={"decision": "changes", "note": "try again"}, headers=h)
        self.assertEqual(self.tasks(h, pid)["research"]["status"], "COMPLETED")

    def test_review_rejects_and_revision_loop(self):
        orig = builtin.content_writer
        n = {"i": 0}

        def sloppy(ctx):
            r = orig(ctx)
            n["i"] += 1
            if n["i"] == 1:
                r.artifacts[0].content["hero"]["title"] = "The award-winning hotel"
            return r
        h = self.signup()
        pid = self.new_project(h)
        with mock.patch.dict(builtin.BUILTIN_RUNNERS, {"content_writer": sloppy}):
            self.to_design_gate(h, pid)
            self.approve_pending(h, pid, "design")
        t = self.tasks(h, pid)
        self.assertEqual(t["content"]["revision_count"], 1)
        versions = db().q("SELECT v.version FROM artifact_versions v JOIN artifacts a ON a.id = v.artifact_id WHERE a.project_id = ? AND a.name = 'content.json'", (pid,))
        self.assertEqual(len(versions), 2, "revisions create new versions, never overwrite")

    def test_execution_limit_blocks_project(self):
        h = self.signup()
        pid = self.new_project(h)
        settings().max_project_executions = 3
        try:
            self.to_design_gate(h, pid)
        finally:
            settings().max_project_executions = 400
        self.assertEqual(self.project(h, pid)["status"], "BLOCKED")


class ChangesAndMemory(AgencyTestCase):
    def test_change_request_remembers_rejected_colour(self):
        h = self.signup()
        pid = self.new_project(h)
        self.full_build(h, pid)
        self.say(h, pid, "I don't want gold anymore")
        msgs = self.c.get(f"/api/projects/{pid}/messages", headers=h).json()
        self.assertEqual(msgs[-1]["meta"]["type"], "change_request")
        self.assertIn("ui_designer", msgs[-1]["meta"]["analysis"]["affected_agents"])
        self.say(h, pid, "yes")
        ds = db().q1("SELECT v.content FROM artifact_versions v JOIN artifacts a ON a.id = v.artifact_id WHERE a.project_id = ? AND a.name = 'design-system.json' ORDER BY v.version DESC", (pid,))
        self.assertNotIn("#c9a45c", ds["content"].lower())
        self.assertEqual(self.project(h, pid)["status"], "USER_ACCEPTANCE", "changes require re-acceptance")
        # weeks later…
        self.approve_pending(h, pid, "uat")
        self.approve_pending(h, pid, "deploy")
        self.say(h, pid, "Make the booking button match the brand")
        self.say(h, pid, "yes")
        ds = db().q1("SELECT v.content FROM artifact_versions v JOIN artifacts a ON a.id = v.artifact_id WHERE a.project_id = ? AND a.name = 'design-system.json' ORDER BY v.version DESC", (pid,))
        self.assertNotIn("#c9a45c", ds["content"].lower(), "rejected colour must never come back")
        mem = self.project(h, pid)["memory"]
        self.assertTrue(any(m["key"] == "avoid_color:gold" for m in mem))

    def test_post_build_contradiction_flagged(self):
        h = self.signup()
        pid = self.new_project(h, "I want a simple brochure website for my hotel")
        self.interview(h, pid, ["Sea Breeze Inn", "Brighton, UK", "Boutique", "Gallery", "English", "Neither", "Warm & welcoming", "skip", "skip", "skip", "skip"])
        self.c.post(f"/api/projects/{pid}/approve-requirements", headers=h)
        self.c.post(f"/api/projects/{pid}/start", headers=h)
        self.say(h, pid, "I want customers to reserve rooms online")
        last = self.c.get(f"/api/projects/{pid}/messages", headers=h).json()[-1]
        self.assertTrue(last["meta"]["analysis"]["contradictions"])
        self.say(h, pid, "yes")
        t = self.tasks(h, pid)
        self.assertIn("backend", t, "new scope adds backend tasks to the plan")
        self.assertIn("booking", self.project(h, pid)["requirements"]["features"])

    def test_artifact_versions_restore_and_diff(self):
        h = self.signup()
        pid = self.new_project(h)
        self.full_build(h, pid)
        self.say(h, pid, "Make it more modern and minimal")
        self.say(h, pid, "yes")
        art = [a for a in self.c.get(f"/api/projects/{pid}/artifacts", headers=h).json() if a["name"] == "design-system.json"][0]
        self.assertGreaterEqual(art["current_version"], 2)
        d = self.c.get(f"/api/artifacts/{art['id']}/diff?a=1&b={art['current_version']}", headers=h).json()["diff"]
        self.assertIn("---", d)
        r = self.c.post(f"/api/artifacts/{art['id']}/restore", json={"version": 1}, headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["version"], art["current_version"] + 1)

    def test_progress_and_blocking_commands(self):
        h = self.signup()
        pid = self.new_project(h)
        self.to_design_gate(h, pid)
        self.say(h, pid, "What is blocking the project?")
        self.assertIn("approval", self.c.get(f"/api/projects/{pid}/messages", headers=h).json()[-1]["content"].lower())
        self.say(h, pid, "Show me the progress")
        self.assertIn("Requirements", self.c.get(f"/api/projects/{pid}/messages", headers=h).json()[-1]["content"])

    def test_deployment_rollback(self):
        h = self.signup()
        pid = self.new_project(h)
        self.full_build(h, pid)
        self.say(h, pid, "Remove the FAQ")
        self.say(h, pid, "yes")
        self.approve_pending(h, pid, "design")  # page structure changed -> design re-approval
        self.approve_pending(h, pid, "uat")
        self.approve_pending(h, pid, "deploy")
        deps = self.c.get(f"/api/projects/{pid}/deployments", headers=h).json()["deployments"]
        self.assertEqual(len(deps), 2)
        old = deps[-1]
        self.assertEqual(self.c.post(f"/api/projects/{pid}/deployments/{old['id']}/rollback", headers=h).status_code, 200)
        self.assertTrue([d for d in self.c.get(f"/api/projects/{pid}/deployments", headers=h).json()["deployments"] if d["id"] == old["id"]][0]["current"])

    def test_delete_requires_confirmation(self):
        h = self.signup()
        pid = self.new_project(h)
        self.assertEqual(self.c.request("DELETE", f"/api/projects/{pid}", json={"confirm": "nope"}, headers=h).status_code, 400)
        name = self.project(h, pid)["name"]
        self.assertEqual(self.c.request("DELETE", f"/api/projects/{pid}", json={"confirm": name}, headers=h).status_code, 200)


class Agents(AgencyTestCase):
    def test_registry_and_routing(self):
        h = self.signup()
        a = self.c.get("/api/agents", headers=h).json()
        self.assertGreaterEqual(a["counts"]["builtin"], 17)
        from agencyos.agents.registry import select_agent
        self.assertEqual(select_agent("ux_designer"), "builtin.ux_designer")
        self.c.post("/api/agents/builtin.ux_designer/disable", headers=h)
        self.assertIsNone(select_agent("ux_designer"))

    def test_importer_reads_repository(self):
        import os
        from pathlib import Path
        repo = Path(os.environ.get("AGENCYOS_TEST_REPO", "/home/claude/ref-500"))
        if not repo.exists():
            self.skipTest("agent repository clone not available")
        settings().agent_repo_path = repo
        h = self.signup()
        r = self.c.post("/api/agents/import", headers=h)
        self.assertEqual(r.status_code, 200, r.text)
        res = r.json()
        self.assertEqual(res["license"], "MIT")
        self.assertGreaterEqual(len(res["runnable"]), 20)
        self.assertGreater(res["catalogue_entries"], 50)
        ag = self.c.get("/api/agents?source=github", headers=h).json()["agents"]
        self.assertTrue(all(not x["enabled"] for x in ag), "imported agents are disabled until reviewed")
        web = [x for x in ag if "web-research" in x["id"]][0]
        self.assertEqual(web["framework"], "langgraph")
        self.assertIn("OPENAI_API_KEY", web["required_credentials"])
        cat = self.c.get("/api/agents?source=catalogue", headers=h).json()["agents"][0]
        self.assertEqual(self.c.post(f"/api/agents/{cat['id']}/enable", headers=h).status_code, 409)

    def test_custom_agent_permissions(self):
        h = self.signup()
        r = self.c.post("/api/agents/custom", json={"name": "Video Editor Agent", "description": "Plans video edits",
                                                    "system_instructions": "You are a video editor.", "permissions": ["DEPLOY"]}, headers=h)
        self.assertEqual(r.status_code, 422)
        r = self.c.post("/api/agents/custom", json={"name": "Video Editor Agent", "description": "Plans video edits",
                                                    "system_instructions": "You are a video editor."}, headers=h)
        self.assertEqual(r.status_code, 201)
        t = self.c.post("/api/agents/custom.video-editor-agent/test", headers=h).json()
        self.assertEqual(t["status"], "failed", "without an LLM the custom agent honestly reports it cannot run")


class LLMRouting(AgencyTestCase):
    def test_invalid_json_retried_then_validated(self):
        from agencyos.llm.base import LLMResponse
        from agencyos.llm.providers import AnthropicProvider
        from agencyos.llm.router import LLMClient
        settings().anthropic_api_key = "test-key"
        settings().llm_provider = "anthropic"
        replies = iter(["not json at all", '{"ok": true}'])
        try:
            with mock.patch.object(AnthropicProvider, "complete", lambda self, **k: LLMResponse(next(replies), "anthropic", k["model"], 10, 5, 0.0001)):
                c = LLMClient(None)
                r = c.generate_json(purpose="t", tier="fast", system="s", prompt="p", fallback=lambda: {"ok": False},
                                    validate=lambda v: [] if v.get("ok") else ["ok must be true"])
            self.assertEqual(r.value, {"ok": True})
            self.assertFalse(r.used_fallback)
            self.assertEqual(r.model, settings().anthropic_model_fast, "fast tier routes to the cheap model")
        finally:
            settings().anthropic_api_key = None
            settings().llm_provider = "mock"

    def test_provider_outage_falls_back(self):
        from agencyos.llm.base import LLMError
        from agencyos.llm.providers import OpenAIProvider
        from agencyos.llm.router import LLMClient
        settings().openai_api_key = "test-key"
        settings().llm_provider = "openai"
        try:
            with mock.patch.object(OpenAIProvider, "complete", side_effect=LLMError("HTTP 503")):
                r = LLMClient(None).generate_json(purpose="t", tier="strong", system="s", prompt="p", fallback=lambda: {"x": 1})
            self.assertTrue(r.used_fallback)
            self.assertTrue(any("503" in n for n in r.notes))
        finally:
            settings().openai_api_key = None
            settings().llm_provider = "mock"


class Security(AgencyTestCase):
    def test_security_scan_finds_secrets_and_sqli(self):
        from pathlib import Path
        import tempfile
        from agencyos.services import qa
        ws = Path(tempfile.mkdtemp())
        (ws / "source" / "api").mkdir(parents=True)
        (ws / "source" / "api" / "x.py").write_text('KEY = "sk-ant-abcdefghijklmnopqrstuvwxyz"\ncur.execute(f"SELECT * FROM t WHERE id={x}")\n')
        r = qa.run_security(ws)
        codes = {i["code"] for i in r["failed"]}
        self.assertIn("SECRET", codes)
        self.assertIn("SQLI", codes)
        self.assertEqual(r["status"], "FAIL")

    def test_path_traversal_blocked(self):
        h = self.signup()
        pid = self.new_project(h)
        r = self.c.get(f"/api/projects/{pid}/file?path=../../agencyos.sqlite3", headers=h)
        self.assertEqual(r.status_code, 404)
        r = self.c.get(f"/api/projects/{pid}/preview/..%2F..%2F.secret_key", headers=h)
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
