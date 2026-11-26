-- Employer contacts: where each contact was found, and when the employer's site was last checked.
alter table contacts add column if not exists source_url text;
alter table contacts add column if not exists checked_at timestamptz default now();
-- The job title of a named recruiter, as the employer's page writes it.
alter table contacts add column if not exists title text;
alter table companies add column if not exists contacts_checked_at timestamptz;
create index if not exists contacts_company on contacts (company_id);
