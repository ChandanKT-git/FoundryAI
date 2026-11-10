"""Standalone unit tests for core FoundryAI modules (no DB, Clerk, or live LLM required)."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import diffs  # noqa: E402
import engine  # noqa: E402
import runtime  # noqa: E402
import sandbox  # noqa: E402


def test_parse_and_merge_files():
    raw = (
        "Updating files.\n\n"
        "<<<FILE /backend/app/main.py>>>\nprint('hi')\n<<<END>>>\n\n"
        "<<<FILE /README.md>>>\n# App\n<<<END>>>\n"
        "<<<DELETE /old.txt>>>\n"
    )
    parsed = engine.parse_files(raw)
    deletes = engine.parse_deletes(raw)
    assert [f["path"] for f in parsed] == ["backend/app/main.py", "README.md"]
    assert deletes == ["old.txt"]

    existing = [
        {"path": "old.txt", "content": "gone"},
        {"path": "keep.txt", "content": "stay"},
        {"path": "README.md", "content": "old"},
    ]
    merged = engine.merge_files(existing, parsed, deletes)
    assert [f["path"] for f in merged] == ["README.md", "backend/app/main.py", "keep.txt"]
    assert next(f["content"] for f in merged if f["path"] == "README.md") == "# App"


def test_parse_review():
    raw = 'Here is the review:\n{"score": 88, "summary": "Solid MVP.", "issues": [{"title": "Missing check", "severity": "HIGH", "file": "main.py", "description": "desc", "suggested_fix": "fix"}]}'
    review = engine.parse_review(raw)
    assert review["score"] == 88
    assert review["summary"] == "Solid MVP."
    assert len(review["issues"]) == 1
    assert review["issues"][0]["severity"] == "high"
    assert review["issues"][0]["status"] == "open"


def test_llm_kwargs_and_stream(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "LLM_API_KEY", "LLM_API_BASE"):
        monkeypatch.delenv(k, raising=False)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        engine._llm_kwargs("anthropic")

    monkeypatch.setenv("LLM_API_KEY", "univ-key")
    monkeypatch.setenv("LLM_API_BASE", "https://proxy.example/v1")
    assert engine._llm_kwargs("anthropic") == {"api_key": "univ-key", "base_url": "https://proxy.example/v1"}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    assert engine._llm_kwargs("openai")["api_key"] == "sk-openai"

    class Delta:
        def __init__(self, content):
            self.content = content

    class Choice:
        def __init__(self, content):
            self.delta = Delta(content)

    class Chunk:
        def __init__(self, content):
            self.choices = [Choice(content)] if content is not None else []

    async def fake_stream():
        yield Chunk("Hello ")
        yield Chunk(None)
        yield Chunk("FoundryAI")

    async def fake_acompletion(**kwargs):
        assert kwargs["model"] == "openai/gpt-6-luna"
        assert kwargs["stream"] is True
        return fake_stream()

    monkeypatch.setattr(engine.litellm, "acompletion", fake_acompletion)
    seen = []

    async def on_delta(text):
        seen.append(text)

    out = asyncio.run(engine.stream_llm("gpt-6-luna", "prompt", on_delta))
    assert out == "Hello FoundryAI"
    assert seen == ["Hello ", "Hello FoundryAI"]


def test_diff_files():
    base = [{"path": "a.py", "content": "x = 1\n"}, {"path": "old.py", "content": "y = 2\n"}]
    target = [{"path": "a.py", "content": "x = 2\n"}, {"path": "new.py", "content": "z = 3\n"}]
    result = diffs.diff_files(base, target)
    by_path = {f["path"]: f for f in result["files"]}
    assert by_path["a.py"]["status"] == "modified"
    assert by_path["old.py"]["status"] == "removed"
    assert by_path["new.py"]["status"] == "added"
    assert result["additions"] == 2
    assert result["deletions"] == 2


def test_sandbox_classify_and_runtime_find_entry():
    files = [
        {"path": "backend/app/main.py", "content": "from fastapi import FastAPI\napp = FastAPI()\n"},
        {"path": "backend/tests/test_api.py", "content": "def test_ok(): assert True\n"},
        {"path": "logic.test.mjs", "content": "import test from 'node:test';\nimport assert from 'node:assert/strict';\n"},
        {"path": "App.test.jsx", "content": "import React from 'react';\n"},
    ]
    py, js, skipped = sandbox.classify(files)
    assert py == ["backend/tests/test_api.py"]
    assert js == ["logic.test.mjs"]
    assert len(skipped) == 1 and skipped[0]["file"] == "App.test.jsx"
    assert runtime.find_entry(files) == ("backend/app/main.py", "app", False)
