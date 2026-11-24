from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.workers import scheduler
from app.workers.scheduler import is_catch_up_due, run_scheduled_search, start_scheduler

# 24 Nov 2026 in New Zealand is UTC+13.
BEFORE_SEVEN_NZ = datetime(2026, 11, 23, 17, 0, tzinfo=UTC)  # 6:00 am NZ, 24 Nov
AFTER_SEVEN_NZ = datetime(2026, 11, 23, 19, 0, tzinfo=UTC)  # 8:00 am NZ, 24 Nov


@pytest.mark.parametrize(
    ("last_run", "now", "due"),
    [
        (None, AFTER_SEVEN_NZ, True),
        (datetime(2026, 11, 23, 18, 30, tzinfo=UTC), AFTER_SEVEN_NZ, False),  # 7:30 am today
        (datetime(2026, 11, 22, 18, 30, tzinfo=UTC), AFTER_SEVEN_NZ, True),  # yesterday's run
        (datetime(2026, 11, 22, 18, 30, tzinfo=UTC), BEFORE_SEVEN_NZ, False),  # still covered
        (datetime(2026, 11, 21, 18, 30, tzinfo=UTC), BEFORE_SEVEN_NZ, True),  # missed yesterday
    ],
)
def test_catch_up_after_the_computer_was_off(last_run, now, due):
    assert is_catch_up_due(last_run, now, hour=7) is due


def test_scheduler_does_not_start_when_disabled():
    settings = Settings(database_url="postgresql://x", scheduler_enabled=False, _env_file=None)

    assert start_scheduler(settings) is None


def test_scheduler_does_not_start_without_a_database():
    assert start_scheduler(Settings(database_url="", _env_file=None)) is None


def test_scheduler_runs_daily_at_the_configured_nz_hour(monkeypatch):
    monkeypatch.setattr(scheduler, "_catch_up", lambda settings: None)
    settings = Settings(database_url="postgresql://x", daily_search_hour=7, _env_file=None)

    running = start_scheduler(settings)
    try:
        trigger = running.get_job("daily-lead-search").trigger
        assert str(trigger.timezone) == "Pacific/Auckland"
        assert "hour='7'" in str(trigger)
    finally:
        running.shutdown(wait=False)


def test_tests_and_default_app_do_not_start_the_scheduler(monkeypatch):
    def fail(settings):
        raise AssertionError("scheduler started")

    monkeypatch.setattr("app.main.start_scheduler", fail)

    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200


@pytest.mark.postgres
def test_scheduled_search_records_a_run(database_url, conn):
    run_scheduled_search(Settings(database_url=database_url, _env_file=None))

    run = conn.execute("select graph, status from graph_runs").fetchone()
    assert run == {"graph": "lead", "status": "ok"}


@pytest.mark.postgres
def test_scheduled_search_skips_quietly_when_one_is_running(database_url, conn):
    conn.execute("insert into graph_runs (graph, status) values ('lead', 'running')")
    conn.commit()

    run_scheduled_search(Settings(database_url=database_url, _env_file=None))

    assert conn.execute("select count(*) as n from graph_runs").fetchone()["n"] == 1
