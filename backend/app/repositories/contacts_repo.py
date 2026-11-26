from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg


def get_company(conn: psycopg.Connection, company_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        """
        select id, name, website, phone, email, linkedin_url, contacts_checked_at
        from companies where id = %s
        """,
        (company_id,),
    ).fetchone()


def set_checked(conn: psycopg.Connection, company_id: UUID, checked_at: datetime) -> None:
    conn.execute(
        "update companies set contacts_checked_at = %s where id = %s",
        (checked_at, company_id),
    )


def fill_email(conn: psycopg.Connection, company_id: UUID, email: str) -> None:
    """Set the company's general email only while it is empty."""
    conn.execute(
        "update companies set email = %s where id = %s and coalesce(email, '') = ''",
        (email, company_id),
    )


def fill_linkedin(conn: psycopg.Connection, company_id: UUID, url: str) -> None:
    conn.execute(
        """
        update companies set linkedin_url = %s
        where id = %s and coalesce(linkedin_url, '') = ''
        """,
        (url, company_id),
    )


def delete_website_recruiters(conn: psycopg.Connection, company_id: UUID) -> None:
    conn.execute(
        "delete from contacts where company_id = %s and role = 'recruiter' and source = 'website'",
        (company_id,),
    )


def add_recruiter(
    conn: psycopg.Connection,
    company_id: UUID,
    *,
    name: str,
    title: str,
    email: str | None,
    phone: str | None,
    source_url: str | None,
    checked_at: datetime,
) -> None:
    conn.execute(
        """
        insert into contacts
            (company_id, name, title, role, email, phone, source, confidence, source_url,
             checked_at)
        values (%s, %s, %s, 'recruiter', %s, %s, 'website', 'check', %s, %s)
        """,
        (company_id, name, title, email, phone, source_url, checked_at),
    )


def list_recruiters(conn: psycopg.Connection, company_id: UUID) -> list[dict[str, Any]]:
    return conn.execute(
        """
        select name, title, email, phone, source_url
        from contacts
        where company_id = %s and role = 'recruiter' and source = 'website'
        order by name
        """,
        (company_id,),
    ).fetchall()
