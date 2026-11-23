# Folder structure

This is the target layout from the plan. Some files arrive in later phases.

```text
job-autopilot/
├── AGENT.md                     # rules for any AI coding agent working in this repo
├── GOAL.md                      # what we are building and why
├── ARCHITECTURE.md              # layers, dependency rules, debugging
├── docs/                        # DATABASE.md, PROCESS_FLOW.md, this file
│
├── backend/
│   ├── pyproject.toml
│   ├── .env.example             # every key name, no values
│   ├── app/
│   │   ├── main.py              # FastAPI app: create app, include routers. Nothing else.
│   │   │
│   │   ├── core/                # shared plumbing, no business logic
│   │   │   ├── config.py        # pydantic-settings, reads .env
│   │   │   ├── logging.py       # JSON logs with run_id
│   │   │   ├── errors.py        # AppError, ProviderError, NotFound
│   │   │   └── deps.py          # FastAPI dependencies (db, current profile)
│   │   │
│   │   ├── db/
│   │   │   └── client.py        # one Supabase client
│   │   │
│   │   ├── schemas/             # Pydantic models = API + domain shapes
│   │   │   ├── job.py  company.py  contact.py  application.py
│   │   │   ├── resume.py  outbox.py  call.py  settings.py
│   │   │
│   │   ├── repositories/        # ONLY database reads/writes, one file per table group
│   │   │   ├── jobs_repo.py  companies_repo.py  applications_repo.py
│   │   │   ├── resumes_repo.py  outbox_repo.py  events_repo.py  runs_repo.py
│   │   │
│   │   ├── providers/           # ONLY external APIs. One file per provider.
│   │   │   ├── llm/             # base.py (interface) claude.py openai.py gemini.py factory.py
│   │   │   ├── search/          # tavily.py brave.py serpapi.py
│   │   │   ├── jobs/            # trademe.py gmail_alerts.py ats.py
│   │   │   ├── company/         # nzbn.py companies_office.py places.py website_reader.py
│   │   │   ├── channels/        # gmail_sender.py whatsapp.py
│   │   │   └── voice/           # omnidim.py
│   │   │
│   │   ├── services/            # business rules. Call repositories + providers.
│   │   │   ├── lead_service.py  enrich_service.py  resume_service.py  matching_service.py
│   │   │   ├── outreach_service.py  settings_service.py
│   │   │
│   │   ├── chains/              # LLM chains. Prompt + model + output parser.
│   │   │   ├── manager.py       # get_chain(name) → builds chain with model from settings
│   │   │   ├── resume_profile_chain.py   query_chain.py
│   │   │   ├── score_chain.py   tailor_chain.py   fact_check_chain.py
│   │   │   ├── company_summary_chain.py   cover_note_chain.py
│   │   │   └── prompts/         # score.md tailor.md fact_check.md ... (plain text, easy to edit)
│   │   │
│   │   ├── graphs/              # LangGraph. One folder per graph.
│   │   │   ├── lead/
│   │   │   │   ├── graph.py     # ONLY: StateGraph, add_node, add_edge, compile
│   │   │   │   ├── state.py     # LeadState TypedDict
│   │   │   │   ├── routes.py    # conditional edge functions (return next node name)
│   │   │   │   └── nodes/       # one file per node: load_resume_profile.py build_queries.py fetch_jobs.py
│   │   │   │                    #   dedupe.py enrich.py prefilter.py score.py shortlist.py
│   │   │   ├── resume/          # same shape: graph.py state.py routes.py nodes/
│   │   │   ├── outreach/        # same shape
│   │   │   └── runner.py        # run_graph(name, input): logs graph_runs row, catches errors
│   │   │
│   │   ├── api/                 # FastAPI routers. Validate input, call a service, return schema.
│   │   │   ├── jobs.py  companies.py  applications.py  resumes.py
│   │   │   ├── settings.py  runs.py  webhooks.py
│   │   │
│   │   └── workers/
│   │       ├── scheduler.py     # APScheduler: daily lead run, 15-min outreach run
│   │       └── outbox_worker.py
│   │
│   └── tests/
│       ├── unit/                # mirrors app/: test_nodes/, test_chains/, test_services/
│       ├── integration/         # real Supabase local + mocked providers
│       └── fixtures/            # sample job posts, sample resume, recorded API responses
│
├── frontend/                    # React + Vite + TypeScript + Tailwind
│   ├── src/
│   │   ├── main.tsx  App.tsx    # router only
│   │   ├── api/                 # client.ts (fetch wrapper) + one file per backend router
│   │   ├── types/               # generated from FastAPI OpenAPI (npm run gen:types)
│   │   ├── pages/
│   │   │   ├── Pipeline.tsx     # board: found → replied
│   │   │   ├── JobDetail.tsx    # job + employer profile + resume + timeline
│   │   │   ├── Approvals.tsx
│   │   │   └── settings/        # AiProviders.tsx CallAgent.tsx DataSources.tsx
│   │   ├── components/          # Card, StatusPill, SourceBadge, Timeline, MapPin
│   │   └── hooks/               # useJobs, useApplication (TanStack Query)
│   └── package.json
│
└── supabase/
    ├── migrations/              # 0001_init.sql, 0002_company_facts.sql ...
    └── seed.sql                 # example profile + 3 example jobs
```

## Where a change goes

| Change | Folder |
|---|---|
| A new external API | `backend/app/providers/` |
| A SQL query | `backend/app/repositories/` |
| A business rule | `backend/app/services/` |
| A prompt or scoring method | `backend/app/chains/` |
| A step in a pipeline | `backend/app/graphs/<graph>/nodes/` |
| A new endpoint | `backend/app/api/` |
| A new screen | `frontend/src/pages/` |
| A database change | a new file in `supabase/migrations/` |
