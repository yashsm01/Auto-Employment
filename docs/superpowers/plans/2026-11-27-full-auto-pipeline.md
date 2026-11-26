# Hands-off Job Hunting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set the resume and areas once; the app finds jobs, finds employer contacts, applies, follows up, and approaches Google Maps employers within strict limits — with no clicks, WhatsApp updates, and a contacts list in the Outbox.

**Architecture:** Reuse the existing pipeline. Approving a job triggers the existing contact lookup; Auto mode waits for it. Google Maps employers become "speculative" applications (a job with source `nearby`, `applications.kind = 'speculative'`) so the Outbox's sending, follow-ups, reply and bounce checks, limits and notifications apply unchanged, with a one-follow-up cap and an outreach block list.

**Tech Stack:** FastAPI, psycopg3, LangGraph/Anthropic chains, APScheduler, fpdf2/python-docx (existing); React 19, TanStack Query, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-27-full-auto-pipeline-design.md` (research: `reports/NZ employer contact sources and limits.md`).

## Global Constraints

- Company contacts only: the employer's published emails and phone (website, Google Maps), the contact named in the advert, and hiring contacts named on the employer's own pages (existing rules). Never named staff/owners/coworkers from elsewhere, never email-finder services, never guessed addresses, never LinkedIn.
- No WhatsApp, texts or calls to employers from this feature. No submitting applications on job sites (SEEK, Trade Me, jobs.govt.nz).
- Google Maps outreach: only when Auto mode **and** the Google Maps outreach switch are on (switch off by default); at most `prospects_per_day` new speculative records a day (1–10, default 5); one email and **one** follow-up 5 working days later, then closed; never an employer already tied to an advert application; an `outreach_blocks` row (reply, bounce, "no unsolicited" on their site) stops speculative outreach to that employer forever.
- Speculative email subject: "Enquiry about opportunities at {company} – {name}". Body ends with exactly: "If you'd rather I didn't contact you again, just reply and I won't." Attachment: the master CV PDF in the chosen design.
- One shared daily send limit; advert applications send before speculative ones; unsent emails carry to the next run.
- Missing-contact reasons, exactly: "Website not checked yet", "Checked {d Mon yyyy}: no email on the site", "No website known", "Could not read the website", "Advert asks you to apply on the job site".
- Evening summary at 18:00 NZ time, only when something happened that day.
- Contact details never sent to AI (use `app.core.documents.ai_resume_json` / `redact_contact_details`).
- Never open `Aayush_Modi_Resume.pdf`; tests use made-up data; never send real emails, WhatsApp messages or calls in tests; no network in tests.
- No new dependencies. Migration number `0011`. Frontend types from `create_app().openapi()` dumped to a file, never port 8000. Do not commit unless the user asks.

## Review Focus

1. **An employer that publishes no email** (like Endava) gets no speculative record and no email, and isn't retried until its contacts are re-checked. Test in Task 5.
2. **Running prospecting twice in one day** creates no more than `prospects_per_day` records in total. Test in Task 5.
3. **A reply or bounce to a speculative email** blocks that employer; it is never picked again. Test in Task 6.
4. **A master CV with no roles** starts no Google Maps outreach and sends one WhatsApp: "Add your work history in the Resume builder to start Google Maps outreach." Test in Task 5.
5. **An advert saying "apply online only"** is never emailed by Auto mode; the user gets the existing apply-yourself update. Test in Task 3.

---

### Task 1: Carry-over fixes

**Files:**
- Modify: `backend/app/services/resume_build_service.py` (`ensure_sections`), `backend/app/services/contact_extract.py` (`_CONTACT` link matching), `README.md`, `docs/PROCESS_FLOW.md`
- Test: `backend/tests/integration/test_tailoring_flow.py`, `backend/tests/unit/test_services/test_contact_extract.py`

**Interfaces:** Produces nothing new; `ensure_sections` returns `usable_sections(...)` of a freshly read result (None when it has no roles), as it already does for cached sections.

- [ ] **Step 1: Failing tests:** `test_a_first_ai_read_without_roles_never_reaches_the_tailored_pdf` (no cached sections; the sections chain returns skills but no roles; the tailored PDF text contains the uploaded resume's work history); `test_contactless_and_image_links_are_not_contact_pages` (`/x/contactless-payments.webp`, link text "Contactless payments" → `contact_url is None`; "Contact us" → found; links ending in .webp/.png/.jpg/.svg/.pdf/.gif are never contact or careers pages).
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement** (`_CONTACT` matches whole words `contact` / `contact us` / `get in touch`, not `contactless`; skip file-extension links). Fix the three stale doc lines: PROCESS_FLOW says 0009 adds `added` (it's 0010); README's AI empty-list fallback line; PROCESS_FLOW's "a roles-less save writes no sections" (save writes them; tailoring ignores them without roles). **Step 4: Run, full backend suite, ruff. PASS.**

---

### Task 2: Migration 0011 and settings

**Files:**
- Create: `supabase/migrations/0011_outreach.sql`
- Modify: `backend/app/schemas/auto.py` and `backend/app/api/auto.py` (extend the existing Auto mode settings), `backend/app/services/auto_service.py` (`get_settings`/`save_settings`), `backend/tests/integration/test_migrate.py`
- Test: `backend/tests/integration/test_auto_mode.py` (add)

**Interfaces:**
- Migration: `jobs.source` check adds `'nearby'`; `applications` add `kind text not null default 'advert' check (kind in ('advert','speculative'))`; `profiles` add `business_types text[] not null default '{}'`, `prospects_enabled boolean not null default false`, `prospects_per_day integer not null default 5 check (prospects_per_day between 1 and 10)`; `create table if not exists outreach_blocks (profile_id uuid not null references profiles(id) on delete cascade, company_id uuid not null references companies(id) on delete cascade, reason text not null check (reason in ('replied','bounced','no_unsolicited','manual')), created_at timestamptz not null default now(), primary key (profile_id, company_id))` with row-level security like the other tables. Idempotent style of 0005–0010.
- `AutoModeSettings` gains `prospects_enabled: bool = False`, `prospects_per_day: int = Field(5, ge=1, le=10)`, `business_types: list[str]` (≤20 items, each 1–60 chars). Saving `prospects_enabled = True` while Auto mode is off → 400 "Turn on Auto mode first."
- When `business_types` is empty and the resume profile has `industries`, `get_settings` returns them as the suggested list (`business_types_suggested: list[str]`), never saved until the user saves (my call: no extra AI call).

- [ ] **Step 1: Failing tests:** `test_migration_0011_applies_on_an_existing_database`, `test_prospect_settings_round_trip`, `test_prospects_need_auto_mode`, `test_business_types_are_suggested_from_resume_industries`.
- [ ] **Step 2–4:** Run (FAIL), implement, run + full suite + ruff (PASS).

---

### Task 3: Contacts found on approval, advert contact, site-only adverts

**Files:**
- Create: `backend/app/services/advert_contact.py`
- Modify: `backend/app/api/applications.py` (approve schedules `refresh_contacts` in the background), `backend/app/services/auto_service.py` (`_approve_jobs` runs the lookup inline via `contact_service.lookup` with tools from `source_service.build_contact_tools`; `_queue_emails` waits and skips site-only adverts), `backend/app/workers/outbox_job.py` (pass contact tools into auto mode)
- Test: `backend/tests/unit/test_services/test_advert_contact.py`, `backend/tests/integration/test_auto_mode.py`, `backend/tests/integration/test_api.py` or the existing approve-route test file

**Interfaces:**
- `AdvertContact(name: str | None, role: str | None, email: str | None, phone: str | None)`; `advert_contact(description: str) -> AdvertContact | None` — plain code: a capitalised two-or-three-word name next to "contact", "call", "email", "speak to" or "talk to", an optional role after a comma, the first email and NZ phone in the same sentence (`find_emails`, `nz_e164`).
- `applies_on_site_only(description: str, url: str | None) -> bool` — True for the phrases (case-insensitive) "apply online only", "apply only through", "applications through seek only", "only applications submitted", "no agencies", "no recruitment agencies", "please do not contact", "no direct approaches", "via our careers site only", or a URL host ending `jobs.govt.nz`.
- Auto mode `_queue_emails`: no address and the company has a website and `contacts_checked_at` is null → skip silently (try again next pass); site-only advert → never queue, send the existing `auto_apply_yourself` update once.

- [ ] **Step 1: Failing tests:** `test_advert_contact_reads_a_named_contact_with_phone`, `test_advert_contact_ignores_a_bare_company_name`, `test_site_only_phrases_and_jobs_govt_nz`, `test_approving_a_job_starts_a_contact_lookup` (API; background replaced by a recorder), `test_auto_mode_looks_up_contacts_before_queueing`, `test_auto_mode_waits_for_an_unchecked_website` (Review Focus 5 companion), `test_auto_mode_never_emails_an_apply_online_only_advert` (Review Focus 5).
- [ ] **Step 2–4:** Run (FAIL), implement, run + full suite + ruff (PASS).

---

### Task 4: Area clean-up

**Files:**
- Modify: `backend/app/services/lead_service.py` (expose `in_regions(job_row, regions) -> bool`, reusing `_in_regions`), `backend/app/services/resume_service.py` (`update` closes outside-area jobs when regions change), `backend/app/schemas/resume.py` (`ProfileView.closed_outside_areas: int = 0` on the save response)
- Test: `backend/tests/integration/test_profile_api.py` (add)

**Interfaces:** When `regions` changes, applications in `found` or `shortlisted` whose job fails `in_regions` become `closed` with an event note "Outside your areas"; the save response reports how many. Approved and later statuses are never touched. Clearing all regions (all of NZ) closes nothing.

- [ ] **Step 1: Failing tests:** `test_changing_areas_closes_outside_jobs`, `test_approved_jobs_are_kept_when_areas_change`, `test_remote_area_keeps_remote_jobs`.
- [ ] **Step 2–4:** Run (FAIL), implement, run + full suite + ruff (PASS).

---

### Task 5: Google Maps prospecting

**Files:**
- Create: `backend/app/services/prospect_service.py`, `backend/app/chains/speculative_chain.py`, `backend/app/repositories/outreach_repo.py`
- Modify: `backend/app/services/employer_service.py` (`discovery_queries` uses `business_types` "{type} in {town}" when set, else today's titles), `backend/app/services/contact_service.py` (`lookup` records an `outreach_blocks` row with reason `no_unsolicited` when the read pages contain "no unsolicited", "do not accept unsolicited", "not accept unsolicited", "no recruitment agencies" or "no cold calls"), `backend/app/workers/lead_job.py` / `scheduler.py` (run prospecting right after the daily search when Auto mode and the switch are on), `backend/app/chains/manager.py` (`get_speculative_chain`)
- Test: `backend/tests/integration/test_prospecting.py`, `backend/tests/unit/test_chains/test_speculative_chain.py`

**Interfaces:**
- `outreach_repo.blocked(conn, profile_id) -> set[UUID]`, `outreach_repo.block(conn, profile_id, company_id, reason) -> None` (insert, ignore duplicates).
- `prospect_service.run_daily(conn, settings, profile_id, tools: ContactTools, chain: SpeculativeChain | None, now) -> dict[str, int]` returning `{"created": n, "skipped_no_email": n, "blocked": n}`:
  - candidates: the profile's saved employers (incl. those `discover` saved) in the chosen areas, not blocked, not already having any application (advert or speculative) for that company, oldest first;
  - stops when `prospects_per_day` speculative records were already created today (NZ day; count `applications.kind='speculative'` created today);
  - for each: `contact_service.lookup(..., force=False)`; skip if blocked by the lookup or no hiring/general email; otherwise create a job (`source='nearby'`, `external_id=str(company_id)`, title "Speculative application", company, location from the company address) and an application (`kind='speculative'`, `auto_approved_at=now`) with a resume record: the master CV rendered to PDF and Word in the chosen design (Task-6 subject is set at queue time) and a cover note from `SpeculativeChain.run(ai_resume_json(sections, contact), employer_facts)` passed through the existing number/skill/declined checks, or, without AI, a short standard note; then status `approved` (no tailoring graph);
  - a master CV without roles → create nothing and send one WhatsApp (dedupe key per day): "Add your work history in the Resume builder to start Google Maps outreach."
- `SpeculativeChain(llm).run(cv_json: str, employer: dict) -> str` (body only, 80–160 words, page/CV text treated as data).

- [ ] **Step 1: Failing tests:** `test_prospecting_creates_speculative_records_up_to_the_daily_cap` (Review Focus 2: two runs, cap 2 → 2 records), `test_an_employer_without_a_published_email_is_skipped` (Review Focus 1), `test_no_unsolicited_on_their_site_blocks_the_employer`, `test_an_employer_with_an_advert_application_is_never_prospected`, `test_a_cv_without_roles_starts_no_outreach_and_says_so` (Review Focus 4), `test_prospecting_needs_auto_mode_and_the_switch`, `test_speculative_note_never_contains_contact_details` (captured LLM input), `test_business_types_drive_the_maps_queries`.
- [ ] **Step 2–4:** Run (FAIL), implement, run + full suite + ruff (PASS).

---

### Task 6: Sending speculative emails

**Files:**
- Modify: `backend/app/services/outbox_service.py` (subject and stop line by kind; `MAX_FOLLOW_UPS` by kind: advert 2, speculative 1; short speculative follow-up body), `backend/app/services/auto_service.py` (`_queue_emails` queues speculative records with the suggested company address), `backend/app/repositories/outbox_repo.py` (due order: advert before speculative), `backend/app/workers/outbox_job.py` (a reply or bounce on a speculative record also calls `outreach_repo.block` with `replied`/`bounced`)
- Test: `backend/tests/integration/test_outbox_flow.py` (add), `backend/tests/unit/test_services/test_outbox_rules.py` (add)

**Interfaces:** Speculative subject "Enquiry about opportunities at {company} – {name}"; body = cover note + signature + blank line + the exact stop line; follow-up ends with the stop line too. Ask mode applies to speculative follow-ups like advert ones.

- [ ] **Step 1: Failing tests:** `test_speculative_email_has_the_subject_and_stop_line`, `test_speculative_gets_one_follow_up_then_closes`, `test_adverts_send_before_speculative_within_the_daily_limit`, `test_a_reply_to_a_speculative_email_blocks_the_employer` (Review Focus 3), `test_a_bounce_on_a_speculative_email_blocks_the_employer` (fake sender and mail reader only).
- [ ] **Step 2–4:** Run (FAIL), implement, run + full suite + ruff (PASS).

---

### Task 7: Evening summary

**Files:**
- Modify: `backend/app/services/notify_service.py` (`daily_summary(conn, profile_id, day) -> str | None`), `backend/app/workers/scheduler.py` (cron 18:00 Pacific/Auckland)
- Test: `backend/tests/integration/test_calls_flow.py` or a new `test_daily_summary.py`

**Interfaces:** `daily_summary` counts today's (NZ day) events: applications sent, follow-ups sent, replies, bounces, speculative emails sent, jobs left to apply for on a job site; returns None when all are zero; otherwise one message, e.g. "Today: 3 applications sent, 1 follow-up, 1 reply, 2 Google Maps employers emailed, 1 job to apply for on its site." Sent with dedupe key `daily-summary:{yyyy-mm-dd}`.

- [ ] **Step 1: Failing tests:** `test_summary_counts_todays_activity`, `test_no_summary_on_a_quiet_day`, `test_summary_is_sent_once_per_day`.
- [ ] **Step 2–4:** Run (FAIL), implement, run + full suite + ruff (PASS).

---

### Task 8: Outbox contacts list API

**Files:**
- Create: `backend/app/services/outbox_contacts.py`, `backend/app/schemas/outbox_contacts.py`
- Modify: `backend/app/api/outbox.py` (`GET /outbox/contacts`, `POST /applications/{application_id}/find-contacts`)
- Test: `backend/tests/integration/test_outbox_contacts.py`

**Interfaces:**
- `ContactRow(application_id, title, company, kind: "advert"|"speculative", status, hiring_emails: list[str], emails: list[str], advert_contact: AdvertContact | None, phone: str | None, phone_source: str | None, address_used: str | None, missing_reason: str | None, checked_at: datetime | None)`; `OutboxContacts(rows: list[ContactRow])` for this profile's applications in approved, sent, followed_up and replied.
- `missing_reason` is set only when no address is known, in this order: site-only advert → "Advert asks you to apply on the job site"; no website → "No website known"; never checked → "Website not checked yet"; last lookup note starts "Could not read" → "Could not read the website"; else "Checked {d Mon yyyy}: no email on the site".
- `POST /applications/{id}/find-contacts` forces `contact_service.lookup` for the job's company (404 for another profile) and returns the updated `ContactRow`.
- `SavedEmployer` (`backend/app/schemas/employer.py`) gains `outreach_status: Literal["emailed", "replied", "blocked"] | None` and `outreach_at: datetime | None`, filled in `employer_service.list_saved`: `blocked` when an `outreach_blocks` row exists (reason replied → `replied`), else `emailed` when a sent speculative application exists.

- [ ] **Step 1: Failing tests:** `test_contacts_list_shows_found_details_and_sources`, each missing reason (`test_missing_reason_*`, five tests), `test_find_contacts_forces_a_lookup`, `test_another_profiles_job_is_not_found`, `test_saved_employers_show_outreach_status`.
- [ ] **Step 2–4:** Run (FAIL), implement, run + full suite + ruff (PASS).

---

### Task 9: Screens

**Files:**
- Regenerate: `frontend/src/types/api.ts`
- Create: `frontend/src/components/OutboxContacts.tsx` (+ test)
- Modify: `frontend/src/pages/Outbox.tsx` (Contacts list section; "Speculative" label on speculative items), `frontend/src/pages/Settings.tsx` (Auto mode › "Google Maps employers": switch "Email Google Maps employers automatically", business types chips with the suggested list shown until saved, "New employers a day" 1–10), `frontend/src/pages/Employers.tsx` (saved card status "Emailed {date}", "Replied" or "Do not contact"), API modules and tests

**Interfaces:** Contacts list: one row per `ContactRow` with source labels, the address used, the missing reason in plain text, and **Find contacts** (accessible name includes the company). The switch shows "Turn on Auto mode first." when Auto mode is off.

- [ ] **Step 1: Failing tests:** `contacts list shows details and reasons`, `Find contacts posts and updates the row`, `speculative items are labelled`, `the Google Maps settings save`, `the switch needs Auto mode`, `saved employers show outreach status`.
- [ ] **Step 2–4:** Run (FAIL), implement, `npx vitest run` and `npm run build` (PASS).

---

### Task 10: Docs and live check

- [ ] Update `README.md` (hands-off flow; Google Maps outreach and its limits; contacts list; evening summary; what still needs the user: job-site-only adverts) and `docs/PROCESS_FLOW.md` (exact rules), matching the code.
- [ ] Live check on a temporary Postgres cluster with made-up data, fake Places, fake website reader and fake sender (no network, no AI, no real email): approve a job (lookup runs, address appears), run prospecting (cap respected, no-email employer skipped), process the outbox (advert then speculative; subject and stop line present), simulate a reply (employer blocked), produce the evening summary. Record results, then stop the cluster and delete its folder.
