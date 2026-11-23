"""Apply the SQL files in supabase/migrations to any Postgres database.

Usage: python -m app.db.migrate [--seed]
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from app.core.config import Settings
from app.db.client import connect

SUPABASE_DIR = Path(__file__).parents[3] / "supabase"
_NEEDS_PGVECTOR = "create extension if not exists vector"


@dataclass
class MigrationResult:
    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def apply_migrations(conn: psycopg.Connection, directory: Path) -> MigrationResult:
    """Apply new migrations in order. A file needing a missing pgvector is skipped."""
    result = MigrationResult()
    with conn.transaction():
        conn.execute(
            "create table if not exists schema_migrations ("
            "name text primary key, applied_at timestamptz not null default now())"
        )
        conn.execute("alter table schema_migrations enable row level security")
        done = {row["name"] for row in conn.execute("select name from schema_migrations")}
        has_pgvector = (
            conn.execute("select 1 from pg_available_extensions where name = 'vector'").fetchone()
            is not None
        )

        for path in sorted(directory.glob("*.sql")):
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            if _NEEDS_PGVECTOR in sql.lower() and not has_pgvector:
                result.skipped.append(path.name)
                continue
            conn.execute(sql)
            conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
            result.applied.append(path.name)
    return result


def apply_seed(conn: psycopg.Connection, path: Path) -> None:
    with conn.transaction():
        conn.execute(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="store_true", help="also load the example profile")
    args = parser.parse_args()

    settings = Settings()
    if not settings.database_url:
        parser.error("DATABASE_URL is not set. Add it to backend/.env")

    with connect(settings.database_url) as conn:
        result = apply_migrations(conn, SUPABASE_DIR / "migrations")
        if args.seed:
            apply_seed(conn, SUPABASE_DIR / "seed.sql")

    print(f"Applied: {', '.join(result.applied) or 'nothing new'}")
    if result.skipped:
        print(f"Skipped (pgvector is not installed): {', '.join(result.skipped)}")


if __name__ == "__main__":
    main()
