-- NZ Job Autopilot: core tables. Runs on Supabase and on plain Postgres 13+.
-- Embedding columns are in 0002 and the Supabase auth link is in 0003.

create table profiles (
    id uuid primary key default gen_random_uuid(),
    user_id uuid unique,
    full_name text not null,
    field text,
    target_roles text[] not null default '{}',
    regions text[] not null default '{}',
    work_rights text check (work_rights in ('citizen', 'resident', 'open_visa', 'needs_sponsorship')),
    salary_min integer check (salary_min >= 0),
    avoid_keywords text[] not null default '{}',
    shortlist_threshold integer not null default 70 check (shortlist_threshold between 0 and 100),
    auto_mode boolean not null default false,
    daily_send_limit integer not null default 15 check (daily_send_limit >= 0),
    created_at timestamptz not null default now()
);

create table settings (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null unique references profiles (id) on delete cascade,
    ai jsonb not null default '{}',
    call_agent jsonb not null default '{}',
    data_sources jsonb not null default '{}',
    updated_at timestamptz not null default now()
);

create table resumes (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references profiles (id) on delete cascade,
    kind text not null check (kind in ('base', 'tailored')),
    application_id uuid,
    content jsonb not null default '{}',
    file_path text,
    facts_used jsonb not null default '[]',
    created_at timestamptz not null default now(),
    check ((kind = 'base') = (application_id is null))
);

create table resume_profiles (
    id uuid primary key default gen_random_uuid(),
    resume_id uuid not null unique references resumes (id) on delete cascade,
    titles text[] not null default '{}',
    skills jsonb not null default '[]',
    tools text[] not null default '{}',
    industries text[] not null default '{}',
    seniority text,
    search_queries text[] not null default '{}',
    updated_at timestamptz not null default now()
);

create table companies (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    name_key text generated always as (lower(btrim(name))) stored unique,
    nzbn text unique,
    website text,
    linkedin_url text,
    industry text,
    size_band text,
    about text,
    address text,
    lat double precision,
    lng double precision,
    google_place_id text,
    phone text,
    email text,
    updated_at timestamptz not null default now()
);

create table company_facts (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies (id) on delete cascade,
    field text not null,
    value text not null,
    source text not null check (source in ('job_post', 'nzbn', 'places', 'website', 'tavily', 'manual')),
    confidence text not null check (confidence in ('high', 'medium', 'check')),
    source_url text,
    fetched_at timestamptz not null default now(),
    unique (company_id, field, value)
);

create table contacts (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies (id) on delete cascade,
    name text,
    role text check (role in ('director', 'hiring_manager', 'recruiter', 'general')),
    email text,
    phone text,
    linkedin_url text,
    source text,
    confidence text check (confidence in ('high', 'medium', 'check'))
);

create table jobs (
    id uuid primary key default gen_random_uuid(),
    company_id uuid references companies (id) on delete set null,
    source text not null check (source in ('trademe', 'gmail_alert', 'ats', 'serpapi', 'example')),
    external_id text not null,
    title text not null,
    location text not null default '',
    region text not null default '',
    salary_min integer,
    salary_max integer,
    url text,
    description text not null default '',
    posted_at timestamptz,
    closes_at timestamptz,
    dedupe_hash text not null unique,
    created_at timestamptz not null default now(),
    unique (source, external_id)
);

create table applications (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references profiles (id) on delete cascade,
    job_id uuid not null references jobs (id) on delete cascade,
    score integer check (score between 0 and 100),
    similarity double precision,
    matched_skills text[] not null default '{}',
    missing_skills text[] not null default '{}',
    score_reason text,
    status text not null default 'found' check (status in (
        'found', 'shortlisted', 'tailoring', 'ready', 'approved',
        'sent', 'followed_up', 'replied', 'closed'
    )),
    resume_id uuid references resumes (id) on delete set null,
    next_follow_up date,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (profile_id, job_id)
);

alter table resumes
    add constraint resumes_application_id_fkey
    foreign key (application_id) references applications (id) on delete cascade;

create table feedback (
    id uuid primary key default gen_random_uuid(),
    application_id uuid not null references applications (id) on delete cascade,
    action text not null check (action in ('approve', 'skip')),
    reason text,
    created_at timestamptz not null default now()
);

create table outbox (
    id uuid primary key default gen_random_uuid(),
    application_id uuid not null references applications (id) on delete cascade,
    channel text not null check (channel in ('email', 'whatsapp')),
    to_address text not null,
    subject text,
    body text not null,
    attachment_path text,
    status text not null default 'queued' check (status in ('queued', 'sent', 'failed')),
    attempts integer not null default 0,
    error text,
    scheduled_at timestamptz not null default now(),
    sent_at timestamptz
);

create table calls (
    id uuid primary key default gen_random_uuid(),
    application_id uuid not null references applications (id) on delete cascade,
    contact_id uuid references contacts (id) on delete set null,
    omnidim_call_id text,
    status text not null default 'queued' check (status in ('queued', 'ringing', 'done', 'failed')),
    duration_sec integer,
    transcript text,
    summary text,
    next_action text,
    created_at timestamptz not null default now()
);

create table events (
    id uuid primary key default gen_random_uuid(),
    application_id uuid references applications (id) on delete cascade,
    company_id uuid references companies (id) on delete cascade,
    type text not null check (type in (
        'found', 'shortlisted', 'approved', 'skipped', 'emailed', 'replied', 'called', 'note'
    )),
    payload jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create table graph_runs (
    id uuid primary key default gen_random_uuid(),
    graph text not null check (graph in ('lead', 'resume', 'outreach')),
    application_id uuid references applications (id) on delete set null,
    status text not null default 'running' check (status in ('running', 'ok', 'error')),
    input jsonb not null default '{}',
    output jsonb not null default '{}',
    error text,
    failed_node text,
    started_at timestamptz not null default now(),
    finished_at timestamptz
);

-- Only one run of a graph at a time.
create unique index graph_runs_one_running on graph_runs (graph) where status = 'running';

create index applications_board_idx on applications (profile_id, status, score desc);
create index outbox_queue_idx on outbox (status, scheduled_at);
create index events_application_idx on events (application_id, created_at);

-- Supabase publishes the public schema through its API. With RLS on and no policies,
-- only the backend's database role can read or write these tables.
alter table profiles enable row level security;
alter table settings enable row level security;
alter table resumes enable row level security;
alter table resume_profiles enable row level security;
alter table companies enable row level security;
alter table company_facts enable row level security;
alter table contacts enable row level security;
alter table jobs enable row level security;
alter table applications enable row level security;
alter table feedback enable row level security;
alter table outbox enable row level security;
alter table calls enable row level security;
alter table events enable row level security;
alter table graph_runs enable row level security;
