# Iteration 2: Version diff API + sandboxed test runner (run, history, auto-fix, safety)
import time
import uuid
from datetime import datetime, timezone

from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

from conftest import BASE_URL, SAMPLE_PID

DB = MongoClient("mongodb://localhost:27017")["test_database"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _insert_project(files, name):
    sample = DB.projects.find_one({"id": SAMPLE_PID}, {"_id": 0, "user_id": 1})
    pid = str(uuid.uuid4())
    DB.projects.insert_one({
        "id": pid, "user_id": sample["user_id"], "name": f"TEST_{name}", "idea": "TEST sandbox project",
        "model": "gpt-6-luna", "status": "ready", "busy": False, "error": None,
        "stage_status": {s: "done" for s in ("plan", "architecture", "code", "tests", "review")},
        "plan": "", "architecture": "", "files": files, "review": None, "logs": {}, "version_count": 0,
        "created_at": _now(), "updated_at": _now()})
    return pid


def _cleanup(pid):
    DB.projects.delete_one({"id": pid})
    DB.versions.delete_many({"project_id": pid})
    DB.test_runs.delete_many({"project_id": pid})


def _wait_run(client, pid, rid, timeout=240):
    end = time.time() + timeout
    seen_live = False
    while time.time() < end:
        runs = client.get(f"{BASE_URL}/api/projects/{pid}/tests/runs").json()
        r = next(x for x in runs if x["id"] == rid)
        if r.get("live_fix") is not None:
            seen_live = True
        if r["status"] != "running":
            r["_seen_live"] = seen_live
            return r
        time.sleep(2)
    pytest.fail("test run did not finish in time")


# ---------- Diff API ----------
class TestDiff:
    def _versions(self, c):
        r = c.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/versions")
        assert r.status_code == 200
        return r.json()

    def test_diff_first_vs_current(self, client_a):
        vs = self._versions(client_a)
        assert len(vs) >= 2
        first = vs[-1]
        r = client_a.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": first["id"], "target": "current"})
        assert r.status_code == 200
        d = r.json()
        assert d["base"] == f"v{first['number']}" and d["target"] == "Current"
        assert isinstance(d["files"], list) and len(d["files"]) > 0
        assert d["additions"] == sum(f["additions"] for f in d["files"])
        assert d["deletions"] == sum(f["deletions"] for f in d["files"])
        for f in d["files"]:
            assert f["status"] in ("added", "removed", "modified")
            for h in f["hunks"]:
                assert h["header"].startswith("@@")
                for ln in h["lines"]:
                    assert ln["t"] in ("+", "-", " ") and "s" in ln
                    if ln["t"] == "+":
                        assert ln["o"] is None and isinstance(ln["n"], int)
                    if ln["t"] == "-":
                        assert ln["n"] is None and isinstance(ln["o"], int)
            plus = sum(1 for h in f["hunks"] for ln in h["lines"] if ln["t"] == "+")
            minus = sum(1 for h in f["hunks"] for ln in h["lines"] if ln["t"] == "-")
            if not f["truncated"]:
                assert plus == f["additions"] and minus == f["deletions"]

    def test_diff_reverse_swaps_counts(self, client_a):
        vs = self._versions(client_a)
        first = vs[-1]["id"]
        a = client_a.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": first, "target": "current"}).json()
        b = client_a.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": "current", "target": first}).json()
        assert a["additions"] == b["deletions"] and a["deletions"] == b["additions"]

    def test_diff_identical(self, client_a):
        r = client_a.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": "current", "target": "current"})
        assert r.status_code == 200 and r.json()["files"] == []
        vid = self._versions(client_a)[0]["id"]
        r = client_a.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": vid, "target": vid})
        assert r.status_code == 200 and r.json()["files"] == [] and r.json()["additions"] == 0

    def test_diff_unknown_version(self, client_a):
        r = client_a.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": "nope", "target": "current"})
        assert r.status_code == 404

    def test_diff_other_user(self, client_b):
        r = client_b.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": "current", "target": "current"})
        assert r.status_code == 404

    def test_diff_no_token(self):
        r = requests.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": "current", "target": "current"})
        assert r.status_code == 401


# ---------- Test runs API ----------
BACKEND_ENV = Path(__file__).resolve().parents[1] / ".env"

SECURITY_TEST = f'''
import os, socket, subprocess, pytest

def test_tcp_blocked():
    with pytest.raises(PermissionError):
        socket.create_connection(("127.0.0.1", 27017), timeout=3)

def test_env_unreadable():
    with pytest.raises(PermissionError):
        open("{BACKEND_ENV}").read()

def test_no_secrets_in_env():
    keys = " ".join(os.environ)
    assert "MONGO" not in keys and "CLERK" not in keys and "KEY" not in keys

def test_proc1_environ_unreadable():
    with pytest.raises(PermissionError):
        open("/proc/1/environ").read()

def test_unix_socket_connect_blocked():
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with pytest.raises(OSError):
        s.connect("/tmp/mongodb-27017.sock")

def test_curl_blocked():
    r = subprocess.run(["python3", "-c", "import urllib.request;urllib.request.urlopen('http://example.com',timeout=3)"], capture_output=True)
    assert r.returncode != 0
'''


class TestRuns:
    def test_run_validation(self, client_a, client_b):
        r = client_a.post(f"{BASE_URL}/api/projects/{SAMPLE_PID}/tests/run", json={"max_attempts": 5})
        assert r.status_code == 422
        r = client_a.post(f"{BASE_URL}/api/projects/{SAMPLE_PID}/tests/run", json={"max_attempts": 0})
        assert r.status_code == 422
        r = client_b.post(f"{BASE_URL}/api/projects/{SAMPLE_PID}/tests/run", json={})
        assert r.status_code == 404
        assert requests.post(f"{BASE_URL}/api/projects/{SAMPLE_PID}/tests/run", json={}).status_code == 401
        assert client_b.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/tests/runs").status_code == 404

    def test_run_no_files_400(self, client_a):
        pid = _insert_project([], "nofiles")
        try:
            r = client_a.post(f"{BASE_URL}/api/projects/{pid}/tests/run", json={})
            assert r.status_code == 400
        finally:
            _cleanup(pid)

    def test_sandbox_security_single_attempt(self, client_a):
        pid = _insert_project([{"path": "tests/test_security.py", "content": SECURITY_TEST}], "sandbox")
        try:
            r = client_a.post(f"{BASE_URL}/api/projects/{pid}/tests/run", json={"auto_fix": False, "max_attempts": 1})
            assert r.status_code == 200
            run = r.json()
            assert run["status"] == "running" and run["auto_fix"] is False
            # busy -> 409
            r2 = client_a.post(f"{BASE_URL}/api/projects/{pid}/tests/run", json={"auto_fix": False, "max_attempts": 1})
            assert r2.status_code == 409
            done = _wait_run(client_a, pid, run["id"])
            assert len(done["attempts"]) == 1 and done["attempts"][0]["fix"] is None
            cases = {c["name"]: c for c in done["attempts"][0]["cases"]}
            print({k: (v["status"], v["message"][:200]) for k, v in cases.items()})
            for name in ("test_tcp_blocked", "test_env_unreadable", "test_no_secrets_in_env",
                         "test_proc1_environ_unreadable", "test_unix_socket_connect_blocked", "test_curl_blocked"):
                assert cases[name]["status"] == "passed", (name, cases[name]["message"][:500])
            assert done["status"] == "passed"
            p = client_a.get(f"{BASE_URL}/api/projects/{pid}").json()
            assert p["version_count"] == 0 and p["busy"] is False
            assert p["test_summary"]["status"] == "passed" and p["test_summary"]["run_id"] == run["id"]
            lst = client_a.get(f"{BASE_URL}/api/projects").json()
            assert next(x for x in lst if x["id"] == pid)["test_summary"]["passed"] == 6
        finally:
            _cleanup(pid)

    def test_failing_no_autofix_one_attempt(self, client_a):
        files = [{"path": "calc.py", "content": "def add(a, b):\n    return a - b\n"},
                 {"path": "test_calc.py", "content": "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n\ndef test_ok():\n    assert True\n"}]
        pid = _insert_project(files, "nofix")
        try:
            run = client_a.post(f"{BASE_URL}/api/projects/{pid}/tests/run", json={"auto_fix": False, "max_attempts": 1}).json()
            done = _wait_run(client_a, pid, run["id"])
            assert done["status"] == "failed"
            a = done["attempts"][0]
            assert len(done["attempts"]) == 1 and a["fix"] is None and a["passed"] == 1 and a["failed"] == 1
            assert client_a.get(f"{BASE_URL}/api/projects/{pid}").json()["version_count"] == 0
        finally:
            _cleanup(pid)

    def test_no_runnable_tests(self, client_a):
        pid = _insert_project([{"path": "main.py", "content": "print(1)\n"}], "notests")
        try:
            run = client_a.post(f"{BASE_URL}/api/projects/{pid}/tests/run", json={"auto_fix": True}).json()
            done = _wait_run(client_a, pid, run["id"])
            assert done["status"] == "no_tests"
        finally:
            _cleanup(pid)

    def test_autofix_creates_version(self, client_a):
        files = [{"path": "calc.py", "content": "def add(a, b):\n    return a - b\n"},
                 {"path": "test_calc.py", "content": "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"}]
        pid = _insert_project(files, "autofix")
        try:
            run = client_a.post(f"{BASE_URL}/api/projects/{pid}/tests/run", json={"auto_fix": True, "max_attempts": 2}).json()
            done = _wait_run(client_a, pid, run["id"], timeout=280)
            print("status", done["status"], "live seen", done["_seen_live"], done.get("note"))
            assert done["status"] == "passed"
            assert len(done["attempts"]) == 2
            fix = done["attempts"][0]["fix"]
            assert fix and fix["version"] == 1 and "calc.py" in fix["changed_files"] and fix["explanation"]
            p = client_a.get(f"{BASE_URL}/api/projects/{pid}").json()
            assert p["version_count"] == 1
            vs = client_a.get(f"{BASE_URL}/api/projects/{pid}/versions").json()
            assert vs[0]["label"].startswith("Auto-fix")
            d = client_a.get(f"{BASE_URL}/api/projects/{pid}/diff", params={"base": vs[0]["id"], "target": "current"}).json()
            assert d["files"] == []
        finally:
            _cleanup(pid)
