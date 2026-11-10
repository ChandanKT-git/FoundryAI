# Iteration 5: runtime follow-ups (infra header stripping, memory limit, crash error text, delete removes token, sample start)
import pytest
import requests

from conftest import BASE_URL, SAMPLE_PID
from test_foundry_diff_tests import _insert_project, _cleanup
from test_foundry_runtime import CRASH_MAIN, _start, _stop

APP_MAIN = '''from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

app = FastAPI()


@app.get("/")
def root():
    return {"ok": True}


@app.get("/api/headers")
def headers(request: Request):
    return dict(request.headers)


@app.get("/api/alloc")
def alloc(mb: int = 1536):
    b = bytearray(mb * 2**20)
    return {"allocated_mb": len(b) // 2**20}


@app.get("/api/go")
def go():
    return RedirectResponse("/api/headers", status_code=307)


@app.get("/api/go-abs")
def go_abs():
    return RedirectResponse("https://example.com/x", status_code=307)
'''


def files():
    return [{"path": "backend/app/__init__.py", "content": ""}, {"path": "backend/app/main.py", "content": APP_MAIN},
            {"path": "preview.html", "content": "<html><head></head><body>x</body></html>"}]


@pytest.fixture(scope="module")
def created():
    ids = []
    yield ids
    for pid in ids:
        _cleanup(pid)


@pytest.fixture(scope="module")
def app5(created, token_a):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token_a}"})
    _stop(s, SAMPLE_PID)
    pid = _insert_project(files(), "rt5_app")
    created.append(pid)
    d = _start(s, pid).json()
    assert d["status"] == "running", d
    yield pid, d, s
    _stop(s, pid)


class TestHeaders:
    def test_infra_headers_stripped(self, app5):
        b = f"{BASE_URL}{app5[1]['base_path']}"
        # cf-* are added by the real edge (spoofing them gets a Cloudflare 403)
        sent = {"Via": "1.1 x", "X-Cloud-Trace-Context": "t", "X-Forwarded-For": "1.1.1.1",
                "X-Custom": "keep", "Cookie": "a=b"}
        h = {k.lower(): v for k, v in requests.get(f"{b}/api/headers", headers=sent).json().items()}
        print(h)
        bad = [k for k in h if k.startswith(("cf-", "cloudflare", "x-forwarded", "x-cloud")) or k in ("via", "cookie")]
        assert not bad, bad
        assert h.get("x-custom") == "keep"

    def test_relative_redirect(self, app5):
        r = requests.get(f"{BASE_URL}{app5[1]['base_path']}/api/go", allow_redirects=False)
        print(r.headers.get("location"))
        assert r.status_code == 307 and r.headers["location"] == app5[1]["base_path"] + "/api/headers"

    def test_external_redirect_untouched(self, app5):
        r = requests.get(f"{BASE_URL}{app5[1]['base_path']}/api/go-abs", allow_redirects=False)
        assert r.headers["location"] == "https://example.com/x"


class TestMemory:
    def test_big_alloc_fails(self, app5):
        b = f"{BASE_URL}{app5[1]['base_path']}"
        r = requests.get(f"{b}/api/alloc", params={"mb": 1536}, timeout=60)
        print(r.status_code, r.text[:200])
        assert r.status_code >= 500
        st = app5[2].get(f"{BASE_URL}/api/projects/{app5[0]}/runtime").json()
        print(st["status"], st["logs"][-500:])
        assert "MemoryError" in st["logs"] or st["status"] == "crashed"

    def test_small_alloc_ok_after(self, app5):
        st = app5[2].get(f"{BASE_URL}/api/projects/{app5[0]}/runtime").json()
        if st["status"] != "running":
            pytest.skip("process died after big alloc")
        r = requests.get(f"{BASE_URL}{app5[1]['base_path']}/api/alloc", params={"mb": 50})
        assert r.status_code == 200 and r.json()["allocated_mb"] == 50


class TestCrashError:
    def test_error_has_last_line(self, created, client_a):
        pid = _insert_project([{"path": "backend/app/__init__.py", "content": ""},
                               {"path": "backend/app/main.py", "content": CRASH_MAIN}], "rt5_crash")
        created.append(pid)
        d = _start(client_a, pid).json()
        print(d["error"])
        assert d["status"] == "crashed"
        assert "TEST_boom_on_import" in d["error"]
        assert "/tmp/" not in d["error"]


class TestDelete:
    def test_delete_removes_token(self, created, client_a):
        pid = _insert_project(files(), "rt5_del")
        created.append(pid)
        _stop(client_a, pid)
        d = _start(client_a, pid).json()
        if d["status"] != "running":
            pytest.fail(f"start failed {d}")
        b = f"{BASE_URL}{d['base_path']}"
        assert requests.get(f"{b}/api/headers").status_code == 200
        r = client_a.delete(f"{BASE_URL}/api/projects/{pid}")
        assert r.status_code == 200
        assert requests.get(f"{b}/api/headers").status_code == 503
        assert client_a.get(f"{BASE_URL}/api/projects/{pid}/runtime").status_code == 404


class TestSample:
    def test_sample_start_tasks(self, app5, client_a):
        _stop(client_a, app5[0])
        try:
            d = _start(client_a, SAMPLE_PID).json()
            assert d["status"] == "running", d
            r = requests.get(f"{BASE_URL}{d['base_path']}/api/tasks")
            assert r.status_code == 200 and isinstance(r.json(), list)
        finally:
            _stop(client_a, SAMPLE_PID)
