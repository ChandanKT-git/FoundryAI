# Iteration 3: sandbox uid uniqueness, file visibility hardening, test_summary.version/stale, diff trailing-newline, regression
import sys
import uuid
from pathlib import Path

import requests

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(TESTS_DIR))

from conftest import BASE_URL, SAMPLE_PID  # noqa: E402
from test_foundry_diff_tests import DB, _insert_project, _cleanup, _wait_run, _now  # noqa: E402


# ---------- sandbox uid allocation (unit) ----------
def test_take_uid_distinct():
    import sandbox
    a = sandbox._take_uid()
    b = sandbox._take_uid()
    try:
        assert a != b
        assert 61000 <= a < 65000 and 61000 <= b < 65000
        assert a in sandbox._active_uids and b in sandbox._active_uids
    finally:
        sandbox._active_uids.discard(a)
        sandbox._active_uids.discard(b)


def test_take_uid_skips_in_use():
    import sandbox
    taken = [sandbox._take_uid() for _ in range(50)]
    try:
        assert len(set(taken)) == 50
    finally:
        for u in taken:
            sandbox._active_uids.discard(u)


VIS_TEST = f'''
import os, socket, subprocess, pytest

def test_supervisor_logs_hidden():
    with pytest.raises(PermissionError):
        os.listdir("/var/log/supervisor")

def test_supervisor_log_read_hidden():
    with pytest.raises(PermissionError):
        open("/var/log/supervisor/backend.err.log").read()

def test_supervisor_conf_hidden():
    with pytest.raises(PermissionError):
        os.listdir("/etc/supervisor")

def test_memory_hidden():
    with pytest.raises(PermissionError):
        os.listdir("{ROOT_DIR}/memory")

def test_creds_hidden():
    with pytest.raises(PermissionError):
        open("{ROOT_DIR}/memory/test_credentials.md").read()

def test_env_unreadable():
    with pytest.raises(PermissionError):
        open("{BACKEND_DIR}/.env").read()

def test_tcp_blocked():
    with pytest.raises(PermissionError):
        socket.create_connection(("127.0.0.1", 27017), timeout=3)

def test_net_blocked():
    r = subprocess.run(["python3", "-c", "import urllib.request;urllib.request.urlopen('http://example.com',timeout=3)"], capture_output=True)
    assert r.returncode != 0
'''


class TestSandboxRuns:
    def test_visibility_and_summary_version(self, client_a):
        pid = _insert_project([{"path": "tests/test_vis.py", "content": VIS_TEST}], "vis")
        try:
            r = client_a.post(f"{BASE_URL}/api/projects/{pid}/tests/run", json={"auto_fix": False, "max_attempts": 1})
            assert r.status_code == 200
            done = _wait_run(client_a, pid, r.json()["id"])
            cases = {c["name"]: c for c in done["attempts"][0]["cases"]}
            print({k: (v["status"], v["message"][:150]) for k, v in cases.items()})
            assert len(cases) == 8
            for name, c in cases.items():
                assert c["status"] == "passed", (name, c["message"][:400])
            assert done["status"] == "passed"
            p = client_a.get(f"{BASE_URL}/api/projects/{pid}").json()
            ts = p["test_summary"]
            assert ts["version"] == 0 == p["version_count"]
            assert ts["passed"] == 8
        finally:
            _cleanup(pid)

    def test_concurrent_runs(self, client_a):
        files = [{"path": "test_a.py", "content": "import os, time\n\ndef test_uid():\n    time.sleep(2)\n    open('uid.txt','w').write(str(os.getuid()))\n    assert os.getuid() >= 61000\n"}]
        p1 = _insert_project(files, "conc1")
        p2 = _insert_project(files, "conc2")
        try:
            r1 = client_a.post(f"{BASE_URL}/api/projects/{p1}/tests/run", json={"auto_fix": False, "max_attempts": 1})
            r2 = client_a.post(f"{BASE_URL}/api/projects/{p2}/tests/run", json={"auto_fix": False, "max_attempts": 1})
            assert r1.status_code == 200 and r2.status_code == 200
            d1 = _wait_run(client_a, p1, r1.json()["id"])
            d2 = _wait_run(client_a, p2, r2.json()["id"])
            assert d1["status"] == "passed" and d2["status"] == "passed"
        finally:
            _cleanup(p1)
            _cleanup(p2)

    def test_stale_after_restore(self, client_a):
        files = [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"},
                 {"path": "test_calc.py", "content": "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"}]
        pid = _insert_project(files, "stale")
        p = DB.projects.find_one({"id": pid}, {"_id": 0})
        vid = str(uuid.uuid4())
        DB.versions.insert_one({"id": vid, "project_id": pid, "user_id": p["user_id"], "number": 1, "label": "TEST v1",
                                "files": files, "file_count": 2, "created_at": _now()})
        DB.projects.update_one({"id": pid}, {"$set": {"version_count": 1}})
        try:
            run = client_a.post(f"{BASE_URL}/api/projects/{pid}/tests/run", json={"auto_fix": False, "max_attempts": 1}).json()
            _wait_run(client_a, pid, run["id"])
            pr = client_a.get(f"{BASE_URL}/api/projects/{pid}").json()
            assert pr["test_summary"]["version"] == 1 and pr["version_count"] == 1
            # find restore endpoint
            rr = client_a.post(f"{BASE_URL}/api/projects/{pid}/versions/{vid}/restore")
            print("restore", rr.status_code, rr.text[:200])
            assert rr.status_code == 200
            pr = client_a.get(f"{BASE_URL}/api/projects/{pid}").json()
            assert pr["version_count"] == 2
            assert pr["test_summary"]["version"] < pr["version_count"]
        finally:
            _cleanup(pid)


# ---------- diff ----------
def test_diff_trailing_newline_only(client_a):
    v1 = [{"path": "a.py", "content": "x = 1"}, {"path": "b.py", "content": "y\n"}]
    v2 = [{"path": "a.py", "content": "x = 1\n"}, {"path": "b.py", "content": "y\nz\n"}]
    pid = _insert_project(v2, "diffnl")
    p = DB.projects.find_one({"id": pid}, {"_id": 0})
    vid = str(uuid.uuid4())
    DB.versions.insert_one({"id": vid, "project_id": pid, "user_id": p["user_id"], "number": 1, "label": "TEST v1",
                            "files": v1, "file_count": 2, "created_at": _now()})
    try:
        d = client_a.get(f"{BASE_URL}/api/projects/{pid}/diff", params={"base": vid, "target": "current"}).json()
        fs = {f["path"]: f for f in d["files"]}
        print(fs.get("a.py"))
        assert fs["a.py"]["status"] == "modified" and fs["a.py"]["hunks"] == []
        assert fs["b.py"]["additions"] == 1 and len(fs["b.py"]["hunks"]) >= 1
    finally:
        _cleanup(pid)


def test_sample_diff_hunks(client_a):
    vs = client_a.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/versions").json()
    d = client_a.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": vs[-1]["id"], "target": "current"}).json()
    assert any(f["hunks"] for f in d["files"])
    assert requests.get(f"{BASE_URL}/api/projects/{SAMPLE_PID}/diff", params={"base": "current", "target": "current"}).status_code == 401
