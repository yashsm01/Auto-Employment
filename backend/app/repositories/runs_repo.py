from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

STALE_AFTER = "1 hour"


def start(conn: psycopg.Connection, graph: str, graph_input: dict[str, Any]) -> UUID | None:
    """Create a running row. Returns None if this graph is already running."""
    conn.execute(
        """
        update graph_runs
        set status = 'error', error = 'Abandoned: run did not finish', finished_at = now()
        where graph = %s and status = 'running' and started_at < now() - %s::interval
        """,
        (graph, STALE_AFTER),
    )
    row = conn.execute(
        """
        insert into graph_runs (graph, status, input) values (%s, 'running', %s)
        on conflict (graph) where status = 'running' do nothing
        returning id
        """,
        (graph, Jsonb(graph_input)),
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
