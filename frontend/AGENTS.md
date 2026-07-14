<!-- ai_log_analyzer frontend/, AGENTS.md. Next.js 14 dashboard. -->

# frontend/

Next.js 14 + React 18 + TypeScript dashboard. Dev: `npm run dev`.

| Path | What it is |
|---|---|
| `app/` | Routes: `login/` (auth screen), `dashboard/` (main incident-analysis UI). See `app/AGENTS.md`. |
| `components/` | UI components: source upload/selection, analysis tabs, Mermaid rendering. See `components/AGENTS.md`. |
| `lib/` | API client and shared types (see `lib/AGENTS.md`). |

## Conventions
- All backend calls go through `lib/api.ts` — don't `fetch()` the backend directly from a
  component or page.
- Types in `lib/types.ts` mirror backend `schemas.py`; update both in the same change when the
  API contract changes.
