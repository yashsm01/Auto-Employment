from uuid import UUID

import psycopg

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
