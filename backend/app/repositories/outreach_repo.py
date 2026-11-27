"""Google Maps outreach: blocked employers, and the speculative applications made for them."""

from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg


def blocked(conn: psycopg.Connection, profile_id: UUID) -> set[UUID]:
    rows = conn.execute(
        "select company_id from outreach_blocks where profile_id = %s", (profile_id,)
    ).fetchall()
    return {row["company_id"] for row in rows}


def block(conn: psycopg.Connection, profile_id: UUID, company_id: UUID, reason: str) -> None:
    conn.execute(
        """
        insert into outreach_blocks (profile_id, company_id, reason)
        values (%s, %s, %s)
        on conflict (profile_id, company_id) do nothing
        """,
        (profile_id, company_id, reason),
    )


def block_rows(conn: psycopg.Connection, profile_id: UUID) -> list[dict[str, Any]]:
    return conn.execute(
        "select company_id, reason, created_at from outreach_blocks where profile_id = %s",
        (profile_id,),
    ).fetchall()


def first_speculative_sends(conn: psycopg.Connection, profile_id: UUID) -> dict[UUID, datetime]:
    """When the first email of each speculative application was sent, by employer."""
    rows = conn.execute(
        """
        select j.company_id, min(o.sent_at) as sent_at
        from outbox o
        join applications a on a.id = o.application_id
        join jobs j on j.id = a.job_id
        where a.profile_id = %s and a.kind = 'speculative'
          and o.kind = 'application' and o.status = 'sent' and j.company_id is not null
        group by j.company_id
        """,
        (profile_id,),
    ).fetchall()
    return {row["company_id"]: row["sent_at"] for row in rows}


def created_since(conn: psycopg.Connection, profile_id: UUID, since: datetime) -> int:
    """Speculative applications this profile has created since the given time."""
    return conn.execute(
        """
        select count(*) as n from applications
        where profile_id = %s and kind = 'speculative' and created_at >= %s
        """,
        (profile_id, since),
    ).fetchone()["n"]


def company_for_outreach(conn: psycopg.Connection, company_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        "select id, name, address, about, industry, website from companies where id = %s",
        (company_id,),
    ).fetchone()


def nearby_job(conn: psycopg.Connection, company_id: UUID) -> UUID | None:
    """The Maps job for this employer, shared by every profile that prospects it."""
    row = conn.execute(
        "select id from jobs where company_id = %s and source = 'nearby' "
        "order by created_at, id limit 1",
        (company_id,),
    ).fetchone()
    return row["id"] if row else None


def insert_speculative(
    conn: psycopg.Connection, profile_id: UUID, job_id: UUID, now: datetime
) -> UUID:
    """A speculative application, approved at once. It has no tailoring step."""
    row = conn.execute(
        """
        insert into applications (profile_id, job_id, status, kind, created_at, updated_at,
                                  auto_approved_at)
        values (%s, %s, 'approved', 'speculative', %s, %s, %s)
        returning id
        """,
        (profile_id, job_id, now, now, now),
    ).fetchone()
    return row["id"]


def has_no_unsolicited(conn: psycopg.Connection, company_id: UUID) -> bool:
    """Whether the employer's own page says it does not want unsolicited applications."""
    row = conn.execute(
        "select exists (select 1 from company_facts where company_id = %s "
        "and field = 'no_unsolicited') as found",
        (company_id,),
    ).fetchone()
    return bool(row["found"])
