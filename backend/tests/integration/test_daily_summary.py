"""The 18:00 summary of the day's activity. Rows are written with explicit timestamps, so the
New Zealand day is pinned and never depends on the real clock."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.config import Settings
from app.repositories import profiles_repo
from app.services import notify_service
from app.workers import scheduler

pytestmark = pytest.mark.postgres

NZ = ZoneInfo("Pacific/Auckland")
DAY = date(2026, 11, 24)  # New Zealand is UTC+13 on this day
SIX_PM = datetime(2026, 11, 24, 18, 0, tzinfo=NZ)
ADDRESS = "hiring@example-employer.invalid"


def _settings(database_url: str) -> Settings:
    return Settings(database_url=database_url, whatsapp_enabled=True,
                    whatsapp_service_url="http://127.0.0.1:9/send",
                    whatsapp_to="+64210000000", _env_file=None)


def _nz(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=NZ)


def _profile(conn, name: str = "Sample Person") -> str:
    if name == "Sample Person":
        return str(profiles_repo.first_profile_id(conn))
    return str(conn.execute(
        "insert into profiles (full_name) values (%s) returning id", (name,)
    ).fetchone()["id"])


def _application(conn, profile_id: str, kind: str = "advert") -> str:
    job_key = conn.execute("select gen_random_uuid()::text as k").fetchone()["k"]
    company = conn.execute(
        "insert into companies (name) values (%s) returning id", (f"Example {job_key} Ltd",)
    ).fetchone()["id"]
    job = conn.execute(
        "insert into jobs (company_id, source, external_id, title, dedupe_hash) "
        "values (%s, 'example', %s, 'Data Engineer', %s) returning id",
        (company, job_key, job_key),
    ).fetchone()["id"]
    return str(conn.execute(
        "insert into applications (profile_id, job_id, status, kind) "
        "values (%s, %s, 'sent', %s) returning id",
        (profile_id, job, kind),
    ).fetchone()["id"])


def _email(conn, application_id: str, kind: str, sent_at: datetime,
           to_address: str = ADDRESS) -> None:
    conn.execute(
        "insert into outbox (application_id, channel, to_address, body, kind, status, sent_at) "
        "values (%s, 'email', %s, 'Kia ora', %s, 'sent', %s)",
        (application_id, to_address, kind, sent_at),
    )


def _reply(conn, application_id: str, at: datetime) -> None:
    conn.execute(
        "insert into events (type, application_id, payload, created_at) "
        "values ('replied', %s, '{}', %s)",
        (application_id, at),
    )


def _notice(conn, profile_id: str, kind: str, at: datetime, key: str) -> None:
    conn.execute(
        "insert into notifications (profile_id, kind, text, dedupe_key, created_at) "
        "values (%s, %s, 'x', %s, %s)",
        (profile_id, kind, key, at),
    )


def _busy_day(conn, profile_id: str) -> None:
    """Three applications sent, one follow-up, one reply, two bounces, two Google Maps
    employers emailed and one job to apply for on its site."""
    advert_1 = _application(conn, profile_id, "advert")
    advert_2 = _application(conn, profile_id, "advert")
    advert_3 = _application(conn, profile_id, "advert")
    speculative_1 = _application(conn, profile_id, "speculative")
    speculative_2 = _application(conn, profile_id, "speculative")
    _email(conn, advert_1, "application", _nz(DAY, 9))
    _email(conn, advert_2, "application", _nz(DAY, 10))
    _email(conn, advert_3, "application", _nz(DAY, 11))
    _email(conn, speculative_1, "application", _nz(DAY, 12))
    _email(conn, speculative_2, "application", _nz(DAY, 13))
    _email(conn, advert_1, "follow_up", _nz(DAY, 14))
    _reply(conn, advert_2, _nz(DAY, 15))
    _notice(conn, profile_id, "bounced", _nz(DAY, 16), "bounced:one")
    _notice(conn, profile_id, "bounced", _nz(DAY, 16, 5), "bounced:two")
    _notice(conn, profile_id, "auto_apply_yourself", _nz(DAY, 17), "auto-apply-yourself:one")


def test_summary_counts_todays_activity(conn, database_url):
    profile_id = _profile(conn)
    _busy_day(conn, profile_id)

    text = notify_service.daily_summary(conn, profile_id, DAY)

    assert text == ("Today: 3 applications sent, 1 follow-up, 1 reply, 2 bounced emails, "
                    "2 Google Maps employers emailed, 1 job to apply for on its site.")


def test_no_summary_on_a_quiet_day(conn, database_url):
    profile_id = _profile(conn)
    # Activity on the days either side only.
    advert = _application(conn, profile_id)
    _email(conn, advert, "application", _nz(DAY - timedelta(days=1), 23, 59))
    _email(conn, advert, "application", _nz(DAY + timedelta(days=1), 0, 0))

    assert notify_service.daily_summary(conn, profile_id, DAY) is None


def test_summary_is_sent_once_per_day(conn, database_url):
    settings = _settings(database_url)
    profile_id = _profile(conn)
    _busy_day(conn, profile_id)

    notify_service.send_daily_summaries(conn, settings, SIX_PM)
    notify_service.send_daily_summaries(conn, settings, SIX_PM + timedelta(minutes=15))

    rows = conn.execute(
        "select dedupe_key, kind from notifications where kind = 'daily_summary'"
    ).fetchall()
    assert [row["dedupe_key"] for row in rows] == [f"daily-summary:{profile_id}:2026-11-24"]


def test_window_is_the_new_zealand_day_only(conn, database_url):
    profile_id = _profile(conn)
    advert = _application(conn, profile_id)
    _email(conn, advert, "application", _nz(DAY - timedelta(days=1), 23, 59))
    _email(conn, advert, "application", _nz(DAY, 0, 0))
    _email(conn, advert, "application", _nz(DAY, 23, 59))
    _email(conn, advert, "application", _nz(DAY + timedelta(days=1), 0, 0))

    assert notify_service.daily_summary(conn, profile_id, DAY) == "Today: 2 applications sent."


def test_daylight_saving_day_is_a_full_nz_day(conn, database_url):
    # New Zealand daylight saving ends on 5 April 2026, so that day has 25 hours.
    day = date(2026, 4, 5)
    profile_id = _profile(conn)
    advert = _application(conn, profile_id)
    _email(conn, advert, "application", _nz(day, 0, 5))
    _email(conn, advert, "application", _nz(day, 23, 55))
    _email(conn, advert, "application", _nz(day + timedelta(days=1), 0, 0))

    assert notify_service.daily_summary(conn, profile_id, day) == "Today: 2 applications sent."


def test_singular_forms_and_no_addresses(conn, database_url):
    profile_id = _profile(conn)
    advert = _application(conn, profile_id)
    speculative = _application(conn, profile_id, "speculative")
    _email(conn, advert, "application", _nz(DAY, 9))
    _email(conn, advert, "follow_up", _nz(DAY, 10))
    _reply(conn, advert, _nz(DAY, 11))
    _notice(conn, profile_id, "bounced", _nz(DAY, 12), "bounced:single")
    _email(conn, speculative, "application", _nz(DAY, 13))
    _notice(conn, profile_id, "auto_apply_yourself", _nz(DAY, 14), "auto-apply-yourself:single")

    text = notify_service.daily_summary(conn, profile_id, DAY)

    assert text == ("Today: 1 application sent, 1 follow-up, 1 reply, 1 bounced email, "
                    "1 Google Maps employer emailed, 1 job to apply for on its site.")
    assert "@" not in text and ADDRESS not in text


def test_other_profiles_activity_is_not_counted(conn, database_url):
    mine = _profile(conn)
    theirs = _profile(conn, "Other Person")
    _busy_day(conn, theirs)

    assert notify_service.daily_summary(conn, mine, DAY) is None


def test_no_summary_is_queued_without_whatsapp(conn, database_url):
    profile_id = _profile(conn)
    _busy_day(conn, profile_id)
    settings = Settings(database_url=database_url, whatsapp_enabled=False, _env_file=None)

    notify_service.send_daily_summaries(conn, settings, SIX_PM)

    assert conn.execute("select count(*) as n from notifications "
                        "where kind = 'daily_summary'").fetchone()["n"] == 0


def test_scheduler_sends_the_summary_at_six_pm_nz(monkeypatch, database_url):
    monkeypatch.setattr(scheduler, "_catch_up", lambda settings: None)
    settings = Settings(database_url=database_url, _env_file=None)

    running = scheduler.start_scheduler(settings)
    try:
        job = running.get_job("daily-summary")
        assert str(job.trigger.timezone) == "Pacific/Auckland"
        assert "hour='18'" in str(job.trigger) and "minute='0'" in str(job.trigger)
    finally:
        running.shutdown(wait=False)


def test_scheduler_summary_failure_is_logged_not_raised(monkeypatch, caplog, database_url):
    def broken(*args, **kwargs):
        raise RuntimeError("database is down")

    monkeypatch.setattr(scheduler, "connect", broken)

    scheduler.run_daily_summaries(_settings(database_url))

    assert "Daily summary failed" in caplog.text



def test_next_days_activity_gets_its_own_summary(conn, database_url):
    settings = _settings(database_url)
    profile_id = _profile(conn)
    _busy_day(conn, profile_id)
    notify_service.send_daily_summaries(conn, settings, SIX_PM)

    advert = _application(conn, profile_id)
    _email(conn, advert, "application", _nz(DAY + timedelta(days=1), 9))
    notify_service.send_daily_summaries(conn, settings, _nz(DAY + timedelta(days=1), 18))

    keys = conn.execute(
        "select dedupe_key from notifications where kind = 'daily_summary' order by dedupe_key"
    ).fetchall()
    assert [row["dedupe_key"] for row in keys] == [
        f"daily-summary:{profile_id}:2026-11-24",
        f"daily-summary:{profile_id}:2026-11-25",
    ]
