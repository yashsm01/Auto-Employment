-- Phase 5: auto mode, switched on by the user (profiles.auto_mode).
-- Jobs approved by auto mode are marked, so only their resumes are approved automatically.
alter table applications add column if not exists auto_approved_at timestamptz;
create index if not exists applications_auto on applications (auto_approved_at)
    where auto_approved_at is not null;
