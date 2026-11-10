# FoundryAI slow LLM flows on the sample project: chat edit (+409 busy), apply-fix, version restore
import time
from conftest import BASE_URL, SAMPLE_PID

P = f"{BASE_URL}/api/projects/{SAMPLE_PID}"


def wait_idle(c, timeout=280):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not c.get(P).json()["busy"]:
            return True
        time.sleep(4)
    return False


class TestLLMFlows:
    def test_chat_edit(self, client_a):
        assert wait_idle(client_a, 60)
        v_before = client_a.get(P).json()["version_count"]
        r = client_a.post(f"{P}/chat", json={"message": "TEST_ change the page title in preview.html to 'TaskFlow Pro'",
                                              "model": "gpt-6-luna"})
        assert r.status_code == 200, r.text
        mid = r.json()["message_id"]
        assert client_a.get(P).json()["busy"] is True
        r2 = client_a.post(f"{P}/chat", json={"message": "second request"})
        assert r2.status_code == 409
        saw_streaming = False
        t0 = time.time()
        msg = None
        while time.time() - t0 < 250:
            msgs = client_a.get(f"{P}/messages").json()
            msg = next(m for m in msgs if m["id"] == mid)
            if msg["status"] == "streaming":
                saw_streaming = True
            else:
                break
            time.sleep(3)
        print("final msg:", msg["status"], msg["changed_files"], msg["version"], msg["content"][:200])
        assert saw_streaming
        assert msg["status"] == "done"
        assert msg["changed_files"] and msg["version"] == v_before + 1
        assert wait_idle(client_a, 30)
        assert client_a.get(P).json()["version_count"] == v_before + 1

    def test_apply_fix(self, client_a):
        assert wait_idle(client_a, 60)
        p = client_a.get(P).json()
        issue = next(i for i in p["review"]["issues"] if i["status"] == "open")
        v_before = p["version_count"]
        r = client_a.post(f"{P}/issues/{issue['id']}/fix", json={"model": "gpt-6-luna"})
        assert r.status_code == 200, r.text
        assert wait_idle(client_a, 270)
        p = client_a.get(P).json()
        st = next(i for i in p["review"]["issues"] if i["id"] == issue["id"])["status"]
        msgs = client_a.get(f"{P}/messages").json()
        m = next(m for m in msgs if m["id"] == r.json()["message_id"])
        print("fix msg:", m["status"], m["changed_files"], m["version"])
        assert st == "fixed"
        assert p["version_count"] == v_before + 1

    def test_restore(self, client_a):
        assert wait_idle(client_a, 60)
        vs = client_a.get(f"{P}/versions").json()
        v1 = next(v for v in vs if v["number"] == 1)
        v1_files = client_a.get(f"{P}/versions/{v1['id']}").json()["files"]
        r = client_a.post(f"{P}/versions/{v1['id']}/restore")
        assert r.status_code == 200
        n = r.json()["version"]
        assert n == len(vs) + 1 or n == max(v["number"] for v in vs) + 1
        p = client_a.get(P).json()
        assert p["files"] == v1_files and p["version_count"] == n
        vs2 = client_a.get(f"{P}/versions").json()
        assert vs2[0]["number"] == n and vs2[0]["label"] == "Restored v1"
