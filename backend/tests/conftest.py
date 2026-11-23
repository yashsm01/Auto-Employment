"""Integration tests run on a real, throwaway Postgres server.

Set TEST_DATABASE_URL to use an existing server (the role must be able to create
databases). Otherwise a temporary cluster is created with the local Postgres tools.
"""

import os
import shutil
import socket
import subprocess
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from app.db.client import connect
from app.db.migrate import apply_migrations, apply_seed

REPO_ROOT = Path(__file__).parents[2]
MIGRATIONS = REPO_ROOT / "supabase" / "migrations"
SEED = REPO_ROOT / "supabase" / "seed.sql"
TEMPLATE_DB = "autopilot_test_template"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run_quietly(*command: str) -> None:
    subprocess.run(
        command, check=True, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[str]:
    configured = os.environ.get("TEST_DATABASE_URL")
    if configured:
        yield configured
        return

    initdb, pg_ctl = shutil.which("initdb"), shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        pytest.skip("Postgres tools not found and TEST_DATABASE_URL is not set")

    root = Path(tempfile.mkdtemp(prefix="autopilot-pg-"))
    data = root / "data"
    port = _free_port()
    _run_quietly(initdb, "-D", str(data), "-U", "postgres", "-A", "trust", "-E", "UTF8")
    _run_quietly(
        pg_ctl, "-D", str(data), "-l", str(root / "server.log"), "-w",
        "-o", f"-p {port} -h 127.0.0.1", "start",
    )
    try:
        yield f"postgresql://postgres@127.0.0.1:{port}/postgres"
    finally:
        _run_quietly(pg_ctl, "-D", str(data), "-m", "fast", "-w", "stop")
        shutil.rmtree(root, ignore_errors=True)


def _database_url(server_url: str, name: str) -> str:
    return f"{server_url.rsplit('/', 1)[0]}/{name}"


@pytest.fixture(scope="session")
def template_database(postgres_server: str) -> str:
    with psycopg.connect(postgres_server, autocommit=True) as admin:
        admin.execute(f"drop database if exists {TEMPLATE_DB}")
        admin.execute(f"create database {TEMPLATE_DB}")
    with connect(_database_url(postgres_server, TEMPLATE_DB)) as conn:
        apply_migrations(conn, MIGRATIONS)
        apply_seed(conn, SEED)
        conn.commit()
    return TEMPLATE_DB


@pytest.fixture
def database_url(postgres_server: str, template_database: str) -> Iterator[str]:
    name = f"autopilot_test_{uuid.uuid4().hex}"
    with psycopg.connect(postgres_server, autocommit=True) as admin:
        admin.execute(f"create database {name} template {template_database}")
    try:
        yield _database_url(postgres_server, name)
    finally:
        with psycopg.connect(postgres_server, autocommit=True) as admin:
            admin.execute(f"drop database if exists {name} with (force)")


@pytest.fixture
def empty_database_url(postgres_server: str) -> Iterator[str]:
    name = f"autopilot_empty_{uuid.uuid4().hex}"
    with psycopg.connect(postgres_server, autocommit=True) as admin:
        admin.execute(f"create database {name}")
    try:
        yield _database_url(postgres_server, name)
    finally:
        with psycopg.connect(postgres_server, autocommit=True) as admin:
            admin.execute(f"drop database if exists {name} with (force)")


@pytest.fixture
def conn(database_url: str) -> Iterator[psycopg.Connection]:
    with connect(database_url) as connection:
        yield connection
