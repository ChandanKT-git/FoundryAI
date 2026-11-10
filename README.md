# FoundryAI

An autonomous AI software engineering platform that transforms natural-language app ideas into product requirements, system architecture, source code, sandboxed automated tests, AI code reviews, and live interactive previews.

## Key Features

- **5-Stage Streaming Pipeline**: Streams **Plan (PRD)** → **Architecture** → **Code** → **Tests** → **Review** in real time with stage logs and failure retry.
- **Multi-Model Support**: Switch between Claude Opus 5.5, Claude Sonnet 5.5, GPT 6 Luna, and Gemini 3.1 Pro via [LiteLLM](https://docs.litellm.ai/) per project or per chat message.
- **3-Pane Engineering Workspace**: File explorer, syntax-highlighted code viewer, Markdown plan/architecture tabs, AI code review with one-click issue fixes, and ZIP export.
- **Sandboxed Live Preview & Backend Runtime**: Renders `preview.html` in a sandboxed iframe (with Mock/Live API toggle) and launches generated FastAPI backends over private Unix sockets as unprivileged UIDs with `seccomp` network isolation and resource limits.
- **Sandboxed Test Runner & Auto-Fix Loop**: Executes generated `pytest` and `node:test` suites inside the isolated sandbox and can iteratively auto-fix failing tests across new project versions.
- **Version History & Line Diffs**: Snapshots every build, chat edit, fix, and restore; supports side-by-side version diffs and one-click rollback.
- **Authentication & Project Isolation**: Clerk authentication (`@clerk/react` + PyJWT JWKS verification) with per-user project ownership and atomic busy locks.

## Tech Stack

- **Backend**: Python, FastAPI, Motor (async MongoDB), LiteLLM, PyJWT, `pyseccomp`, `uvicorn`
- **Frontend**: React 19, Tailwind CSS, shadcn/ui (Radix UI), CRACO, Prism (`prism-react-renderer`), JSZip, Clerk React

## Project Structure

```text
.
├── backend/
│   ├── server.py          # FastAPI routes, pipeline orchestration, runtime & diff APIs
│   ├── engine.py          # Prompts, file/review parsers, LiteLLM streaming
│   ├── sandbox.py         # Isolated pytest / node:test runner & JUnit parser
│   ├── sandbox_launch.py  # Unprivileged UID, rlimits, and seccomp syscall filter
│   ├── runtime.py         # Unix-socket FastAPI runtime manager & HTTP proxy
│   ├── clerk_auth.py      # Clerk config, production proxy, and JWKS token verification
│   ├── diffs.py           # Unified file diff builder
│   └── tests/             # API, diff, sandbox, and runtime pytest suites
├── frontend/
│   ├── public/            # Static HTML template
│   └── src/
│       ├── pages/         # Landing, AuthShell, Dashboard, Workspace
│       └── components/    # Workspace panes, live preview, diff dialog, UI primitives
└── tests/                 # Clerk test token helper
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+ & Yarn
- MongoDB running locally or remotely
- A [Clerk](https://clerk.com/) application and API keys for your chosen LLM providers

### 1. Configure Environment Variables

Copy the example env files and fill in your credentials:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 2. Run the Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

### 3. Run the Frontend

```bash
cd frontend
yarn install
yarn start
```

Open [http://localhost:3000](http://localhost:3000) in your browser.
