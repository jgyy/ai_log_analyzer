<!-- ai_log_analyzer backend/, SKILLS.md. -->

# Skills: backend/

| Task | Where |
|---|---|
| Add/change a route | `main.py` — keep handlers thin, both analysis entry points must stay on the same `ai_service.py` pipeline |
| Change AI provider integration, retries, or Mermaid validation | `ai_service.py` |
| Add a new evidence source | `connectors.py` (local) or `connectors_vm.py` (remote), then wire into `main.py` |
| Add a new remediation action | `actions.py`, as an allowlisted action, never freeform |
| Change the API/AI response contract | `schemas.py`, and mirror in `../frontend/lib/types.ts` |
| Add a DB model or migration | `database.py` |
| Change auth/roles | `auth.py` |
| Store a new kind of credential | encrypt via `crypto_utils.py`, never plaintext |
| Change manual log preprocessing | `log_processor.py` |
| Run tests | `unittest`, files named `test_*.py` |
