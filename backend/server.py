import asyncio
import logging
import os
import uuid
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, StringConstraints
from pymongo import ASCENDING, DESCENDING, IndexModel
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

try:  # launched as `backend.server` (the default)
    from backend.clerk_auth import clerk_router, require_user
    from backend import engine, sandbox, diffs, runtime
except ModuleNotFoundError:  # launched from inside backend/ as `server`
    from clerk_auth import clerk_router, require_user
    import engine
    import sandbox
    import diffs
    import runtime

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
logger = logging.getLogger("foundryai")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

INDEXES: dict[str, list[IndexModel]] = {
    "projects": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("user_id", ASCENDING), ("updated_at", DESCENDING)], name="user_updated"),
    ],
    "messages": [IndexModel([("project_id", ASCENDING), ("created_at", ASCENDING)], name="project_created")],
    "versions": [IndexModel([("project_id", ASCENDING), ("number", DESCENDING)], name="project_number")],
    "test_runs": [IndexModel([("project_id", ASCENDING), ("created_at", DESCENDING)], name="project_created")],
}

app = FastAPI()
api = APIRouter(prefix="/api")

LIVE: dict = {}       # project_id -> {"stage", "text"} while a pipeline stage streams
LIVE_MSG: dict = {}   # message_id -> streaming text
LIVE_RUN: dict = {}   # test_run_id -> streaming auto-fix text
TASKS: set = set()
STATUS_OF = {"plan": "planning", "architecture": "planning", "code": "building", "tests": "building", "review": "reviewing"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def spawn(coro):
    t = asyncio.create_task(coro)
    TASKS.add(t)
    t.add_done_callback(TASKS.discard)


class ProjectIn(BaseModel):
    idea: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=4000)]
    model: str = engine.DEFAULT_MODEL


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    model: Optional[str] = None


class FixIn(BaseModel):
    model: Optional[str] = None


class ModelIn(BaseModel):
    model: str


class RunTestsIn(BaseModel):
    auto_fix: bool = True
    max_attempts: int = Field(3, ge=1, le=4)
    model: Optional[str] = None


def check_model(model: str) -> str:
    if model not in engine.MODELS:
        raise HTTPException(status_code=400, detail="Unknown model")
    return model


async def get_owned(pid: str, user_id: str) -> dict:
    p = await db.projects.find_one({"id": pid, "user_id": user_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    return p


async def set_project(pid: str, **fields):
    fields["updated_at"] = now()
    await db.projects.update_one({"id": pid}, {"$set": fields})


async def acquire(pid: str):
    if not await db.projects.find_one_and_update({"id": pid, "busy": {"$ne": True}}, {"$set": {"busy": True}}):
        raise HTTPException(status_code=409, detail="Agent is already working")


async def save_version(p: dict, files: list, label: str) -> int:
    number = p.get("version_count", 0) + 1
    await db.versions.insert_one({
        "id": str(uuid.uuid4()), "project_id": p["id"], "user_id": p["user_id"], "number": number,
        "label": label[:80], "files": files, "file_count": len(files), "created_at": now(),
    })
    await set_project(p["id"], version_count=number)
    p["version_count"] = number
    rt = runtime.RUNTIMES.get(p["id"])
    if rt and rt.status == "running":  # keep the live backend on the latest code
        spawn(restart_runtime(p["id"]))
    return number


async def restart_runtime(pid: str):
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    if p:
        try:
            await runtime.start(p)
        except Exception as exc:
            logger.exception("runtime restart %s failed", pid)
            rt = runtime.RUNTIMES.get(pid)
            if rt:
                rt.status, rt.error = "failed", f"Could not restart on the new code: {str(exc)[:200]}"


async def run_pipeline(pid: str):
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    for stage in engine.STAGES:
        if p["stage_status"][stage] == "done":
            continue
        p["stage_status"][stage] = "running"
        await set_project(pid, stage_status=p["stage_status"], status=STATUS_OF[stage], error=None)
        LIVE[pid] = {"stage": stage, "text": ""}

        async def on_delta(text, stage=stage):
            LIVE[pid] = {"stage": stage, "text": text}

        try:
            limit = 24000 if stage in ("code", "tests") else 8000
            text = await engine.stream_llm(p["model"], engine.stage_prompt(stage, p), on_delta, limit)
            update = {}
            if stage == "plan":
                update["plan"] = text
                first = text.strip().splitlines()[0] if text.strip() else ""
                if first.startswith("# "):
                    update["name"] = first[2:].strip()[:60]
            elif stage == "architecture":
                update["architecture"] = text
            elif stage == "code":
                files = engine.parse_files(text)
                if not files:
                    raise ValueError("The model returned no files")
                update["files"] = files
            elif stage == "tests":
                update["files"] = engine.merge_files(p["files"], engine.parse_files(text))
            elif stage == "review":
                update["review"] = engine.parse_review(text)
            p.update(update)
            p["stage_status"][stage] = "done"
            update.setdefault("logs", {})
            p.setdefault("logs", {})[stage] = text[-200000:]
            update["logs"] = p["logs"]
            await set_project(pid, stage_status=p["stage_status"], **update)
            if stage == "tests":
                await save_version(p, p["files"], "Initial build: code + tests")
        except Exception as exc:
            logger.exception("pipeline %s stage %s failed", pid, stage)
            p["stage_status"][stage] = "failed"
            await set_project(pid, stage_status=p["stage_status"], status="failed", busy=False,
                              error=f"{stage} failed: {str(exc)[:300]}")
            LIVE.pop(pid, None)
            return
    LIVE.pop(pid, None)
    await set_project(pid, status="ready", busy=False)


async def run_edit(pid: str, mid: str, request: str, model: str, issue_id: Optional[str]):
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    history = await db.messages.find({"project_id": pid, "status": "done"}, {"_id": 0}).sort("created_at", 1).to_list(50)
    LIVE_MSG[mid] = ""

    async def on_delta(text):
        LIVE_MSG[mid] = text

    try:
        text = await engine.stream_llm(model, engine.edit_prompt(p, history, request), on_delta, 24000)
        cut = [i for i in (text.find("<<<FILE"), text.find("<<<DELETE")) if i >= 0]
        explanation = (text[:min(cut)] if cut else text).strip() or "Done."
        new_files, deletes = engine.parse_files(text), engine.parse_deletes(text)
        changed = [f["path"] for f in new_files] + deletes
        version = None
        if changed:
            files = engine.merge_files(p["files"], new_files, deletes)
            await set_project(pid, files=files)
            version = await save_version(p, files, request)
        if issue_id and changed:
            await db.projects.update_one({"id": pid, "review.issues.id": issue_id},
                                         {"$set": {"review.issues.$.status": "fixed", "review.issues.$.fixed_in": version}})
        await db.messages.update_one({"id": mid}, {"$set": {
            "content": explanation, "changed_files": changed, "version": version, "status": "done"}})
    except Exception as exc:
        logger.exception("edit %s failed", pid)
        await db.messages.update_one({"id": mid}, {"$set": {
            "content": f"Something went wrong: {str(exc)[:300]}", "status": "error"}})
    LIVE_MSG.pop(mid, None)
    await set_project(pid, busy=False, status=p["status"])


async def set_run(rid: str, **fields):
    await db.test_runs.update_one({"id": rid}, {"$set": fields})


async def run_test_loop(pid: str, rid: str, auto_fix: bool, max_attempts: int, model: str):
    attempts, status, note = [], "failed", None
    try:
        for n in range(1, max_attempts + 1):
            await set_run(rid, phase=f"Running tests in sandbox (attempt {n}/{max_attempts})")
            p = await db.projects.find_one({"id": pid}, {"_id": 0})
            result = await sandbox.run_tests(p["files"])
            attempts.append({"n": n, **result, "fix": None})
            await set_run(rid, attempts=attempts)
            if result["failed"] == 0 and result["errors"] == 0:
                status = "passed" if result["passed"] else "no_tests"
                break
            if not auto_fix or n == max_attempts:
                break
            await set_run(rid, phase=f"Agent is fixing {result['failed'] + result['errors']} failing test(s)")
            LIVE_RUN[rid] = ""

            async def on_delta(text):
                LIVE_RUN[rid] = text

            text = await engine.stream_llm(model, engine.fix_tests_prompt(p, result), on_delta, 24000)
            LIVE_RUN.pop(rid, None)
            new_files = engine.parse_files(text)
            cut = text.find("<<<FILE")
            explanation = (text[:cut] if cut >= 0 else text).strip()
            if not new_files:
                note = "The agent could not produce a fix: " + explanation[:300]
                break
            files = engine.merge_files(p["files"], new_files)
            await set_project(pid, files=files)
            version = await save_version(p, files, f"Auto-fix after test run (attempt {n})")
            attempts[-1]["fix"] = {"explanation": explanation, "changed_files": [f["path"] for f in new_files], "version": version}
            await set_run(rid, attempts=attempts)
    except Exception as exc:
        logger.exception("test run %s failed", rid)
        status, note = "error", str(exc)[:400]
    LIVE_RUN.pop(rid, None)
    last = attempts[-1] if attempts else {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    p_end = await db.projects.find_one({"id": pid}, {"_id": 0, "version_count": 1})
    summary = {"status": status, "passed": last["passed"], "failed": last["failed"] + last["errors"],
               "skipped": last["skipped"], "attempts": len(attempts), "run_id": rid, "at": now(),
               "version": (p_end or {}).get("version_count", 0)}
    await set_run(rid, status=status, phase=None, note=note, finished_at=now())
    await set_project(pid, busy=False, test_summary=summary)


def project_out(p: dict, full: bool = True) -> dict:
    if not full:
        return {k: p.get(k) for k in ("id", "name", "idea", "model", "status", "stage_status", "busy",
                                      "version_count", "created_at", "updated_at", "test_summary")} | {
            "file_count": len(p.get("files", [])), "score": (p.get("review") or {}).get("score")}
    p.pop("logs", None)
    p["live"] = LIVE.get(p["id"])
    return p


@api.get("/")
async def root():
    return {"message": "FoundryAI API"}


@api.get("/models")
async def list_models():
    return {"default": engine.DEFAULT_MODEL, "models": [{"id": k, **v} for k, v in engine.MODELS.items()]}


@api.get("/projects")
async def list_projects(user: dict = Depends(require_user)):
    docs = await db.projects.find({"user_id": user["user_id"]}, {"_id": 0, "logs": 0, "plan": 0, "architecture": 0}) \
        .sort("updated_at", -1).to_list(200)
    return [project_out(d, full=False) for d in docs]


@api.post("/projects")
async def create_project(body: ProjectIn, user: dict = Depends(require_user)):
    check_model(body.model)
    words = body.idea.split()
    p = {
        "id": str(uuid.uuid4()), "user_id": user["user_id"], "name": " ".join(words[:5])[:60],
        "idea": body.idea.strip(), "model": body.model, "status": "planning", "busy": True, "error": None,
        "stage_status": {s: "pending" for s in engine.STAGES}, "plan": "", "architecture": "", "files": [],
        "review": None, "logs": {}, "version_count": 0, "created_at": now(), "updated_at": now(),
    }
    await db.projects.insert_one(dict(p))
    spawn(run_pipeline(p["id"]))
    return project_out(p, full=False)


@api.get("/projects/{pid}")
async def get_project(pid: str, user: dict = Depends(require_user)):
    return project_out(await get_owned(pid, user["user_id"]))


@api.get("/projects/{pid}/logs/{stage}")
async def get_log(pid: str, stage: str, user: dict = Depends(require_user)):
    p = await get_owned(pid, user["user_id"])
    return {"stage": stage, "text": (p.get("logs") or {}).get(stage, "")}


@api.patch("/projects/{pid}/model")
async def set_model(pid: str, body: ModelIn, user: dict = Depends(require_user)):
    await get_owned(pid, user["user_id"])
    await set_project(pid, model=check_model(body.model))
    return {"model": body.model}


@api.post("/projects/{pid}/resume")
async def resume(pid: str, user: dict = Depends(require_user)):
    await get_owned(pid, user["user_id"])
    await acquire(pid)
    await set_project(pid, error=None)
    spawn(run_pipeline(pid))
    return {"ok": True}


@api.delete("/projects/{pid}")
async def delete_project(pid: str, user: dict = Depends(require_user)):
    p = await get_owned(pid, user["user_id"])
    if p.get("busy"):
        raise HTTPException(status_code=409, detail="Wait for the agent to finish before deleting")
    await db.projects.delete_one({"id": pid})
    await db.messages.delete_many({"project_id": pid})
    await db.versions.delete_many({"project_id": pid})
    await db.test_runs.delete_many({"project_id": pid})
    await runtime.forget(pid)
    return {"ok": True}


async def start_edit(p: dict, request: str, display: str, model: Optional[str], issue_id: Optional[str] = None):
    if not p.get("files"):
        raise HTTPException(status_code=400, detail="Project has no code yet")
    model = check_model(model or p["model"])
    await acquire(p["id"])
    t = now()
    user_msg = {"id": str(uuid.uuid4()), "project_id": p["id"], "role": "user", "content": display,
                "model": model, "status": "done", "created_at": t}
    ai_msg = {"id": str(uuid.uuid4()), "project_id": p["id"], "role": "assistant", "content": "", "model": model,
              "status": "streaming", "changed_files": [], "version": None, "created_at": now()}
    await db.messages.insert_many([dict(user_msg), dict(ai_msg)])
    spawn(run_edit(p["id"], ai_msg["id"], request, model, issue_id))
    return {"message_id": ai_msg["id"]}


@api.post("/projects/{pid}/chat")
async def chat(pid: str, body: ChatIn, user: dict = Depends(require_user)):
    p = await get_owned(pid, user["user_id"])
    return await start_edit(p, body.message.strip(), body.message.strip(), body.model)


@api.post("/projects/{pid}/issues/{iid}/fix")
async def fix_issue(pid: str, iid: str, body: FixIn, user: dict = Depends(require_user)):
    p = await get_owned(pid, user["user_id"])
    issue = next((i for i in (p.get("review") or {}).get("issues", []) if i["id"] == iid), None)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    request = (f"Fix this code review issue ({issue['severity']}) in {issue['file']}: {issue['title']}. "
               f"{issue['description']} Suggested fix: {issue['suggested_fix']}")
    return await start_edit(p, request, f"Apply fix: {issue['title']}", body.model, iid)


@api.get("/projects/{pid}/messages")
async def messages(pid: str, user: dict = Depends(require_user)):
    await get_owned(pid, user["user_id"])
    docs = await db.messages.find({"project_id": pid}, {"_id": 0}).sort("created_at", 1).to_list(500)
    for d in docs:
        if d["status"] == "streaming":
            d["content"] = LIVE_MSG.get(d["id"], "")
    return docs


@api.get("/projects/{pid}/versions")
async def versions(pid: str, user: dict = Depends(require_user)):
    await get_owned(pid, user["user_id"])
    return await db.versions.find({"project_id": pid}, {"_id": 0, "files": 0}).sort("number", -1).to_list(200)


@api.get("/projects/{pid}/versions/{vid}")
async def version_detail(pid: str, vid: str, user: dict = Depends(require_user)):
    await get_owned(pid, user["user_id"])
    v = await db.versions.find_one({"id": vid, "project_id": pid}, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    return v


@api.post("/projects/{pid}/versions/{vid}/restore")
async def restore(pid: str, vid: str, user: dict = Depends(require_user)):
    p = await get_owned(pid, user["user_id"])
    v = await db.versions.find_one({"id": vid, "project_id": pid}, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    await acquire(pid)
    try:
        review = p.get("review")
        if review:  # fixes made after the restored version are no longer in the code
            for i in review["issues"]:
                if i.get("status") == "fixed" and (i.get("fixed_in") or 0) > v["number"]:
                    i["status"], i["fixed_in"] = "open", None
        await set_project(pid, files=v["files"], review=review)
        number = await save_version(p, v["files"], f"Restored v{v['number']}")
    finally:
        await set_project(pid, busy=False)
    return {"version": number}


@api.get("/projects/{pid}/diff")
async def diff(pid: str, base: str, target: str = "current", user: dict = Depends(require_user)):
    p = await get_owned(pid, user["user_id"])

    async def files_of(ref: str):
        if ref == "current":
            return p["files"], "Current"
        v = await db.versions.find_one({"id": ref, "project_id": pid}, {"_id": 0})
        if not v:
            raise HTTPException(status_code=404, detail="Version not found")
        return v["files"], f"v{v['number']}"

    (a, a_label), (b, b_label) = await files_of(base), await files_of(target)
    return {"base": a_label, "target": b_label, **diffs.diff_files(a, b)}


@api.post("/projects/{pid}/tests/run")
async def run_tests(pid: str, body: RunTestsIn, user: dict = Depends(require_user)):
    p = await get_owned(pid, user["user_id"])
    if not p.get("files"):
        raise HTTPException(status_code=400, detail="Project has no code yet")
    model = check_model(body.model or p["model"])
    await acquire(pid)
    run = {"id": str(uuid.uuid4()), "project_id": pid, "user_id": user["user_id"], "status": "running",
           "phase": "Preparing sandbox", "auto_fix": body.auto_fix, "max_attempts": body.max_attempts, "model": model,
           "attempts": [], "note": None, "created_at": now(), "finished_at": None}
    try:
        await db.test_runs.insert_one(dict(run))
    except Exception:
        await set_project(pid, busy=False)
        raise
    spawn(run_test_loop(pid, run["id"], body.auto_fix, body.max_attempts, model))
    return run


@api.get("/projects/{pid}/tests/runs")
async def test_runs(pid: str, user: dict = Depends(require_user)):
    await get_owned(pid, user["user_id"])
    runs = await db.test_runs.find({"project_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(20)
    for r in runs:
        r["live_fix"] = LIVE_RUN.get(r["id"])
    return runs


def runtime_out(pid: str, p: dict) -> dict:
    rt = runtime.RUNTIMES.get(pid)
    if not rt:
        return {"status": "idle", "logs": "", "stale": False}
    return {**rt.info(), "stale": rt.status == "running" and (rt.version or 0) < p.get("version_count", 0)}


@api.get("/projects/{pid}/runtime")
async def runtime_status(pid: str, user: dict = Depends(require_user)):
    return runtime_out(pid, await get_owned(pid, user["user_id"]))


@api.post("/projects/{pid}/runtime/start")
async def runtime_start(pid: str, user: dict = Depends(require_user)):
    p = await get_owned(pid, user["user_id"])
    if not p.get("files"):
        raise HTTPException(status_code=400, detail="Project has no code yet")
    try:
        await runtime.start(p)
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    return runtime_out(pid, p)


@api.post("/projects/{pid}/runtime/stop")
async def runtime_stop(pid: str, user: dict = Depends(require_user)):
    p = await get_owned(pid, user["user_id"])
    await runtime.stop(pid)
    return runtime_out(pid, p)


# Capability URL used by the sandboxed preview iframe; the unguessable token is the access check.
@api.api_route("/runtime/{token}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def runtime_proxy(token: str, path: str, request: Request):
    status, headers, content = await runtime.forward(token, path, request.method, list(request.query_params.multi_items()),
                                                     dict(request.headers), await request.body())
    return Response(content=content, status_code=status, headers=headers)


app.include_router(api)
app.include_router(clerk_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)


@app.on_event("startup")
async def startup():
    app.state.index_task = asyncio.create_task(ensure_indexes())
    spawn(runtime.reaper())
    with suppress(OSError):  # sandboxed test runs use other uids; keep secrets unreadable to them
        os.chmod(ROOT_DIR / ".env", 0o600)
    for private in ("/var/log/supervisor", "/etc/supervisor", str(ROOT_DIR.parent / "memory")):
        with suppress(OSError):
            os.chmod(private, 0o700)
    await db.test_runs.update_many({"status": "running"}, {"$set": {
        "status": "error", "phase": None, "note": "Interrupted by a server restart. Run the tests again."}})
    # Work interrupted by a restart cannot continue; mark it so the user can retry.
    async for p in db.projects.find({"busy": True}, {"_id": 0, "id": 1, "stage_status": 1, "status": 1}):
        ss = {k: ("failed" if v == "running" else v) for k, v in p["stage_status"].items()}
        status = "failed" if ss != p["stage_status"] else p["status"]
        await db.projects.update_one({"id": p["id"]}, {"$set": {
            "busy": False, "stage_status": ss, "status": status,
            "error": "Interrupted by a server restart. Retry to continue." if status == "failed" else None}})
    await db.messages.update_many({"status": "streaming"}, {"$set": {
        "status": "error", "content": "Interrupted by a server restart. Please send again."}})


@app.on_event("shutdown")
async def shutdown():
    await runtime.stop_all()
    app.state.index_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    client.close()
