"""The Outbox contacts list: what each application's employer publishes, and why none was found."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_contact_tools, get_settings
from app.core.errors import ProviderError
from app.main import create_app
from app.repositories import companies_repo, outreach_repo, profiles_repo
from app.services import contact_service, employer_service
from app.services.contact_service import ContactTools
from tests.factories import NOW
from tests.integration.test_contacts import (
    CAREERS,
    CONTACT,
    CONTACT_TEXT,
    HOME,
    HOME_TEXT,
    FakeReader,
)
from tests.integration.test_outbox_flow import (
    PROSPECT_DAY,
    FakeMail,
    FakeSender,
    _send_pass,
    _speculative_application,
    _speculative_setup,
)
from tests.integration.test_prospecting import _employer

pytestmark = pytest.mark.postgres

# 1 am on 3 November in New Zealand (daylight saving), so the date must be the 3rd.
CHECKED = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
PLAIN_ADVERT = "Build services with Python and SQL."


class _PinnedClock(datetime):
    """Stands in for datetime in the find-contacts route so the lookup time is fixed."""

    @classmethod
    def now(cls, tz=None):
        return NOW


@pytest.fixture
def settings(database_url, tmp_path) -> Settings:
    return Settings(database_url=database_url, upload_dir=tmp_path, _env_file=None)


@pytest.fixture
def sending(database_url, tmp_path) -> Settings:
    return Settings(database_url=database_url, upload_dir=tmp_path, email_send_enabled=True,
                    email_enabled=True, email_address="me@example.com",
                    email_app_password="app-password", _env_file=None)


def _client(settings, tools: ContactTools | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_contact_tools] = lambda: tools or ContactTools(
        reader=None, recruiter=None
    )
    return TestClient(app)


def _profile_id(conn) -> UUID:
    return profiles_repo.first_profile_id(conn)


def _company(conn, name: str, website: str | None = HOME, checked=None, attempted=None) -> UUID:
    row = conn.execute(
        "insert into companies (name, website, contacts_checked_at, contacts_attempted_at) "
        "values (%s, %s, %s, %s) returning id",
        (name, website, checked, attempted),
    ).fetchone()
    conn.commit()
    return row["id"]


def _application(conn, company_id, *, description=PLAIN_ADVERT, title="Junior Python Developer",
                 kind="advert", status="approved", source="example", url=None,
                 profile_id=None) -> UUID:
    profile_id = profile_id or _profile_id(conn)
    job = conn.execute(
        "insert into jobs (company_id, source, external_id, title, description, url, dedupe_hash) "
        "values (%s, %s, %s, %s, %s, %s, %s) returning id",
        (company_id, source, str(uuid4()), title, description, url, str(uuid4())),
    ).fetchone()
    app = conn.execute(
        "insert into applications (profile_id, job_id, status, kind) "
        "values (%s, %s, %s, %s) returning id",
        (profile_id, job["id"], status, kind),
    ).fetchone()
    conn.commit()
    return app["id"]


def _queue(conn, application_id, to: str, status: str = "queued") -> None:
    conn.execute(
        "insert into outbox (application_id, channel, kind, to_address, body, status) "
        "values (%s, 'email', 'application', %s, 'Kia ora', %s)",
        (application_id, to, status),
    )
    conn.commit()


def _row(client, application_id) -> dict:
    rows = client.get("/outbox/contacts").json()["rows"]
    return next(row for row in rows if row["application_id"] == str(application_id))


def test_contacts_list_shows_found_details_and_sources(conn, settings):
    company_id = _company(conn, "Example Ltd", HOME)
    careers = "Apply to careers@example.co.nz for any role."
    reader = FakeReader({HOME: HOME_TEXT, CONTACT: CONTACT_TEXT, CAREERS: careers})
    contact_service.lookup(conn, company_id, ContactTools(reader=reader, recruiter=None), NOW)
    conn.commit()
    advert = (
        "Build services in Python. Contact Jane Doe, Team Lead, jane.doe@example.co.nz to apply."
    )
    app_id = _application(conn, company_id, description=advert, title="Python Developer")
    _queue(conn, app_id, "jane.doe@example.co.nz")

    with _client(settings) as client:
        response = client.get("/outbox/contacts")
        row = _row(client, app_id)

    assert response.status_code == 200
    assert row["kind"] == "advert"
    assert row["title"] == "Python Developer"
    assert row["company"] == "Example Ltd"
    assert row["status"] == "approved"
    assert row["hiring_emails"] == ["careers@example.co.nz"]
    assert row["emails"] == ["info@example.co.nz"]
    assert row["phone"] == "03-688 1234"
    assert row["phone_source"] == "Website"
    assert row["advert_contact"] == {
        "name": "Jane Doe", "role": "Team Lead", "email": "jane.doe@example.co.nz", "phone": None,
    }
    assert row["address_used"] == "jane.doe@example.co.nz"
    assert row["missing_reason"] is None
    assert row["checked_at"] is not None


def test_missing_reason_site_only_advert(conn, settings):
    company_id = _company(conn, "Site Only Ltd", HOME, checked=CHECKED, attempted=CHECKED)
    app_id = _application(conn, company_id,
                          description="Apply online only through our careers site.")

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "Advert asks you to apply on the job site"


def test_missing_reason_no_website(conn, settings):
    company_id = _company(conn, "No Site Ltd", website=None)
    app_id = _application(conn, company_id)

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "No website known"


def test_missing_reason_never_checked(conn, settings):
    company_id = _company(conn, "New Lead Ltd", HOME)
    app_id = _application(conn, company_id)

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "Website not checked yet"


def test_missing_reason_could_not_read(conn, settings):
    # A transient failure: the attempt started but never finished, so nothing was checked.
    company_id = _company(conn, "Timeout Ltd", HOME, checked=None, attempted=CHECKED)
    app_id = _application(conn, company_id)

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "Could not read the website"


def test_missing_reason_checked_with_no_email(conn, settings):
    company_id = _company(conn, "Checked Ltd", HOME, checked=CHECKED, attempted=CHECKED)
    app_id = _application(conn, company_id)

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "Checked 3 Nov 2026: no email on the site"
    assert row["checked_at"] is not None


def test_missing_reason_unfinished_retry_after_an_earlier_check_could_not_read(conn, settings):
    company_id = _company(conn, "Retry Ltd", HOME, checked=CHECKED - timedelta(days=40),
                          attempted=CHECKED)
    app_id = _application(conn, company_id)

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "Could not read the website"


def test_missing_reason_bare_host_is_read_with_a_scheme_added(conn, settings):
    # Job sources often give a bare host. It must be checked as https, not called unreadable.
    company_id = _company(conn, "Bare Host Ltd", "bare-host.co.nz", checked=CHECKED,
                          attempted=CHECKED)
    app_id = _application(conn, company_id)

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "Checked 3 Nov 2026: no email on the site"


def test_missing_reason_website_address_not_allowed(conn, settings):
    company_id = _company(conn, "Local Ltd", "http://127.0.0.1/", checked=CHECKED,
                          attempted=None)
    app_id = _application(conn, company_id)

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "Could not read the website"


def test_speculative_rows_have_no_advert_contact_or_site_only_reason(conn, settings):
    company_id = _company(conn, "Maps Only Ltd", website=None)
    app_id = _application(conn, company_id, kind="speculative", source="nearby",
                          title="Speculative application",
                          description="Apply online only. Contact Jane Doe, Owner.")

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["kind"] == "speculative"
    assert row["advert_contact"] is None
    assert row["missing_reason"] == "No website known"


def test_find_contacts_forces_a_lookup(conn, settings, monkeypatch):
    monkeypatch.setattr("app.api.outbox.datetime", _PinnedClock)
    company_id = _company(conn, "Example Ltd", HOME, checked=NOW - timedelta(days=1),
                          attempted=NOW - timedelta(days=1))
    app_id = _application(conn, company_id)
    reader = FakeReader({HOME: "Welcome. Email info@example.co.nz for enquiries."})

    tools = ContactTools(reader=reader, recruiter=None)
    with _client(settings, tools) as client:
        response = client.post(f"/applications/{app_id}/find-contacts")

    assert response.status_code == 200
    assert reader.urls == [HOME]
    row = response.json()
    assert row["application_id"] == str(app_id)
    assert row["emails"] == ["info@example.co.nz"]
    assert datetime.fromisoformat(row["checked_at"]) == NOW


def test_another_profiles_job_is_not_found(conn, settings):
    other = conn.execute(
        "insert into profiles (full_name) values ('Other Person') returning id"
    ).fetchone()["id"]
    conn.commit()
    company_id = _company(conn, "Other Ltd", HOME)
    other_app = _application(conn, company_id, profile_id=other)
    no_company_app = _application(conn, None)

    with _client(settings) as client:
        listed = client.get("/outbox/contacts").json()["rows"]
        other_response = client.post(f"/applications/{other_app}/find-contacts")
        no_company_response = client.post(f"/applications/{no_company_app}/find-contacts")

    assert other_response.status_code == 404
    assert no_company_response.status_code == 404
    assert str(other_app) not in {row["application_id"] for row in listed}


def test_speculative_record_opens_in_the_application_and_review_pages(
    conn, settings, database_url, tmp_path
):
    _speculative_setup(conn, database_url, tmp_path)
    app_id = _speculative_application(conn)["id"]

    with _client(settings) as client:
        detail = client.get(f"/applications/{app_id}")
        resume = client.get(f"/applications/{app_id}/resume")
        review = client.get("/resume-review")

    assert detail.status_code == 200
    assert resume.status_code == 200
    assert resume.json()["tailored"] is None
    # Speculative applications are approved without a review step, so the review list is empty.
    assert review.status_code == 200
    assert review.json() == {"items": []}


def test_saved_employers_show_outreach_status(conn, database_url, tmp_path, sending):
    _speculative_setup(conn, database_url, tmp_path, name="Timaru Trades")
    assert _send_pass(sending, FakeSender(), PROSPECT_DAY, mail=FakeMail())["sent"] == 1
    sent_at = conn.execute(
        "select sent_at from outbox where kind = 'application' and status = 'sent'"
    ).fetchone()["sent_at"]
    profile_id = _profile_id(conn)
    replied = _employer(conn, profile_id, "Replied Co")
    manual = _employer(conn, profile_id, "Manual Co")
    _employer(conn, profile_id, "Quiet Co")
    outreach_repo.block(conn, profile_id, replied, "replied")
    outreach_repo.block(conn, profile_id, manual, "manual")
    conn.commit()

    items = {item.name: item for item in employer_service.list_saved(conn, profile_id).items}

    assert items["Timaru Trades"].outreach_status == "emailed"
    assert items["Timaru Trades"].outreach_at == sent_at
    assert items["Replied Co"].outreach_status == "replied"
    assert items["Replied Co"].outreach_at is not None
    assert items["Manual Co"].outreach_status == "blocked"
    assert items["Quiet Co"].outreach_status is None
    assert items["Quiet Co"].outreach_at is None


def test_a_refused_read_is_reported_as_could_not_read(conn, settings):
    company_id = _company(conn, "Refused Ltd", HOME)
    reader = FakeReader(errors={HOME: ProviderError("website", "HTTP 403")})
    contact_service.lookup(conn, company_id, ContactTools(reader=reader, recruiter=None), NOW)
    conn.commit()
    app_id = _application(conn, company_id)

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "Could not read the website"


def test_a_later_successful_read_clears_the_refused_one(conn, settings):
    company_id = _company(conn, "Recovered Ltd", HOME)
    refused = FakeReader(errors={HOME: ProviderError("website", "HTTP 403")})
    contact_service.lookup(conn, company_id, ContactTools(reader=refused, recruiter=None), NOW)
    readable = FakeReader({HOME: "Welcome to Recovered Ltd. No email is published here."})
    # 7 am UTC on 25 November is 8 pm on 25 November in New Zealand.
    later = NOW + timedelta(days=1)
    contact_service.lookup(
        conn, company_id, ContactTools(reader=readable, recruiter=None), later, force=True
    )
    conn.commit()
    app_id = _application(conn, company_id)

    with _client(settings) as client:
        row = _row(client, app_id)

    assert row["missing_reason"] == "Checked 25 Nov 2026: no email on the site"


def test_the_refused_read_never_shows_as_a_contact(conn):
    company_id = _company(conn, "Hidden Ltd", HOME)
    refused = FakeReader(errors={HOME: ProviderError("website", "HTTP 403")})
    contact_service.lookup(conn, company_id, ContactTools(reader=refused, recruiter=None), NOW)
    conn.commit()

    details = contact_service.view(conn, company_id)

    assert details.emails == []
    assert details.hiring_emails == []
    assert details.phone is None
    fields = {fact["field"] for fact in companies_repo.list_facts(conn, company_id)}
    assert "site_unreadable" not in fields


def test_a_refused_site_still_needs_research(conn):
    company_id = _company(conn, "Research Ltd", HOME)
    refused = FakeReader(errors={HOME: ProviderError("website", "HTTP 403")})
    contact_service.lookup(conn, company_id, ContactTools(reader=refused, recruiter=None), NOW)
    conn.commit()
    app_id = _application(conn, company_id)

    found = companies_repo.needing_research(conn, [app_id], 10)

    assert [row["id"] for row in found] == [company_id]

