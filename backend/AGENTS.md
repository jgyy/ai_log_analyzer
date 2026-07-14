<!-- ai_log_analyzer backend/, AGENTS.md. FastAPI service. -->

# backend/

FastAPI service, flat module layout (no subpackages). Dev: `uvicorn main:app --reload`. Tests are
Python `unittest`, files named `test_*.py`.

| File | What it is |
|---|---|
| `main.py` | Routes and request orchestration; both `/api/analyze` (legacy manual logs) and `/api/incidents/analyze` (current source-based flow) share one pipeline. |
| `ai_service.py` | Gemini/Claude integration: provider selection, retries, Mermaid diagram validation/regeneration. |
| `connectors.py` | Local manual/Linux/Docker evidence collection. |
| `connectors_vm.py` | Remote VM evidence collection. |
| `actions.py` | Allowlisted remediation action execution. |
| `schemas.py` | Pydantic API and AI response schemas — the contract with `frontend/lib/types.ts`. |
| `database.py` | SQLAlchemy models: users, organizations, analysis history, audit logs. |
| `auth.py` | JWT auth, role checks, bcrypt password hashing. |
| `crypto_utils.py` | Encryption helpers for stored connector credentials. |
| `log_processor.py` | Manual log preprocessing before it reaches the AI service. |

## Conventions
- Both analysis entry points (`main.py`) must keep flowing through the same `ai_service.py`
  pipeline — don't fork provider-selection or retry logic per endpoint.
- New remediation actions go in `actions.py` as an explicitly allowlisted action — never let AI
  output choose an arbitrary command to run.
- Connector credentials are encrypted via `crypto_utils.py` before being stored; never persist
  them in plaintext.
- Don't log full log content, decrypted credentials, or full AI prompts/responses at `info` level.
