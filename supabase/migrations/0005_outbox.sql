-- Phase 3: sending applications, follow-ups and the Outbox.

alter table outbox add column if not exists kind text not null default 'application';
alter table outbox drop constraint if exists outbox_kind_check;
alter table outbox add constraint outbox_kind_check check (kind in ('application', 'follow_up'));
alter table outbox add column if not exists message_id text;
alter table outbox add column if not exists reply_to_message_id text;
alter table outbox add column if not exists attachment_name text;
alter table outbox drop constraint if exists outbox_status_check;
alter table outbox add constraint outbox_status_check
    check (status in ('queued', 'sent', 'failed', 'cancelled'));
create index if not exists outbox_due on outbox (scheduled_at) where status = 'queued';
create index if not exists outbox_application on outbox (application_id, scheduled_at);

-- How the job was applied for: by email from this app, or by the user on the job site.
alter table applications add column if not exists apply_method text;
alter table applications drop constraint if exists applications_apply_method_check;
alter table applications add constraint applications_apply_method_check
    check (apply_method in ('email', 'manual'));
alter table applications add column if not exists applied_at timestamptz;
alter table applications add column if not exists follow_ups integer not null default 0;
