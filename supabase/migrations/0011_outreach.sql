-- Phase 6: Google Maps outreach. Speculative emails to employers that have no advert.

-- Places found on Google Maps are stored as jobs with source 'nearby'.
alter table jobs drop constraint if exists jobs_source_check;
alter table jobs add constraint jobs_source_check
    check (source in ('trademe', 'gmail_alert', 'ats', 'serpapi', 'example', 'nearby'));

-- An application is either for an advert, or a speculative email to an employer.
alter table applications add column if not exists kind text not null default 'advert';
alter table applications drop constraint if exists applications_kind_check;
alter table applications add constraint applications_kind_check
    check (kind in ('advert', 'speculative'));

-- The business types to search for, the on/off switch, and how many new prospects a day.
alter table profiles add column if not exists business_types text[] not null default '{}';
alter table profiles add column if not exists prospects_enabled boolean not null default false;
alter table profiles add column if not exists prospects_per_day integer not null default 5;
alter table profiles drop constraint if exists profiles_prospects_per_day_check;
alter table profiles add constraint profiles_prospects_per_day_check
    check (prospects_per_day between 1 and 10);

-- Employers this profile must not email again, and why.
create table if not exists outreach_blocks (
    profile_id uuid not null references profiles (id) on delete cascade,
    company_id uuid not null references companies (id) on delete cascade,
    reason text not null check (reason in ('replied', 'bounced', 'no_unsolicited', 'manual')),
    created_at timestamptz not null default now(),
    primary key (profile_id, company_id)
);
alter table outreach_blocks enable row level security;
