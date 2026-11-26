-- True when a "have" added the skill, so undoing it removes the skill again. Older "have" rows
-- default to false, so undo never removes what the user already had.
alter table skill_decisions add column if not exists added boolean not null default false;
