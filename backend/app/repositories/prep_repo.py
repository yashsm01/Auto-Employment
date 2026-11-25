"""Preparation packs from deep search, and the queue they wait in."""

from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb

NZ_TIME = ZoneInfo("Pacific/Auckland")


def month_start_nz(now: datetime) -> datetime:
    """Start of the New Zealand calendar month that `now` falls in."""
    local = now.astimezone(NZ_TIME)
    return datetime(local.year, local.month, 1, tzinfo=NZ_TIME)


def insert_queued(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    application_id: UUID | str,
    company_id: UUID | str | None,
    extra: str | None,
) -> UUID:
    return conn.execute(
        """
        insert into prep_packs (profile_id, application_id, company_id, extra)
        values (%s, %s, %s, %s)
        returning id
        """,
        (profile_id, application_id, company_id, extra),
    ).fetchone()["id"]


def get(conn: psycopg.Connection, pack_id: UUID | str) -> dict[str, Any] | None:
    return conn.execute("select * from prep_packs where id = %s", (pack_id,)).fetchone()


def open_for_application(
    conn: psycopg.Connection, application_id: UUID | str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        select * from prep_packs
        where application_id = %s and status in ('queued', 'running')
        order by created_at desc
        limit 1
        """,
        (application_id,),
    ).fetchone()


def next_queued(conn: psycopg.Connection, skip: list[str]) -> dict[str, Any] | None:
    return conn.execute(
        """
        select * from prep_packs
        where status = 'queued' and id <> all(%s::uuid[])
        order by created_at, id
        limit 1
        for update skip locked
        """,
        (skip,),
    ).fetchone()


def mark_running(conn: psycopg.Connection, pack_id: UUID | str) -> bool:
    """Claim a queued pack. False if another worker already took it."""
    return conn.execute(
        "update prep_packs set status = 'running', started_at = now() "
        "where id = %s and status = 'queued'",
        (pack_id,),
    ).rowcount == 1


def finish(
    conn: psycopg.Connection,
    pack_id: UUID | str,
    *,
    content: dict[str, Any],
    sources: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    notes: list[str],
    cost_usd: float,
    places_calls: int,
) -> None:
    conn.execute(
        """
        update prep_packs set
            status = 'done', error = null, content = %s, sources = %s, facts = %s,
            notes = %s, cost_usd = %s, places_calls = %s, finished_at = now()
        where id = %s
        """,
        (
            Jsonb(content), Jsonb(sources), Jsonb(facts), Jsonb(notes),
            cost_usd, places_calls, pack_id,
        ),
    )


def fail(conn: psycopg.Connection, pack_id: UUID | str, error: str) -> None:
    conn.execute(
        "update prep_packs set status = 'failed', error = %s, finished_at = now() where id = %s",
        (error, pack_id),
    )


def latest_for_application(
    conn: psycopg.Connection, profile_id: UUID | str, application_id: UUID | str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        select * from prep_packs
        where profile_id = %s and application_id = %s
        order by created_at desc, id desc
        limit 1
        """,
        (profile_id, application_id),
    ).fetchone()


def count_since(conn: psycopg.Connection, profile_id: UUID | str, since: datetime) -> int:
    return conn.execute(
        "select count(*) as n from prep_packs where profile_id = %s and created_at >= %s "
        "and not (status = 'failed' and cost_usd = 0)",
        (profile_id, since),
    ).fetchone()["n"]


def places_calls_since(
    conn: psycopg.Connection, profile_id: UUID | str, since: datetime
) -> int:
    return conn.execute(
        "select coalesce(sum(places_calls), 0) as n from prep_packs "
        "where profile_id = %s and created_at >= %s",
        (profile_id, since),
    ).fetchone()["n"]


def recent_employer_facts(
    conn: psycopg.Connection, company_id: UUID | str, since: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """Facts and sources of the newest finished pack for this employer, if recent enough."""
    row = conn.execute(
        """
        select facts, sources from prep_packs
        where company_id = %s and status = 'done' and finished_at >= %s
        order by finished_at desc
        limit 1
        """,
        (company_id, since),
    ).fetchone()
    return (row["facts"], row["sources"]) if row else None


def job_extras(conn: psycopg.Connection, application_id: UUID | str) -> dict[str, Any]:
    """The advert URL, the employer's website and address, and the user's regions."""
    return conn.execute(
        """
        select j.url, c.website, c.address, p.regions
        from applications a
        join jobs j on j.id = a.job_id
        join profiles p on p.id = a.profile_id
        left join companies c on c.id = j.company_id
        where a.id = %s
        """,
        (application_id,),
    ).fetchone()


def requeue(conn: psycopg.Connection, pack_id: UUID | str) -> None:
    conn.execute(
        "update prep_packs set status = 'queued', started_at = null where id = %s", (pack_id,)
    )


def fail_stale(conn: psycopg.Connection, minutes: int, error: str) -> int:
    """Packs left 'running' for too long were cut off, for example by a restart."""
    return conn.execute(
        """
        update prep_packs set status = 'failed', error = %s, finished_at = now()
        where status = 'running' and started_at < now() - make_interval(mins => %s)
        """,
        (error, minutes),
    ).rowcount


def application_company(
    conn: psycopg.Connection, profile_id: UUID | str, application_id: UUID | str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        select a.id, j.company_id
        from applications a
        join jobs j on j.id = a.job_id
        where a.id = %s and a.profile_id = %s
        """,
        (application_id, profile_id),
    ).fetchone()
