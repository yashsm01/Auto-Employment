from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.calls import get_omni, get_whatsapp
from app.core.config import Settings
from app.core.deps import get_settings
from app.core.workdays import NZ_TIME, nz_today
from app.main import create_app
from app.workers.outbox_job import process_outbox
from tests.integration.test_outbox_flow import FakeMail, FakeSender, _approved

pytestmark = pytest.mark.postgres

T = datetime.now(UTC) + timedelta(minutes=1)


def nz_morning(days_after_t: int, hour: int = 10) -> datetime:
    """10am NZ on the first weekday at least this many days after T."""
    day = nz_today(T + timedelta(days=days_after_t))
    moment = datetime(day.year, day.month, day.day, hour, tzinfo=NZ_TIME)
    while moment.weekday() >= 5:
        moment += timedelta(days=1)
    return moment.astimezone(UTC)


class FakeOmni:
    def __init__(self, error: Exception | None = None) -> None:
        self.dispatched: list[dict] = []
        self.logs: dict[str, dict] = {}
        self.error = error

    def dispatch(self, **call) -> str:
        if self.error:
            raise self.error
        self.dispatched.append(call)
        return f"req-{len(self.dispatched)}"

    def find_log(self, *, agent_id: int, app_call_id: str, pages: int = 3):
        return self.logs.get(app_call_id)


class FakeWhatsApp:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, to: str, text: str) -> None:
        self.sent.append((to, text))


def _settings(database_url, tmp_path, **overrides) -> Settings:
    values = dict(
        database_url=database_url, upload_dir=tmp_path, email_send_enabled=True,
        email_enabled=True, email_address="me@example.com", email_app_password="pw",
        calls_enabled=True, omnidim_api_key="omni-key", omnidim_agent_id=158910,
        whatsapp_enabled=True, whatsapp_service_url="http://127.0.0.1:9/send",
        whatsapp_to="+64224379369", _env_file=None,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(autouse=True)
def no_background_runs(monkeypatch):
    """The API starts an outbox run after some actions. In these tests it would build real
    Gmail, OmniDimension and WhatsApp clients, so the tests drive every run themselves."""
    monkeypatch.setattr("app.api.outbox.process_outbox", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.api.calls.process_outbox", lambda *args, **kwargs: None)


@pytest.fixture
def settings(database_url, tmp_path) -> Settings:
    return _settings(database_url, tmp_path)


@pytest.fixture
def fakes():
    return {"omni": FakeOmni(), "whatsapp": FakeWhatsApp(), "sender": FakeSender()}


@pytest.fixture
def client(settings, fakes):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_omni] = lambda: fakes["omni"]
    app.dependency_overrides[get_whatsapp] = lambda: fakes["whatsapp"]
    with TestClient(app) as test_client:
        yield test_client


def _run(settings, fakes, now, mail=None):
    return process_outbox(settings, sender=fakes["sender"], mail=mail or FakeMail(), now=now,
                          omni=fakes["omni"], whatsapp=fakes["whatsapp"])


def _followed_up_twice(client, conn, settings, fakes, phone="03-688 1234") -> str:
    app_id = _approved(client, conn)
    conn.execute(
        "update companies set phone = %s where id = (select j.company_id from applications a "
        "join jobs j on j.id = a.job_id where a.id = %s)", (phone, app_id))
    conn.commit()
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    for days in (0, 7, 14):
        _run(settings, fakes, T + timedelta(days=days))
    assert len(fakes["sender"].sent) == 3
    return app_id


def _call(conn, app_id) -> dict:
    return conn.execute(
        "select * from calls where application_id = %s order by created_at desc", (app_id,)
    ).fetchone()


def _application(conn, app_id) -> dict:
    return conn.execute("select * from applications where id = %s", (app_id,)).fetchone()


def test_no_reply_after_two_follow_ups_calls_the_published_number(client, conn, settings, fakes):
    app_id = _followed_up_twice(client, conn, settings, fakes)

    _run(settings, fakes, nz_morning(21))

    call = fakes["omni"].dispatched[0]
    assert call["to_number"] == "+6436881234"
    assert call["agent_id"] == 158910
    assert call["call_context"]["job_title"] == "Data Engineer"
    assert call["call_context"]["company"] == "Example Freight Tech"
    assert call["call_context"]["candidate_name"] == "Sample Person"
    row = _call(conn, app_id)
    assert call["metadata"] == {"app_call_id": str(row["id"])}
    assert (row["status"], row["request_id"]) == ("ringing", "req-1")
    application = _application(conn, app_id)
    assert (application["status"], application["next_follow_up"]) == ("followed_up", None)


def test_a_finished_call_is_saved_and_you_get_a_whatsapp_summary(client, conn, settings, fakes):
    app_id = _followed_up_twice(client, conn, settings, fakes)
    _run(settings, fakes, nz_morning(21))
    call_id = str(_call(conn, app_id)["id"])
    fakes["omni"].logs[call_id] = {
        "id": 3517893, "call_status": "completed", "call_duration_in_seconds": 95,
        "call_conversation": "Agent: Kia ora<br/>Employer: send it to HR@Freight.Example",
        "extracted_variables": {"contact_email": "HR@Freight.Example"},
        "metadata": {"app_call_id": call_id},
    }

    _run(settings, fakes, nz_morning(21, hour=11))

    row = _call(conn, app_id)
    assert (row["status"], row["duration_sec"], row["omnidim_call_id"]) == ("done", 95, "3517893")
    assert row["transcript"] == "Agent: Kia ora\nEmployer: send it to HR@Freight.Example"
    assert row["extracted"]["captured_email"] == "hr@freight.example"
    texts = [text for _, text in fakes["whatsapp"].sent]
    assert any("Example Freight Tech" in t and "hr@freight.example" in t for t in texts)
    waiting = client.get("/outbox").json()["waiting"][0]
    assert (waiting["call_status"], waiting["captured_email"]) == ("done", "hr@freight.example")

    assert client.post(f"/applications/{app_id}/send-after-call",
                       json={"to": "hr@freight.example"}).status_code == 200
    _run(settings, fakes, nz_morning(21, hour=12))
    email = fakes["sender"].sent[-1]
    assert email["to"] == "hr@freight.example"
    assert email["subject"] == "Following our call: Data Engineer – Sample Person"
    assert email["attachment"].read_bytes().startswith(b"%PDF-")


def test_without_a_phone_number_the_job_closes_as_before(client, conn, settings, fakes):
    app_id = _followed_up_twice(client, conn, settings, fakes, phone=None)

    _run(settings, fakes, nz_morning(21))

    assert fakes["omni"].dispatched == []
    assert _application(conn, app_id)["status"] == "closed"


def test_with_calls_switched_off_the_job_closes_as_before(
    database_url, tmp_path, conn, fakes
):
    settings = _settings(database_url, tmp_path, calls_enabled=False)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        app_id = _followed_up_twice(client, conn, settings, fakes)
        _run(settings, fakes, nz_morning(21))

    assert fakes["omni"].dispatched == []
    assert _application(conn, app_id)["status"] == "closed"


def test_the_monthly_call_limit_is_kept(database_url, tmp_path, conn, fakes):
    settings = _settings(database_url, tmp_path, max_calls_per_month=0)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        app_id = _followed_up_twice(client, conn, settings, fakes)
        _run(settings, fakes, nz_morning(21))

    assert fakes["omni"].dispatched == []
    assert _application(conn, app_id)["status"] == "closed"


def test_calls_wait_for_business_hours(client, conn, settings, fakes):
    app_id = _followed_up_twice(client, conn, settings, fakes)

    _run(settings, fakes, nz_morning(21, hour=7))
    assert fakes["omni"].dispatched == []
    assert _call(conn, app_id)["status"] == "queued"

    _run(settings, fakes, nz_morning(21, hour=10))
    assert len(fakes["omni"].dispatched) == 1


def test_a_call_with_no_record_after_two_hours_is_marked_failed(client, conn, settings, fakes):
    app_id = _followed_up_twice(client, conn, settings, fakes)
    _run(settings, fakes, nz_morning(21, hour=10))

    _run(settings, fakes, nz_morning(21, hour=13))

    row = _call(conn, app_id)
    assert row["status"] == "failed"
    assert "No call record" in row["error"]


def test_test_call_rings_your_own_phone(client, conn, fakes):
    _approved(client, conn)  # uploads the resume with phone +64 21 000 0000

    response = client.post("/calls/test")

    assert response.status_code == 200
    assert fakes["omni"].dispatched[0]["to_number"] == "+64210000000"
    assert response.json()["calls"]["used_this_month"] == 1


def test_whatsapp_tells_you_when_an_employer_replies_once(client, conn, settings, fakes):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    _run(settings, fakes, T)
    mail = FakeMail(replies_from=("jobs@example.co.nz",))

    _run(settings, fakes, T + timedelta(days=1), mail=mail)
    _run(settings, fakes, T + timedelta(days=1, hours=1), mail=mail)

    replies = [text for to, text in fakes["whatsapp"].sent if "replied" in text]
    assert replies == ["Example Freight Tech replied about Data Engineer."]
    assert fakes["whatsapp"].sent[0][0] == "+64224379369"


def test_no_whatsapp_updates_are_kept_when_it_is_off(database_url, tmp_path, conn, fakes):
    settings = _settings(database_url, tmp_path, whatsapp_enabled=False)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        app_id = _approved(client, conn)
        client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
        _run(settings, fakes, T)
        _run(settings, fakes, T + timedelta(days=1),
             mail=FakeMail(replies_from=("jobs@example.co.nz",)))

    assert fakes["whatsapp"].sent == []
    assert conn.execute("select count(*) as n from notifications").fetchone()["n"] == 0


def test_test_whatsapp_and_the_settings_view(client, fakes):
    view = client.get("/settings/phase4").json()
    assert view["calls"] == {"configured": True, "enabled": True, "used_this_month": 0,
                             "monthly_limit": 5}
    assert view["whatsapp"]["configured"] is True
    assert view["whatsapp"]["to"] == "+64 22 *** *369"

    assert client.post("/notifications/test").status_code == 200
    assert fakes["whatsapp"].sent == [("+64224379369", "Test message from NZ Job Autopilot.")]


def test_a_reply_cancels_a_call_still_waiting_for_business_hours(client, conn, settings, fakes):
    app_id = _followed_up_twice(client, conn, settings, fakes)
    _run(settings, fakes, nz_morning(21, hour=7))  # queued overnight
    assert _call(conn, app_id)["status"] == "queued"

    _run(settings, fakes, nz_morning(21, hour=8),
         mail=FakeMail(replies_from=("jobs@example.co.nz",)))
    _run(settings, fakes, nz_morning(21, hour=10))

    assert fakes["omni"].dispatched == []
    row = _call(conn, app_id)
    assert (row["status"], row["error"]) == ("failed", "Cancelled: the employer replied.")


def test_closing_a_job_cancels_its_waiting_call(client, conn, settings, fakes):
    app_id = _followed_up_twice(client, conn, settings, fakes)
    _run(settings, fakes, nz_morning(21, hour=7))

    client.post(f"/applications/{app_id}/outcome", json={"action": "closed"})
    _run(settings, fakes, nz_morning(21, hour=10))

    assert fakes["omni"].dispatched == []
    assert _call(conn, app_id)["error"] == "Cancelled: you closed the job."
