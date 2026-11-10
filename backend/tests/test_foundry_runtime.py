# Iteration 4: live sandboxed backends (runtime start/stop/status, capability proxy, sandbox safety, restart on new version, limits)
import time
import uuid

from pathlib import Path

import pytest
import requests

from conftest import BASE_URL, SAMPLE_PID
from test_foundry_diff_tests import DB, _insert_project, _now, _cleanup

BACKEND_ENV = str(Path(__file__).resolve().parents[1] / ".env")

PROBE_MAIN = '''import os, socket
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI()
ITEMS = {}


class Item(BaseModel):
    name: str


@app.get("/")
def root():
    return {"ok": True}


@app.get("/api/probe")
def probe():
    out = {}
    try:
        socket.create_connection(("127.0.0.1", 27017), timeout=2)
        out["tcp"] = "connected"
    except Exception as e:
        out["tcp"] = type(e).__name__
    try:
        open(__BACKEND_ENV__).read()
        out["env_file"] = "read"
    except Exception as e:
        out["env_file"] = type(e).__name__
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect("/tmp/mongodb-27017.sock")
        out["unix_connect"] = "connected"
    except Exception as e:
        out["unix_connect"] = type(e).__name__
    out["env_keys"] = sorted(os.environ.keys())
    out["db_url"] = os.environ.get("DATABASE_URL")
    out["uid"] = os.getuid()
    return out


@app.get("/api/headers")
def headers(request: Request):
    return dict(request.headers)


@app.get("/api/go")
def go():
    return RedirectResponse("/api/categories", status_code=307)


@app.get("/api/categories")
def list_categories(q: str = ""):
    return [{"id": k, "name": v} for k, v in ITEMS.items() if q in v]


@app.post("/api/categories", status_code=201)
def create_category(item: Item):
    cid = str(len(ITEMS) + 1)
    ITEMS[cid] = item.name
    return {"id": cid, "name": item.name}


@app.put("/api/categories/{cid}")
def update_category(cid: str, item: Item):
    ITEMS[cid] = item.name
    return {"id": cid, "name": item.name}


@app.delete("/api/categories/{cid}")
def delete_category(cid: str):
    ITEMS.pop(cid, None)
    return {"deleted": cid}
'''

VER_MAIN = 'from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get("/api/ver")\ndef ver():\n    return {"v": %d}\n'
CRASH_MAIN = 'from fastapi import FastAPI\n\nraise RuntimeError("TEST_boom_on_import")\napp = FastAPI()\n'


def probe_files():
    return [{"path": "backend/app/__init__.py", "content": ""}, {"path": "backend/app/main.py", "content": PROBE_MAIN.replace("__BACKEND_ENV__", repr(BACKEND_ENV))},
            {"path": "preview.html", "content": "<html><head></head><body>x</body></html>"}]


@pytest.fixture(scope="module")
def created():
    ids = []
    yield ids
    for pid in ids:
        _cleanup(pid)


def _start(client, pid, timeout=420):
    return client.post(f"{BASE_URL}/api/projects/{pid}/runtime/start", timeout=timeout)


def _stop(client, pid):
    return client.post(f"{BASE_URL}/api/projects/{pid}/runtime/stop", timeout=60)


@pytest.fixture(scope="module")
def probe(created, token_a):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token_a}"})
    _stop(s, SAMPLE_PID)  # free a per-user slot
    pid = _insert_project(probe_files(), "rt_probe")
    created.append(pid)
    r = _start(s, pid)
    assert r.status_code == 200, r.text
    data = r.json()
    yield pid, data
    _stop(s, pid)


class TestRuntimeStart:
    def test_auth_required(self, probe):
        r = requests.post(f"{BASE_URL}/api/projects/{probe[0]}/runtime/start")
        assert r.status_code == 401
        r = requests.get(f"{BASE_URL}/api/projects/{probe[0]}/runtime")
        assert r.status_code == 401

    def test_other_user_404(self, probe, client_b):
        assert client_b.post(f"{BASE_URL}/api/projects/{probe[0]}/runtime/start").status_code == 404
        assert client_b.get(f"{BASE_URL}/api/projects/{probe[0]}/runtime").status_code == 404
        assert client_b.post(f"{BASE_URL}/api/projects/{probe[0]}/runtime/stop").status_code == 404

    def test_start_running(self, probe):
        pid, data = probe
        print(data.get("logs"))
        assert data["status"] == "running", data
        assert data["entry"] == "app.main:app"
        assert data["base_path"] == f"/api/runtime/{data['token']}"
        assert "uvicorn" in data["logs"]
        assert data["stale"] is False

    def test_status_get(self, probe, client_a):
        r = client_a.get(f"{BASE_URL}/api/projects/{probe[0]}/runtime")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "running" and d["base_path"] == probe[1]["base_path"]
        assert "logs" in d and d["stale"] is False

    def test_no_files_400(self, created, client_a):
        pid = _insert_project([], "rt_nofiles")
        created.append(pid)
        r = _start(client_a, pid)
        assert r.status_code == 400

    def test_idle_status(self, created, client_a):
        pid = _insert_project([{"path": "a.txt", "content": "x"}], "rt_idle")
        created.append(pid)
        d = client_a.get(f"{BASE_URL}/api/projects/{pid}/runtime").json()
        assert d["status"] == "idle"

    def test_no_fastapi_failed(self, created, client_a):
        pid = _insert_project([{"path": "backend/x.py", "content": "print('hi')\n"}], "rt_noapp")
        created.append(pid)
        r = _start(client_a, pid)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "failed" and "FastAPI" in (d["error"] or "")

    def test_crash_on_import(self, created, client_a):
        pid = _insert_project([{"path": "backend/app/__init__.py", "content": ""},
                               {"path": "backend/app/main.py", "content": CRASH_MAIN}], "rt_crash")
        created.append(pid)
        r = _start(client_a, pid)
        assert r.status_code == 200
        d = r.json()
        print(d)
        assert d["status"] in ("crashed", "failed")
        assert "TEST_boom_on_import" in d["logs"]
        assert d["error"]


class TestProxy:
    def base(self, probe):
        return f"{BASE_URL}{probe[1]['base_path']}"

    def test_crud_passthrough_no_auth(self, probe):
        b = self.base(probe)
        r = requests.post(f"{b}/api/categories", json={"name": "TEST_cat"})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        lst = requests.get(f"{b}/api/categories", params={"q": "TEST_"}).json()
        assert any(c["id"] == cid and c["name"] == "TEST_cat" for c in lst)
        r = requests.put(f"{b}/api/categories/{cid}", json={"name": "TEST_cat2"})
        assert r.status_code == 200 and r.json()["name"] == "TEST_cat2"
        r = requests.delete(f"{b}/api/categories/{cid}")
        assert r.status_code == 200
        assert not any(c["id"] == cid for c in requests.get(f"{b}/api/categories").json())

    def test_validation_passthrough(self, probe):
        r = requests.post(f"{self.base(probe)}/api/categories", json={})
        assert r.status_code == 422

    def test_bad_token_503(self):
        r = requests.get(f"{BASE_URL}/api/runtime/nope-not-a-token/api/categories")
        assert r.status_code == 503

    def test_cookie_and_auth_not_forwarded(self, probe):
        r = requests.get(f"{self.base(probe)}/api/headers", headers={"Cookie": "__session=secret", "X-Custom": "1"})
        h = {k.lower(): v for k, v in r.json().items()}
        print(h)
        assert "cookie" not in h
        assert h.get("x-custom") == "1"

    def test_cors_origin_null(self, probe):
        b = self.base(probe)
        pre = requests.options(f"{b}/api/categories", headers={"Origin": "null", "Access-Control-Request-Method": "POST",
                                                                "Access-Control-Request-Headers": "content-type"})
        print(pre.status_code, dict(pre.headers))
        assert pre.status_code == 200
        assert pre.headers.get("access-control-allow-origin") in ("*", "null")
        r = requests.get(f"{b}/api/categories", headers={"Origin": "null"})
        assert r.headers.get("access-control-allow-origin") in ("*", "null")

    def test_redirect_rewritten(self, probe):
        r = requests.get(f"{self.base(probe)}/api/go", allow_redirects=False)
        print(r.status_code, r.headers.get("location"))
        assert r.status_code == 307
        assert r.headers["location"].startswith(probe[1]["base_path"] + "/api/categories")


class TestSandboxSafety:
    def test_probe(self, probe):
        d = requests.get(f"{BASE_URL}{probe[1]['base_path']}/api/probe").json()
        print(d)
        assert d["tcp"] in ("PermissionError", "OSError")
        assert d["env_file"] == "PermissionError"
        assert d["unix_connect"] != "connected"
        assert d["uid"] >= 61000
        assert not any(
            k in d["env_keys"]
            for k in ("MONGO_URL", "CLERK_SECRET_KEY", "DB_NAME", "LLM_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
        )
        assert d["db_url"].startswith("sqlite:///")


class TestRestartAndLimits:
    def test_restart_same_token_on_restore(self, created, client_a):
        pid = _insert_project([{"path": "backend/app/__init__.py", "content": ""},
                               {"path": "backend/app/main.py", "content": VER_MAIN % 2}], "rt_ver")
        created.append(pid)
        p = DB.projects.find_one({"id": pid}, {"_id": 0})
        vids = {}
        for n in (1, 2):
            vids[n] = str(uuid.uuid4())
            DB.versions.insert_one({"id": vids[n], "project_id": pid, "user_id": p["user_id"], "number": n, "label": f"TEST v{n}",
                                    "files": [{"path": "backend/app/__init__.py", "content": ""},
                                              {"path": "backend/app/main.py", "content": VER_MAIN % n}],
                                    "file_count": 2, "created_at": _now()})
        DB.projects.update_one({"id": pid}, {"$set": {"version_count": 2}})
        try:
            d = _start(client_a, pid).json()
            assert d["status"] == "running", d
            base = f"{BASE_URL}{d['base_path']}"
            assert requests.get(f"{base}/api/ver").json() == {"v": 2}
            r = client_a.post(f"{BASE_URL}/api/projects/{pid}/versions/{vids[1]}/restore")
            assert r.status_code == 200, r.text
            saw_stale, ok = False, False
            for _ in range(60):
                s = client_a.get(f"{BASE_URL}/api/projects/{pid}/runtime").json()
                saw_stale = saw_stale or s.get("stale")
                if s["status"] == "running" and not s["stale"]:
                    assert s["base_path"] == d["base_path"]
                    if requests.get(f"{base}/api/ver").json() == {"v": 1}:
                        ok = True
                        break
                time.sleep(0.5)
            print("saw_stale", saw_stale)
            assert ok, "runtime did not restart on restored code"
        finally:
            _stop(client_a, pid)

    def test_stop_then_proxy_503(self, created, client_a):
        pid = _insert_project(probe_files(), "rt_stop")
        created.append(pid)
        d = _start(client_a, pid).json()
        assert d["status"] == "running"
        r = _stop(client_a, pid)
        assert r.status_code == 200 and r.json()["status"] == "stopped"
        assert client_a.get(f"{BASE_URL}/api/projects/{pid}/runtime").json()["status"] == "stopped"
        assert requests.get(f"{BASE_URL}{d['base_path']}/api/categories").status_code == 503

    def test_per_user_limit_429(self, created, client_a, probe):
        # probe is running (1). Start a second (2), third must be 429.
        p2 = _insert_project(probe_files(), "rt_lim2")
        p3 = _insert_project(probe_files(), "rt_lim3")
        created.extend([p2, p3])
        try:
            assert _start(client_a, p2).json()["status"] == "running"
            r = _start(client_a, p3)
            print(r.status_code, r.text)
            assert r.status_code == 429
            # sanity: after stopping one, the third can start
            _stop(client_a, p2)
            assert _start(client_a, p3).json()["status"] == "running"
        finally:
            _stop(client_a, p2)
            _stop(client_a, p3)


class TestRedirectSlash:
    def test_trailing_slash_redirect_rewritten(self, probe):
        r = requests.get(f"{BASE_URL}{probe[1]['base_path']}/api/categories/", allow_redirects=False)
        print(r.status_code, r.headers.get("location"))
        assert r.status_code == 307
        assert r.headers["location"].startswith(probe[1]["base_path"] + "/api/categories")
