"""FastAPI dependencies. Write routes must call conn.commit() before returning."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import httpx
import psycopg
from fastapi import Depends

from app.core.config import Settings
from app.core.errors import AppError, BadRequest, NotFound
from app.db.client import connect
from app.providers.company.places import PlacesClient
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


def get_places(settings: SettingsDep) -> Iterator[PlacesClient]:
    key = settings.google_maps_api_key.get_secret_value()
    if not key:
        raise BadRequest(
            "Google Maps is not connected. Add GOOGLE_MAPS_API_KEY to backend/.env "
            "and restart the backend."
        )
    with httpx.Client(timeout=20) as client:
        yield PlacesClient(client, key)
