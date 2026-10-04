import os
import shutil
import tempfile
import unittest

os.environ.setdefault("AGENCYOS_LLM_PROVIDER", "mock")
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)

from starlette.testclient import TestClient  # noqa: E402

from agencyos.api.app import create_app  # noqa: E402
from agencyos.db import db  # noqa: E402
from agencyos.orchestration.engine import orchestrator  # noqa: E402

HOTEL_ANSWERS = ["The Grand Vista Hotel", "Lisbon, Portugal", "Luxury", "Online booking", "Deluxe King, Junior Suite, Penthouse",
                 "Pay online", "Guest checkout is fine", "Yes", "Gallery, Guest reviews, FAQ", "English", "Logo only",
                 "Luxury & elegant", "dark green and gold", "hello@grandvista.pt +351 21 000 0000", "skip", "skip"]


class AgencyTestCase(unittest.TestCase):
    visual = False

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from agencyos.api import common
        common._hits.clear()
        orchestrator.sync = True
        self.app = create_app(data_dir=self.tmp, step_delay=0, llm_provider="mock", anthropic_api_key=None, openai_api_key=None,
                              frontend_dist=__import__("pathlib").Path(self.tmp) / "nofrontend")
        self.c = TestClient(self.app)
        self.c.__enter__()
        if not self.visual:
            from agencyos.agents import builtin
            from agencyos.services import qa
            self._orig_qa = builtin.qa_engineer

            def fast_qa(ctx):
                ctx.params["visual"] = False
                return self._orig_qa(ctx)
            builtin.BUILTIN_RUNNERS["qa_engineer"] = fast_qa

    def tearDown(self):
        from agencyos.agents import builtin
        builtin.BUILTIN_RUNNERS["qa_engineer"] = builtin.qa_engineer
        self.c.__exit__(None, None, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def signup(self, email="alex@example.com", name="Alex Carter", password="correct-horse-1"):
        r = self.c.post("/api/auth/signup", json={"email": email, "name": name, "password": password})
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": "Bearer " + r.json()["token"]}

    def new_project(self, h, idea="I want a website for my hotel"):
        r = self.c.post("/api/projects", json={"idea": idea}, headers=h)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def say(self, h, pid, text):
        r = self.c.post(f"/api/projects/{pid}/messages", json={"content": text}, headers=h)
        self.assertEqual(r.status_code, 201, r.text)

    def project(self, h, pid):
        return self.c.get(f"/api/projects/{pid}", headers=h).json()

    def interview(self, h, pid, answers=HOTEL_ANSWERS):
        for a in answers:
            if self.project(h, pid)["pending_approvals"]:
                break
            self.say(h, pid, a)

    def to_design_gate(self, h, pid):
        self.interview(h, pid)
        self.assertEqual(self.c.post(f"/api/projects/{pid}/approve-requirements", headers=h).status_code, 200)
        self.assertEqual(self.c.post(f"/api/projects/{pid}/start", headers=h).status_code, 200)

    def approve_pending(self, h, pid, gate=None):
        aps = [a for a in self.c.get("/api/approvals", headers=h).json() if a["project_id"] == pid and (gate is None or a["gate"] == gate)]
        self.assertTrue(aps, f"no pending approval {gate}")
        r = self.c.post(f"/api/approvals/{aps[0]['id']}/decide", json={"decision": "approve"}, headers=h)
        self.assertEqual(r.status_code, 200, r.text)
        return aps[0]

    def tasks(self, h, pid):
        return {t["key"]: t for t in self.c.get(f"/api/projects/{pid}/tasks", headers=h).json()}

    def full_build(self, h, pid):
        self.to_design_gate(h, pid)
        self.approve_pending(h, pid, "design")
        self.approve_pending(h, pid, "uat")
        self.approve_pending(h, pid, "deploy")
