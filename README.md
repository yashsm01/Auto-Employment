# Auto-Employment: NZ Job Autopilot

A personal tool that finds New Zealand jobs, scores them against your resume, and tracks each one from shortlist to reply.

**Current state: Phase 1.** It searches, scores and shortlists jobs. It does not send anything to employers yet. Without API keys it uses clearly labelled example jobs.

## Run it locally

You need Python 3.12, Node 20 or newer, and a Postgres database.

```powershell
# 1. Create a database (or use a Supabase project)
createdb -U postgres job_autopilot

# 2. Backend
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
copy .env.example .env      # then set DATABASE_URL in .env
.venv\Scripts\python -m app.db.migrate --seed
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# 3. Frontend, in a second terminal
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and press **Run search now**.

The backend has no login yet, so run it only on your own computer.

## Project docs

- [GOAL.md](GOAL.md): what this is, the phases, and the rules
- [ARCHITECTURE.md](ARCHITECTURE.md): layers and debugging
- [AGENT.md](AGENT.md): commands and rules for AI coding agents
- [docs/DATABASE.md](docs/DATABASE.md), [docs/PROCESS_FLOW.md](docs/PROCESS_FLOW.md), [docs/FOLDER_STRUCTURE.md](docs/FOLDER_STRUCTURE.md)
