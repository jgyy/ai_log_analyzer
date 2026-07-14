<!-- ai_log_analyzer frontend/, SKILLS.md. -->

# Skills: frontend/

| Task | Where |
|---|---|
| Add a new page/route | `app/` — see `app/SKILLS.md` |
| Add or change a UI component | `components/` — see `components/SKILLS.md` |
| Call a new backend endpoint | `lib/api.ts` — add a method there, never a raw `fetch()` in a component |
| Update the API contract | `lib/types.ts`, kept in sync with `../backend/schemas.py` in the same change |
| Run the dev server | `npm run dev` |
