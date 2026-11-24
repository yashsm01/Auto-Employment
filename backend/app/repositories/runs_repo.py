from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

# A run still "running" after this long was cut off, for example by a restart.
STALE_AFTER = {"lead": "1 hour", "resume": "10 minutes", "prep": "10 minutes"}


def start(
    conn: psycopg.Connection,
    graph: str,
    graph_input: dict[str, Any],
    application_id: str | None = None,
) -> UUID | None:
    """Create a running row. Returns None if this graph is already running."""
    conn.execute(
        """
        update graph_runs
        set status = 'error', error = 'Abandoned: run did not finish', finished_at = now()
        where graph = %s and status = 'running' and started_at < now() - %s::interval
        """,
        (graph, STALE_AFTER.get(graph, "1 hour")),
    )
    row = conn.execute(
        """
        insert into graph_runs (graph, status, input, application_id)
        values (%s, 'running', %s, %s)
        on conflict (graph) where status = 'running' do nothing
        returning id
        """,
        (graph, Jsonb(graph_input), application_id),
    ).fetchone()
    return row["id"] if row else None


def finish(conn: psycopg.Connection, run_id: UUID, output: dict[str, Any]) -> None:
    conn.execute(
        "update graph_runs set status = 'ok', output = %s, finished_at = now() where id = %s",
        (Jsonb(output), run_id),
    )


def fail(
    conn: psycopg.Connection, run_id: UUID, error: str, failed_node: str | None
) -> None:
    conn.execute(
        """
        update graph_runs
        set status = 'error', error = %s, failed_node = %s, finished_at = now()
        where id = %s
        """,
        (error, failed_node, run_id),
    )


def last_finished_at(conn: psycopg.Connection, graph: str) -> datetime | None:
    row = conn.execute(
        "select max(finished_at) as at from graph_runs where graph = %s and status = 'ok'",
        (graph,),
    ).fetchone()
    return row["at"]


def last_sources(conn: psycopg.Connection, graph: str) -> list[dict[str, Any]]:
    row = conn.execute(
        """
        select output -> 'sources' as sources
        from graph_runs
        where graph = %s and status = 'ok'
        order by finished_at desc
        limit 1
        """,
        (graph,),
    ).fetchone()
    return (row["sources"] or []) if row else []


def latest_for_application(
    conn: psycopg.Connection, graph: str, application_id: UUID | str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        select status, error, started_at
        from graph_runs
        where graph = %s and application_id = %s
        order by started_at desc
        limit 1
        """,
        (graph, application_id),
    ).fetchone()
