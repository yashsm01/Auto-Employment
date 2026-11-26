-- Resume builder: the skills each ad asks for, as read from the ad itself.
alter table applications add column if not exists required_skills text[] not null default '{}';
alter table applications add column if not exists preferred_skills text[] not null default '{}';
alter table applications add column if not exists requirements_split boolean not null default false;

-- The user's answer to each skill the ad asks for: "have" or "no", keyed by a normalised skill.
create table if not exists skill_decisions (
    profile_id uuid not null references profiles (id) on delete cascade,
    skill_key text not null,
    skill text not null,
    decision text not null check (decision in ('have', 'no')),
    decided_at timestamptz not null default now(),
    primary key (profile_id, skill_key)
);
alter table skill_decisions enable row level security;
-- True when a "have" added the skill, so undoing it removes the skill again. Older "have" rows
-- and rows from before this column default to false, so undo never removes what the user had.
alter table skill_decisions add column if not exists added boolean not null default false;

-- Drafts wait in the Outbox until the user approves them.
alter table outbox drop constraint if exists outbox_status_check;
alter table outbox add constraint outbox_status_check
    check (status in ('queued', 'sent', 'failed', 'cancelled', 'draft'));
