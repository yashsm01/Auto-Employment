# Database

Postgres on Supabase. Migrations are plain SQL in `supabase/migrations` and also run on local Postgres.

| Migration | Purpose |
|---|---|
| `0001_init.sql` | All 14 tables, constraints, indexes, and row level security |
| `0002_embeddings.sql` | pgvector columns (768 dimensions) and an HNSW index. Skipped if pgvector is not installed |
| `0003_supabase_auth.sql` | Links `profiles.user_id` to Supabase Auth. Does nothing on plain Postgres |

## Why the main tables exist

- **resume_profiles** turns the resume into skills, titles and search queries.
- **company_facts** keeps the source and confidence of every employer detail.
- **applications** holds one job's score and status for a profile.
- **graph_runs** stores each run's input, output and failing step. A partial unique index allows one running graph at a time.

## Security

Row level security is on for every table with no policies. Supabase's public API therefore cannot read or write them. The backend connects with a database role that bypasses RLS, so `DATABASE_URL` must stay on the server.

## Changes from the original plan

- Added `profiles.shortlist_threshold`, `jobs.closes_at` and a unique `companies.name_key`.
- Added `example` as a job source and `job_post` as a fact source.
- `resumes.application_id` and `applications.resume_id` reference each other, so one foreign key is added after both tables exist.

## Diagram

```mermaid
erDiagram
    profiles ||--o{ resumes : owns
    resumes ||--o| resume_profiles : "parsed into"
    applications ||--o{ feedback : "rated by you"
    profiles ||--|| settings : has
    profiles ||--o{ applications : makes
    companies ||--o{ jobs : posts
    companies ||--o{ contacts : has
    companies ||--o{ company_facts : "described by"
    jobs ||--o{ applications : "applied via"
    applications ||--o| resumes : "uses tailored"
    applications ||--o{ outbox : sends
    applications ||--o{ calls : "followed by"
    contacts ||--o{ calls : receives
    applications ||--o{ events : logs
    companies ||--o{ events : logs
    graph_runs }o--|| applications : "traces (optional)"

    profiles {
        uuid id PK
        uuid user_id "supabase auth"
        text full_name
        text field
        text[] target_roles
        text[] regions
        text work_rights
        int salary_min
        text[] avoid_keywords
        bool auto_mode
        int daily_send_limit
        int shortlist_threshold
        timestamptz created_at
    }
    resume_profiles {
        uuid id PK
        uuid resume_id FK "base resume"
        text[] titles "roles held + target"
        jsonb skills "name, years, level"
        text[] tools
        text[] industries
        text seniority
        text[] search_queries "generated, editable"
        vector embedding "768 dimensions, migration 0002"
        timestamptz updated_at
    }
    feedback {
        uuid id PK
        uuid application_id FK
        text action "approve | skip"
        text reason
        timestamptz created_at
    }
    settings {
        uuid id PK
        uuid profile_id FK
        jsonb ai "providers, models, which does what"
        jsonb call_agent "omnidimension voice, llm, script"
        jsonb data_sources "on/off per source"
        timestamptz updated_at
    }
    resumes {
        uuid id PK
        uuid profile_id FK
        text kind "base | tailored"
        uuid application_id FK "null for base"
        jsonb content "parsed sections"
        text file_path "supabase storage"
        jsonb facts_used "employer facts cited"
        timestamptz created_at
    }
    companies {
        uuid id PK
        text name
        text nzbn UK
        text website
        text linkedin_url
        text industry
        text size_band
        text about
        text address
        float lat
        float lng
        text google_place_id
        text phone
        text email
        timestamptz updated_at
    }
    company_facts {
        uuid id PK
        uuid company_id FK
        text field "e.g. about, recent_project"
        text value
        text source "job_post | nzbn | places | website | tavily | manual"
        text confidence "high | medium | check"
        text source_url
        timestamptz fetched_at
    }
    contacts {
        uuid id PK
        uuid company_id FK
        text name
        text role "director | hiring_manager | recruiter | general"
        text email
        text phone
        text linkedin_url
        text source
        text confidence
    }
    jobs {
        uuid id PK
        uuid company_id FK
        text source "trademe | gmail_alert | ats | serpapi | example"
        text external_id
        text title
        text location
        text region
        int salary_min
        int salary_max
        text url
        text description
        timestamptz posted_at
        timestamptz closes_at
        text dedupe_hash UK
        vector embedding "768 dimensions, migration 0002"
        timestamptz created_at
    }
    applications {
        uuid id PK
        uuid profile_id FK
        uuid job_id FK
        int score
        float similarity "embedding vs resume"
        text[] matched_skills
        text[] missing_skills
        text score_reason
        text status "found > shortlisted > tailoring > ready > approved > sent > followed_up > replied > closed"
        uuid resume_id FK
        date next_follow_up
        timestamptz created_at
        timestamptz updated_at
    }
    outbox {
        uuid id PK
        uuid application_id FK
        text channel "email | whatsapp"
        text to_address
        text subject
        text body
        text attachment_path
        text status "queued | sent | failed"
        int attempts
        text error
        timestamptz scheduled_at
        timestamptz sent_at
    }
    calls {
        uuid id PK
        uuid application_id FK
        uuid contact_id FK
        text omnidim_call_id
        text status "queued | ringing | done | failed"
        int duration_sec
        text transcript
        text summary
        text next_action
        timestamptz created_at
    }
    events {
        uuid id PK
        uuid application_id FK
        uuid company_id FK
        text type "found | shortlisted | approved | skipped | emailed | replied | called | note"
        jsonb payload
        timestamptz created_at
    }
    graph_runs {
        uuid id PK
        text graph "lead | resume | outreach"
        uuid application_id FK
        text status "running | ok | error"
        jsonb input
        jsonb output
        text error
        text failed_node
        timestamptz started_at
        timestamptz finished_at
    }
```
