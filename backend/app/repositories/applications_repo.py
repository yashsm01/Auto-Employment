from typing import Any
from uuid import UUID

import psycopg

from app.schemas.job import ScoreResult

_CARD_COLUMNS = """
    a.id, a.status, a.score, a.matched_skills, a.missing_skills, a.score_reason,
    j.title, j.location, j.region, j.salary_min, j.salary_max, j.source, j.url,
    coalesce(c.name, 'Unknown employer') as company
"""
_CARD_JOIN = """
    from applications a
    join jobs j on j.id = a.job_id
    left join companies c on c.id = j.company_id
"""


def record_score(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    job_id: UUID,
    result: ScoreResult,
    status: str,
) -> UUID:
    row = conn.execute(
        """
        insert into applications (
            profile_id, job_id, score, matched_skills, missing_skills, score_reason, status
        ) values (%s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (profile_id, job_id, result.score, result.matched_skills, result.missing_skills,
         result.reason, status),
    ).fetchone()
    return row["id"]


def mark_shortlisted(conn: psycopg.Connection, application_ids: list[UUID]) -> None:
    conn.execute(
        """
        update applications set status = 'shortlisted', updated_at = now()
        where id = any(%s) and status = 'found'
        """,
        (application_ids,),
    )


def list_by_status(
    conn: psycopg.Connection, profile_id: UUID, statuses: list[str]
) -> list[dict[str, Any]]:
    return conn.execute(
        f"""
        select {_CARD_COLUMNS}
        {_CARD_JOIN}
        where a.profile_id = %s and a.status = any(%s)
        order by a.score desc nulls last, a.created_at, a.id
        """,
        (profile_id, statuses),
    ).fetchall()


def stats(conn: psycopg.Connection, profile_id: UUID) -> dict[str, int]:
    return conn.execute(
        """
        select
            count(*) filter (
                where created_at >= date_trunc('day', now() at time zone 'Pacific/Auckland')
                    at time zone 'Pacific/Auckland'
            ) as found_today,
            count(*) filter (where status = 'shortlisted') as shortlisted,
            count(*) filter (where status = 'ready') as ready_to_send,
            count(*) filter (
                where status = 'replied' and updated_at >= now() - interval '7 days'
            ) as replies_this_week
        from applications
        where profile_id = %s
        """,
        (profile_id,),
    ).fetchone()


def lock(
    conn: psycopg.Connection, profile_id: UUID, application_id: UUID
) -> dict[str, Any] | None:
    return conn.execute(
        """
        select a.id, a.status, j.company_id
        from applications a join jobs j on j.id = a.job_id
        where a.id = %s and a.profile_id = %s
        for update of a
        """,
        (application_id, profile_id),
    ).fetchone()


def set_status(conn: psycopg.Connection, application_id: UUID, status: str) -> None:
    conn.execute(
        "update applications set status = %s, updated_at = now() where id = %s",
        (status, application_id),
    )


def add_feedback(
    conn: psycopg.Connection, application_id: UUID, action: str, reason: str | None
) -> None:
    conn.execute(
        "insert into feedback (application_id, action, reason) values (%s, %s, %s)",
        (application_id, action, reason),
    )
