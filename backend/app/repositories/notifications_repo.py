"""WhatsApp updates waiting to go to the user. A dedupe key stops repeats."""

from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg


def add(conn: psycopg.Connection, profile_id: UUID | str, kind: str, text: str,
        dedupe_key: str) -> None:
    conn.execute(
        "insert into notifications (profile_id, kind, text, dedupe_key) values (%s, %s, %s, %s) "
        "on conflict (dedupe_key) do nothing",
        (profile_id, kind, text, dedupe_key),
    )


def queued(conn: psycopg.Connection, limit: int = 20) -> list[dict[str, Any]]:
    return conn.execute(
        "select * from notifications where status = 'queued' order by created_at limit %s",
        (limit,),
    ).fetchall()


def mark_sent(conn: psycopg.Connection, notification_id: UUID | str, now: datetime) -> None:
    conn.execute(
        "update notifications set status = 'sent', sent_at = %s, attempts = attempts + 1 "
        "where id = %s",
        (now, notification_id),
    )


def record_failure(conn: psycopg.Connection, notification_id: UUID | str, error: str,
                   max_attempts: int) -> None:
    conn.execute(
        """
        update notifications set attempts = attempts + 1, error = %s,
            status = case when attempts + 1 >= %s then 'failed' else 'queued' end
        where id = %s
        """,
        (error, max_attempts, notification_id),
    )
