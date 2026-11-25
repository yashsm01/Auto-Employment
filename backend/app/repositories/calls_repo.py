"""AI phone calls: queued, ringing, then done or failed."""

from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


def queue(conn: psycopg.Connection, *, profile_id: UUID | str, application_id: UUID | str | None,
          purpose: str, to_number: str) -> UUID:
    return conn.execute(
        "insert into calls (profile_id, application_id, purpose, to_number) "
        "values (%s, %s, %s, %s) returning id",
        (profile_id, application_id, purpose, to_number),
    ).fetchone()["id"]


def exists_for_application(conn: psycopg.Connection, application_id: UUID | str) -> bool:
    return conn.execute(
        "select 1 from calls where application_id = %s and purpose = 'follow_up' limit 1",
        (application_id,),
    ).fetchone() is not None


def count_since(conn: psycopg.Connection, profile_id: UUID | str, since: datetime) -> int:
    return conn.execute(
        "select count(*) as n from calls where profile_id = %s and created_at >= %s",
        (profile_id, since),
    ).fetchone()["n"]


def queued(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return conn.execute(
        "select * from calls where status = 'queued' order by created_at"
    ).fetchall()


def ringing(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return conn.execute(
        "select * from calls where status = 'ringing' order by dispatched_at"
    ).fetchall()


def mark_ringing(conn: psycopg.Connection, call_id: UUID | str, request_id: str,
                 now: datetime) -> None:
    conn.execute(
        "update calls set status = 'ringing', request_id = %s, dispatched_at = %s where id = %s",
        (request_id, now, call_id),
    )


def finish(conn: psycopg.Connection, call_id: UUID | str, *, status: str, log_id: str | None,
           duration: int | None, transcript: str | None, extracted: dict[str, Any],
           error: str | None, now: datetime) -> None:
    conn.execute(
        """
        update calls set status = %s, omnidim_call_id = %s, duration_sec = %s, transcript = %s,
            extracted = %s, error = %s, finished_at = %s
        where id = %s
        """,
        (status, log_id, duration, transcript, Jsonb(extracted), error, now, call_id),
    )


def fail(conn: psycopg.Connection, call_id: UUID | str, error: str, now: datetime) -> None:
    conn.execute(
        "update calls set status = 'failed', error = %s, finished_at = %s where id = %s",
        (error, now, call_id),
    )


def recent(conn: psycopg.Connection, profile_id: UUID | str, limit: int = 20) -> list[dict]:
    return conn.execute(
        """
        select c.*, j.title, coalesce(co.name, '') as company
        from calls c
        left join applications a on a.id = c.application_id
        left join jobs j on j.id = a.job_id
        left join companies co on co.id = j.company_id
        where c.profile_id = %s
        order by c.created_at desc
        limit %s
        """,
        (profile_id, limit),
    ).fetchall()


def cancel_queued(conn: psycopg.Connection, application_id: UUID | str, reason: str) -> None:
    """A call not yet made is cancelled when the job no longer needs it."""
    conn.execute(
        "update calls set status = 'failed', error = %s, finished_at = now() "
        "where application_id = %s and status = 'queued'",
        (reason, application_id),
    )
