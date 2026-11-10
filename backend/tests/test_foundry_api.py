# FoundryAI fast API tests: auth, isolation, validation, project reads, model, logs, versions
import requests
import pytest
from conftest import BASE_URL, SAMPLE_PID

P = f"{BASE_URL}/api/projects/{SAMPLE_PID}"


class TestAuthRequired:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/projects"), ("post", "/api/projects"), ("get", f"/api/projects/{SAMPLE_PID}"),
        ("delete", f"/api/projects/{SAMPLE_PID}"), ("post", f"/api/projects/{SAMPLE_PID}/chat"),
        ("get", f"/api/projects/{SAMPLE_PID}/messages"), ("get", f"/api/projects/{SAMPLE_PID}/versions"),
        ("patch", f"/api/projects/{SAMPLE_PID}/model"), ("post", f"/api/projects/{SAMPLE_PID}/resume"),
        ("get", f"/api/projects/{SAMPLE_PID}/logs/plan"),
    ])
    def test_401_without_token(self, method, path):
        r = getattr(requests, method)(BASE_URL + path, json={})
        assert r.status_code == 401, f"{method} {path} -> {r.status_code}"

    def test_public_models(self):
        r = requests.get(f"{BASE_URL}/api/models")
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()["models"]]
        assert set(ids) == {"claude-opus-5-5", "claude-sonnet-5-5", "gpt-6-luna", "gemini-3.1-pro-preview"}


class TestIsolation:
    def test_b_cannot_access_a(self, client_b):
        assert client_b.get(P).status_code == 404
        assert client_b.patch(f"{P}/model", json={"model": "gpt-6-luna"}).status_code == 404
        assert client_b.post(f"{P}/chat", json={"message": "hi there"}).status_code == 404
        assert client_b.post(f"{P}/resume").status_code == 404
        assert client_b.get(f"{P}/messages").status_code == 404
        assert client_b.get(f"{P}/versions").status_code == 404
        assert client_b.delete(P).status_code == 404

    def test_b_list_excludes_a(self, client_b):
        r = client_b.get(f"{BASE_URL}/api/projects")
        assert r.status_code == 200
        assert SAMPLE_PID not in [p["id"] for p in r.json()]

    def test_a_still_has_project(self, client_a):
        assert client_a.get(P).status_code == 200


class TestProjectReads:
    def test_list_own(self, client_a):
        r = client_a.get(f"{BASE_URL}/api/projects")
        assert r.status_code == 200
        d = next(p for p in r.json() if p["id"] == SAMPLE_PID)
        assert d["file_count"] > 0 and isinstance(d["score"], int)
        assert "files" not in d and "plan" not in d

    def test_get_detail(self, client_a):
        d = client_a.get(P).json()
        for k in ("plan", "architecture", "files", "review", "stage_status", "live"):
            assert k in d
        assert "_id" not in d and "logs" not in d
        assert any(f["path"] == "preview.html" for f in d["files"])
        assert d["review"]["issues"]

    def test_logs(self, client_a):
        r = client_a.get(f"{P}/logs/plan")
        assert r.status_code == 200 and r.json()["stage"] == "plan" and len(r.json()["text"]) > 50

    def test_get_404(self, client_a):
        assert client_a.get(f"{BASE_URL}/api/projects/nonexistent-id").status_code == 404


class TestValidation:
    def test_invalid_model(self, client_a):
        r = client_a.post(f"{BASE_URL}/api/projects", json={"idea": "A todo list app", "model": "bogus"})
        assert r.status_code == 400

    def test_short_idea(self, client_a):
        r = client_a.post(f"{BASE_URL}/api/projects", json={"idea": "abc", "model": "gpt-6-luna"})
        assert r.status_code == 422

    def test_chat_empty(self, client_a):
        assert client_a.post(f"{P}/chat", json={"message": ""}).status_code == 422

    def test_fix_unknown_issue(self, client_a):
        assert client_a.post(f"{P}/issues/nope/fix", json={}).status_code == 404

    def test_patch_model_invalid(self, client_a):
        assert client_a.patch(f"{P}/model", json={"model": "bogus"}).status_code == 400


class TestModelAndVersions:
    def test_patch_model_roundtrip(self, client_a):
        orig = client_a.get(P).json()["model"]
        r = client_a.patch(f"{P}/model", json={"model": "gpt-6-luna"})
        assert r.status_code == 200 and r.json()["model"] == "gpt-6-luna"
        assert client_a.get(P).json()["model"] == "gpt-6-luna"
        client_a.patch(f"{P}/model", json={"model": orig})

    def test_versions_list_and_detail(self, client_a):
        vs = client_a.get(f"{P}/versions").json()
        assert len(vs) >= 1 and "files" not in vs[0]
        d = client_a.get(f"{P}/versions/{vs[-1]['id']}").json()
        assert d["files"] and d["number"] == vs[-1]["number"]
        assert client_a.get(f"{P}/versions/nope").status_code == 404
