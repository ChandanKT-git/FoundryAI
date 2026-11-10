import json
import os
import re
import uuid

try:
    from backend.sandbox import AVAILABLE as SANDBOX
except ModuleNotFoundError:
    from sandbox import AVAILABLE as SANDBOX

import litellm

MODELS = {
    "claude-opus-5-5": {"provider": "anthropic", "label": "Claude Opus 5.5"},
    "claude-sonnet-5-5": {"provider": "anthropic", "label": "Claude Sonnet 5.5"},
    "gpt-6-luna": {"provider": "openai", "label": "GPT 6 Luna"},
    "gemini-3.1-pro-preview": {"provider": "gemini", "label": "Gemini 3.1 Pro"},
}
PROVIDER_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
DEFAULT_MODEL = "claude-sonnet-5-5"
STAGES = ["plan", "architecture", "code", "tests", "review"]

FILE_RE = re.compile(r"<<<FILE\s+(.+?)>>>\n(.*?)\n?<<<END>>>", re.DOTALL)
DELETE_RE = re.compile(r"<<<DELETE\s+(.+?)>>>")

FILE_FORMAT = (
    "Output every file using EXACTLY this format, with nothing between blocks except blank lines:\n"
    "<<<FILE relative/path.ext>>>\n<full file content>\n<<<END>>>\n"
    "Never wrap file blocks in markdown code fences."
)

PREVIEW_API_RULE = (
    "preview.html must talk to the real backend when it runs live: if `window.FOUNDRY_API_BASE` is defined, load and "
    "save ALL data with fetch(`${window.FOUNDRY_API_BASE}/api/...`) against the backend's real routes (show loading "
    "and error states); if it is undefined, fall back to in-memory mock data so the UI still works offline."
)

SYSTEM = (
    "You are FoundryAI, an autonomous senior software engineer. You plan, design, write, test and review "
    "production-quality software. Be precise, concrete and concise."
)


def _llm_kwargs(provider: str) -> dict:
    """Resolve API credentials for the target provider or unified LLM gateway."""
    env_var = PROVIDER_ENV_KEYS.get(provider)
    api_key = (os.environ.get(env_var) if env_var else None) or os.environ.get("LLM_API_KEY")
    if not api_key:
        expected = f"{env_var} or LLM_API_KEY" if env_var else "LLM_API_KEY"
        raise RuntimeError(f"Missing API key for provider '{provider}': set {expected}")
    kwargs = {"api_key": api_key}
    if os.environ.get("LLM_API_BASE"):
        kwargs["base_url"] = os.environ["LLM_API_BASE"]
    return kwargs


async def stream_llm(model: str, prompt: str, on_delta, max_tokens: int = 16000) -> str:
    provider = MODELS[model]["provider"]
    stream = await litellm.acompletion(
        model=f"{provider}/{model}",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        stream=True,
        **_llm_kwargs(provider),
    )
    text = ""
    async for chunk in stream:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        content = getattr(delta, "content", None) if delta else None
        if content:
            text += content
            await on_delta(text)
    return text


def files_blob(files: list, limit: int = 120000) -> str:
    out = "\n\n".join(f"<<<FILE {f['path']}>>>\n{f['content']}\n<<<END>>>" for f in files)
    return out[:limit]


def parse_files(text: str) -> list:
    return [{"path": p.strip().lstrip("/"), "content": c} for p, c in FILE_RE.findall(text)]


def parse_deletes(text: str) -> list:
    return [p.strip().lstrip("/") for p in DELETE_RE.findall(text)]


def merge_files(existing: list, new: list, deletes: list = ()) -> list:
    by_path = {f["path"]: f for f in existing if f["path"] not in deletes}
    for f in new:
        by_path[f["path"]] = f
    return sorted(by_path.values(), key=lambda f: f["path"])


def parse_review(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start:end + 1])
    issues = []
    for i in data.get("issues", []):
        issues.append({
            "id": str(uuid.uuid4())[:8],
            "title": str(i.get("title", "Issue")),
            "severity": str(i.get("severity", "medium")).lower(),
            "file": str(i.get("file", "")),
            "description": str(i.get("description", "")),
            "suggested_fix": str(i.get("suggested_fix", "")),
            "status": "open",
        })
    return {"score": int(data.get("score", 0)), "summary": str(data.get("summary", "")), "issues": issues}


def stage_prompt(stage: str, p: dict) -> str:
    idea = p["idea"]
    if stage == "plan":
        return (
            f"Write a product requirements document (PRD) in Markdown for this app idea:\n\n\"{idea}\"\n\n"
            "Start with a level-1 heading containing ONLY a short catchy product name (2-3 words). Then sections: "
            "## Overview, ## Goals, ## Target Users, ## Core Features (bulleted, MVP scope), ## User Stories "
            "(As a..., I want..., so that...), ## Out of Scope. Keep it under 600 words."
        )
    if stage == "architecture":
        return (
            f"App idea: \"{idea}\"\n\nPRD:\n{p['plan']}\n\n"
            "Design the software architecture in Markdown. Default to a React + Tailwind frontend and a Python "
            "FastAPI backend unless the idea requires something else. Sections: ## Tech Stack, ## System Overview "
            "(include an ASCII box diagram in a ```text code block showing components and data flow), "
            "## Components, ## Data Entities (fields per entity), ## API Endpoints (METHOD /path - purpose), "
            "## File Structure (a ```text tree). Keep it under 700 words."
        )
    if stage == "code":
        return (
            f"App idea: \"{idea}\"\n\nPRD:\n{p['plan']}\n\nArchitecture:\n{p['architecture']}\n\n"
            "Generate the complete MVP source code following the architecture. Requirements:\n"
            "- 8 to 14 files total, real working code, no placeholders or TODOs.\n"
            "- Include README.md with setup steps.\n"
            "- MANDATORY: include `preview.html` at the root: a single self-contained HTML file that runs the "
            "app's full front-end UI in a browser (use React 18 UMD + Babel standalone + Tailwind CDN from public "
            "CDNs). It must be polished and interactive. " + PREVIEW_API_RULE + "\n"
            "- Backend: a FastAPI app object named `app` in backend/app/main.py (routes under /api), creating its "
            "SQLite tables on startup and reading the database URL from env DATABASE_URL (default "
            "sqlite:///./app.db). It is run live in a sandbox via `uvicorn app.main:app` with backend/ on the path.\n"
            f"- Keep backend dependencies within what the sandbox provides: {SANDBOX}\n\n"
            + FILE_FORMAT
        )
    if stage == "tests":
        return (
            f"App idea: \"{idea}\"\n\nProject files:\n{files_blob(p['files'])}\n\n"
            "Write automated tests for this project. They will be EXECUTED in a sandbox that has: "
            f"{SANDBOX}\n"
            "- Backend: pytest files named test_*.py using FastAPI TestClient and an isolated temporary or "
            "in-memory SQLite database (override dependencies/env so tests never touch real data). Import the app "
            "the way it would resolve with the backend folder on the Python path (e.g. `from app.main import app`).\n"
            "- Frontend logic: plain Node tests named *.test.mjs using `node:test` and `node:assert/strict`, "
            "importing pure JS logic modules (create small pure .mjs helper modules in the source if needed). "
            "No Jest, no JSX, no npm packages.\n"
            "3 to 5 test files covering main flows and edge cases. Make sure they pass against the code.\n\n"
            + FILE_FORMAT
        )
    if stage == "review":
        return (
            f"Review this project as a strict senior engineer. Files:\n{files_blob(p['files'])}\n\n"
            "Find real bugs, security issues, missing error handling and correctness problems. "
            "Respond with ONLY a JSON object, no prose, no code fences:\n"
            '{"score": <0-100 quality score>, "summary": "<2 sentence verdict>", "issues": [{"title": "...", '
            '"severity": "critical|high|medium|low", "file": "<path>", "description": "...", '
            '"suggested_fix": "..."}]}\nList 3 to 8 issues, most severe first.'
        )
    raise ValueError(stage)


def edit_prompt(p: dict, history: list, request: str) -> str:
    convo = "\n".join(f"{m['role'].upper()}: {m['content'][:1500]}" for m in history[-6:])
    return (
        f"You are maintaining this project.\nApp idea: \"{p['idea']}\"\n\nCurrent files:\n{files_blob(p['files'])}\n\n"
        f"Recent conversation:\n{convo}\n\nNew request from the user:\n\"{request}\"\n\n"
        "First write a short explanation (2-5 sentences, plain text) of what you will change and why. "
        "Then output ONLY the files you change or create, each with its FULL new content. "
        "To delete a file output a line `<<<DELETE path>>>`. Keep `preview.html` in sync with any front-end "
        "and API changes so the live preview reflects them. " + PREVIEW_API_RULE + " If no code change is needed, "
        "just answer.\n\n" + FILE_FORMAT
    )


def fix_tests_prompt(p: dict, result: dict) -> str:
    failing = [c for c in result["cases"] if c["status"] in ("failed", "error")]
    report = "\n\n".join(f"[{c['status'].upper()}] {c['file']} :: {c['name']}\n{c['message'][:1500]}" for c in failing[:15])
    return (
        f"The project's automated tests were executed in a sandbox ({SANDBOX}) and some failed.\n\n"
        f"Project files:\n{files_blob(p['files'])}\n\nFailures:\n{report}\n\nRaw output (tail):\n{result['output'][-4000:]}\n\n"
        "Fix the root causes. Prefer fixing bugs in the source code; only change a test when the test itself is wrong. "
        "If a failure is caused by a dependency the sandbox lacks, rewrite the code or test to avoid it. "
        "First write a short explanation (2-4 sentences) of the causes and your fixes, then output ONLY the changed "
        "files with their FULL new content.\n\n" + FILE_FORMAT
    )
