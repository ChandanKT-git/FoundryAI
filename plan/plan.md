# FoundryAI — Autonomous AI Software Engineering Platform

FoundryAI turns a plain-language app idea into an engineered project: a product plan, an architecture, real code files, tests and a code review, plus a live preview.
Users keep shaping the app by chatting with the agent, which updates the files and re-checks its work.

## Who it's for
- Founders and product people who want to go from idea to a working prototype without writing code.
- Developers who want a fast first draft of a project (plan, structure, code, tests) to download and continue.
- Students and makers learning how real software is planned and built.

## Core features and experience
- **Sign-in with email and password** — each user has a private workspace; projects are visible only to their owner.
- **Projects dashboard** — list of the user's projects with status (planning, building, reviewing, ready), model used and last update.
- **Idea intake** — the user describes the app in plain words and picks the AI model for this project.
- **Multi-model choice** — Claude Opus 5.5, Claude Sonnet 5.5, GPT 6 Luna and Gemini 3.1 Pro; switchable per project and per chat message.
- **Engineering pipeline, shown step by step with live streaming output:**
  1. Product plan (PRD): goals, users, features, user stories.
  2. Architecture: components, data entities, API endpoints, tech choices, shown as a readable diagram-style overview.
  3. Code generation: a full file tree with real source files.
  4. Test files written alongside the code.
  5. AI code review and bug report: issues listed by severity, each with a suggested fix and a one-click "apply fix".
- **Code workspace** — file tree plus code viewer with syntax highlighting; files can be viewed, copied and the whole project downloaded as a zip.
- **Live preview** — the app's front end runs inside FoundryAI in a safe, isolated preview pane, refreshing after each change.
- **Chat to change the app** — ask for edits ("add a dark mode", "fix the login bug"); the agent explains its change, updates only the affected files, and shows what changed.
- **Version history** — every agent change is saved as a version the user can view or restore.

## User flow
1. Sign up / sign in with email and password.
2. From the dashboard, click "New project", describe the idea, choose a model.
3. Watch the pipeline run: plan → architecture → code → tests → review, each step streaming in.
4. Open the workspace: browse files, see the live preview, read the bug report and apply fixes.
5. Use the chat to request changes; the preview and files update, and a new version is saved.
6. Download the project as a zip at any time.

## UI/UX feel
- A focused, IDE-inspired "engineering control room": dark workspace, crisp monospace accents, clear status indicators for each pipeline stage.
- Three-pane workspace (files · code/preview · agent chat) on desktop; stacked tabs on phones.
- Live streaming text and progress animations so the agent feels actively at work.

## Implementation phases
**Phase 1 — MVP (built now)**
- Email/password sign-in, private projects, dashboard.
- Full pipeline: plan, architecture, code, tests, code review with bug report and apply-fix.
- Model selection across the four models.
- Code workspace, zip download, live front-end preview.
- Chat-driven edits and version history.

**Phase 2 — Running full apps**
- Run generated back ends and databases in a live sandbox, not just the front end.
- Actually execute the generated tests and show pass/fail results; agent auto-fixes failures in a loop.
- Shareable public preview links.

**Phase 3 — Evolve and collaborate**
- Push to GitHub and one-click deployment of generated apps.
- Team workspaces with shared projects and comments.
- Import an existing codebase for the agent to understand and maintain; usage and cost tracking per project.

## Assumptions
- Sign-in uses Clerk authentication (email + password, with built-in password reset and email verification); no Google sign-in.
- No admin role or admin panel in the MVP; every user simply manages their own projects.
- AI runs via LiteLLM using configured provider API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `LLM_API_KEY` / `LLM_API_BASE`). Default model for new projects is Claude Sonnet 5.5.
- Live preview in Phase 1 covers the front end (web pages / React UI); back-end code is generated, reviewed and downloadable but not executed until Phase 2.
- Generated tests are written and reviewed by the AI but not executed in Phase 1.
- Generated apps default to a web stack (React front end with a Python or Node back end) unless the user's idea asks for something else.
- English-only interface; no billing or usage limits inside FoundryAI for now.
