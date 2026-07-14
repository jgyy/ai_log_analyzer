<!-- ai_log_analyzer frontend/lib/, AGENTS.md. -->

# frontend/lib/

| File | What it is |
|---|---|
| `api.ts` | Backend API client — every backend call goes through here. |
| `types.ts` | Frontend copy of backend response types; keep in sync with `backend/schemas.py`. |

## Conventions
- Add a new backend endpoint call as a new method here, not as an inline `fetch` in a component.
