-- Phase 4: AI phone calls after unanswered follow-ups, and WhatsApp updates to the user.

alter table calls alter column application_id drop not null;
alter table calls add column if not exists profile_id uuid references profiles (id) on delete cascade;
alter table calls add column if not exists purpose text not null default 'follow_up';
alter table calls drop constraint if exists calls_purpose_check;
alter table calls add constraint calls_purpose_check check (purpose in ('follow_up', 'test'));
alter table calls add column if not exists to_number text;
alter table calls add column if not exists request_id text;
alter table calls add column if not exists extracted jsonb not null default '{}';
alter table calls add column if not exists error text;
alter table calls add column if not exists dispatched_at timestamptz;
alter table calls add column if not exists finished_at timestamptz;
create index if not exists calls_open on calls (created_at) where status in ('queued', 'ringing');

-- An email sent after a call, to the address the employer gave.
alter table outbox drop constraint if exists outbox_kind_check;
alter table outbox add constraint outbox_kind_check
    check (kind in ('application', 'follow_up', 'after_call'));

create table if not exists notifications (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references profiles (id) on delete cascade,
    kind text not null,
    text text not null,
    dedupe_key text unique,
    status text not null default 'queued' check (status in ('queued', 'sent', 'failed')),
    attempts integer not null default 0,
    error text,
    created_at timestamptz not null default now(),
    sent_at timestamptz
);
create index if not exists notifications_queue on notifications (created_at)
    where status = 'queued';
alter table notifications enable row level security;
