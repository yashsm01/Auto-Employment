from datetime import timedelta

import psycopg
import pytest

from app.chains.recruiter_chain import RecruiterChain, RecruiterFound, RecruiterResult
from app.core.errors import ProviderError
from app.db.client import connect
from app.repositories import companies_repo
from app.schemas.contacts import Recruiter
from app.services import contact_service
from app.services.contact_service import ContactTools, verify_recruiter
from tests.factories import NOW
from tests.fakes import ScriptedLLM

pytestmark = pytest.mark.postgres

HOME = "https://example.co.nz"
CONTACT = "https://example.co.nz/contact"
CAREERS = "https://example.co.nz/careers"
HOME_TEXT = "Welcome to Example Ltd. [Contact us](/contact) [Careers](/careers)"
CONTACT_TEXT = "Contact us. Email info@example.co.nz or call 03-688 1234."
CAREERS_TEXT = (
    "Apply to careers@example.co.nz. Talk to Jane Example, Talent Partner, jane@example.co.nz"
)
JANE_QUOTE = "Talk to Jane Example, Talent Partner, jane@example.co.nz"


class FakeReader:
    def __init__(self, pages=None, errors=None) -> None:
        self.pages = pages or {}
        self.errors = errors or {}
        self.urls: list[str] = []

    def read(self, url):
        self.urls.append(url)
        if url in self.errors:
            raise self.errors[url]
        if url not in self.pages:
            raise ProviderError("website", "HTTP 404")
        return self.pages[url]


def _pages() -> dict[str, str]:
    return {HOME: HOME_TEXT, CONTACT: CONTACT_TEXT, CAREERS: CAREERS_TEXT}


def _jane(quote: str = JANE_QUOTE, phone: str | None = None) -> RecruiterResult:
    return RecruiterResult(contacts=[RecruiterFound(
        name="Jane Example", role="Talent Partner", email="jane@example.co.nz",
        phone=phone, quote=quote,
    )])


def _company(conn, website: str | None = HOME) -> str:
    row = conn.execute(
        "insert into companies (name, website) values ('Example Ltd', %s) returning id",
        (website,),
    ).fetchone()
    return row["id"]


def _tools(reader, llm=None) -> ContactTools:
    return ContactTools(reader=reader, recruiter=RecruiterChain(llm) if llm else None)


def test_lookup_reads_home_contact_and_careers_pages_and_stores_contacts(conn):
    company_id = _company(conn)
    reader = FakeReader(_pages())
    llm = ScriptedLLM(RecruiterResult(), _jane())

    result = contact_service.lookup(conn, company_id, _tools(reader, llm), NOW)

    assert reader.urls == [HOME, CONTACT, CAREERS]
    assert result.notes == []
    assert "Welcome" not in llm.calls[0]["user"]
    view = contact_service.view(conn, company_id)
    assert view.emails == ["info@example.co.nz"]
    assert view.hiring_emails == ["careers@example.co.nz"]
    assert view.recruiters == [Recruiter(
        name="Jane Example", role="Talent Partner", email="jane@example.co.nz",
        phone=None, source_url=CAREERS,
    )]
    assert view.phone == "03-688 1234"
    assert view.phone_source == "Website"
    assert view.contact_page == CONTACT
    assert view.careers_page == CAREERS
    assert view.checked_at == NOW
    assert view.notes == []


def test_a_recruiter_whose_quote_is_not_on_the_page_is_dropped(conn):
    company_id = _company(conn)
    reader = FakeReader(_pages())
    llm = ScriptedLLM(RecruiterResult(), _jane(quote="Jane leads our graduate programme"))

    contact_service.lookup(conn, company_id, _tools(reader, llm), NOW)

    assert contact_service.view(conn, company_id).recruiters == []


def test_a_recruiter_phone_must_be_on_the_page(conn):
    company_id = _company(conn)
    reader = FakeReader(_pages())
    llm = ScriptedLLM(RecruiterResult(), _jane(phone="09 555 1234"))

    contact_service.lookup(conn, company_id, _tools(reader, llm), NOW)

    assert contact_service.view(conn, company_id).recruiters[0].phone is None


def test_no_website_gives_maps_details_only(conn):
    company_id = _company(conn, website=None)
    companies_repo.add_fact(conn, company_id, "phone", "09 000 0000", "places", "high")
    reader = FakeReader()

    result = contact_service.lookup(conn, company_id, _tools(reader), NOW)

    assert reader.urls == []
    assert result.notes == ["No website to read."]
    view = contact_service.view(conn, company_id)
    assert view.phone == "09 000 0000"
    assert view.phone_source == "Google Maps"
    assert view.checked_at == NOW


def test_a_blocked_site_keeps_maps_details_and_says_so(conn):
    company_id = _company(conn)
    companies_repo.add_fact(conn, company_id, "phone", "09 000 0000", "places", "high")
    reader = FakeReader(errors={HOME: ProviderError("website", "HTTP 403")})

    result = contact_service.lookup(conn, company_id, _tools(reader), NOW)

    assert len(result.notes) == 1
    assert result.notes[0].startswith("Could not read")
    view = contact_service.view(conn, company_id)
    assert view.phone == "09 000 0000"
    assert view.checked_at == NOW


def test_without_a_reader_nothing_is_checked(conn):
    company_id = _company(conn)

    result = contact_service.lookup(conn, company_id, ContactTools(None, None), NOW)

    assert result.notes == ["Website reading is not set up."]
    assert contact_service.view(conn, company_id).checked_at is None


def test_a_lookup_within_30_days_is_skipped_unless_forced(conn):
    company_id = _company(conn)
    reader = FakeReader(_pages())
    llm = ScriptedLLM(RecruiterResult(), _jane(), RecruiterResult(), _jane())
    tools = _tools(reader, llm)
    contact_service.lookup(conn, company_id, tools, NOW)
    assert len(reader.urls) == 3

    later = NOW + timedelta(days=1)
    skipped = contact_service.lookup(conn, company_id, tools, later)
    assert len(reader.urls) == 3
    assert skipped.notes == []

    contact_service.lookup(conn, company_id, tools, later, force=True)
    assert len(reader.urls) == 6
    view = contact_service.view(conn, company_id)
    assert len(view.recruiters) == 1
    assert view.checked_at == later


def test_linkedin_is_linked_never_read(conn):
    company_id = _company(conn)
    home = (
        HOME_TEXT
        + " [LinkedIn](https://www.linkedin.com/company/example-ltd)"
        + " [Jobs](https://linkedin.com/company/x/jobs)"
    )
    reader = FakeReader({HOME: home, CONTACT: CONTACT_TEXT, CAREERS: CAREERS_TEXT})

    contact_service.lookup(conn, company_id, _tools(reader), NOW)

    assert all("linkedin.com" not in url for url in reader.urls)
    view = contact_service.view(conn, company_id)
    assert view.linkedin == "https://www.linkedin.com/company/example-ltd"
    stored = conn.execute("select linkedin_url from companies where id = %s", (company_id,))
    assert stored.fetchone()["linkedin_url"] == "https://www.linkedin.com/company/example-ltd"


def test_a_linkedin_website_is_not_read(conn):
    company_id = _company(conn, website="https://www.linkedin.com/company/example-ltd")
    reader = FakeReader(_pages())

    result = contact_service.lookup(conn, company_id, _tools(reader), NOW)

    assert reader.urls == []
    assert result.notes[0].startswith("Could not read")


def test_view_reads_opening_hours_and_rating_facts(conn):
    company_id = _company(conn)
    companies_repo.add_fact(conn, company_id, "opening_hours", "Mon 9-5; Tue 9-5", "places", "high")
    companies_repo.add_fact(conn, company_id, "rating", "4.6 (120)", "places", "high")

    view = contact_service.view(conn, company_id)

    assert view.hours == ["Mon 9-5", "Tue 9-5"]
    assert view.rating == 4.6
    assert view.rating_count == 120


def test_view_leaves_a_malformed_rating_empty(conn):
    company_id = _company(conn)
    companies_repo.add_fact(conn, company_id, "rating", "great", "places", "high")

    view = contact_service.view(conn, company_id)

    assert view.rating is None
    assert view.rating_count is None


def _found(**overrides) -> RecruiterFound:
    values = {
        "name": "Jane Example", "role": "Talent Partner", "email": "jane@example.co.nz",
        "phone": None, "quote": "Talk to Jane Example, Talent Partner",
    }
    values.update(overrides)
    return RecruiterFound(**values)


def test_verify_recruiter_accepts_a_quote_and_name_on_the_page():
    assert verify_recruiter(_found(), CAREERS_TEXT)


@pytest.mark.parametrize("overrides", [
    {"name": "Sam Other"},
    {"quote": "Jane Example runs our graduate programme"},
    {"quote": " ".join(["word"] * 26)},
    {"role": "Chef"},
    {"email": "sam@example.co.nz"},
    {"name": "  "},
])
def test_verify_recruiter_rejects_anything_not_on_the_page(overrides):
    assert not verify_recruiter(_found(**overrides), CAREERS_TEXT)


def test_a_failed_recruiter_check_adds_a_note_and_the_lookup_continues(conn):
    company_id = _company(conn)
    reader = FakeReader(_pages())
    llm = ScriptedLLM(ProviderError("claude", "timed out"), _jane())

    result = contact_service.lookup(conn, company_id, _tools(reader, llm), NOW)

    assert result.notes == ["Could not check for a hiring contact."]
    assert reader.urls == [HOME, CONTACT, CAREERS]
    view = contact_service.view(conn, company_id)
    assert [person.name for person in view.recruiters] == ["Jane Example"]
    assert view.checked_at == NOW


PLAIN_CAREERS = "Apply to careers@example.co.nz."


def test_a_forced_lookup_drops_the_website_details_the_site_no_longer_shows(conn):
    company_id = _company(conn)
    reader = FakeReader(_pages())
    contact_service.lookup(conn, company_id, _tools(reader), NOW)
    reader.pages[CONTACT] = "Contact us. Email hello@example.co.nz or call 03-688 5678."
    reader.pages[CAREERS] = PLAIN_CAREERS.replace("careers@", "jobs@")

    contact_service.lookup(conn, company_id, _tools(reader), NOW + timedelta(days=1), force=True)

    view = contact_service.view(conn, company_id)
    assert view.emails == ["hello@example.co.nz"]
    assert view.hiring_emails == ["jobs@example.co.nz"]
    assert view.phone == "03-688 5678"


def test_a_lookup_that_cannot_read_the_contact_page_keeps_the_known_details(conn):
    company_id = _company(conn)
    reader = FakeReader(_pages())
    reader.pages[CAREERS] = PLAIN_CAREERS
    contact_service.lookup(conn, company_id, _tools(reader), NOW)
    reader.errors[CONTACT] = ProviderError("website", "HTTP 403")

    result = contact_service.lookup(conn, company_id, _tools(reader), NOW + timedelta(days=1),
                                    force=True)

    assert result.notes == ["Could not read the contact page (HTTP 403)."]
    view = contact_service.view(conn, company_id)
    assert view.emails == ["info@example.co.nz"]
    assert view.phone == "03-688 1234"


def test_a_lookup_never_deletes_facts_from_other_sources(conn):
    company_id = _company(conn)
    companies_repo.add_fact(conn, company_id, "email", "sales@example.co.nz", "tavily",
                            "medium", "https://news.example")
    contact_service.lookup(conn, company_id, _tools(FakeReader(_pages())), NOW)

    contact_service.lookup(conn, company_id, _tools(FakeReader(_pages())), NOW, force=True)

    facts = companies_repo.list_facts(conn, company_id)
    assert ("sales@example.co.nz", "tavily") in {
        (fact["value"], fact["source"]) for fact in facts if fact["field"] == "email"
    }


def test_addresses_show_newest_first_and_in_page_order_within_a_lookup(conn):
    company_id = _company(conn)
    reader = FakeReader(_pages())
    reader.pages[CONTACT] = "Email sales@example.co.nz or info@example.co.nz."
    reader.pages[CAREERS] = PLAIN_CAREERS
    contact_service.lookup(conn, company_id, _tools(reader), NOW)
    assert contact_service.view(conn, company_id).emails == [
        "sales@example.co.nz", "info@example.co.nz",
    ]

    # The contact page fails, so this lookup only adds: the home page address is newest.
    reader.pages[HOME] = HOME_TEXT + " Write to new@example.co.nz."
    reader.errors[CONTACT] = ProviderError("website", "HTTP 503")
    contact_service.lookup(conn, company_id, _tools(reader), NOW + timedelta(days=1), force=True)

    assert contact_service.view(conn, company_id).emails == [
        "new@example.co.nz", "sales@example.co.nz", "info@example.co.nz",
    ]


def test_a_one_page_site_with_anchor_links_is_read_once_and_never_sent_to_ai(conn):
    company_id = _company(conn)
    home = "Welcome. [Contact](#contact) [Careers](#careers) Email info@example.co.nz"
    reader = FakeReader({HOME: home})
    llm = ScriptedLLM()

    result = contact_service.lookup(conn, company_id, _tools(reader, llm), NOW)

    assert reader.urls == [HOME]
    assert llm.calls == []
    assert result.notes == []
    view = contact_service.view(conn, company_id)
    assert view.emails == ["info@example.co.nz"]
    assert view.contact_page is None
    assert view.careers_page is None


def test_a_website_without_a_scheme_is_read_as_https(conn):
    company_id = _company(conn, website="www.example.co.nz")
    reader = FakeReader({"https://www.example.co.nz": "Welcome. Email info@example.co.nz"})

    result = contact_service.lookup(conn, company_id, _tools(reader), NOW)

    assert reader.urls == ["https://www.example.co.nz"]
    assert result.notes == []
    assert contact_service.view(conn, company_id).emails == ["info@example.co.nz"]


def test_an_address_first_seen_in_a_job_advert_is_shown_once_the_website_has_it(conn):
    company_id = _company(conn)
    companies_repo.add_fact(conn, company_id, "email", "info@example.co.nz", "job_post",
                            "medium", "https://advert.example/job")

    contact_service.lookup(conn, company_id, _tools(FakeReader(_pages())), NOW)

    assert "info@example.co.nz" in contact_service.view(conn, company_id).emails


@pytest.mark.parametrize("error", ["HTTP 503", "HTTP 429", "request failed (ConnectTimeout)"])
def test_a_transient_failure_leaves_the_site_due_for_an_automatic_retry(conn, error):
    company_id = _company(conn)
    reader = FakeReader(errors={HOME: ProviderError("website", error)})
    contact_service.lookup(conn, company_id, _tools(reader), NOW)
    assert contact_service.view(conn, company_id).checked_at is None

    reader.errors.clear()
    reader.pages = _pages()
    contact_service.lookup(conn, company_id, _tools(reader), NOW + timedelta(hours=1))

    assert reader.urls == [HOME, HOME, CONTACT, CAREERS]
    assert contact_service.view(conn, company_id).checked_at == NOW + timedelta(hours=1)


def test_a_failed_read_records_the_attempt_but_not_a_check(conn):
    company_id = _company(conn)
    reader = FakeReader(errors={HOME: ProviderError("website", "request failed (timeout)")})

    contact_service.lookup(conn, company_id, _tools(reader), NOW)

    row = conn.execute(
        "select contacts_attempted_at, contacts_checked_at from companies where id = %s",
        (company_id,),
    ).fetchone()
    assert row["contacts_attempted_at"] == NOW
    assert row["contacts_checked_at"] is None


def test_the_no_unsolicited_statement_blocks_but_is_never_listed_as_a_fact(conn):
    company_id = _company(conn)
    pages = {HOME: "Welcome to Example Ltd. We do not accept unsolicited applications."}
    contact_service.lookup(conn, company_id, _tools(FakeReader(pages)), NOW)
    conn.commit()

    fields = {fact["field"] for fact in companies_repo.list_facts(conn, company_id)}
    stored = conn.execute(
        "select count(*) as n from company_facts "
        "where company_id = %s and field = 'no_unsolicited'",
        (company_id,),
    ).fetchone()["n"]

    assert "no_unsolicited" not in fields
    assert stored == 1


class _ProbingReader(FakeReader):
    """Records whether the employer's company row is free to lock while a page is read."""

    def __init__(self, probe, pages) -> None:
        super().__init__(pages)
        self.probe = probe
        self.free_during_reads: list[bool] = []

    def read(self, url):
        self.free_during_reads.append(self.probe())
        return super().read(url)


class _ProbingRecruiter:
    """Records whether the company row is free to lock while the AI checks a page."""

    def __init__(self, probe) -> None:
        self.probe = probe
        self.free_during_checks: list[bool] = []

    def run(self, text, name):
        self.free_during_checks.append(self.probe())
        return _jane()


def test_no_row_lock_is_held_while_employer_pages_and_ai_checks_run(conn, database_url):
    company_id = _company(conn)
    conn.commit()

    def row_is_free() -> bool:
        with connect(database_url) as other:
            try:
                other.execute("select id from companies where id = %s for update nowait",
                              (company_id,))
                return True
            except psycopg.errors.LockNotAvailable:
                return False

    reader = _ProbingReader(row_is_free, _pages())
    recruiter = _ProbingRecruiter(row_is_free)
    tools = ContactTools(reader=reader, recruiter=recruiter)

    contact_service.lookup(conn, company_id, tools, NOW)
    conn.commit()

    assert reader.free_during_reads == [True, True, True]
    assert recruiter.free_during_checks == [True, True]
    assert contact_service.view(conn, company_id).emails == ["info@example.co.nz"]
