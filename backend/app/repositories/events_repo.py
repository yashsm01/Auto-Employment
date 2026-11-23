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
        "insert into events (type, application_id, company_id, payload) values (%s, %s, %s, %s)",
        (event_type, application_id, company_id, Jsonb(payload or {})),
    )
