import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.chains.manager import get_chain
from app.core.config import Settings
from app.core.deps import get_settings
from app.core.errors import ProviderError
from app.core.workdays import add_working_days, nz_today
from app.graphs.lead.deps import LeadDeps
from app.graphs.runner import run_graph
from app.main import create_app
from app.providers.jobs.gmail_alerts import EmailMessage
from app.repositories import companies_repo
from app.workers.outbox_job import process_outbox
from tests.documents import make_pdf
from tests.factories import make_job

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"
RESUME_LINES = (
    "Sample Person",
    "sample.person@example.invalid | +64 21 000 0000",
    "Data Engineer",
    "Example Retail Ltd",
    "Built data pipelines with Python and Airflow for 3 teams.",
    "Skills: Python, SQL, Docker, Airflow",
)
ADVERT = "Build pipelines with Python, SQL and Airflow. Send your CV to Jobs@Example.co.nz."

# Hours ahead, so the worker always runs after the real time the API queued at, however
# long the suite has been running.
T = datetime.now(UTC) + timedelta(hours=6)


class OneSource:
    name = "one"

    def __init__(self, job) -> None:
        self.job = job

    def search(self, keywords):
        return [self.job]


class FakeSender:
    def __init__(self, *errors: Exception) -> None:
        self.sent: list[dict] = []
        self.errors = list(errors)

    def send(self, **email) -> str:
        if self.errors:
            raise self.errors.pop(0)
        self.sent.append(email)
        return f"<msg{len(self.sent)}@example.com>"


class FakeMail:
    """Has a reply from these addresses, auto-replies from others, and bounces for others."""

    def __init__(self, replies_from: tuple[str, ...] = (), auto_replies_from: tuple[str, ...] = (),
                 bounced: tuple[str, ...] = ()) -> None:
        self.replies_from = replies_from
        self.auto_replies_from = auto_replies_from
        self.bounced = bounced
        self.queries: list[str] = []

    def list_ids(self, query: str, limit: int) -> list[str]:
        self.queries.append(query)
        if "mailer-daemon" in query:
            return ["b1"] if any(f'"{a}"' in query for a in self.bounced) else []
        if any(f"from:{a}" in query for a in self.replies_from):
            return ["r1"]
        if any(f"from:{a}" in query for a in self.auto_replies_from):
            return ["a1"]
        return []

    def read(self, message_id: str) -> EmailMessage:
        auto = message_id == "a1"
        return EmailMessage(id=message_id, subject="Automatic reply" if auto else "Re: Application",
                            sender="jobs@example.co.nz", text="Thanks", auto_reply=auto)

    def close(self) -> None:
        pass


@pytest.fixture
def settings(database_url, tmp_path) -> Settings:
    return Settings(database_url=database_url, upload_dir=tmp_path, _env_file=None)


@pytest.fixture
def sending(database_url, tmp_path) -> Settings:
    return Settings(database_url=database_url, upload_dir=tmp_path, email_send_enabled=True,
                    email_enabled=True, email_address="me@example.com",
                    email_app_password="app-password", _env_file=None)


@pytest.fixture
def client(settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client


def _approved(client, conn, key="1", description=ADVERT) -> str:
    """Upload the resume, shortlist a job, approve it, let tailoring run, approve the resume."""
    client.post(
        "/profile/resume", files={"file": ("resume.pdf", make_pdf(*RESUME_LINES))}
    ).raise_for_status()
    company = "Example Freight Tech" if key == "1" else f"Example Freight Tech {key}"
    job = make_job(external_id=f"out-{key}", title="Data Engineer",
                   company=company, description=description)
    deps = LeadDeps(conn=conn, sources=[OneSource(job)], score_chain=get_chain("score"), now=T)
    run_graph("lead", {"profile_id": PROFILE_ID}, deps)
    app_id = str(conn.execute(
        "select a.id from applications a join jobs j on j.id = a.job_id "
        "where j.external_id = %s", (f"out-{key}",)
    ).fetchone()["id"])
    client.post(f"/applications/{app_id}/decision", json={"action": "approve"}).raise_for_status()
    client.post(
        f"/applications/{app_id}/resume-decision", json={"action": "approve"}
    ).raise_for_status()
    return app_id


def _application(conn, app_id) -> dict:
    return conn.execute("select * from applications where id = %s", (app_id,)).fetchone()


def _outbox(conn, app_id) -> list[dict]:
    return conn.execute(
        "select * from outbox where application_id = %s order by scheduled_at", (app_id,)
    ).fetchall()


def test_an_approved_resume_waits_in_the_outbox_with_the_advert_address_suggested(client, conn):
    app_id = _approved(client, conn)

    view = client.get("/outbox").json()

    assert view["sending_enabled"] is False
    assert [(i["application_id"], i["suggested_to"]) for i in view["to_send"]] == [
        (app_id, "jobs@example.co.nz")]
    assert view["daily_limit"] == 15


def test_queueing_and_sending_an_email(client, conn, sending):
    app_id = _approved(client, conn)
    queued = client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    assert queued.status_code == 200
    sender = FakeSender()

    report = process_outbox(sending, sender=sender, mail=FakeMail(), now=T)

    assert report["sent"] == 1
    email = sender.sent[0]
    assert email["to"] == "jobs@example.co.nz"
    assert email["subject"] == "Application for Data Engineer – Sample Person"
    assert email["body"].startswith("Kia ora,")
    assert email["attachment"].read_bytes().startswith(b"%PDF-")
    assert email["attachment_name"] == "Sample Person - Data Engineer.pdf"
    row = _application(conn, app_id)
    assert (row["status"], row["apply_method"]) == ("sent", "email")
    assert row["next_follow_up"] == add_working_days(nz_today(T), 5)
    assert _outbox(conn, app_id)[0]["message_id"] == "<msg1@example.com>"
    events = conn.execute(
        "select type from events where application_id = %s", (app_id,)).fetchall()
    assert "emailed" in [e["type"] for e in events]


def test_nothing_is_sent_while_sending_is_switched_off(client, conn, settings):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender()

    process_outbox(settings, sender=sender, mail=FakeMail(), now=T)

    assert sender.sent == []
    assert _outbox(conn, app_id)[0]["status"] == "queued"


def test_the_daily_limit_holds_back_extra_emails(client, conn, sending):
    first, second = _approved(client, conn, "1"), _approved(client, conn, "2")
    assert client.put("/outbox/settings", json={"daily_send_limit": 1}).status_code == 200
    client.post(f"/applications/{first}/send", json={"to": "jobs@example.co.nz"})
    client.post(f"/applications/{second}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender()

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T)
    assert len(sender.sent) == 1
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(hours=1))
    assert len(sender.sent) == 1

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=1))
    assert len(sender.sent) == 2


def test_a_failing_send_is_retried_then_marked_failed_and_can_be_tried_again(
    client, conn, sending
):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender(*[ProviderError("email", "sending failed (OSError)")] * 3)

    for minutes in (0, 15, 30):
        process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(minutes=minutes))

    row = _outbox(conn, app_id)[0]
    assert (row["status"], row["attempts"]) == ("failed", 3)
    assert client.get("/outbox").json()["failed"][0]["error"] == "email: sending failed (OSError)"
    assert client.post(f"/outbox/{row['id']}/retry").status_code == 200
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(hours=1))
    assert _application(conn, app_id)["status"] == "sent"


def test_follow_ups_are_sent_in_the_same_thread_then_the_job_closes(client, conn, sending):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender()
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T)

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=4))
    assert len(sender.sent) == 1  # not due yet

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=7))
    follow_up = sender.sent[1]
    assert follow_up["subject"] == "Re: Application for Data Engineer – Sample Person"
    assert follow_up["reply_to_message_id"] == "<msg1@example.com>"
    assert follow_up.get("attachment") is None
    assert "following up" in follow_up["body"]
    row = _application(conn, app_id)
    assert (row["status"], row["follow_ups"]) == ("followed_up", 1)

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=14))
    assert _application(conn, app_id)["follow_ups"] == 2
    assert len(sender.sent) == 3

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=21))
    assert len(sender.sent) == 3
    assert _application(conn, app_id)["status"] == "closed"


def test_a_reply_stops_follow_ups(client, conn, sending):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender()
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T)
    mail = FakeMail(replies_from=("jobs@example.co.nz",))

    report = process_outbox(sending, sender=sender, mail=mail, now=T + timedelta(days=7))

    assert report["replies"] == 1
    assert f"from:jobs@example.co.nz after:{nz_today(T):%Y/%m/%d}" in mail.queries
    assert _application(conn, app_id)["status"] == "replied"
    assert len(sender.sent) == 1
    events = conn.execute(
        "select type from events where application_id = %s", (app_id,)).fetchall()
    assert "replied" in [e["type"] for e in events]


def test_applying_yourself_tracks_the_job_and_reminds_you_to_follow_up(client, conn, sending):
    app_id = _approved(
        client, conn, description="Build pipelines with Python, SQL and Airflow. Apply online."
    )
    assert client.get("/outbox").json()["to_send"][0]["suggested_to"] is None

    assert client.post(f"/applications/{app_id}/applied").status_code == 200
    row = _application(conn, app_id)
    assert (row["status"], row["apply_method"]) == ("sent", "manual")

    conn.execute(
        "update applications set next_follow_up = current_date - 1 where id = %s", (app_id,))
    conn.commit()
    waiting = client.get("/outbox").json()["waiting"]
    assert [(w["application_id"], w["follow_up_due"], w["apply_method"]) for w in waiting] == [
        (app_id, True, "manual")]

    sender = FakeSender()
    process_outbox(sending, sender=sender, mail=FakeMail(), now=datetime.now(UTC))
    assert sender.sent == []  # no address, so the app never emails a manual application

    client.post(f"/applications/{app_id}/outcome", json={"action": "followed_up"})
    row = _application(conn, app_id)
    assert (row["status"], row["follow_ups"]) == ("followed_up", 1)


def test_cancelling_a_queued_email_puts_it_back_to_send(client, conn):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    outbox_id = client.get("/outbox").json()["queued"][0]["id"]

    assert client.post(f"/outbox/{outbox_id}/cancel").status_code == 200

    view = client.get("/outbox").json()
    assert view["queued"] == []
    assert [i["application_id"] for i in view["to_send"]] == [app_id]


def test_an_invalid_address_is_refused(client, conn):
    app_id = _approved(client, conn)

    response = client.post(f"/applications/{app_id}/send", json={"to": "jobs at example"})

    assert response.status_code == 400
    assert response.json()["detail"] == "That is not a valid email address."
    assert _outbox(conn, app_id) == []


def test_only_approved_resumes_can_be_sent(client, conn):
    app_id = _approved(client, conn)
    conn.execute("update applications set status = 'ready' where id = %s", (app_id,))
    conn.commit()

    response = client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})

    assert response.status_code == 409


def test_marking_a_reply_or_closing_cancels_waiting_follow_ups(client, conn, sending):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    process_outbox(sending, sender=FakeSender(), mail=FakeMail(), now=T)

    assert client.post(
        f"/applications/{app_id}/outcome", json={"action": "replied"}).status_code == 200

    row = _application(conn, app_id)
    assert (row["status"], row["next_follow_up"]) == ("replied", None)
    assert client.get("/outbox").json()["replied"][0]["application_id"] == app_id


def test_a_second_outbox_run_waits_while_one_is_running(client, conn, sending, database_url):
    import psycopg

    from app.workers.outbox_job import LOCK_KEY

    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender()
    with psycopg.connect(database_url, autocommit=True) as other:
        other.execute("select pg_advisory_lock(%s)", (LOCK_KEY,))
        report = process_outbox(sending, sender=sender, mail=FakeMail(), now=T)
        assert report["skipped"] == 1
        assert sender.sent == []
        other.execute("select pg_advisory_unlock(%s)", (LOCK_KEY,))

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T)
    assert len(sender.sent) == 1


def test_an_out_of_office_reply_does_not_count_as_a_reply(client, conn, sending):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender()
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T)

    report = process_outbox(sending, sender=sender, now=T + timedelta(days=1),
                            mail=FakeMail(auto_replies_from=("jobs@example.co.nz",)))

    assert report["replies"] == 0
    assert _application(conn, app_id)["status"] == "sent"


def test_a_bounced_email_returns_the_job_to_ready_to_apply(client, conn, sending):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender()
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T)

    report = process_outbox(sending, sender=sender, now=T + timedelta(days=1),
                            mail=FakeMail(bounced=("jobs@example.co.nz",)))

    assert report["bounced"] == 1
    row = _application(conn, app_id)
    assert (row["status"], row["apply_method"], row["next_follow_up"]) == ("approved", None, None)
    email = _outbox(conn, app_id)[0]
    assert (email["status"], email["error"]) == (
        "failed", "Bounced: jobs@example.co.nz does not accept email.")
    assert [i["application_id"] for i in client.get("/outbox").json()["to_send"]] == [app_id]


def test_the_outbox_suggests_the_hiring_email_when_the_advert_has_none(client, conn):
    app_id = _approved(client, conn, description="Build pipelines with Python and Airflow.")
    company_id = conn.execute(
        "select j.company_id from applications a join jobs j on j.id = a.job_id where a.id = %s",
        (app_id,),
    ).fetchone()["company_id"]
    companies_repo.add_fact(conn, company_id, "hiring_email", "talent@example.co.nz",
                            "website", "high")
    conn.commit()

    view = client.get("/outbox").json()

    assert view["to_send"][0]["suggested_to"] == "talent@example.co.nz"


def test_the_outbox_suggests_a_recruiters_email_when_there_is_no_hiring_email(client, conn):
    app_id = _approved(client, conn, description="Build pipelines with Python and Airflow.")
    company_id = conn.execute(
        "select j.company_id from applications a join jobs j on j.id = a.job_id where a.id = %s",
        (app_id,),
    ).fetchone()["company_id"]
    conn.execute(
        "insert into contacts (company_id, name, role, email, source, confidence) "
        "values (%s, 'Jane Example', 'recruiter', 'jane@example.co.nz', 'website', 'check')",
        (company_id,),
    )
    conn.commit()

    view = client.get("/outbox").json()

    assert view["to_send"][0]["suggested_to"] == "jane@example.co.nz"


def test_the_outbox_does_not_suggest_a_recruiter_found_by_another_source(client, conn):
    app_id = _approved(client, conn, description="Build pipelines with Python and Airflow.")
    company_id = conn.execute(
        "select j.company_id from applications a join jobs j on j.id = a.job_id where a.id = %s",
        (app_id,),
    ).fetchone()["company_id"]
    conn.execute(
        "insert into contacts (company_id, name, role, email, source, confidence) "
        "values (%s, 'Sam Example', 'recruiter', 'sam@example.co.nz', 'tavily', 'check')",
        (company_id,),
    )
    conn.commit()

    view = client.get("/outbox").json()

    assert view["to_send"][0]["suggested_to"] is None


def test_the_outbox_suggests_the_newest_hiring_email(client, conn):
    app_id = _approved(client, conn, description="Build pipelines with Python and Airflow.")
    company_id = conn.execute(
        "select j.company_id from applications a join jobs j on j.id = a.job_id where a.id = %s",
        (app_id,),
    ).fetchone()["company_id"]
    conn.execute(
        "insert into company_facts (company_id, field, value, source, confidence, fetched_at) "
        "values (%s, 'hiring_email', 'old@example.co.nz', 'website', 'high', '2026-01-01'), "
        "(%s, 'hiring_email', 'new@example.co.nz', 'website', 'high', '2026-11-01')",
        (company_id, company_id),
    )
    conn.commit()

    view = client.get("/outbox").json()

    assert view["to_send"][0]["suggested_to"] == "new@example.co.nz"


def _sent_first_email(client, conn, sending):
    app_id = _approved(client, conn)
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender()
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T)
    return app_id, sender


def _draft_id(client, app_id) -> str:
    drafts = client.get("/outbox").json()["drafts"]
    assert [d["application_id"] for d in drafts] == [app_id]
    return drafts[0]["id"]


def test_the_application_email_carries_phone_and_whatsapp(client, conn, sending):
    app_id = _approved(client, conn)
    contact = {"name": "Sample Person", "phone": "021 000 0000", "whatsapp": "+64 22 111 1111"}
    conn.execute(
        "update resumes set content = jsonb_set(content, '{contact}', %s::jsonb) "
        "where profile_id = %s and kind = 'base'",
        (json.dumps(contact), PROFILE_ID),
    )
    conn.commit()
    client.post(f"/applications/{app_id}/send", json={"to": "jobs@example.co.nz"})
    sender = FakeSender()

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T)

    assert sender.sent[0]["body"].endswith(
        "Phone: 021 000 0000\nWhatsApp: +64 22 111 1111"
    )


def test_follow_up_settings_round_trip(client):
    assert client.get("/settings/follow-ups").json() == {"mode": "auto"}

    saved = client.put("/settings/follow-ups", json={"mode": "ask"})

    assert saved.status_code == 200
    assert saved.json() == {"mode": "ask"}
    assert client.get("/settings/follow-ups").json() == {"mode": "ask"}
    assert client.put("/settings/follow-ups", json={"mode": "sometimes"}).status_code == 422


def test_auto_mode_still_sends_follow_ups_itself(client, conn, sending):
    app_id, sender = _sent_first_email(client, conn, sending)

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=7))

    assert len(sender.sent) == 2
    assert _application(conn, app_id)["status"] == "followed_up"
    assert client.get("/outbox").json()["drafts"] == []


def test_ask_mode_creates_one_draft_and_sends_nothing(client, conn, sending):
    app_id, sender = _sent_first_email(client, conn, sending)
    assert client.put("/settings/follow-ups", json={"mode": "ask"}).status_code == 200

    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=7))
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=8))

    assert len(sender.sent) == 1
    drafts = [r for r in _outbox(conn, app_id) if r["status"] == "draft"]
    assert [(d["kind"], d["attachment_path"]) for d in drafts] == [("follow_up", None)]
    assert _application(conn, app_id)["next_follow_up"] is None
    assert _application(conn, app_id)["follow_ups"] == 0
    assert _draft_id(client, app_id)


def test_send_queues_the_draft_and_the_next_run_sends_it(client, conn, sending):
    app_id, sender = _sent_first_email(client, conn, sending)
    client.put("/settings/follow-ups", json={"mode": "ask"})
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=7))
    draft_id = _draft_id(client, app_id)

    response = client.post(f"/outbox/{draft_id}/send")

    assert response.status_code == 200
    assert response.json()["drafts"] == []
    assert [q["id"] for q in response.json()["queued"]] == [draft_id]
    assert client.post(f"/outbox/{draft_id}/send").status_code == 404
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=8))
    assert len(sender.sent) == 2
    assert sender.sent[1]["subject"] == "Re: Application for Data Engineer – Sample Person"
    assert _application(conn, app_id)["follow_ups"] == 1
    assert _application(conn, app_id)["status"] == "followed_up"


def test_sending_something_that_is_not_a_draft_is_not_found(client, conn, sending):
    app_id, _ = _sent_first_email(client, conn, sending)
    sent_id = _outbox(conn, app_id)[0]["id"]

    assert client.post(f"/outbox/{sent_id}/send").status_code == 404


def test_skip_cancels_the_draft_and_stops_follow_ups(client, conn, sending):
    app_id, sender = _sent_first_email(client, conn, sending)
    client.put("/settings/follow-ups", json={"mode": "ask"})
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=7))
    draft_id = _draft_id(client, app_id)

    assert client.post(f"/outbox/{draft_id}/cancel").status_code == 200

    assert [r["status"] for r in _outbox(conn, app_id) if str(r["id"]) == draft_id] == ["cancelled"]
    assert _application(conn, app_id)["next_follow_up"] is None
    assert client.get("/outbox").json()["drafts"] == []
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=14))
    assert len(sender.sent) == 1


def test_a_reply_cancels_a_waiting_draft(client, conn, sending):
    app_id, sender = _sent_first_email(client, conn, sending)
    client.put("/settings/follow-ups", json={"mode": "ask"})
    process_outbox(sending, sender=sender, mail=FakeMail(), now=T + timedelta(days=7))
    draft_id = _draft_id(client, app_id)
    mail = FakeMail(replies_from=("jobs@example.co.nz",))

    process_outbox(sending, sender=sender, mail=mail, now=T + timedelta(days=8))

    assert _application(conn, app_id)["status"] == "replied"
    assert [r["status"] for r in _outbox(conn, app_id) if str(r["id"]) == draft_id] == ["cancelled"]
    assert client.post(f"/outbox/{draft_id}/send").status_code == 404
