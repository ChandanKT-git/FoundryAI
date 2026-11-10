"""Live sandboxed backends: run a generated FastAPI app on a private unix socket and proxy HTTP to it."""
import asyncio
import collections
import json
import os
import re
import secrets
import signal
import time
from pathlib import Path

import httpx

try:
    from backend import sandbox
except ModuleNotFoundError:
    import sandbox

APP_RE = re.compile(r"^(\w+)\s*(?::\s*FastAPI\s*)?=\s*FastAPI\(", re.M)
FACTORY_RE = re.compile(r"^def\s+(create_app|get_app|make_app)\s*\(", re.M)
IDLE_LIMIT = 20 * 60
MAX_AGE = 2 * 3600
MAX_RUNNING = 8
MAX_PER_USER = 2
HOP = {"host", "connection", "keep-alive", "content-length", "transfer-encoding", "te", "trailer", "upgrade",
       "cookie", "content-encoding", "proxy-authorization", "via", "forwarded", "true-client-ip"}
INFRA_PREFIXES = ("origin", "x-forwarded", "x-real-ip", "x-request-id", "x-cloud", "x-envoy", "x-original", "sec-",
                  "cf-", "cloudflare", "cdn-", "priority")

RUNTIMES: dict = {}   # project_id -> Runtime
BY_TOKEN: dict = {}   # token -> project_id
_locks: dict = {}


class Runtime:
    def __init__(self, project_id: str, user_id: str, token: str):
        self.project_id, self.user_id, self.token = project_id, user_id, token
        self.status, self.error, self.entry = "starting", None, None
        self.logs = collections.deque(maxlen=400)
        self.proc = self.root = self.uid = self.client = self.pump = None
        self.started_at = self.last_used = time.time()
        self.version = None

    def info(self) -> dict:
        return {"status": self.status, "error": self.error, "entry": self.entry, "token": self.token,
                "base_path": f"/api/runtime/{self.token}", "started_at": self.started_at,
                "version": self.version, "logs": "\n".join(self.logs)}


def find_entry(files: list):
    cands = []
    for f in files:
        p = f["path"]
        if not p.endswith(".py") or sandbox.PY_TEST.search(p) or "/tests/" in f"/{p}":
            continue
        m = APP_RE.search(f["content"])
        if m:
            cands.append((p, m.group(1), False))
            continue
        m = FACTORY_RE.search(f["content"])
        if m and "FastAPI(" in f["content"]:
            cands.append((p, m.group(1), True))
    cands.sort(key=lambda c: (not c[0].startswith("backend/"), Path(c[0]).name not in ("main.py", "app.py", "server.py"), len(c[0])))
    return cands[0] if cands else None


def module_for(root: Path, path: str) -> str:
    target = root / path
    bases = sorted((Path(b) for b in sandbox.python_paths(root)), key=lambda b: len(b.parts), reverse=True)
    base = next(b for b in bases if b in target.parents)
    return ".".join(target.relative_to(base).with_suffix("").parts)


async def _pump(rt: Runtime):
    async for line in rt.proc.stdout:
        text = line.decode(errors="replace").rstrip()
        rt.logs.append(text.replace(str(rt.root), "/sandbox") if rt.root else text)
    await rt.proc.wait()
    if rt.status in ("running", "starting"):
        rt.status = "crashed"
        last = next((ln for ln in reversed(rt.logs) if ln.strip()), "")
        rt.error = f"The backend process exited (code {rt.proc.returncode}): {last[:240]}"


async def _cleanup(rt: Runtime):
    if rt.proc and rt.proc.returncode is None:
        try:
            os.killpg(rt.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await rt.proc.wait()
    if rt.pump:
        rt.pump.cancel()
    if rt.client:
        await rt.client.aclose()
    if rt.root:
        sandbox.release_dir(rt.root, rt.uid)
    rt.proc = rt.client = rt.root = rt.pump = None


async def stop(project_id: str, reason: str = "Stopped"):
    rt = RUNTIMES.get(project_id)
    if not rt:
        return
    await _cleanup(rt)
    if rt.status not in ("crashed", "failed"):
        rt.status, rt.error = "stopped", None if reason == "Stopped" else reason


def running_count(user_id: str = None) -> int:
    return sum(1 for r in RUNTIMES.values() if r.status in ("running", "starting") and (user_id is None or r.user_id == user_id))


async def start(project: dict) -> Runtime:
    pid = project["id"]
    lock = _locks.setdefault(pid, asyncio.Lock())
    async with lock:
        old = RUNTIMES.get(pid)
        token = old.token if old else secrets.token_urlsafe(24)
        if old:
            await _cleanup(old)
        others = [r for r in RUNTIMES.values() if r.project_id != pid and r.status in ("running", "starting")]
        if len(others) >= MAX_RUNNING:
            raise RuntimeError("Too many live backends are running right now. Try again in a few minutes.")
        if sum(1 for r in others if r.user_id == project["user_id"]) >= MAX_PER_USER:
            raise RuntimeError(f"You can run up to {MAX_PER_USER} live backends at once. Stop another project's backend first.")
        rt = Runtime(pid, project["user_id"], token)
        rt.version = project.get("version_count", 0)
        RUNTIMES[pid], BY_TOKEN[token] = rt, pid
        entry = find_entry(project["files"])
        if not entry:
            rt.status, rt.error = "failed", "No FastAPI app found. The backend needs a module like backend/app/main.py with `app = FastAPI()`."
            return rt
        await sandbox.ensure_venv()
        rt.root, rt.uid = await sandbox.prepare_dir(project["files"])
        sock = rt.root / ".foundry" / "app.sock"
        module = module_for(rt.root, entry[0])
        rt.entry = f"{module}:{entry[1]}{' (factory)' if entry[2] else ''}"
        cmd = sandbox.launch_cmd(rt.uid, rt.root) + [str(sandbox.VENV / "bin" / "python"), "-m", "uvicorn",
                                                      f"{module}:{entry[1]}", "--uds", str(sock)]
        if entry[2]:
            cmd.append("--factory")
        env = {"PATH": os.environ.get("PATH", ""), "SANDBOX_PYTHONPATH": ":".join(sandbox.python_paths(rt.root)),
               "SANDBOX_CPU": "300", "SANDBOX_MEM": str(1024 * 2**20), "SANDBOX_ENV": json.dumps({
                   "DATABASE_URL": f"sqlite:///{rt.root}/.foundry/app.db", "FOUNDRY_SANDBOX": "1", "FORGE_SANDBOX": "1", "PYTHONUNBUFFERED": "1"})}
        rt.logs.append(f"$ uvicorn {module}:{entry[1]}  (sandboxed, no network, 1 GB memory)")
        rt.proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                                                       env=env, start_new_session=True)
        rt.pump = asyncio.create_task(_pump(rt))
        rt.client = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=str(sock)), base_url="http://sandbox", timeout=30)
        for _ in range(60):
            if rt.status == "crashed":
                break
            if sock.exists():
                try:
                    await rt.client.get("/", timeout=3)
                    rt.status = "running"
                    break
                except httpx.HTTPError:
                    pass
            await asyncio.sleep(0.5)
        if rt.status == "starting":
            rt.status, rt.error = "failed", "The backend did not start within 30 seconds."
        if rt.status != "running":
            await _cleanup(rt)
        rt.last_used = time.time()
        return rt


async def forward(token: str, path: str, method: str, query: list, headers: dict, body: bytes):
    """Returns (status, headers, content)."""
    rt = RUNTIMES.get(BY_TOKEN.get(token, ""))
    if not rt or rt.status != "running" or not rt.client:
        return 503, {"content-type": "application/json"}, b'{"detail":"Live backend is not running. Start it from the preview pane."}'
    rt.last_used = time.time()
    fwd = {k: v for k, v in headers.items() if k.lower() not in HOP and not k.lower().startswith(INFRA_PREFIXES)}
    try:
        r = await rt.client.request(method, "/" + path, params=query, headers=fwd, content=body)
    except httpx.HTTPError as exc:
        return 502, {"content-type": "application/json"}, json.dumps({"detail": f"Backend error: {exc}"}).encode()
    out = {}
    for k, v in r.headers.items():
        lk = k.lower()
        if lk in HOP or lk.startswith("access-control-") or lk == "set-cookie":
            continue
        if lk == "location" and v.startswith("http://sandbox"):
            v = f"/api/runtime/{token}" + v[len("http://sandbox"):]
        elif lk == "location" and v.startswith("/") and not v.startswith("//") and not v.startswith("/api/runtime/"):
            v = f"/api/runtime/{token}" + v
        out[k] = v
    return r.status_code, out, r.content


async def reaper():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        for pid, rt in list(RUNTIMES.items()):
            if rt.status == "running" and (now - rt.last_used > IDLE_LIMIT or now - rt.started_at > MAX_AGE):
                await stop(pid, "Stopped automatically after inactivity.")
            elif rt.status == "crashed" and rt.proc is not None:
                await _cleanup(rt)


async def forget(project_id: str):
    await stop(project_id)
    rt = RUNTIMES.pop(project_id, None)
    if rt:
        BY_TOKEN.pop(rt.token, None)


async def stop_all():
    for pid in list(RUNTIMES):
        await stop(pid)
