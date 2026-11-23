from collections.abc import Iterable
from uuid import UUID

import psycopg

from app.schemas.job import JobDraft


def existing_hashes(conn: psycopg.Connection, hashes: Iterable[str]) -> set[str]:
    rows = conn.execute(
        "select dedupe_hash from jobs where dedupe_hash = any(%s)", (list(hashes),)
    ).fetchall()
    return {row["dedupe_hash"] for row in rows}


def insert(
    conn: psycopg.Connection, job: JobDraft, company_id: UUID, dedupe_hash: str
) -> UUID | None:
    """Store a job. Returns None if the source's listing is already stored."""
    row = conn.execute(
        """
        insert into jobs (
            company_id, source, external_id, title, location, region, salary_min, salary_max,
            url, description, posted_at, closes_at, dedupe_hash
        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict do nothing
        returning id
        """,
        (
            company_id, job.source, job.external_id, job.title, job.location, job.region,
            job.salary_min, job.salary_max, job.url, job.description, job.posted_at,
            job.closes_at, dedupe_hash,
        ),
    ).fetchone()
    return row["id"] if row else None
