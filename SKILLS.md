<!-- ai_log_analyzer, project-root SKILLS.md. Task-oriented companion to
     AGENTS.md: "how do I do X here" rather than "how is this built".
     Each subdirectory has its own local SKILLS.md; read it when working
     there. Keep entries anchored on stable paths, not counts that rot. -->

# Skills: ai_log_analyzer

Common tasks across this repo, with the file(s) they touch.

| Task | Where |
|---|---|
| Add a new analysis data source (beyond manual/Linux/Docker/VM) | `backend/connectors.py` or `backend/connectors_vm.py`, wired into `main.py`'s shared pipeline |
| Add a field to the AI's structured output | `backend/schemas.py` (Pydantic schema) + `frontend/lib/types.ts` (mirror type) in the same change |
| Add a new remediation action | `backend/actions.py`, as an explicitly allowlisted action |
| Change AI provider behavior (retries, model choice, Mermaid validation) | `backend/ai_service.py` |
| Add a new authenticated backend endpoint | `backend/main.py`, going through `backend/auth.py`'s JWT dependency |
| Add a new result tab in the UI | `frontend/components/TabViews/`, composed into `frontend/components/AnalysisTab.tsx` |
| Add a new backend call from the frontend | `frontend/lib/api.ts` (never `fetch()` from a component) |
| Render new AI-generated diagram/text content | route through `frontend/components/MermaidDiagram.tsx`'s sanitizer, don't inject raw AI output |

See each subdirectory's `SKILLS.md` for area-specific task lists.
