# Resume Builder and Skill Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A master CV you edit, in four ATS-safe designs (PDF and Word), with an ATS check, each job's requirements and skill coverage feeding the existing search → tailor → send → follow-up flow, your WhatsApp number in emails, and a manual follow-up option.

**Architecture:** The master CV lives in the base resume's `content` (extended `BaseSections` and `ContactDetails`, plus `template`). A shared layout module feeds a PDF renderer (fpdf2, bundled DejaVu Sans) and a Word renderer (python-docx). The existing scoring call also returns required and nice-to-have skills, which are checked against the ad text. Coverage is plain code over the master CV (or tailored) sections, with a synonym table and per-profile skill decisions.

**Tech Stack:** FastAPI, Pydantic v2, psycopg3, fpdf2, python-docx, pypdf (all already dependencies); React 19, TanStack Query, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-26-resume-builder-design.md` (research: `reports/ATS resume parsing and scoring NZ.md`; mockups: https://claude.ai/artifact/1PYGFyigCNBq9td3rnkmhE).

## Global Constraints

- Never open `Aayush_Modi_Resume.pdf`. Tests and live checks use made-up CV data only.
- Contact details (name, email, phone, location, LinkedIn, WhatsApp, work rights) are never sent to AI.
- Tailoring never changes titles, employers or dates, and never adds a skill the master CV does not show.
- A skill the user marked **Not me** is never claimed in a tailored resume or cover note.
- No pass mark and no single "ATS score". Coverage heading: "Skill coverage for this job". Coverage text: "How many of the ad's skills your CV shows, and where. Employers' systems differ, so this is a guide, not a prediction of an interview." Empty: "No skills found in this ad."
- Design ids and names: `classic` Classic, `modern` Modern, `compact` Compact, `executive` Executive. Default `classic`.
- Headings, in order: "Profile", "Key skills", "Work history", "Education and certifications", "Interests" (only when filled in), "Referees". Referees default: "Available on request."
- Files: A4, one column, no tables, text boxes, images, or page header/footer content; each file under 2,621,440 bytes (2.5 MB). File name `First-Last-CV.pdf` / `.docx` from the contact name.
- PDF uses the bundled DejaVu Sans for all designs. Word fonts: Classic Georgia; Modern Calibri; Compact Arial; Executive Cambria headings and Calibri body.
- Copy: menu item "Resume builder" (route `/builder`, after Shortlist); buttons "I have this", "Not me", "Undo", "Download PDF", "Download Word", "Show what ATS software reads" / "Hide what ATS software reads", "Send", "Skip"; follow-up options "Send follow-ups automatically" (default) and "Ask me before each follow-up"; Outbox section "Follow-ups waiting for you".
- The app never messages employers on WhatsApp.
- No new dependencies. Frontend types are generated from `create_app().openapi()` dumped to a file, never from port 8000. Don't use ports 8000/5173 or the user's database.
- Do not commit unless the user asks.

## Review Focus

1. **Macrons and en dashes** ("Tāmaki Makaurau", "Mar 2022 – Present") render in all four designs, PDF and Word, and survive in the ATS text. Test in Task 2.
2. **A role with no bullets or no dates** renders without error, and the ATS check names that role under the dates rule. Test in Task 3.
3. **An ad with no skills found** gives "0 of 0", the panel shows "No skills found in this ad.", and the Shortlist shows no chip. Tests in Tasks 5 and 9.
4. **I have this for "power bi" when Key skills already has "Power BI"** adds nothing twice. Test in Task 5.
5. **Repeated outbox runs in ask mode** create one draft per due follow-up, never more. Test in Task 7.

---

### Task 1: Master CV data and API

**Files:**
- Modify: `backend/app/schemas/tailoring.py` (`ContactDetails`: add `location` ≤80, `linkedin` ≤200, `whatsapp` ≤40, `work_rights` ≤120, all `str | None = None`; `BaseSections`: add `headline: str = ""`, `interests: str = ""`, `referees: str = "Available on request."`)
- Create: `backend/app/schemas/master_cv.py`, `backend/app/services/master_cv_service.py`, `backend/app/api/master_cv.py` (register in `app/main.py`)
- Modify: `backend/app/repositories/resumes_repo.py` (`save_master`), `backend/app/services/tailoring_service.py` (`assemble` copies `headline`, `interests`, `referees` from base)
- Test: `backend/tests/integration/test_master_cv.py`

**Interfaces:**
- Produces:
  - `TemplateId = Literal["classic", "modern", "compact", "executive"]`
  - `MasterCV(contact: ContactDetails, sections: BaseSections, template: TemplateId = "classic")` with limits: roles ≤15, bullets ≤12 per role, skills ≤60, education ≤20, any text ≤2000 chars.
  - `MasterCVView(MasterCV)` adds `source: Literal["resume", "ai", "empty"]` (cached sections, read now by AI, or an empty form).
  - `master_cv_service.load(conn, profile_id, sections_chain: ResumeSectionsChain | None) -> MasterCVView`
  - `master_cv_service.save(conn, profile_id, cv: MasterCV) -> MasterCVView`
  - `master_cv_service.add_skill(conn, profile_id, skill: str) -> bool` and `remove_skill(conn, profile_id, skill: str) -> bool` (casefold match; True when changed; both also update the resume profile)
  - `resumes_repo.save_master(conn, resume_id, sections: dict, contact: dict, template: str) -> None`
  - Routes `GET /master-cv` → `MasterCVView`, `PUT /master-cv` (body `MasterCV`) → `MasterCVView`. No base resume → 400 "Upload your resume first, then build on it here."
- Consumes: `resumes_repo.latest_base`; the `ResumeSectionsChain` built by `chains.manager.get_tailoring_chains(settings)`; the base resume text the resume graph reads (see `resume_build_service.load_context`).

- [ ] **Step 1: Failing tests** (`ScriptedLLM` from `tests/fakes.py` for the sections chain):
```python
def test_master_cv_reads_cached_sections_and_contact(conn): ...      # source == "resume"
def test_old_cached_sections_load_with_new_defaults(conn): ...      # referees == "Available on request.", headline == ""
def test_master_cv_without_sections_or_ai_is_an_empty_form(conn): ...  # source == "empty"; contact kept
def test_sections_are_read_by_ai_once_and_contact_is_not_sent(conn): ...  # source == "ai"; email/phone not in llm.calls[0]["user"]; second load makes no call
def test_saving_keeps_titles_dates_and_bullets_exactly(conn): ...   # round trip incl. "Mar 2022 – Present", "Tāmaki Makaurau"
def test_saving_adds_new_skills_and_headline_to_the_resume_profile(conn): ...  # "dbt" added; existing skills kept; nothing removed
def test_add_skill_ignores_case_and_remove_skill_reverses_it(conn): ...  # add "power bi" when "Power BI" exists -> False
def test_master_cv_needs_a_resume(client): ...                      # 400 with the exact message
```
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** The resume profile update only adds: skills not already in `skills` or `tools` (casefold) as `SkillEntry(name)`, and a non-empty headline to `titles`.
- [ ] **Step 4: Run these tests, then the full backend suite and `ruff check app tests`. Expect PASS.**

---

### Task 2: Four designs as PDF and Word

**Files:**
- Create: `backend/app/core/resume_layout.py`, `backend/app/core/resume_docx.py`
- Modify: `backend/app/core/resume_pdf.py` (`render_resume_pdf` gains `template: TemplateId = "classic"`; looks table), `backend/app/api/master_cv.py` (`GET /master-cv/file?format=pdf|docx`)
- Test: `backend/tests/unit/test_resume_layout.py`, `backend/tests/unit/test_resume_files.py`, add to `test_master_cv.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Block(kind: Literal["name","headline","contact","rights","heading","text","role","entry","bullet"], text: str, right: str = "", sub: str = "")`
  - `layout_blocks(contact: ContactDetails, resume: BaseSections) -> list[Block]` (spec order and headings; `role.text` = title, `right` = dates, `sub` = "employer, location"; Interests only when non-empty)
  - `contact_line(contact) -> str`: city · phone · email · LinkedIn, then "WhatsApp {n}" only when its digits differ from the phone's
  - `cv_file_name(contact, ext) -> str` → "Alex-Morgan-CV.pdf" ("CV.pdf" when no name)
  - `render_resume_docx(contact, resume, path, template: TemplateId = "classic") -> None`
  - Looks (PDF): classic black accent, centred uppercase name, uppercase headings with a rule; modern `#0F5C5C`, left name, uppercase accent headings with rule; compact `#1F3A5F`, smaller type, skills joined " · "; executive `#1F3A5F`, sentence-case headings, rule under the contact block.
- Consumes: Task 1 schemas.

- [ ] **Step 1: Failing tests:**
```python
def test_blocks_follow_the_nz_order_with_exact_headings(): ...
def test_interests_heading_only_when_filled(): ...
def test_whatsapp_shown_only_when_it_differs_from_the_phone(): ...   # "021 000 0000" vs "+64 21 000 0000" -> same
@pytest.mark.parametrize("template", ["classic", "modern", "compact", "executive"])
def test_pdf_text_has_name_first_and_headings_in_order(template, tmp_path): ...  # pypdf; "Tāmaki Makaurau" and "–" survive
@pytest.mark.parametrize("template", [...])
def test_docx_has_no_tables_headers_or_images_and_uses_the_design_font(template, tmp_path): ...  # doc.tables == []; section header/footer empty; inline_shapes empty; Classic run font "Georgia"
def test_files_stay_under_2_5_mb(tmp_path): ...
def test_download_route_names_the_file_from_the_contact(client): ...  # Content-Disposition "Alex-Morgan-CV.docx"
```
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement** (both renderers iterate `layout_blocks`; dates right-aligned with a right tab stop in Word and a right-aligned cell in fpdf2; nothing in `header()`/`footer()`). **Step 4: Run, then the full suite and ruff. Expect PASS.**

---

### Task 3: ATS check and plain-text preview

**Files:**
- Create: `backend/app/services/ats_check.py`
- Modify: `backend/app/schemas/master_cv.py` (`AtsItem`, `AtsReport`; `MasterCVView.ats: AtsReport | None = None`), `backend/app/services/master_cv_service.py` (`load`/`save` render both files to `upload_dir/previews/` and attach the report)
- Test: `backend/tests/unit/test_ats_check.py`

**Interfaces:**
- Produces: `AtsItem(label: str, ok: bool, detail: str = "")`; `AtsReport(items: list[AtsItem], text: str, pages: int, pdf_bytes: int, docx_bytes: int)`; `ats_check.check(cv: MasterCV, pdf_path: Path, docx_path: Path) -> AtsReport`.
- Items, in this order, with these labels:
  1. "One column, no tables, text boxes or images" (always ok, detail "Every design is built this way.")
  2. "Name and contact details at the top of the page body" (first non-empty line of the PDF text is the name, and email or phone is set)
  3. "Standard section names in the NZ order" (every heading present in the text, in order)
  4. "Dates as month and year" (each `role.dates` matches `^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4} [–-] (Present|(Jan|…|Dec)[a-z]* \d{4})$`; detail names the failing role titles)
  5. "2 pages or fewer"
  6. "Profile of 50 to 150 words" (detail "{n} words")
  7. "No photo, date of birth, gender, marital status, nationality or religion" (case-insensitive scan of the text for `date of birth|\bdob\b|marital status|nationality|gender|religion`)
  8. "Work rights stated"
  9. "Files under 2.5 MB" (detail "PDF {kb} KB, Word {kb} KB")
- `text` = pypdf text of all pages joined by "\n".

- [ ] **Step 1: Failing tests:** `test_a_clean_cv_passes_every_item`, `test_year_only_and_missing_dates_name_the_role` (Review Focus 2: a role with `dates=""` and no bullets still renders), `test_personal_details_are_flagged`, `test_a_three_page_cv_is_flagged`, `test_profile_word_count_is_reported`, `test_missing_work_rights_is_flagged`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: Run, then the full suite and ruff. Expect PASS.**

---

### Task 4: Requirements from the ad

**Files:**
- Create: `supabase/migrations/0009_resume_builder.sql`
- Modify: `backend/app/schemas/job.py` (`ScoreResult`: `required_skills`, `preferred_skills: list[str] = []`, `requirements_split: bool = False`), `backend/app/chains/score_chain.py`, `backend/app/repositories/applications_repo.py` (insert/upsert writes the three columns)
- Test: `backend/tests/unit/test_chains/test_score_chain.py` (add), `backend/tests/integration/test_lead_graph.py` (add)

**Interfaces:**
- Migration: `applications` add `required_skills text[] not null default '{}'`, `preferred_skills text[] not null default '{}'`, `requirements_split boolean not null default false`; `create table if not exists skill_decisions (profile_id uuid not null references profiles (id) on delete cascade, skill_key text not null, skill text not null, decision text not null check (decision in ('have','no')), decided_at timestamptz not null default now(), primary key (profile_id, skill_key))`; outbox status check becomes `('queued','sent','failed','cancelled','draft')`.
- `JobScoreExtraction` gains `required_skills` and `preferred_skills` (prompt rules: required = skills or qualifications the ad calls required or essential; preferred = ones it calls preferred, desirable, nice to have or a bonus; the ad's wording; at most 12 each).
- `LLMScoreChain` keeps only skills where `contains_term(job.search_text(), skill)`, dedupes by casefold, drops from preferred any also in required, and sets `requirements_split=True`. `KeywordScoreChain` sets `required_skills = matched + missing`, `preferred_skills = []`, `requirements_split=False`.

- [ ] **Step 1: Failing tests:** `test_ai_requirements_not_in_the_ad_are_dropped` ("Kubernetes" absent from the ad is removed), `test_a_skill_in_both_lists_stays_required`, `test_keyword_scoring_lists_found_skills_as_one_group`, `test_lead_graph_stores_requirements_on_the_application`, `test_migration_0009_applies_on_an_existing_database`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: Run, then the full suite and ruff. Expect PASS.**

---

### Task 5: Skill coverage and decisions

**Files:**
- Create: `backend/app/core/skill_synonyms.py`, `backend/app/schemas/coverage.py`, `backend/app/services/coverage_service.py`, `backend/app/repositories/skills_repo.py`, `backend/app/api/coverage.py` (register)
- Modify: `backend/app/schemas/application.py` (`ShortlistItem`: `required_covered: int`, `required_total: int`, `requirements_split: bool`), `backend/app/services/application_service.py` (`shortlist_items` fills them)
- Test: `backend/tests/unit/test_services/test_coverage.py`, `backend/tests/integration/test_coverage_api.py`

**Interfaces:**
- `SYNONYMS: dict[str, tuple[str, ...]]` seed: AWS↔Amazon Web Services; GCP↔Google Cloud; JavaScript↔JS; TypeScript↔TS; PostgreSQL↔Postgres; SQL Server↔MS SQL; Power BI↔PowerBI; Excel↔Microsoft Excel, MS Excel; Kubernetes↔K8s; Machine learning↔ML; CI/CD↔continuous integration; .NET↔dotnet; Node.js↔NodeJS; React↔React.js. `variants(skill: str) -> list[str]` (the skill first, then its synonyms, both directions, casefold lookup).
- `SkillCoverage(name: str, status: Literal["shown","added","missing","declined"], evidence: str, matched_as: str | None)`; `Coverage(required: list[SkillCoverage], preferred: list[SkillCoverage], split: bool, required_text: str, preferred_text: str)`.
- `coverage_service.coverage(sections: BaseSections, required: list[str], preferred: list[str], split: bool, decisions: dict[str, str]) -> Coverage`. Search order and evidence text: a role's title or bullets → "Shown in: {title}, {dates}"; headline or summary → "Shown in: Profile"; skills list → "Shown in: Key skills", or status `added` and "Added by you to Key skills" when the decision is `have`; education → "Shown in: Education". Not found: decision `no` → `declined`, "You said you don't have this."; else `missing`, "Not in your CV yet". `matched_as` is the variant when it isn't the skill itself. Covered = shown + added; text "{covered} of {total}".
- `skills_repo.decisions(conn, profile_id) -> dict[str, str]`, `set_decision(conn, profile_id, skill, decision | None)` (key = `skill.strip().casefold()`; None deletes).
- `coverage_service.decide(conn, profile_id, skill, decision: Literal["have","no"] | None) -> None`: `have` → set + `master_cv_service.add_skill`; `no` → set; None → if the previous decision was `have`, `remove_skill`; then delete.
- `coverage_service.for_application(conn, profile_id, application_id) -> Coverage` (master CV sections; 404 for another profile's application).
- Routes: `GET /applications/{application_id}/coverage` → `Coverage`; `POST /skills/decision` body `{skill: str (1–80 chars), decision: "have" | "no" | null}` → `{"ok": true}`.

- [ ] **Step 1: Failing tests:** `test_role_evidence_wins_over_key_skills`, `test_a_synonym_in_a_bullet_covers_the_skill_and_says_so` ("Amazon Web Services" covers AWS, `matched_as == "Amazon Web Services"`), `test_have_counts_as_added_and_no_as_declined`, `test_counts_text`, `test_no_requirements_gives_0_of_0` (Review Focus 3), `test_have_adds_to_the_master_cv_and_profile_once` (Review Focus 4), `test_undo_have_removes_the_skill_again`, `test_another_profiles_coverage_is_not_found`, `test_shortlist_items_carry_required_counts`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: Run, then the full suite and ruff. Expect PASS.**

---

### Task 6: Tailored resumes use the design, Word file and decisions

**Files:**
- Modify: `backend/app/graphs/resume/nodes/render_pdf.py` (pass the master CV `template`; also write `<same stem>.docx`), `backend/app/services/resume_build_service.py` (content stores `template`), `backend/app/services/tailoring_service.py` (`check_facts` gains `declined: list[str] = ()`), `backend/app/graphs/resume/nodes/check_facts.py` (passes the profile's `no` skills), `backend/app/schemas/tailoring.py` (`TailoredResumeView`: `coverage: Coverage | None`, `docx_url: str | None`), `backend/app/services/resume_review_service.py`, `backend/app/api/resumes.py` (`GET /resumes/{resume_id}/docx`)
- Test: `backend/tests/integration/test_tailoring_flow.py` (add), `backend/tests/unit/test_services/test_tailoring_service.py` (add)

**Interfaces:**
- Declined rule: a tailored bullet or summary that mentions a declined skill (any variant) not present in the base text goes back to the original wording; a cover-note sentence that mentions one is removed; note "Removed a mention of {skill}, which you said you don't have."
- `TailoredResumeView.coverage` = `coverage(tailored sections, application requirements, decisions)`; `docx_url` = `/resumes/{id}/docx` when the file exists.

- [ ] **Step 1: Failing tests:** `test_tailored_files_use_the_chosen_design` (content `template == "modern"`; the `.docx` exists), `test_docx_route_serves_the_word_file_for_this_profile_only`, `test_a_declined_skill_is_removed_from_the_cover_note_and_bullets`, `test_review_view_includes_coverage_of_the_tailored_version`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: Run, then the full suite and ruff. Expect PASS.**

---

### Task 7: WhatsApp number in emails and follow-ups you approve

**Files:**
- Modify: `backend/app/services/outbox_service.py` (`signature(contact: ContactDetails) -> str` used by application and follow-up bodies; `view` adds `drafts`; `send_draft`), `backend/app/workers/outbox_job.py` (follow-up step), `backend/app/repositories/outbox_repo.py`, `backend/app/schemas/outbox.py` (`OutboxView.drafts: list[OutboxItem]`; `FollowUpSettings(mode: Literal["auto","ask"] = "auto")`), `backend/app/api/outbox.py` (`GET/PUT /settings/follow-ups`, `POST /outbox/{outbox_id}/send`)
- Test: `backend/tests/unit/test_services/test_signature.py`, `backend/tests/integration/test_outbox_flow.py` (add)

**Interfaces:**
- `signature`: "Ngā mihi,\n{name}" then "Phone and WhatsApp: {phone}" when both are set with the same digits; otherwise "Phone: {phone}" and/or "WhatsApp: {whatsapp}" lines; just "Ngā mihi" when nothing is set.
- Follow-up mode is stored at `settings.ai -> 'follow_ups' -> 'mode'` (merge like `auto_service.save_settings`). In `ask` mode the follow-up step writes the follow-up outbox row with status `draft` instead of `queued`, at most one per application while a draft or queued follow-up exists; `process_outbox` never sends drafts. `POST /outbox/{id}/send` turns this profile's draft into `queued` now (404 otherwise). The existing cancel turns a draft into `cancelled` and stops follow-ups. Closing after two follow-ups is unchanged.

- [ ] **Step 1: Failing tests:** `test_signature_combines_phone_and_whatsapp_when_the_same`, `test_signature_lists_both_when_they_differ`, `test_ask_mode_creates_one_draft_and_sends_nothing` (two `process_outbox` runs, Review Focus 5), `test_send_queues_the_draft_and_the_next_run_sends_it` (fake sender; never real email), `test_skip_cancels_the_draft_and_stops_follow_ups`, `test_auto_mode_is_unchanged`, `test_follow_up_settings_round_trip`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: Run, then the full suite and ruff. Expect PASS.**

---

### Task 8: Resume builder page

**Files:**
- Regenerate: `frontend/src/types/api.ts` from `create_app().openapi()` dumped to a scratch file (`npx openapi-typescript <file> -o src/types/api.ts`)
- Create: `frontend/src/api/masterCv.ts`, `frontend/src/hooks/useMasterCv.ts`, `frontend/src/pages/ResumeBuilder.tsx`, `frontend/src/components/builder/DesignPicker.tsx`, `SectionsEditor.tsx`, `CvPreview.tsx`, `AtsCheckPanel.tsx`, and `frontend/src/pages/ResumeBuilder.test.tsx`
- Modify: `frontend/src/App.tsx` (route `builder`), `frontend/src/components/Layout.tsx` (menu item after Shortlist)

**Interfaces:**
- `getMasterCv()`, `saveMasterCv(cv)`, `masterCvFileUrl(format: "pdf" | "docx")`.
- The editor edits every master CV field: contact incl. city, LinkedIn, WhatsApp and work rights; headline; profile with a live word count; key skills with the existing `ChipEditor`; roles (add, remove, move up and down; bullets the same); education; interests; referees. **Save CV** sends the whole `MasterCV`. `CvPreview` renders the chosen design's order and headings in HTML. `AtsCheckPanel` lists the report items with a tick or a warning and the parse-text toggle. When `source == "empty"`: "We couldn't read sections from your resume. Fill them in here."

- [ ] **Step 1: Failing tests:** `shows the sections from the API`, `choosing a design and saving sends the template`, `an edited role date is saved exactly as typed`, `ATS items and the parse preview toggle show`, `the empty form message shows when nothing was read`, `the menu has Resume builder after Shortlist`, `download links point at the PDF and Word files`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: `npx vitest run` and `npm run build` pass.**

---

### Task 9: Coverage panel, Shortlist chip, follow-up switch and drafts

**Files:**
- Create: `frontend/src/components/CoveragePanel.tsx`, `CoveragePanel.test.tsx`
- Modify: `frontend/src/pages/TailoredResume.tsx` (panel, **Download Word**), `Shortlist.tsx` (chip), `Settings.tsx` (Auto mode tab, "Follow-ups" section), `Outbox.tsx` ("Follow-ups waiting for you" with **Send** and **Skip**), their API modules and tests

**Interfaces:**
- `<CoveragePanel coverage={Coverage} onDecide={(skill, decision: "have" | "no" | null) => void} busy?={boolean} />`: groups "Required in the ad" and "Nice to have" when `split`, else one group "Skills the ad mentions"; each count shown; spec copy; "No skills found in this ad." when both lists are empty; rows show name, evidence and `matched_as`; buttons per status (missing: I have this / Not me; added or declined: Undo).
- After a decision: invalidate the tailored resume view, the shortlist and the master CV queries.
- Chip: "Skills: {covered} of {total} required" (or "… in the ad" when not split); hidden when total is 0.

- [ ] **Step 1: Failing tests:** `groups and counts follow split`, `the empty message shows with no skills` (Review Focus 3), `I have this posts have and Undo posts null`, `the tailored page offers Download Word`, `the shortlist chip shows and hides`, `the follow-up switch saves ask`, `a draft follow-up can be sent or skipped`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: `npx vitest run` and `npm run build` pass.**

---

### Task 10: Docs and live check

- [ ] Update `README.md` ("Resume builder" and "Skill coverage" sections; follow-up mode under the Outbox section; WhatsApp number in emails) and `docs/PROCESS_FLOW.md` (master CV, designs, ATS check, requirements, coverage, decisions, follow-up drafts), matching the code.
- [ ] Live check on a temporary Postgres cluster (as `backend/tests/conftest.py` makes one) with a made-up CV, no network and no AI: save a master CV, render all four designs as PDF and Word, run the ATS check, decide one skill, and confirm the text order and file sizes. Record the results in the report, then stop the cluster and delete its folder.
