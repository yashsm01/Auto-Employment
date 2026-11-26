"""Saved employers and Maps usage, stored in settings.data_sources."""

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.schemas.employer import SaveEmployer


def load_data(conn: psycopg.Connection, profile_id: UUID, lock: bool = False) -> dict[str, Any]:
    conn.execute(
        "insert into settings (profile_id) values (%s) on conflict (profile_id) do nothing",
        (profile_id,),
    )
    query = "select data_sources from settings where profile_id = %s"
    row = conn.execute(f"{query} for update" if lock else query, (profile_id,)).fetchone()
    return row["data_sources"]


def update_data(conn: psycopg.Connection, profile_id: UUID, patch: dict[str, Any]) -> None:
    conn.execute(
        """
        update settings
        set data_sources = data_sources || %s, updated_at = now()
        where profile_id = %s
        """,
        (Jsonb(patch), profile_id),
    )


def upsert_company(conn: psycopg.Connection, employer: SaveEmployer) -> UUID:
    row = conn.execute(
        """
        insert into companies (name, google_place_id, address, phone, website, lat, lng)
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (name_key) do update set
            google_place_id = coalesce(companies.google_place_id, excluded.google_place_id),
            address = coalesce(companies.address, excluded.address),
            phone = coalesce(companies.phone, excluded.phone),
            website = coalesce(companies.website, excluded.website),
            lat = coalesce(companies.lat, excluded.lat),
            lng = coalesce(companies.lng, excluded.lng),
            updated_at = now()
        returning id
        """,
        (
            employer.name, employer.place_id, employer.address, employer.phone,
            employer.website, employer.lat, employer.lng,
        ),
    ).fetchone()
    return row["id"]


def companies_by_id(
    conn: psycopg.Connection, company_ids: list[str]
) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        select id, name, address, phone, website, google_place_id
        from companies
        where id = any(%s::uuid[])
        """,
        (company_ids,),
    ).fetchall()
    return {str(row["id"]): row for row in rows}


def applies_to_company(conn: psycopg.Connection, profile_id: UUID, company_id: UUID) -> bool:
    """Whether one of this profile's applications is for a job at this employer."""
    row = conn.execute(
        """
        select exists (
            select 1 from applications a
            join jobs j on j.id = a.job_id
            where a.profile_id = %s and j.company_id = %s
        ) as found
        """,
        (profile_id, company_id),
    ).fetchone()
    return bool(row["found"])
