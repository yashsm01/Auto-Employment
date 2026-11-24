from typing import Any
from uuid import UUID

import psycopg

from app.providers.company.places import PlaceMatch
from app.schemas.job import JobDraft

_FACT_FIELDS = {
    "website": "company_website",
    "phone": "company_phone",
    "email": "company_email",
    "address": "company_address",
}


def upsert_from_job(conn: psycopg.Connection, job: JobDraft) -> UUID:
    """Create the employer or fill gaps. Existing values are never overwritten."""
    row = conn.execute(
        """
        insert into companies (name, website, phone, email, address)
        values (%s, %s, %s, %s, %s)
        on conflict (name_key) do update set
            website = coalesce(companies.website, excluded.website),
            phone = coalesce(companies.phone, excluded.phone),
            email = coalesce(companies.email, excluded.email),
            address = coalesce(companies.address, excluded.address),
            updated_at = now()
        returning id
        """,
        (job.company, job.company_website, job.company_phone, job.company_email,
         job.company_address),
    ).fetchone()
    return row["id"]


def add_job_post_facts(conn: psycopg.Connection, company_id: UUID, job: JobDraft) -> None:
    """Record where each employer detail came from."""
    for field, attribute in _FACT_FIELDS.items():
        value = getattr(job, attribute)
        if value:
            conn.execute(
                """
                insert into company_facts (company_id, field, value, source, confidence, source_url)
                values (%s, %s, %s, 'job_post', 'medium', %s)
                on conflict (company_id, field, value) do nothing
                """,
                (company_id, field, value, job.url),
            )


def needing_research(
    conn: psycopg.Connection, application_ids: list[UUID], limit: int
) -> list[dict[str, Any]]:
    """Employers of these applications with no researched facts, best match first."""
    return conn.execute(
        """
        select * from (
            select distinct on (c.id)
                c.id, c.name, c.website, j.location, j.region, a.score
            from applications a
            join jobs j on j.id = a.job_id
            join companies c on c.id = j.company_id
            where a.id = any(%s)
              and not exists (
                  select 1 from company_facts f
                  where f.company_id = c.id and f.source in ('places', 'website', 'tavily')
              )
            order by c.id, a.score desc
        ) employers
        order by score desc, name
        limit %s
        """,
        (application_ids, limit),
    ).fetchall()


def apply_place(conn: psycopg.Connection, company_id: UUID, place: PlaceMatch) -> None:
    conn.execute(
        """
        update companies set
            google_place_id = coalesce(google_place_id, %s),
            address = coalesce(address, %s),
            lat = coalesce(lat, %s),
            lng = coalesce(lng, %s),
            website = coalesce(website, %s),
            phone = coalesce(phone, %s),
            updated_at = now()
        where id = %s
        """,
        (place.place_id, place.address, place.lat, place.lng, place.website, place.phone,
         company_id),
    )


def set_about(conn: psycopg.Connection, company_id: UUID, about: str) -> None:
    conn.execute(
        "update companies set about = coalesce(about, %s), updated_at = now() where id = %s",
        (about, company_id),
    )


def add_fact(
    conn: psycopg.Connection,
    company_id: UUID,
    field: str,
    value: str,
    source: str,
    confidence: str,
    source_url: str | None = None,
) -> None:
    conn.execute(
        """
        insert into company_facts (company_id, field, value, source, confidence, source_url)
        values (%s, %s, %s, %s, %s, %s)
        on conflict (company_id, field, value) do nothing
        """,
        (company_id, field, value, source, confidence, source_url),
    )


def list_facts(conn: psycopg.Connection, company_id: UUID) -> list[dict[str, Any]]:
    return conn.execute(
        """
        select field, value, source, confidence, source_url
        from company_facts
        where company_id = %s
        order by field, fetched_at
        """,
        (company_id,),
    ).fetchall()
