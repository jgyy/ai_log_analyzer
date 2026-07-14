<!-- ai_log_analyzer, project-root CLAUDE.md. Keep this lean and repo-wide;
     anchor guidance on stable paths and symbols, not counts that rot.
     No em dashes, en dashes, or emojis. -->

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
| `backend/main.py` | FastAPI routes and request orchestration; both `/api/analyze` (legacy) and `/api/incidents/analyze` (current) endpoints. |
| `backend/ai_service.py` | Gemini/Claude integration: provider selection, retries, Mermaid diagram validation/regeneration. |
| `backend/connectors.py` / `connectors_vm.py` | Local manual/Linux/Docker evidence collection, and remote VM evidence collection. |
| `backend/actions.py` | Allowlisted remediation action execution — never add a new action without it being explicitly allowlisted. |
| `backend/schemas.py` | Pydantic API and AI response schemas — the contract between backend and frontend `lib/types.ts`. |
| `backend/database.py` | SQLAlchemy models: users, organizations, analysis history, audit logs. |
| `backend/auth.py` | JWT auth, role checks, bcrypt password hashing. |
| `backend/crypto_utils.py` | Secret/credential encryption helpers for stored connector config. |
| `backend/log_processor.py` | Manual log preprocessing before it reaches the AI service. |
| `frontend/components/LogUploader.tsx` | Main source-selection + Analyze workflow entry point. |
| `frontend/components/MermaidDiagram.tsx` | Mermaid rendering with a defensive sanitizer as the final safety net. |
| `frontend/components/TabViews/` | Timeline, root cause, mitigation, overview result views. |
| `frontend/lib/api.ts` | Backend API client; `frontend/lib/types.ts` mirrors backend response schemas. |
| `docs/ai-dev/` | AI-assisted development notes for this repo. |

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
