from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.chains.manager import get_chain
from app.core.config import Settings
from app.core.deps import get_settings
from app.graphs.lead.deps import LeadDeps
from app.graphs.runner import run_graph
from app.main import create_app
from app.workers.outbox_job import process_outbox
from app.workers.tailor_job import process_tailoring_queue
from tests.documents import make_pdf
from tests.factories import make_job
from tests.integration.test_calls_flow import FakeOmni, FakeWhatsApp, nz_morning
from tests.integration.test_outbox_flow import RESUME_LINES, FakeMail, FakeSender

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"
ADVERT = "Build pipelines with Python, SQL and Airflow. Send your CV to jobs@freight.example."


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
    return {"sender": FakeSender(), "whatsapp": FakeWhatsApp(), "omni": FakeOmni()}


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
                          omni=fakes["omni"], whatsapp=fakes["whatsapp"])


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
    assert any("apply on the job site" in t for t in texts)


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
