from collections.abc import Sequence
from datetime import datetime
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


# Facts the contact lookup writes from the employer's own pages. They are not research.
# no_unsolicited is a page statement that blocks outreach. It is never shown as a contact.
# site_unreadable records a refused read: the employer is still unresearched.
CONTACT_FIELDS = [
    "email", "hiring_email", "phone", "contact_page", "careers_page", "linkedin",
    "no_unsolicited", "site_unreadable",
]


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
                  where f.company_id = c.id
                    and (f.source in ('places', 'tavily')
                         or (f.source = 'website' and f.field <> all(%s::text[])))
              )
            order by c.id, a.score desc
        ) employers
        order by score desc, name
        limit %s
        """,
        (application_ids, CONTACT_FIELDS, limit),
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


def replace_fact(
    conn: psycopg.Connection,
    company_id: UUID,
    field: str,
    value: str,
    source: str,
    confidence: str,
) -> None:
    """Keep one value for this field from this source, such as the latest Maps rating."""
    conn.execute(
        "delete from company_facts where company_id = %s and field = %s and source = %s",
        (company_id, field, source),
    )
    add_fact(conn, company_id, field, value, source, confidence)


def add_place_details(
    conn: psycopg.Connection,
    company_id: UUID,
    hours: Sequence[str],
    rating: float | None,
    rating_count: int | None,
) -> None:
    """Google Maps opening hours and rating. A rating needs its count to be shown."""
    if hours:
        replace_fact(conn, company_id, "opening_hours", "; ".join(hours), "places", "high")
    if rating is not None and rating_count is not None:
        replace_fact(
            conn, company_id, "rating", f"{rating:g} ({rating_count})", "places", "high"
        )


def delete_website_facts(conn: psycopg.Connection, company_id: UUID, fields: list[str]) -> None:
    """Forget the employer's own page facts for these fields. Other sources are kept."""
    conn.execute(
        "delete from company_facts where company_id = %s and source = 'website' "
        "and field = any(%s::text[])",
        (company_id, fields),
    )


UNREADABLE_FIELD = "site_unreadable"


def set_unreadable(
    conn: psycopg.Connection, company_id: UUID, note: str, source_url: str, fetched_at: datetime
) -> None:
    """The last lookup read no page of the employer's site. Not a contact: see list_facts."""
    clear_unreadable(conn, company_id)
    conn.execute(
        """
        insert into company_facts (company_id, field, value, source, confidence, source_url,
                                   fetched_at)
        values (%s, %s, %s, 'website', 'high', %s, %s)
        """,
        (company_id, UNREADABLE_FIELD, note, source_url, fetched_at),
    )


def clear_unreadable(conn: psycopg.Connection, company_id: UUID) -> None:
    conn.execute(
        "delete from company_facts where company_id = %s and field = %s and source = 'website'",
        (company_id, UNREADABLE_FIELD),
    )


def upsert_website_fact(
    conn: psycopg.Connection,
    company_id: UUID,
    field: str,
    value: str,
    source_url: str | None,
    fetched_at: datetime,
) -> None:
    """A contact fact the employer's own page states. An advert's copy of it becomes the
    website's (the page is the stronger, current source). Maps facts keep their source."""
    conn.execute(
        """
        insert into company_facts (company_id, field, value, source, confidence, source_url,
                                   fetched_at)
        values (%s, %s, %s, 'website', 'high', %s, %s)
        on conflict (company_id, field, value) do update set
            source = 'website', confidence = 'high', source_url = excluded.source_url,
            fetched_at = excluded.fetched_at
        where company_facts.source in ('job_post', 'website')
        """,
        (company_id, field, value, source_url, fetched_at),
    )


def list_facts(conn: psycopg.Connection, company_id: UUID) -> list[dict[str, Any]]:
    return conn.execute(
        """
        select field, value, source, confidence, source_url
        from company_facts
        where company_id = %s and field not in ('site_unreadable', 'no_unsolicited')
        order by field, fetched_at desc
        """,
        (company_id,),
    ).fetchall()
