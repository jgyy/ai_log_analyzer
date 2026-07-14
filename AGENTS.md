<!-- ai_log_analyzer, project-root AGENTS.md. AI-agent-agnostic entry point:
     followed by Claude Code, Codex, Cursor, or any other coding agent. Keep
     this lean and repo-wide; each subdirectory listed below has its own
     local AGENTS.md with area-specific guidance, loaded on demand when an
     agent works there — do not duplicate that detail here. Anchor guidance
     on stable paths and symbols, not counts that rot. No em dashes, en
     dashes, or emojis. -->

# DevOps AI Log Analyzer

Incident analysis MVP for DevOps/SRE/platform teams: collects manual logs or local Linux/Docker
evidence, sends structured evidence to an AI provider, and returns an investigation timeline, root
cause, mitigation plan, and Mermaid diagrams. Stack: FastAPI backend, Next.js 14 frontend,
SQLAlchemy + SQLite, JWT auth, Google Gemini / Anthropic Claude as pluggable AI providers.

Full architecture, tech stack, and component breakdown live in `ARCHITECTURE.md` — read that
before making structural changes; this file is the quick orientation + conventions layer.

## Repo map
| Path | What it is |
|---|---|
| `backend/` | FastAPI service (flat layout: routes, AI integration, connectors, actions, auth). See `backend/AGENTS.md`. |
| `frontend/` | Next.js 14 dashboard; see `frontend/AGENTS.md` (and `frontend/app/`, `frontend/components/`, `frontend/components/TabViews/`, `frontend/lib/` for their own `AGENTS.md`). |
| `docs/ai-dev/` | AI-assisted development notes for this repo. |

Most directories above have their own `AGENTS.md`; read it when you work there.

## Commands
- Backend: `cd backend && uvicorn main:app --reload`; tests are Python `unittest` (`test_*.py`).
- Frontend: `cd frontend && npm run dev`.

## Architecture (the load-bearing ideas)
- **One pipeline, two entry points.** Manual logs and connector-backed incidents both flow through
  the same `ai_service.py` model execution pipeline, so provider selection, Mermaid validation, and
  retry behavior stay identical regardless of evidence source.
- **AI output is schema-validated, not trusted verbatim.** Mermaid diagrams are checked for valid
  syntax and regenerated (up to 3 attempts) before being returned; the frontend sanitizes again
  before rendering. Apply the same discipline to any new AI-generated structured field.
- **Every analysis and action endpoint is auth-protected** (JWT bearer + role check via `auth.py`).
  A new endpoint that reads or mutates incident/org data must go through the same auth dependency,
  not a bespoke check.
- **Remediation actions are allowlisted, never freeform.** `actions.py` executes only known,
  vetted actions — never build a path that lets AI output choose an arbitrary shell command.

## Invariants
- Don't log full log content, decrypted credentials, or full AI prompts/responses at `info` level.
- Connector credentials at rest go through `crypto_utils.py`; never store them in plaintext.
- Local Linux/Docker connectors run allowlisted read-only commands only — no connector should gain
  the ability to execute arbitrary user-supplied commands on the host.

## Conventions
- Python: FastAPI route handlers stay thin; provider/connector logic lives in its own module
  (`ai_service.py`, `connectors*.py`), not inlined in `main.py`.
- Frontend types in `lib/types.ts` should track backend `schemas.py` changes in the same PR.
- Commits: Conventional Commits style (`feat: ...`, `fix: ...`, `security: ...`).

## Pointers
`README.md` (product overview, demo, install) · `ARCHITECTURE.md` (full architecture, runtime
diagram, security design, known limits) · `PLAN.md` (roadmap) · `docs/ai-dev/` (AI-assisted
development notes).
