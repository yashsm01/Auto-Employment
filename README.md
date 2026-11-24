# Auto-Employment: NZ Job Autopilot

A personal tool that finds New Zealand jobs, scores them against your resume, researches employers, and tracks each job from shortlist to reply.

**Current state: Phase 2.** It reads your resume, searches, scores, shortlists and researches employers. When you approve a job, it writes a tailored resume and cover note for you to review. It does not send anything to employers yet. Until you add your resume or a job source, it uses clearly labelled example jobs.

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

Open http://localhost:5173, go to **My resume profile**, and upload your resume.

The backend has no login yet, so run it only on your own computer.

## Connect job sources and AI

Everything below is optional. Add keys to `backend/.env`, then restart the backend.

| Feature | What you need | Without it |
|---|---|---|
| Company careers pages | Nothing. Add Greenhouse, Lever or Ashby boards on your profile | No jobs from those companies |
| Local employers from Google Maps | `GOOGLE_MAPS_API_KEY`, plus `ANTHROPIC_API_KEY` to read careers pages | No employer websites checked |
| AI resume reading and scoring | `ANTHROPIC_API_KEY` | Free keyword matching |
| Tailored resumes and cover notes | `ANTHROPIC_API_KEY` | Your resume as it is, with a short standard cover note |
| Job ranking | `GOOGLE_API_KEY` | Skill matching only |
| Trade Me jobs | `TRADEME_CONSUMER_KEY` and `TRADEME_CONSUMER_SECRET` | No Trade Me jobs |
| SEEK, LinkedIn and Indeed alerts | `EMAIL_ENABLED`, `EMAIL_ADDRESS`, `EMAIL_APP_PASSWORD` and `ANTHROPIC_API_KEY` | No alert jobs |
| Employer address and phone | `GOOGLE_MAPS_API_KEY` | Details from the job post only |
| Employer news | `TAVILY_API_KEY` | No news |

Each search lists where it looked on the Pipeline page, and every job shows its source.

With a Maps key, each search finds up to 60 employers for your job titles and towns (3 Maps searches) and checks 8 saved employers' websites for open jobs. Change this with `MAX_DISCOVERY_SEARCHES_PER_RUN`, `MAX_EMPLOYER_SITES_PER_RUN` and `MAX_NEARBY_SEARCHES_PER_DAY` in `.env`. Many small employers have no careers page, so expect a few jobs per search from this source.

To connect Gmail, turn on 2-Step Verification for your Google account, create an app password at https://myaccount.google.com/apppasswords, then set these in `.env`:

```env
EMAIL_ENABLED=true
EMAIL_ADDRESS=you@gmail.com
EMAIL_APP_PASSWORD=your-16-letter-app-password
```

The app reads your mailbox read-only. It never sends, deletes or marks email, and it never opens links from alerts. Set your job alerts for NZ, for example on nz.indeed.com.

The search runs daily at 7 am NZ time **while the backend is running**. If the computer was off, it catches up the next time the backend starts.

## Tailored resumes

1. On **Shortlist**, approve a job. Tailoring starts straight away and usually takes under a minute.
2. Open **Resume review**. Each job shows your original resume next to the tailored one, with reworded lines highlighted.
3. Edit the cover note if you like, then **Approve**, **Reject** or **Regenerate**. **Download PDF** gives the file that will be attached.

Tailoring only rewords and reorders what your resume already says. Titles, employers and dates are copied from your resume, never from the AI. Every result is checked twice: by code (no new numbers or skills) and by a second AI check against your resume and the job post. Anything unsupported goes back to your original wording, and the Fact check box lists what changed back.

Your name, email and phone at the top of the PDF come from **My resume profile** under "Your details for resumes". Your email and phone number are removed from your resume before it is sent to AI. The greeting and sign-off are added by the app.

If tailoring fails, the job shows the error and a **Try again** button. Failed jobs are not retried on their own, so a broken key does not keep using calls. A queue every 15 minutes picks up approved jobs that have not been tried yet, for example after a restart. Approved resumes wait for Phase 3, which adds email sending.

Models are set in `.env`: `RESUME_MODEL` reads your resume into sections, `TAILOR_MODEL` writes the tailored version, and `SCORING_MODEL` runs the fact check.

## Project docs

- [GOAL.md](GOAL.md): what this is, the phases, and the rules
- [ARCHITECTURE.md](ARCHITECTURE.md): layers and debugging
- [AGENT.md](AGENT.md): commands and rules for AI coding agents
- [docs/DATABASE.md](docs/DATABASE.md), [docs/PROCESS_FLOW.md](docs/PROCESS_FLOW.md), [docs/FOLDER_STRUCTURE.md](docs/FOLDER_STRUCTURE.md)
