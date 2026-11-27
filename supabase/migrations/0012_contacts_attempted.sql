-- When the employer's website was last read, even when the read failed. Auto mode waits on it.
alter table companies add column if not exists contacts_attempted_at timestamptz;
