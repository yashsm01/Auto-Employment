from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.repositories import prep_repo
from app.repositories.prep_repo import month_start_nz

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"


def _application(conn, key: str, company: str = "Example Ltd") -> tuple[str, str]:
    company_id = conn.execute(
        "insert into companies (name) values (%s) "
        "on conflict (name_key) do update set name = excluded.name returning id",
        (company,),
    ).fetchone()["id"]
    job_id = conn.execute(
        "insert into jobs (company_id, source, external_id, title, dedupe_hash) "
        "values (%s, 'example', %s, 'Dev', %s) returning id",
        (company_id, key, f"hash-{key}"),
    ).fetchone()["id"]
    application_id = conn.execute(
        "insert into applications (profile_id, job_id, status) "
        "values (%s, %s, 'shortlisted') returning id",
        (PROFILE_ID, job_id),
    ).fetchone()["id"]
    return str(application_id), str(company_id)


def test_queued_packs_come_out_oldest_first(conn):
    first_app, company = _application(conn, "1")
    second_app, _ = _application(conn, "2")
    first = prep_repo.insert_queued(conn, PROFILE_ID, first_app, company, None)
    conn.execute(
        "update prep_packs set created_at = now() - interval '1 minute' where id = %s", (first,)
    )
    second = prep_repo.insert_queued(conn, PROFILE_ID, second_app, company, "extra text")

    assert prep_repo.next_queued(conn, [])["id"] == first
    assert prep_repo.next_queued(conn, [str(first)])["id"] == second
    assert prep_repo.get(conn, second)["extra"] == "extra text"


def test_open_for_application_sees_queued_and_running_only(conn):
    app_id, company = _application(conn, "1")
    pack_id = prep_repo.insert_queued(conn, PROFILE_ID, app_id, company, None)
    assert prep_repo.open_for_application(conn, app_id)["id"] == pack_id

    prep_repo.mark_running(conn, pack_id)
    assert prep_repo.open_for_application(conn, app_id)["status"] == "running"

    prep_repo.finish(
        conn, pack_id, content={"tips": []}, sources=[], facts=[], notes=["n"],
        cost_usd=0.04, places_calls=1,
    )
    assert prep_repo.open_for_application(conn, app_id) is None
    latest = prep_repo.latest_for_application(conn, PROFILE_ID, app_id)
    assert latest["status"] == "done"
    assert latest["notes"] == ["n"]
    assert latest["finished_at"] is not None


def test_a_failed_pack_keeps_its_error(conn):
    app_id, company = _application(conn, "1")
    pack_id = prep_repo.insert_queued(conn, PROFILE_ID, app_id, company, None)

    prep_repo.fail(conn, pack_id, "Tavily: HTTP 500")

    row = prep_repo.get(conn, pack_id)
    assert (row["status"], row["error"]) == ("failed", "Tavily: HTTP 500")


def test_usage_and_places_calls_count_since_a_date(conn):
    app_id, company = _application(conn, "1")
    old = prep_repo.insert_queued(conn, PROFILE_ID, app_id, company, None)
    conn.execute(
        "update prep_packs set created_at = now() - interval '40 days', places_calls = 5 "
        "where id = %s",
        (old,),
    )
    new = prep_repo.insert_queued(conn, PROFILE_ID, app_id, company, None)
    conn.execute("update prep_packs set places_calls = 2 where id = %s", (new,))
    since = datetime.now(UTC) - timedelta(days=30)

    assert prep_repo.count_since(conn, PROFILE_ID, since) == 1
    assert prep_repo.places_calls_since(conn, PROFILE_ID, since) == 2


def test_usage_counts_by_new_zealand_month():
    # 2026-11-30 11:30 UTC is 1 December 00:30 in New Zealand.
    assert month_start_nz(datetime(2026, 11, 30, 11, 30, tzinfo=UTC)) == datetime(
        2026, 12, 1, tzinfo=ZoneInfo("Pacific/Auckland")
    )
    assert month_start_nz(datetime(2026, 11, 15, 3, 0, tzinfo=UTC)) == datetime(
        2026, 11, 1, tzinfo=ZoneInfo("Pacific/Auckland")
    )


def test_recent_employer_facts_only_from_done_packs_inside_the_window(conn):
    app_id, company = _application(conn, "1")
    stale = prep_repo.insert_queued(conn, PROFILE_ID, app_id, company, None)
    prep_repo.finish(
        conn, stale, content={}, sources=[{"id": "s1"}], facts=[{"text": "old"}], notes=[],
        cost_usd=0, places_calls=0,
    )
    conn.execute(
        "update prep_packs set finished_at = now() - interval '40 days' where id = %s", (stale,)
    )
    since = datetime.now(UTC) - timedelta(days=30)
    assert prep_repo.recent_employer_facts(conn, company, since) is None

    queued = prep_repo.insert_queued(conn, PROFILE_ID, app_id, company, None)
    assert prep_repo.recent_employer_facts(conn, company, since) is None

    prep_repo.finish(
        conn, queued, content={}, sources=[{"id": "s2"}], facts=[{"text": "new"}], notes=[],
        cost_usd=0, places_calls=0,
    )
    assert prep_repo.recent_employer_facts(conn, company, since) == (
        [{"text": "new"}],
        [{"id": "s2"}],
    )


def test_a_stuck_deep_search_lock_is_cleared_after_ten_minutes(conn):
    from app.repositories import runs_repo

    conn.execute(
        "insert into graph_runs (graph, status, input, started_at) "
        "values ('prep', 'running', '{}', now() - interval '11 minutes')"
    )

    assert runs_repo.start(conn, "prep", {}) is not None


def test_only_a_queued_pack_can_be_marked_running(conn):
    app_id, company = _application(conn, "1")
    pack_id = prep_repo.insert_queued(conn, PROFILE_ID, app_id, company, None)

    assert prep_repo.mark_running(conn, pack_id) is True
    assert prep_repo.mark_running(conn, pack_id) is False
