import psycopg
import pytest

from app.db.client import connect
from app.db.migrate import apply_migrations
from tests.conftest import MIGRATIONS

pytestmark = pytest.mark.postgres

PLAN_TABLES = {
    "profiles", "settings", "resumes", "resume_profiles", "companies", "company_facts",
    "contacts", "jobs", "applications", "feedback", "outbox", "calls", "events", "graph_runs",
}


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "select tablename from pg_tables where schemaname = 'public'"
    ).fetchall()
    return {row["tablename"] for row in rows}


def test_migrations_create_every_table_in_the_plan(empty_database_url):
    with connect(empty_database_url) as conn:
        apply_migrations(conn, MIGRATIONS)

        assert PLAN_TABLES <= _tables(conn)


def test_migrations_can_run_twice(empty_database_url):
    with connect(empty_database_url) as conn:
        first = apply_migrations(conn, MIGRATIONS)
        second = apply_migrations(conn, MIGRATIONS)

    assert "0001_init.sql" in first.applied
    assert second.applied == []


def test_every_table_has_row_level_security(empty_database_url):
    # Supabase exposes public tables through its API unless RLS is on.
    with connect(empty_database_url) as conn:
        apply_migrations(conn, MIGRATIONS)
        unprotected = conn.execute(
            "select tablename from pg_tables "
            "where schemaname = 'public' and not rowsecurity"
        ).fetchall()

    assert unprotected == []


def test_embeddings_migration_is_skipped_without_pgvector(empty_database_url):
    with connect(empty_database_url) as conn:
        available = conn.execute(
            "select 1 from pg_available_extensions where name = 'vector'"
        ).fetchone()
        if available:
            pytest.skip("pgvector is installed on this server")

        result = apply_migrations(conn, MIGRATIONS)

    assert "0002_embeddings.sql" in result.skipped


def test_application_status_rejects_unknown_values(conn):
    conn.execute("insert into companies (name) values ('Example Ltd')")
    conn.execute(
        "insert into jobs (company_id, source, external_id, title, dedupe_hash) "
        "select id, 'example', '1', 'Dev', 'hash' from companies"
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "insert into applications (profile_id, job_id, status) "
            "select p.id, j.id, 'not-a-status' from profiles p, jobs j"
        )
