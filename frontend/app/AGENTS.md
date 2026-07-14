<!-- ai_log_analyzer frontend/app/, AGENTS.md. -->

# frontend/app/

| Path | What it is |
|---|---|
| `login/` | Auth screen. |
| `dashboard/` | Main incident-analysis UI: source selection (manual/Linux/Docker), Analyze action, result tabs. |

## Conventions
- New authenticated views go under `dashboard/`; keep the "Analyze" action's single entry point
  in `components/LogUploader.tsx` rather than duplicating the trigger flow per page.
