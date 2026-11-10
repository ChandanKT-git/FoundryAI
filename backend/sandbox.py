import asyncio
import itertools
import os
import re
import shutil
import signal
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

LAUNCHER = str(Path(__file__).parent / "sandbox_launch.py")
VENV = Path("/opt/foundry-sandbox")
PACKAGES = ["pytest", "pytest-asyncio", "fastapi", "uvicorn", "httpx", "pydantic", "sqlalchemy", "aiosqlite",
            "python-multipart", "email-validator"]
AVAILABLE = ("Python 3.11 with only: " + ", ".join(PACKAGES) + " and the standard library; "
             "Node.js 24 with only built-in modules (node:test, node:assert). No network, no package installs.")
_venv_lock = asyncio.Lock()
_uids = itertools.cycle(range(61000, 65000))
_active_uids: set = set()


def _take_uid() -> int:
    while True:
        uid = next(_uids)
        if uid not in _active_uids:
            _active_uids.add(uid)
            return uid

PY_TEST = re.compile(r"(^|/)(test_[^/]*|[^/]*_test)\.py$")
JS_TEST = re.compile(r"\.(test|spec)\.(m?js|cjs|jsx|tsx?)$")
BARE_IMPORT = re.compile(r"""(?:from\s+|require\(\s*|import\s+)['"]([^'"./][^'"]*)['"]""")


async def _run(cmd: list, timeout: int, env: dict | None = None) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                                                env=env, start_new_session=True)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        return proc.returncode, out.decode(errors="replace")
    except asyncio.TimeoutError:
        os.killpg(proc.pid, signal.SIGKILL)
        await proc.wait()
        return -9, f"Timed out after {timeout}s"


async def ensure_venv():
    async with _venv_lock:
        if (VENV / "bin" / "pytest").exists() and (VENV / "bin" / "uvicorn").exists():
            return
        code, out = 0, ""
        if not (VENV / "bin" / "pip").exists():
            base_python = os.path.join(sys.base_prefix, "bin", "python3")
            code, out = await _run([base_python, "-m", "venv", str(VENV)], 120)
        if code == 0:
            code, out = await _run([str(VENV / "bin" / "pip"), "install", "-q", *PACKAGES], 300)
        if code != 0:
            shutil.rmtree(VENV, ignore_errors=True)
            raise RuntimeError(f"Could not prepare the sandbox: {out[-400:]}")


def classify(files: list) -> tuple[list, list, list]:
    py, js, skipped = [], [], []
    for f in files:
        path, content = f["path"], f["content"]
        if PY_TEST.search(path):
            py.append(path)
        elif JS_TEST.search(path):
            bare = [m for m in BARE_IMPORT.findall(content) if not m.startswith("node:")]
            if path.endswith((".jsx", ".ts", ".tsx")) or bare or "node:test" not in content:
                reason = f"needs packages ({', '.join(sorted(set(bare))[:3])})" if bare else "needs a JS build/test toolchain"
                skipped.append({"name": path, "file": path, "status": "skipped",
                                "message": f"Not run in sandbox: {reason}. Only plain node:test files run."})
            else:
                js.append(path)
    return py, js, skipped


def parse_junit(xml_path: Path, kind: str) -> list:
    cases = []
    for tc in ET.parse(xml_path).getroot().iter("testcase"):
        status, message = "passed", ""
        for child in tc:
            if child.tag in ("failure", "error"):
                status = "failed" if child.tag == "failure" else "error"
                message = (child.get("message") or "") + "\n" + (child.text or "")
            elif child.tag == "skipped":
                status, message = "skipped", child.get("message") or ""
        cases.append({"name": tc.get("name", "test"), "file": tc.get("classname") or tc.get("file") or kind,
                      "status": status, "message": message.strip()[:3000], "time": float(tc.get("time") or 0)})
    return cases


def _write_files(root: Path, files: list):
    for f in files:
        rel = Path(f["path"])
        if rel.is_absolute() or ".." in rel.parts:
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f["content"])


async def prepare_dir(files: list) -> tuple[Path, int]:
    """Write project files into a fresh private dir owned by a fresh sandbox uid."""
    uid = _take_uid()
    root = Path(tempfile.mkdtemp(prefix="foundry-run-"))
    _write_files(root, files)
    (root / ".foundry").mkdir()
    await _run(["chown", "-R", f"{uid}:{uid}", str(root)], 30)
    os.chmod(root, 0o700)
    return root, uid


def release_dir(root: Path, uid: int):
    shutil.rmtree(root, ignore_errors=True)
    _active_uids.discard(uid)


def launch_cmd(uid: int, root: Path) -> list:
    return [sys.executable, LAUNCHER, str(uid), str(root)]


def python_paths(root: Path) -> list:
    return [str(root)] + [str(root / d) for d in ("backend", "server", "api", "src", "backend/src") if (root / d).is_dir()]


async def run_tests(files: list) -> dict:
    py, js, cases = classify(files)
    started = time.time()
    outputs = []
    if not py and not js:
        return _summary(cases, "No runnable test files found.", started)
    root, uid = await prepare_dir(files)
    try:
        launch = launch_cmd(uid, root)
        if py:
            await ensure_venv()
            env = {"SANDBOX_PYTHONPATH": ":".join(python_paths(root)), "PATH": os.environ.get("PATH", "")}
            code, out = await _run(launch + [str(VENV / "bin" / "python"), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                             "--import-mode=importlib", "-o", "asyncio_mode=auto", "--rootdir", str(root),
                                             "--junitxml=.foundry/py.xml", *py], 150, env)
            outputs.append("$ pytest\n" + out)
            cases += _collect(root / ".foundry" / "py.xml", "pytest", out)
        if js:
            code, out = await _run(launch + ["node", "--test", "--test-reporter=junit",
                                             "--test-reporter-destination=.foundry/js.xml", "--test-reporter=spec",
                                             "--test-reporter-destination=stdout", *js], 120)
            outputs.append("$ node --test\n" + out)
            cases += _collect(root / ".foundry" / "js.xml", "node", out)
    finally:
        release_dir(root, uid)
    return _summary(cases, "\n\n".join(outputs), started)


def _collect(xml_path: Path, kind: str, out: str) -> list:
    try:
        found = parse_junit(xml_path, kind)
    except (OSError, ET.ParseError):
        found = []
    if not found:
        return [{"name": f"{kind} run", "file": kind, "status": "error", "message": out[-3000:], "time": 0}]
    return found


def _summary(cases: list, output: str, started: float) -> dict:
    count = lambda s: sum(1 for c in cases if c["status"] == s)  # noqa: E731
    return {"cases": cases, "output": output[-20000:], "passed": count("passed"), "failed": count("failed"),
            "errors": count("error"), "skipped": count("skipped"), "duration": round(time.time() - started, 2)}
