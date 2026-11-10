# FoundryAI — PRD

## Original problem statement
Build FoundryAI, an autonomous AI software engineering platform that transforms natural-language software ideas into engineered applications through AI-powered product planning, architecture design, code generation, testing and debugging — understands, builds, tests, maintains and evolves apps.

## Architecture
- FastAPI (`server.py` routes + background tasks, `engine.py` prompts/parsing/LLM streaming via litellm + provider API keys), MongoDB (projects, messages, versions).
- Auth: Clerk (email + password), `clerk_auth.py`, every route keyed by user_id.
- Pipeline runs as a background task; live stream text kept in memory and polled (1.2s) by the frontend.
- Files format `<<<FILE path>>> … <<<END>>>`; generated apps include `preview.html` rendered in a sandboxed iframe.
- React (CRA) + Tailwind + shadcn, prism-react-renderer, react-markdown, jszip.

## Personas
Founders/PMs, developers wanting a first draft, students/makers.

## Implemented (Nov 2026)
- Landing, Clerk sign-in/up (dark), dashboard (status, model, score, search, delete)
- New project with idea + model (Claude Opus 5.5, Claude Sonnet 5.5, GPT 6 Luna, Gemini 3.1 Pro)
- 5-stage pipeline (plan, architecture, code, tests, review JSON) with live streaming, retry after failure
- Workspace: file tree, code viewer, copy, zip download, live preview (desktop/mobile toggle), plan/architecture views, review with apply-fix
- Agent chat edits (per-message model), version history with view/restore (reopens issues fixed after restored version)
- Atomic busy lock, mobile pane switcher
- Version diff view: compare any two versions (or current) line by line, restore from the diff dialog
- Sandboxed test runner: pytest + node:test run as a throwaway uid with seccomp (no network), rlimits, scrubbed env; Jest/RTL files skipped; auto-fix loop (up to 3 attempts) creates versions; run history; stale indicator when code changed after the last run
- Live sandboxed backends: generated FastAPI app runs via uvicorn on a private unix socket (same sandbox, 1 GB memory, CPU limit), proxied at /api/runtime/<token>; preview gets window.FOUNDRY_API_BASE in Live mode (Mock toggle); logs panel; auto-restart on new versions; idle stop after 20 min; max 2 per user / 8 total; "Wire preview to live API" chat shortcut; new projects generate wired previews

## Backlog
- P1: Node/Express backends live; JS/Jest tests with package installs in an isolated sandbox
- P1: Shareable public preview links; diff view per version
- P2: GitHub push, deploy, team workspaces, import existing codebase, usage tracking
