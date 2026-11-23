# Rules for AI coding agents

Read [GOAL.md](GOAL.md) and [ARCHITECTURE.md](ARCHITECTURE.md) before changing code.

## Commands

```bash
# Backend, from backend/. Use Python 3.12, because the default `py` here may be newer.
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m app.db.migrate --seed
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# Frontend, from frontend/
npm test
npm run build
npm run dev
npm run gen:types   # needs the backend running
```

Integration tests start their own throwaway Postgres. They need `initdb` and `pg_ctl` on PATH, or `TEST_DATABASE_URL`.

## Code rules

- Imports only point down the layers in ARCHITECTURE.md.
- `graph.py` is wiring only. One node per file.
- SQL lives only in `repositories/`. External HTTP lives only in `providers/`.
- Write a failing test first. Use real Postgres for database behaviour.
- Test fixtures must be labelled synthetic unless they were recorded from the real API.
- After changing an API response, run `npm run gen:types`.
- Change the database only by adding a new migration file.

## Safety rules

- Never scrape SEEK, LinkedIn or Indeed.
- Never commit `.env`, API keys, or resumes. `.gitignore` blocks PDF and Word files.
- Never put credentials in error messages or logs.
- Never send a real message to an employer without the user's approval.
- Never add a fact to a resume that is not in the base resume.
- Keep row level security on for every new table.
