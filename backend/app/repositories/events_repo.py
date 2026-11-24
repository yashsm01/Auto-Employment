from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


def add(
    conn: psycopg.Connection,
    event_type: str,
    application_id: UUID | None = None,
    company_id: UUID | None = None,
    payload: dict | None = None,
) -> None:
    conn.execute(
        "insert into events (type, application_id, company_id, payload, created_at) "
        "values (%s, %s, %s, %s, clock_timestamp())",
        (event_type, application_id, company_id, Jsonb(payload or {})),
    )


def for_application(conn: psycopg.Connection, application_id: UUID) -> list[dict[str, Any]]:
    return conn.execute(
        "select type, payload, created_at from events "
        "where application_id = %s order by created_at",
        (application_id,),
    ).fetchall()
