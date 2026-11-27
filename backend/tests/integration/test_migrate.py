import shutil

import psycopg
import pytest

from app.db.client import connect
from app.db.migrate import apply_migrations
from tests.conftest import MIGRATIONS

pytestmark = pytest.mark.postgres

PLAN_TABLES = {
    "profiles", "settings", "resumes", "resume_profiles", "companies", "company_facts",
    "contacts", "jobs", "applications", "feedback", "outbox", "calls", "events", "graph_runs",
    "skill_decisions", "outreach_blocks",
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


def test_migration_0009_applies_on_an_existing_database(empty_database_url, tmp_path):
    # Migrate a database as it was before 0009, add a job, then apply 0009 on top.
    before = tmp_path / "before"
    before.mkdir()
    for path in MIGRATIONS.glob("*.sql"):
        if path.name < "0009":
            shutil.copy(path, before / path.name)

    with connect(empty_database_url) as conn:
        apply_migrations(conn, before)
        conn.execute("insert into profiles (full_name) values ('Example Person')")
        conn.execute("insert into companies (name) values ('Example Ltd')")
        conn.execute(
            "insert into jobs (company_id, source, external_id, title, dedupe_hash) "
            "select id, 'example', '1', 'Dev', 'hash' from companies"
        )
        conn.execute(
            "insert into applications (profile_id, job_id, score) "
            "select p.id, j.id, 50 from profiles p, jobs j"
        )
        conn.commit()

        result = apply_migrations(conn, MIGRATIONS)

        assert "0009_resume_builder.sql" in result.applied
        row = conn.execute(
            "select required_skills, preferred_skills, requirements_split from applications"
        ).fetchone()
        assert row["required_skills"] == []
        assert row["preferred_skills"] == []
        assert row["requirements_split"] is False
        conn.execute(
            "insert into outbox (application_id, channel, kind, status, to_address, body) "
            "select a.id, 'email', 'application', 'draft', 'a@example.com', 'b' "
            "from applications a"
        )
        conn.execute(
            "insert into skill_decisions (profile_id, skill_key, skill, decision) "
            "select id, 'python', 'Python', 'have' from profiles"
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "insert into skill_decisions (profile_id, skill_key, skill, decision) "
                "select id, 'go', 'Go', 'maybe' from profiles"
            )


def test_migration_0011_applies_on_an_existing_database(empty_database_url, tmp_path):
    # Migrate a database as it was before 0011, add an advert application, then apply 0011.
    before = tmp_path / "before"
    before.mkdir()
    for path in MIGRATIONS.glob("*.sql"):
        if path.name < "0011":
            shutil.copy(path, before / path.name)

    with connect(empty_database_url) as conn:
        apply_migrations(conn, before)
        conn.execute("insert into profiles (full_name) values ('Example Person')")
        conn.execute("insert into companies (name) values ('Example Ltd')")
        conn.execute(
            "insert into jobs (company_id, source, external_id, title, dedupe_hash) "
            "select id, 'example', '1', 'Dev', 'hash' from companies"
        )
        conn.execute(
            "insert into applications (profile_id, job_id, score) "
            "select p.id, j.id, 50 from profiles p, jobs j"
        )
        conn.commit()

        result = apply_migrations(conn, MIGRATIONS)

        assert result.applied == ["0011_outreach.sql", "0012_contacts_attempted.sql"]
        assert conn.execute("select kind from applications").fetchone()["kind"] == "advert"
        profile = conn.execute(
            "select business_types, prospects_enabled, prospects_per_day from profiles"
        ).fetchone()
        assert profile["business_types"] == []
        assert profile["prospects_enabled"] is False
        assert profile["prospects_per_day"] == 5
        conn.execute(
            "insert into jobs (company_id, source, external_id, title, dedupe_hash) "
            "select id, 'nearby', '2', 'Dev', 'hash2' from companies"
        )
        conn.execute(
            "insert into outreach_blocks (profile_id, company_id, reason) "
            "select p.id, c.id, 'replied' from profiles p, companies c"
        )
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("update applications set kind = 'cold'")
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("update profiles set prospects_per_day = 11")
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("update outreach_blocks set reason = 'annoyed'")


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


def test_migrations_allow_prep_runs(conn):
    conn.execute("insert into graph_runs (graph, status) values ('prep', 'ok')")


def test_migration_0010_adds_the_added_flag_to_an_existing_database(empty_database_url, tmp_path):
    # Migrate a database as it was after 0009 (with a skill decision saved), then apply 0010.
    before = tmp_path / "before"
    before.mkdir()
    for path in MIGRATIONS.glob("*.sql"):
        if path.name < "0010":
            shutil.copy(path, before / path.name)

    with connect(empty_database_url) as conn:
        apply_migrations(conn, before)
        conn.execute("insert into profiles (full_name) values ('Example Person')")
        conn.execute(
            "insert into skill_decisions (profile_id, skill_key, skill, decision) "
            "select id, 'python', 'Python', 'have' from profiles"
        )
        conn.commit()

        result = apply_migrations(conn, MIGRATIONS)

        assert "0010_skill_decisions_added.sql" in result.applied
        column = conn.execute(
            "select is_nullable, column_default from information_schema.columns "
            "where table_name = 'skill_decisions' and column_name = 'added'"
        ).fetchone()
        assert column["is_nullable"] == "NO"
        assert column["column_default"] == "false"
        row = conn.execute("select added from skill_decisions").fetchone()
        assert row["added"] is False


def test_migration_0012_records_contact_attempts_on_an_existing_database(
    empty_database_url, tmp_path
):
    before = tmp_path / "before"
    before.mkdir()
    for path in MIGRATIONS.glob("*.sql"):
        if path.name < "0012":
            shutil.copy(path, before / path.name)

    with connect(empty_database_url) as conn:
        apply_migrations(conn, before)
        conn.execute("insert into companies (name) values ('Example Ltd')")
        conn.commit()

        result = apply_migrations(conn, MIGRATIONS)

        assert "0012_contacts_attempted.sql" in result.applied
        column = conn.execute(
            "select data_type from information_schema.columns "
            "where table_name = 'companies' and column_name = 'contacts_attempted_at'"
        ).fetchone()
        assert column["data_type"] == "timestamp with time zone"
