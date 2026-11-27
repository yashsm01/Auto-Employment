from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from psycopg.pq import TransactionStatus

from app.chains.manager import get_chain
from app.core.config import Settings
from app.core.deps import get_settings
from app.core.errors import ProviderError
from app.db.client import connect
from app.graphs.lead.deps import LeadDeps
from app.graphs.runner import run_graph
from app.main import create_app
from app.services import auto_service
from app.services.contact_service import ContactTools
from app.workers.outbox_job import process_outbox
from app.workers.tailor_job import process_tailoring_queue
from tests.documents import make_pdf
from tests.factories import make_job
from tests.integration.test_calls_flow import FakeOmni, FakeWhatsApp, nz_morning
from tests.integration.test_contacts import FakeReader
from tests.integration.test_outbox_flow import RESUME_LINES, FakeMail, FakeSender

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"
ADVERT = "Build pipelines with Python, SQL and Airflow. Send your CV to jobs@freight.example."
NO_EMAIL_ADVERT = "Build pipelines with Python, SQL and Airflow. Apply online."
WEBSITE = "https://freight.example"


@pytest.fixture(autouse=True)
def no_background_runs(monkeypatch):
    """Tests drive every outbox and tailoring run themselves; no real clients are built."""
    for target in ("app.api.outbox.process_outbox", "app.api.calls.process_outbox",
                   "app.api.applications.process_tailoring_queue",
                   "app.api.applications.process_prep_queue"):
        monkeypatch.setattr(target, lambda *args, **kwargs: None)


@pytest.fixture
def settings(database_url, tmp_path) -> Settings:
    return Settings(database_url=database_url, upload_dir=tmp_path, email_send_enabled=True,
                    email_address="me@example.com", email_app_password="pw",
                    whatsapp_enabled=True, whatsapp_service_url="http://127.0.0.1:9/send",
                    whatsapp_to="+64224379369", _env_file=None)


@pytest.fixture
def fakes():
    return {"sender": FakeSender(), "whatsapp": FakeWhatsApp(), "omni": FakeOmni(),
            "contacts": ContactTools(FakeReader({}), None)}


@pytest.fixture
def client(settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client


def _upload(client) -> None:
    client.post(
        "/profile/resume", files={"file": ("resume.pdf", make_pdf(*RESUME_LINES))}
    ).raise_for_status()


def _shortlisted(conn, key: str, score: int, description: str = ADVERT) -> str:
    job = make_job(source="gmail_alert", external_id=f"auto-{key}", title="Data Engineer",
                   company=f"Example Freight Tech {key}", description=description)
    deps = LeadDeps(conn=conn, sources=[OneSource(job)], score_chain=get_chain("score"),
                    now=nz_morning(0))
    run_graph("lead", {"profile_id": PROFILE_ID}, deps)
    app_id = str(conn.execute(
        "select a.id from applications a join jobs j on j.id = a.job_id "
        "where j.external_id = %s", (f"auto-{key}",)).fetchone()["id"])
    conn.execute("update applications set status = 'shortlisted', score = %s where id = %s",
                 (score, app_id))
    conn.commit()
    return app_id


class OneSource:
    name = "one"

    def __init__(self, job) -> None:
        self.job = job

    def search(self, keywords):
        return [self.job]


def _run(settings, fakes, now):
    return process_outbox(settings, sender=fakes["sender"], mail=FakeMail(), now=now,
                          omni=fakes["omni"], whatsapp=fakes["whatsapp"],
                          contact_tools=fakes["contacts"])


def _status(conn, app_id) -> str:
    return conn.execute(
        "select status from applications where id = %s", (app_id,)).fetchone()["status"]


def _switch_on(client, **values) -> None:
    body = {"enabled": True, "min_score": 80, "daily_limit": 5} | values
    assert client.put("/auto-mode", json=body).status_code == 200


def test_auto_mode_is_off_by_default_and_changes_nothing(client, conn, settings, fakes):
    _upload(client)
    app_id = _shortlisted(conn, "1", 95)

    view = client.get("/auto-mode").json()
    _run(settings, fakes, nz_morning(1))

    assert {k: view[k] for k in ("enabled", "min_score", "daily_limit", "approved_today")} == {
        "enabled": False, "min_score": 80, "daily_limit": 5, "approved_today": 0}
    assert _status(conn, app_id) == "shortlisted"


def test_auto_mode_approves_strong_matches_only(client, conn, settings, fakes):
    _upload(client)
    strong, weak = _shortlisted(conn, "1", 90), _shortlisted(conn, "2", 79)
    _switch_on(client)

    report = _run(settings, fakes, nz_morning(1))

    assert report["auto_approved"] == 1
    assert (_status(conn, strong), _status(conn, weak)) == ("tailoring", "shortlisted")
    row = conn.execute(
        "select auto_approved_at from applications where id = %s", (strong,)).fetchone()
    assert row["auto_approved_at"] is not None
    notes = conn.execute(
        "select payload from events where application_id = %s and type = 'note'", (strong,)
    ).fetchall()
    assert any(n["payload"].get("text") == "Approved by auto mode" for n in notes)


def test_the_daily_limit_keeps_the_best_for_today(client, conn, settings, fakes):
    _upload(client)
    good, best = _shortlisted(conn, "1", 85), _shortlisted(conn, "2", 95)
    _switch_on(client, daily_limit=1)

    _run(settings, fakes, nz_morning(1))
    assert (_status(conn, best), _status(conn, good)) == ("tailoring", "shortlisted")

    _run(settings, fakes, nz_morning(1, hour=15))
    assert _status(conn, good) == "shortlisted"

    _run(settings, fakes, nz_morning(1) + timedelta(days=1))
    assert _status(conn, good) == "tailoring"


def test_auto_mode_approves_its_resume_and_emails_the_advert_address(
    client, conn, settings, fakes
):
    _upload(client)
    app_id = _shortlisted(conn, "1", 90)
    _switch_on(client)
    _run(settings, fakes, nz_morning(1))
    process_tailoring_queue(settings)
    assert _status(conn, app_id) == "ready"

    _run(settings, fakes, nz_morning(1, hour=11))

    assert _status(conn, app_id) == "sent"
    email = fakes["sender"].sent[0]
    assert email["to"] == "jobs@freight.example"
    assert email["attachment"].read_bytes().startswith(b"%PDF-")
    texts = [text for _, text in fakes["whatsapp"].sent]
    assert any("Auto mode is sending your application" in t and "Data Engineer" in t for t in texts)


def test_auto_mode_leaves_jobs_you_approved_yourself_for_you(client, conn, settings, fakes):
    _upload(client)
    app_id = _shortlisted(conn, "1", 70)
    client.post(f"/applications/{app_id}/decision", json={"action": "approve"})
    process_tailoring_queue(settings)
    _switch_on(client)

    _run(settings, fakes, nz_morning(1))

    assert _status(conn, app_id) == "ready"
    assert fakes["sender"].sent == []


def test_without_an_email_address_the_job_waits_for_you_to_apply(client, conn, settings, fakes):
    _upload(client)
    app_id = _shortlisted(conn, "1", 90,
                          description="Build pipelines with Python, SQL and Airflow. Apply online.")
    _switch_on(client)
    _run(settings, fakes, nz_morning(1))
    process_tailoring_queue(settings)

    _run(settings, fakes, nz_morning(1, hour=11))

    assert _status(conn, app_id) == "approved"
    assert fakes["sender"].sent == []
    assert client.get("/outbox").json()["to_send"][0]["application_id"] == app_id
    texts = [text for _, text in fakes["whatsapp"].sent]
    assert any("Apply on the job site" in t for t in texts)


def test_auto_mode_needs_your_own_resume(client, conn, settings, fakes):
    app_id = _shortlisted(conn, "1", 95)  # the example profile, no uploaded resume
    _switch_on(client)

    _run(settings, fakes, nz_morning(1))

    assert _status(conn, app_id) == "shortlisted"


def test_settings_are_checked(client):
    assert client.put("/auto-mode", json={
        "enabled": True, "min_score": 101, "daily_limit": 5}).status_code == 422
    assert client.put("/auto-mode", json={
        "enabled": True, "min_score": 80, "daily_limit": 21}).status_code == 422


def test_prospect_settings_round_trip(client, conn):
    body = {"enabled": True, "min_score": 80, "daily_limit": 5, "prospects_enabled": True,
            "prospects_per_day": 3,
            "business_types": [" Logistics ", "logistics", "", "Retail stores"]}
    assert client.put("/auto-mode", json=body).status_code == 200

    view = client.get("/auto-mode").json()

    assert {k: view[k] for k in ("prospects_enabled", "prospects_per_day", "business_types")} == {
        "prospects_enabled": True, "prospects_per_day": 3,
        "business_types": ["Logistics", "Retail stores"]}
    assert view["business_types_suggested"] == []


def test_prospect_settings_are_checked(client):
    base = {"enabled": True, "min_score": 80, "daily_limit": 5}
    too_many = [f"Type {n}" for n in range(21)]
    assert client.put("/auto-mode", json=base | {"prospects_per_day": 11}).status_code == 422
    assert client.put("/auto-mode", json=base | {"business_types": too_many}).status_code == 422
    assert client.put("/auto-mode", json=base | {"business_types": ["x" * 61]}).status_code == 422


def test_prospects_need_auto_mode(client, conn):
    response = client.put("/auto-mode", json={"enabled": False, "prospects_enabled": True})

    assert response.status_code == 400
    assert response.json()["detail"] == "Turn on Auto mode first."
    assert conn.execute(
        "select prospects_enabled from profiles where id = %s", (PROFILE_ID,)).fetchone()[
        "prospects_enabled"] is False

    _switch_on(client, prospects_enabled=True)
    assert client.put("/auto-mode", json={"enabled": False, "min_score": 80,
                                          "daily_limit": 5}).status_code == 200
    row = conn.execute(
        "select auto_mode, prospects_enabled from profiles where id = %s", (PROFILE_ID,)
    ).fetchone()
    assert (row["auto_mode"], row["prospects_enabled"]) == (False, False)


def test_business_types_are_suggested_from_resume_industries(client, conn):
    conn.execute(
        "update resume_profiles set industries = %s where resume_id = %s",
        (["Logistics", "logistics", " Retail "],
         "00000000-0000-4000-8000-000000000002"),
    )
    conn.commit()

    view = client.get("/auto-mode").json()
    assert view["business_types"] == []
    assert view["business_types_suggested"] == ["Logistics", "Retail"]

    assert client.put("/auto-mode", json={"enabled": False, "business_types": ["Rail"]}
                      ).status_code == 200
    view = client.get("/auto-mode").json()
    assert view["business_types"] == ["Rail"]
    assert view["business_types_suggested"] == []


def _employer_of(conn, app_id) -> str:
    return str(conn.execute(
        "select j.company_id from applications a join jobs j on j.id = a.job_id "
        "where a.id = %s", (app_id,)).fetchone()["company_id"])


def _give_website(conn, app_id) -> None:
    conn.execute("update companies set website = %s where id = %s",
                 (WEBSITE, _employer_of(conn, app_id)))
    conn.commit()


def _approve_and_tailor(settings, fakes) -> None:
    _run(settings, fakes, nz_morning(1))
    process_tailoring_queue(settings)


def test_auto_mode_looks_up_contacts_before_queueing(client, conn, settings, fakes):
    _upload(client)
    app_id = _shortlisted(conn, "1", 90, description=NO_EMAIL_ADVERT)
    _give_website(conn, app_id)
    fakes["contacts"] = ContactTools(
        FakeReader({WEBSITE: "Home. Email hello@freight.example for enquiries."}), None)
    _switch_on(client)
    _approve_and_tailor(settings, fakes)

    _run(settings, fakes, nz_morning(1, hour=11))

    assert _status(conn, app_id) == "sent"
    assert fakes["sender"].sent[0]["to"] == "hello@freight.example"


def test_auto_mode_waits_for_an_unchecked_website(client, conn, settings, fakes):
    _upload(client)
    app_id = _shortlisted(conn, "2", 90, description=NO_EMAIL_ADVERT)
    _give_website(conn, app_id)
    fakes["contacts"] = ContactTools(FakeReader(errors={
        WEBSITE: ProviderError("website", "request failed (timeout)")}), None)
    _switch_on(client)
    _approve_and_tailor(settings, fakes)

    _run(settings, fakes, nz_morning(1, hour=11))

    assert _status(conn, app_id) == "approved"
    assert fakes["sender"].sent == []
    checked = conn.execute("select contacts_checked_at from companies where id = %s",
                           (_employer_of(conn, app_id),)).fetchone()["contacts_checked_at"]
    assert checked is None
    texts = [text for _, text in fakes["whatsapp"].sent]
    assert not any("apply on the job site" in t for t in texts)


def test_auto_mode_never_emails_an_apply_online_only_advert(client, conn, settings, fakes):
    _upload(client)
    app_id = _shortlisted(conn, "3", 90, description=ADVERT + " Apply online only.")
    _switch_on(client)
    _approve_and_tailor(settings, fakes)

    _run(settings, fakes, nz_morning(1, hour=11))
    _run(settings, fakes, nz_morning(1, hour=12))

    assert _status(conn, app_id) == "approved"
    assert fakes["sender"].sent == []
    texts = [text for _, text in fakes["whatsapp"].sent]
    assert sum("apply on the job site" in t for t in texts) == 1


def test_a_transient_failure_waits_and_a_later_pass_retries_once_the_site_reads(
    client, conn, settings, fakes
):
    _upload(client)
    app_id = _shortlisted(conn, "4", 90, description=NO_EMAIL_ADVERT)
    _give_website(conn, app_id)
    reader = FakeReader(errors={WEBSITE: ProviderError("website", "request failed (timeout)")})
    fakes["contacts"] = ContactTools(reader, None)
    _switch_on(client)
    first = nz_morning(1)
    _approve_and_tailor(settings, fakes)  # approved at first, the site fails

    _run(settings, fakes, first + timedelta(minutes=30))  # within the hour: no retry
    assert len(reader.urls) == 1
    assert _status(conn, app_id) == "approved"
    assert fakes["sender"].sent == []

    reader.errors, reader.pages = {}, {WEBSITE: "Home. Email hello@freight.example for enquiries."}
    _run(settings, fakes, first + timedelta(hours=2))  # more than an hour later: retried

    assert len(reader.urls) == 2
    assert _status(conn, app_id) == "sent"
    assert [mail["to"] for mail in fakes["sender"].sent] == ["hello@freight.example"]
    _run(settings, fakes, first + timedelta(hours=3))
    assert len(fakes["sender"].sent) == 1


def test_after_a_day_of_failed_reads_the_user_is_told_once_and_the_job_stops_waiting(
    client, conn, settings, fakes
):
    _upload(client)
    app_id = _shortlisted(conn, "5", 90, description=NO_EMAIL_ADVERT)
    _give_website(conn, app_id)
    reader = FakeReader(errors={WEBSITE: ProviderError("website", "request failed (timeout)")})
    fakes["contacts"] = ContactTools(reader, None)
    _switch_on(client)
    first = nz_morning(1)
    _approve_and_tailor(settings, fakes)
    _run(settings, fakes, first + timedelta(hours=2))  # a retry that fails again

    _run(settings, fakes, first + timedelta(hours=25))
    reads_after_giving_up = len(reader.urls)
    _run(settings, fakes, first + timedelta(hours=26))

    assert len(reader.urls) == reads_after_giving_up
    assert _status(conn, app_id) == "approved"
    assert fakes["sender"].sent == []
    texts = [text for _, text in fakes["whatsapp"].sent]
    assert sum("Apply on the job site" in t for t in texts) == 1
    assert ("Auto mode approved Data Engineer at Example Freight Tech 5. No email address found "
            "(Could not read the website). Apply on the job site from the Outbox.") in texts


def test_a_checked_site_with_no_email_says_when_it_was_checked(client, conn, settings, fakes):
    _upload(client)
    app_id = _shortlisted(conn, "8", 90, description=NO_EMAIL_ADVERT)
    _give_website(conn, app_id)
    fakes["contacts"] = ContactTools(FakeReader({WEBSITE: "Home. Nothing to contact us about."}),
                                     None)
    _switch_on(client)
    _approve_and_tailor(settings, fakes)

    _run(settings, fakes, nz_morning(1, hour=11))

    assert _status(conn, app_id) == "approved"
    texts = [text for _, text in fakes["whatsapp"].sent]
    assert any(
        t.startswith("Auto mode approved Data Engineer at Example Freight Tech 8. "
                     "No email address found (Checked ")
        and t.endswith("no email on the site). Apply on the job site from the Outbox.")
        for t in texts
    )
    assert not any("The advert has no email address" in t for t in texts)


class WatchingReader(FakeReader):
    """Records what another connection sees of the application at the moment of each read."""

    def __init__(self, database_url, app_id, pages):
        super().__init__(pages)
        self.database_url, self.app_id, self.seen = database_url, app_id, []

    def read(self, url):
        with connect(self.database_url) as other:
            self.seen.append(other.execute(
                "select status from applications where id = %s", (self.app_id,)).fetchone()[
                "status"])
        return super().read(url)


def test_an_approval_is_committed_before_the_employer_site_is_read(
    client, conn, settings, fakes, database_url
):
    _upload(client)
    app_id = _shortlisted(conn, "6", 90, description=NO_EMAIL_ADVERT)
    _give_website(conn, app_id)
    reader = WatchingReader(database_url, app_id, {WEBSITE: "Home."})
    fakes["contacts"] = ContactTools(reader, None)
    _switch_on(client)

    _run(settings, fakes, nz_morning(1))

    assert reader.seen == ["tailoring"]


def test_no_transaction_is_open_when_a_contact_lookup_starts(
    client, conn, settings, fakes, monkeypatch
):
    _upload(client)
    app_id = _shortlisted(conn, "7", 90, description=NO_EMAIL_ADVERT)
    _give_website(conn, app_id)
    fakes["contacts"] = ContactTools(FakeReader(errors={
        WEBSITE: ProviderError("website", "request failed (timeout)")}), None)
    statuses = []
    real_lookup = auto_service._look_up_contacts

    def spy(conn_, company_id, tools, now):
        statuses.append(conn_.info.transaction_status)
        return real_lookup(conn_, company_id, tools, now)

    monkeypatch.setattr(auto_service, "_look_up_contacts", spy)
    _switch_on(client)
    _approve_and_tailor(settings, fakes)
    _run(settings, fakes, nz_morning(1, hour=12))  # a retry on a later pass

    assert len(statuses) == 2
    assert set(statuses) == {TransactionStatus.IDLE}
