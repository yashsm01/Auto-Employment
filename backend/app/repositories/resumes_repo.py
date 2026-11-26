from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


def latest_base(conn: psycopg.Connection, profile_id: UUID | str) -> dict[str, Any] | None:
    return conn.execute(
        """
        select id, content, file_path
        from resumes
        where profile_id = %s and kind = 'base'
        order by created_at desc
        limit 1
        """,
        (profile_id,),
    ).fetchone()


def save_sections(conn: psycopg.Connection, resume_id: UUID, sections: dict[str, Any]) -> None:
    conn.execute(
        "update resumes set content = content || jsonb_build_object('sections', %s::jsonb) "
        "where id = %s",
        (Jsonb(sections), resume_id),
    )


def save_master(
    conn: psycopg.Connection,
    resume_id: UUID,
    sections: dict[str, Any],
    contact: dict[str, Any],
    template: str,
) -> None:
    """Sections, contact and template in one statement, so they save together."""
    conn.execute(
        "update resumes set content = content || jsonb_build_object("
        "'sections', %s::jsonb, 'contact', %s::jsonb, 'template', %s::text) "
        "where id = %s",
        (Jsonb(sections), Jsonb(contact), template, resume_id),
    )


def set_contact(conn: psycopg.Connection, resume_id: UUID, contact: dict[str, Any]) -> None:
    conn.execute(
        "update resumes set content = content || jsonb_build_object('contact', %s::jsonb) "
        "where id = %s",
        (Jsonb(contact), resume_id),
    )


def insert_tailored(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    application_id: UUID | str,
    content: dict[str, Any],
    file_path: str,
    facts_used: list[str],
) -> UUID:
    row = conn.execute(
        """
        insert into resumes (profile_id, kind, application_id, content, file_path, facts_used)
        values (%s, 'tailored', %s, %s, %s, %s)
        returning id
        """,
        (profile_id, application_id, Jsonb(content), file_path, Jsonb(facts_used)),
    ).fetchone()
    return row["id"]


def get_tailored(
    conn: psycopg.Connection, profile_id: UUID, resume_id: UUID
) -> dict[str, Any] | None:
    return conn.execute(
        """
        select id, application_id, content, file_path, facts_used
        from resumes
        where id = %s and profile_id = %s and kind = 'tailored'
        """,
        (resume_id, profile_id),
    ).fetchone()


def update_cover_note(conn: psycopg.Connection, resume_id: UUID, cover_note: str) -> None:
    conn.execute(
        "update resumes set content = content || jsonb_build_object('cover_note', %s::text) "
        "where id = %s",
        (cover_note, resume_id),
    )
