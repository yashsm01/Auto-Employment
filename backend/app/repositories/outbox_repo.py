"""The outbox queue, and how far each sent application has got."""

from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

_JOB = """
    from applications a
    join jobs j on j.id = a.job_id
    left join companies c on c.id = j.company_id
"""


def application(
    conn: psycopg.Connection, profile_id: UUID | str, application_id: UUID | str
) -> dict[str, Any] | None:
    return conn.execute(
        f"""
        select a.id, a.status, a.apply_method, a.resume_id, a.follow_ups, a.applied_at,
               j.title, j.description, j.url, j.company_id, c.email as company_email,
               coalesce(c.name, 'Unknown employer') as company
        {_JOB}
        where a.id = %s and a.profile_id = %s
        for update of a
        """,
        (application_id, profile_id),
    ).fetchone()


def company_emails(conn: psycopg.Connection, company_id: UUID | None) -> list[str]:
    if company_id is None:
        return []
    rows = conn.execute(
        "select value from company_facts where company_id = %s and field = 'email' "
        "order by fetched_at",
        (company_id,),
    ).fetchall()
    return [row["value"] for row in rows]


def queue(
    conn: psycopg.Connection,
    *,
    application_id: UUID | str,
    kind: str,
    to: str,
    subject: str,
    body: str,
    attachment_path: Path | None,
    attachment_name: str | None,
    reply_to_message_id: str | None,
    scheduled_at: datetime,
) -> UUID:
    return conn.execute(
        """
        insert into outbox (application_id, channel, kind, to_address, subject, body,
                            attachment_path, attachment_name, reply_to_message_id, scheduled_at)
        values (%s, 'email', %s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (application_id, kind, to, subject, body,
         str(attachment_path) if attachment_path else None, attachment_name,
         reply_to_message_id, scheduled_at),
    ).fetchone()["id"]


def pending(conn: psycopg.Connection, application_id: UUID | str, kind: str) -> dict | None:
    """A queued or failed email of this kind that has not been dealt with yet."""
    return conn.execute(
        "select * from outbox where application_id = %s and kind = %s "
        "and status in ('queued', 'failed') order by scheduled_at desc limit 1",
        (application_id, kind),
    ).fetchone()


def get(conn: psycopg.Connection, profile_id: UUID | str, outbox_id: UUID | str) -> dict | None:
    return conn.execute(
        """
        select o.* from outbox o join applications a on a.id = o.application_id
        where o.id = %s and a.profile_id = %s
        """,
        (outbox_id, profile_id),
    ).fetchone()


def set_status(conn: psycopg.Connection, outbox_id: UUID | str, status: str) -> None:
    conn.execute("update outbox set status = %s where id = %s", (status, outbox_id))


def retry(conn: psycopg.Connection, outbox_id: UUID | str, now: datetime) -> None:
    conn.execute(
        "update outbox set status = 'queued', attempts = 0, error = null, scheduled_at = %s "
        "where id = %s",
        (now, outbox_id),
    )


def next_due(conn: psycopg.Connection, now: datetime, skip: list[str]) -> dict | None:
    return conn.execute(
        """
        select o.*, a.profile_id, j.title
        from outbox o
        join applications a on a.id = o.application_id
        join jobs j on j.id = a.job_id
        where o.status = 'queued' and o.scheduled_at <= %s and o.id <> all(%s::uuid[])
        order by o.scheduled_at, o.id
        limit 1
        """,
        (now, skip),
    ).fetchone()


def mark_sent(conn: psycopg.Connection, outbox_id: UUID | str, message_id: str,
              now: datetime) -> None:
    conn.execute(
        "update outbox set status = 'sent', message_id = %s, sent_at = %s, "
        "attempts = attempts + 1, error = null where id = %s",
        (message_id, now, outbox_id),
    )


def record_failure(conn: psycopg.Connection, outbox_id: UUID | str, error: str,
                   max_attempts: int, retry_at: datetime) -> str:
    return conn.execute(
        """
        update outbox set
            attempts = attempts + 1,
            error = %s,
            scheduled_at = %s,
            status = case when attempts + 1 >= %s then 'failed' else 'queued' end
        where id = %s
        returning status
        """,
        (error, retry_at, max_attempts, outbox_id),
    ).fetchone()["status"]


def sent_since(conn: psycopg.Connection, profile_id: UUID | str, since: datetime) -> int:
    return conn.execute(
        """
        select count(*) as n from outbox o join applications a on a.id = o.application_id
        where a.profile_id = %s and o.status = 'sent' and o.sent_at >= %s
        """,
        (profile_id, since),
    ).fetchone()["n"]


def first_sent(conn: psycopg.Connection, application_id: UUID | str) -> dict | None:
    return conn.execute(
        "select * from outbox where application_id = %s and kind = 'application' "
        "and status = 'sent' order by sent_at limit 1",
        (application_id,),
    ).fetchone()


def cancel_pending_follow_ups(conn: psycopg.Connection, application_id: UUID | str) -> None:
    conn.execute(
        "update outbox set status = 'cancelled' where application_id = %s "
        "and kind = 'follow_up' and status in ('queued', 'failed')",
        (application_id,),
    )


def daily_limit(conn: psycopg.Connection, profile_id: UUID | str) -> int:
    return conn.execute(
        "select daily_send_limit from profiles where id = %s", (profile_id,)
    ).fetchone()["daily_send_limit"]


def set_daily_limit(conn: psycopg.Connection, profile_id: UUID | str, limit: int) -> None:
    conn.execute("update profiles set daily_send_limit = %s where id = %s", (limit, profile_id))


# How far each application has got.

def set_method(conn: psycopg.Connection, application_id: UUID | str, method: str | None) -> None:
    conn.execute(
        "update applications set apply_method = %s, updated_at = now() where id = %s",
        (method, application_id),
    )


def mark_applied(conn: psycopg.Connection, application_id: UUID | str, method: str,
                 now: datetime, next_follow_up: date) -> None:
    conn.execute(
        """
        update applications set status = 'sent', apply_method = %s, applied_at = %s,
            follow_ups = 0, next_follow_up = %s, updated_at = now()
        where id = %s
        """,
        (method, now, next_follow_up, application_id),
    )


def mark_followed_up(conn: psycopg.Connection, application_id: UUID | str,
                     next_follow_up: date | None) -> None:
    conn.execute(
        """
        update applications set status = 'followed_up', follow_ups = follow_ups + 1,
            next_follow_up = %s, updated_at = now()
        where id = %s
        """,
        (next_follow_up, application_id),
    )


def set_outcome(conn: psycopg.Connection, application_id: UUID | str, status: str) -> None:
    conn.execute(
        "update applications set status = %s, next_follow_up = null, updated_at = now() "
        "where id = %s",
        (status, application_id),
    )


def stop_follow_ups(conn: psycopg.Connection, application_id: UUID | str) -> None:
    conn.execute(
        "update applications set next_follow_up = null, updated_at = now() where id = %s",
        (application_id,),
    )


def awaiting_reply(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """Emailed applications with no reply yet, and the address they went to."""
    return conn.execute(
        """
        select a.id, a.profile_id, a.applied_at, o.to_address, j.title,
               coalesce(c.name, 'The employer') as company
        from applications a
        join jobs j on j.id = a.job_id
        left join companies c on c.id = j.company_id
        join lateral (
            select to_address from outbox
            where application_id = a.id and kind = 'application' and status = 'sent'
            order by sent_at limit 1
        ) o on true
        where a.apply_method = 'email' and a.status in ('sent', 'followed_up')
        """
    ).fetchall()


def follow_ups_due(conn: psycopg.Connection, today: date) -> list[dict[str, Any]]:
    return conn.execute(
        """
        select a.id, a.profile_id, a.follow_ups, a.applied_at, j.title
        from applications a join jobs j on j.id = a.job_id
        where a.apply_method = 'email' and a.status in ('sent', 'followed_up')
          and a.next_follow_up is not null and a.next_follow_up <= %s
        """,
        (today,),
    ).fetchall()


def to_send_rows(conn: psycopg.Connection, profile_id: UUID | str) -> list[dict[str, Any]]:
    return conn.execute(
        f"""
        select a.id, j.title, j.description, j.url, j.company_id, c.email as company_email,
               coalesce(c.name, 'Unknown employer') as company, r.id as resume_id,
               coalesce(r.content ->> 'cover_note', '') as cover_note
        {_JOB}
        left join resumes r on r.id = a.resume_id
        where a.profile_id = %s and a.status = 'approved' and a.apply_method is null
        order by a.updated_at desc
        """,
        (profile_id,),
    ).fetchall()


def outbox_rows(conn: psycopg.Connection, profile_id: UUID | str,
                status: str) -> list[dict[str, Any]]:
    return conn.execute(
        """
        select o.*, j.title, coalesce(c.name, 'Unknown employer') as company
        from outbox o
        join applications a on a.id = o.application_id
        join jobs j on j.id = a.job_id
        left join companies c on c.id = j.company_id
        where a.profile_id = %s and o.status = %s
        order by o.scheduled_at
        """,
        (profile_id, status),
    ).fetchall()


def waiting_rows(conn: psycopg.Connection, profile_id: UUID | str) -> list[dict[str, Any]]:
    return conn.execute(
        f"""
        select a.id, a.apply_method, a.applied_at, a.follow_ups, a.next_follow_up, j.title,
               j.url, coalesce(c.name, 'Unknown employer') as company,
               (select to_address from outbox
                where application_id = a.id and kind = 'application' and status = 'sent'
                order by sent_at limit 1) as to_address
        {_JOB}
        where a.profile_id = %s and a.status in ('sent', 'followed_up')
        order by a.next_follow_up nulls last, a.applied_at
        """,
        (profile_id,),
    ).fetchall()


def replied_rows(conn: psycopg.Connection, profile_id: UUID | str) -> list[dict[str, Any]]:
    return conn.execute(
        f"""
        select a.id, a.status, a.updated_at, j.title,
               coalesce(c.name, 'Unknown employer') as company
        {_JOB}
        where a.profile_id = %s and a.status = 'replied'
        order by a.updated_at desc
        limit 20
        """,
        (profile_id,),
    ).fetchall()


def manual_follow_ups_due(conn: psycopg.Connection, today: date) -> list[dict[str, Any]]:
    return conn.execute(
        f"""
        select a.id, a.profile_id, a.next_follow_up, j.title,
               coalesce(c.name, 'the employer') as company
        {_JOB}
        where a.apply_method = 'manual' and a.status in ('sent', 'followed_up')
          and a.next_follow_up is not null and a.next_follow_up <= %s
        """,
        (today,),
    ).fetchall()
