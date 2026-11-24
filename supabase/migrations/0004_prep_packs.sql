-- Deep search: one preparation pack per run, waiting in a queue until the worker runs it.

create table if not exists prep_packs (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references profiles (id) on delete cascade,
    application_id uuid not null references applications (id) on delete cascade,
    company_id uuid references companies (id) on delete set null,
    status text not null default 'queued'
        check (status in ('queued', 'running', 'done', 'failed')),
    error text,
    extra text,
    content jsonb not null default '{}',
    sources jsonb not null default '[]',
    facts jsonb not null default '[]',
    notes jsonb not null default '[]',
    cost_usd numeric(10, 5) not null default 0,
    places_calls integer not null default 0,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    finished_at timestamptz
);

create index if not exists prep_packs_queue on prep_packs (created_at) where status = 'queued';
create index if not exists prep_packs_application on prep_packs (application_id, created_at desc);
create index if not exists prep_packs_company on prep_packs (company_id, finished_at desc)
    where status = 'done';

alter table prep_packs enable row level security;

-- The deep search graph records its runs alongside the others.
alter table graph_runs drop constraint if exists graph_runs_graph_check;
alter table graph_runs add constraint graph_runs_graph_check
    check (graph in ('lead', 'resume', 'outreach', 'prep'));
