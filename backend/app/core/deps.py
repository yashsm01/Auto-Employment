"""FastAPI dependencies. Write routes must call conn.commit() before returning."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import Depends

from app.core.config import Settings
from app.core.errors import AppError, NotFound
from app.db.client import connect
from app.repositories import profiles_repo


@lru_cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_conn(settings: SettingsDep) -> Iterator[psycopg.Connection]:
    if not settings.database_url:
        raise AppError("DATABASE_URL is not set. Add it to backend/.env")
    with connect(settings.database_url) as conn:
        yield conn


ConnDep = Annotated[psycopg.Connection, Depends(get_conn)]


def get_profile_id(conn: ConnDep) -> UUID:
    """The app has one user for now, so the first profile is the current one."""
    profile_id = profiles_repo.first_profile_id(conn)
    if profile_id is None:
        raise NotFound("No profile found. Run: python -m app.db.migrate --seed")
    return profile_id


ProfileIdDep = Annotated[UUID, Depends(get_profile_id)]
