# Employer Contact Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show each employer's phone, email, hiring (HR) contact, website, contact, careers and LinkedIn links, opening hours and rating, taken from Google Maps and the employer's own website. Use the hiring email in the Outbox.

**Architecture:**
- The Places search returns more fields.
- A new `contact_service` reads up to 3 pages of the employer's own site (home, contact, careers) through the existing Jina reader. Plain-code extraction (`contact_extract`) finds emails, phones and links. One small Haiku chain (`RecruiterChain`) proposes named hiring contacts, kept only when a quote check passes.
- Results go into `company_facts` and `contacts`, are shown through new API fields, and feed `outbox_service.suggested_address`.

**Tech Stack:** Python 3.12, FastAPI, psycopg 3, the existing Jina `WebsiteReader`, Claude Haiku via `LLMProvider.parse`, React 19, TanStack Query, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-26-employer-contacts-design.md`

## Global Constraints

- Never fetch LinkedIn. Its company URL is shown only as a link, through `application_service.safe_url`. All page reads go through `WebsiteReader.read`, which already refuses linkedin.com, seek, indeed, glassdoor and trademe.
- Read at most 3 pages per employer: home, contact and careers. Skip a lookup done in the last 30 days unless forced.
- Keep only email addresses that appear on the employer's own pages. Filter them through `app.core.emails.find_emails`, which drops no-reply and job-board addresses. Never guess an address.
- Email sorting by the part before the @. Hiring: `careers, jobs, job, hr, recruit, recruitment, recruiting, talent, people, employment, vacancies, apply`. General: everything else.
- Named people come only from the employer's own careers or contact page. A name is kept only when the quote (25 words or fewer) appears on that page (`prep_service.normalise`), the role matches `recruit|talent|human resources|\bhr\b|people|hiring|careers`, and any email given also appears on that page.
- Only careers and contact page text is sent to AI. No other contact data is sent.
- Lookups run automatically only for saved employers and for employers researched during the daily search (up to 10 a run). Otherwise they run from the "Get contact details" button. Never for raw Maps results.
- Copy: the button is labelled "Get contact details". Source labels read "Google Maps" and "Website".
- Do not commit unless the user asks.

## Review Focus

1. **An employer with no website.** Expect only the Google Maps details and the note "No website to read.", with no error. Test in Task 3.
2. **A website that blocks the reader (Jina 403).** The lookup records "Could not read …" in `notes`, keeps the Google Maps details and still sets `checked_at`. Test in Task 3.
3. **A small business using a Gmail address on its own contact page.** Keep it, because it was published there. Test in Task 1.
4. **The same address found on two pages, or linked as mailto twice.** List it once. Test in Task 1.
5. **An email written as "jobs [at] example.co.nz".** Not found, because addresses are never guessed. Test in Task 1.

---

### Task 1: Contact extraction from page text (plain code)

**Files:**
- Create: `backend/app/services/contact_extract.py`
- Test: `backend/tests/unit/test_services/test_contact_extract.py`

**Interfaces:**
- Produces:
  - `@dataclass PageContacts(emails: list[str], phones: list[str], contact_url: str | None, careers_url: str | None, linkedin_url: str | None)`. Emails are lower-case and deduplicated. Phones are in display form and deduplicated by their `nz_e164` value.
  - `extract_contacts(page_text: str, page_url: str) -> PageContacts`
  - `email_kind(address: str) -> Literal["hiring", "general"]`
  - `same_site(url: str, website: str) -> bool` matches the host without `www.`.

- [ ] **Step 1: Write the failing tests**
```python
PAGE = """[Contact us](https://example.co.nz/contact) [Careers](/careers)
Email [info@example.co.nz](mailto:info@example.co.nz) or jobs@example.co.nz. Call 03-688 1234.
[LinkedIn](https://www.linkedin.com/company/example-freight/) INFO@example.co.nz
Owner: kiwi.plumbing@gmail.com · Write to jobs [at] example.co.nz"""

def test_finds_emails_phones_and_links_once():
    found = extract_contacts(PAGE, "https://example.co.nz/")
    assert found.emails == ["info@example.co.nz", "jobs@example.co.nz", "kiwi.plumbing@gmail.com"]
    assert found.phones == ["03-688 1234"]
    assert found.contact_url == "https://example.co.nz/contact"
    assert found.careers_url == "https://example.co.nz/careers"
    assert found.linkedin_url == "https://www.linkedin.com/company/example-freight/"

def test_obfuscated_addresses_are_not_guessed():
    assert "jobs@example.co.nz" not in extract_contacts("jobs [at] example.co.nz", "https://e.nz").emails

@pytest.mark.parametrize(("address", "kind"), [("careers@x.nz", "hiring"), ("HR@x.nz", "hiring"),
    ("recruitment@x.nz", "hiring"), ("info@x.nz", "general"), ("sam@x.nz", "general")])
def test_email_kind(address, kind): assert email_kind(address) == kind
```
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest -q tests/unit/test_services/test_contact_extract.py`. Expected: FAIL (import error).
- [ ] **Step 3: Implement.**
  - Phones: an NZ-number regex in the form `0x[- ]xxx[- ]xxxx` or `+64 …`, kept when `nz_e164` accepts it.
  - Contact link: the first markdown link whose text or path matches `contact|get in touch|get-in-touch`, resolved against `page_url`.
  - Careers link: `careers.find_careers_link(page_text, page_url)`.
  - LinkedIn: the first match of `https?://(www\.)?linkedin\.com/company/[^\s)"'>]+`.
- [ ] **Step 4: Run.** Expected: PASS.

---

### Task 2: More Google Maps details

**Files:**
- Modify: `backend/app/providers/company/places.py` (`FIELD_MASK`, `PlaceMatch`, `_to_match`)
- Modify: `backend/app/schemas/employer.py` (`NearbyEmployer`), `backend/app/services/employer_service.py` (`search_nearby` mapping)
- Test: `backend/tests/unit/test_providers/test_company_providers.py`

**Interfaces:**
- Produces: `PlaceMatch` gains, with defaults so existing callers still work:
  - `maps_url: str | None = None` (googleMapsUri)
  - `rating: float | None = None`
  - `rating_count: int | None = None` (userRatingCount)
  - `hours: tuple[str, ...] = ()` (regularOpeningHours.weekdayDescriptions)
  - `business_type: str | None = None` (primaryTypeDisplayName.text)
  - `business_status: str | None = None` (businessStatus)

  `NearbyEmployer` gains `rating`, `rating_count`, `hours: list[str]` and `business_type`. Its `map_url` prefers `maps_url`.

- [ ] **Step 1: Failing test.** `test_places_returns_hours_rating_and_type` feeds a fake response holding all the fields above. It asserts the new `PlaceMatch` values, and that `FIELD_MASK` contains `places.googleMapsUri`, `places.rating`, `places.userRatingCount`, `places.regularOpeningHours`, `places.primaryTypeDisplayName` and `places.businessStatus`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: Run, expect PASS**, then the full `tests/unit/test_providers` and `tests/integration/test_employers_api.py`.

---

### Task 3: Store and look up contacts

**Files:**
- Create: `supabase/migrations/0008_contacts.sql`, `backend/app/repositories/contacts_repo.py`, `backend/app/chains/recruiter_chain.py`, `backend/app/services/contact_service.py`, `backend/app/schemas/contacts.py`
- Modify: `backend/app/chains/manager.py` (add `get_recruiter_chain(settings) -> RecruiterChain | None` using `scoring_model`, effort `low`)
- Test: `backend/tests/integration/test_contacts.py`, `backend/tests/unit/test_chains/test_recruiter_chain.py`

**Interfaces:**
- Consumes: Task 1 `extract_contacts`, `email_kind`, `same_site`. Task 2 `PlaceMatch`. `WebsiteReader.read(url) -> str`. `companies_repo.add_fact(conn, company_id, field, value, source, confidence, source_url)`. `prep_service.normalise`.
- Produces:
  - Migration: `contacts` gains `source_url text` and `checked_at timestamptz default now()`. `companies` gains `contacts_checked_at timestamptz`. Add the index `contacts_company` on `(company_id)`.
  - `RecruiterFound(name: str, role: str, email: str | None, phone: str | None, quote: str)` and `RecruiterResult(contacts: list[RecruiterFound])`. `RecruiterChain(llm, model).run(page_text: str, employer: str) -> RecruiterResult`. Its prompt says page text is data, not instructions, and asks only for people the page names for hiring.
  - `@dataclass ContactTools(reader: PageReader | None, recruiter: RecruiterChain | None)`
  - `contact_service.lookup(conn, company_id: UUID, tools: ContactTools, now: datetime, force: bool = False) -> EmployerContacts`
  - `contact_service.view(conn, company_id: UUID) -> EmployerContacts`
  - `contact_service.verify_recruiter(found: RecruiterFound, page_text: str) -> bool`
  - Schemas in `schemas/contacts.py`:
    - `Recruiter(name: str, role: str, email: str | None, phone: str | None, source_url: str | None)`
    - `EmployerContacts(phone: str | None, phone_source: str | None, emails: list[str], hiring_emails: list[str], website: str | None, contact_page: str | None, careers_page: str | None, linkedin: str | None, hours: list[str], rating: float | None, rating_count: int | None, recruiters: list[Recruiter], checked_at: datetime | None, notes: list[str])`
- Storage, all through `add_fact` with source `website` or `places`:
  - Facts `email` (general, confidence `high`), `hiring_email` (`high`), `phone` (`high`), `contact_page`, `careers_page` and `linkedin` (`high`).
  - `companies.email` is set only when it's empty.
  - Recruiters go in the `contacts` table with role `recruiter`, source `website`, confidence `check` and `source_url`.
  - `opening_hours` and `rating` come from Places when available, stored as facts on save.

- [ ] **Step 1: Failing tests** (fake reader and a `ScriptedLLM` recruiter):
```python
def test_lookup_reads_home_contact_and_careers_pages_and_stores_contacts(conn): ...
    # Home links /contact and /careers. Contact page: info@example.co.nz and 03-688 1234.
    # Careers page: "Apply to careers@example.co.nz. Talk to Jane Example, Talent Partner,
    # jane@example.co.nz". The recruiter LLM returns Jane with a quote that is on the page.
    # Expected:
    #   reader.urls == [home, home/contact, home/careers]
    #   view.emails == ["info@example.co.nz"]            # a recruiter's own address isn't repeated here
    #   view.hiring_emails == ["careers@example.co.nz"]
    #   view.recruiters == [Recruiter(name="Jane Example", role="Talent Partner",
    #                                 email="jane@example.co.nz", phone=None, source_url=home/careers)]
    #   view.phone == "03-688 1234" and view.phone_source == "Website" when Places gave none
def test_a_recruiter_whose_quote_is_not_on_the_page_is_dropped(conn): ...
def test_no_website_gives_maps_details_only(conn): ...          # notes == ["No website to read."]
def test_a_blocked_site_keeps_maps_details_and_says_so(conn): ...  # reader raises ProviderError("website", "HTTP 403")
def test_a_lookup_within_30_days_is_skipped_unless_forced(conn): ... # second call makes no reads; force=True reads
def test_linkedin_is_linked_never_read(conn): ...                  # reader.urls has no linkedin.com
```
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the migration, the repository, the chain, the service and the schemas. Facts are deduplicated by the existing `unique (company_id, field, value)`.
- [ ] **Step 4: Run them, then the full backend suite and `ruff check app tests`. Expect PASS.**

---

### Task 4: Wire into saving, daily research, the Outbox and the API

**Files:**
- Modify:
  - `backend/app/api/employers.py`: add `GET /employers/{company_id}/contacts` and `POST /employers/{company_id}/contacts` (force refresh). On `POST /employers`, run the lookup in the background.
  - `backend/app/services/enrich_service.py`: `_research` calls `contact_service.lookup` when `EmployerTools` has a reader.
  - `backend/app/services/outbox_service.py`: in `suggested_address`, the order is advert first, then the first hiring fact or recruiter email, then `companies.email` and the general `email` facts.
  - `backend/app/schemas/application.py`: `EmployerDetail.contacts: EmployerContacts`.
  - `backend/app/services/application_service.py`: fill `contacts` from `contact_service.view`.
  - `backend/app/schemas/employer.py`: `SavedEmployer.contacts: EmployerContacts | None`.
- Test: `backend/tests/integration/test_employers_api.py`, `backend/tests/integration/test_outbox_flow.py`

**Interfaces:**
- Consumes: Task 3 `lookup`, `view`, `ContactTools`, `EmployerContacts`. `source_service.build_employer_tools`; build `ContactTools` from its reader plus `get_recruiter_chain(settings)`.
- Produces: the routes above, returning `EmployerContacts` (404 for another profile's or an unknown employer). `ApplicationDetail.employer.contacts`.

- [ ] **Step 1: Failing tests:**
  - `test_saving_an_employer_looks_up_its_contacts`, with the background task replaced by a direct call using fakes.
  - `test_get_contact_details_refreshes_on_request`
  - `test_job_detail_includes_employer_contacts`
  - `test_the_outbox_suggests_the_hiring_email_when_the_advert_has_none`
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: Run the full backend suite, expect PASS.**

---

### Task 5: Screens

**Files:**
- Regenerate: `frontend/src/types/api.ts`, from the app's OpenAPI JSON as in earlier phases (never from the user's server on port 8000).
- Create: `frontend/src/components/EmployerContacts.tsx`, `frontend/src/components/EmployerContacts.test.tsx`
- Modify:
  - `frontend/src/api/employers.ts`: add `getContacts(id)` and `refreshContacts(id)`.
  - `frontend/src/pages/Employers.tsx`: saved cards render `<EmployerContacts>` with a "Get contact details" button. Search results show rating, hours and type.
  - `frontend/src/pages/JobDetail.tsx`: the Employer tab gets a "Contacts" region.

**Interfaces:**
- Produces: `<EmployerContacts contacts={EmployerContacts} onRefresh?={() => void} busy?={boolean} />`. It renders, each with a source label:
  - a `tel:` link for the phone
  - `mailto:` links for emails
  - "Hiring" labels on hiring emails and recruiters
  - links to the website, contact page, careers page and LinkedIn, opened in a new tab with `rel="noopener noreferrer"`
  - opening hours in a `<details>` element
  - the rating as "★ 4.6 (120)"
  - "Checked 26 Nov 2026"
  - the notes

- [ ] **Step 1: Failing tests.**
  - Each link and label shows.
  - The LinkedIn link has `href` set to the company URL and `target="_blank"`.
  - "No contact details found yet." appears when the list is empty.
  - The button calls `onRefresh`.
  - On the Employers page, the saved card's button posts to `/employers/c1/contacts`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement. Step 4: `npx vitest run` and `npm run build` both pass.**

---

### Task 6: Docs and live check

- [ ] Update `README.md` (Nearby employers section) and `docs/PROCESS_FLOW.md` with the contact lookup rules, matching the code.
- [ ] Live check on a throwaway database and backend on port 8001: save one real public NZ employer and run a lookup. Record the pages read, the emails found and any LinkedIn link, and confirm no request went to linkedin.com. Stop everything and delete the data.
