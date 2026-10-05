import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

def _client(tmp_path):
    from packages.config.config import load_settings
    from apps.gateway.db import reset_db, init_db
    reset_db()
    load_settings(data_dir=tmp_path, database_url=f"sqlite:///{tmp_path/'test.sqlite3'}")
    # ensure clean DB file
    db_file = tmp_path / 'test.sqlite3'
    if db_file.exists():
        db_file.unlink()
    from apps.gateway.app import create_app
    app = create_app(data_dir=tmp_path, database_url=f"sqlite:///{tmp_path/'test.sqlite3'}")
    # init_db via lifespan may not run until TestClient enters; ensure tables exist now
    init_db()
    return TestClient(app)

def test_health(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"

def test_signup_and_chat(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/v1/auth/signup", json={"email":"a@b.c","password":"pass123","display_name":"A"})
    assert r.status_code == 200
    token = r.json()["token"]
    # chat requires auth — client holds cookie automatically
    r2 = c.post("/api/v1/chat", json={"message":"Hello Jarvis"})
    assert r2.status_code == 200
    assert "message" in r2.json()

def test_tools_list_requires_auth(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/v1/tools")
    assert r.status_code == 401  # no auth
    # after signup
    c.post("/api/v1/auth/signup", json={"email":"u@u.c","password":"pass123"})
    r2 = c.get("/api/v1/tools")
    assert r2.status_code == 200
    assert len(r2.json()["tools"]) > 5

def test_permission_bypass(tmp_path):
    c = _client(tmp_path)
    c.post("/api/v1/auth/signup", json={"email":"b@c.d","password":"pass123"})
    # email.send is high risk → should return approval_required, not execute
    r = c.post("/api/v1/tools/execute", json={"tool":"email.send","arguments":{"to":"x@y.z","subject":"hi","body":"hello"}})
    assert r.status_code == 200
    assert r.json().get("approval_required") is True

def test_files_sandbox(tmp_path):
    c = _client(tmp_path)
    c.post("/api/v1/auth/signup", json={"email":"s@s.c","password":"pass123"})
    # try path traversal via files.read
    r = c.post("/api/v1/tools/execute", json={"tool":"files.read","arguments":{"path":"../../etc/passwd"}})
    # should either fail validation or return error but not leak file
    # In Phase 1, files.read returns error dict inside 200 or 400
    # We assert no raw /etc/passwd content
    body = r.text.lower()
    assert "root:" not in body  # typical passwd content should not leak
