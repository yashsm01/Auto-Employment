"""Runs queued deep searches one at a time."""

import logging
import re
from datetime import UTC, datetime

import httpx
import psycopg

from app.chains.manager import get_prep_chains
from app.core.config import Settings
from app.core.errors import Conflict
from app.db.client import connect
from app.graphs.prep.deps import PrepDeps
from app.graphs.runner import run_graph
from app.providers.company.places import PlacesClient
from app.providers.company.website_reader import WebsiteReader
from app.providers.search.tavily import TavilySearch
from app.repositories import prep_repo
from app.services.prep_service import NO_KEY_MESSAGE

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_SECONDS = 30
STALE_MINUTES = 10
INTERRUPTED_MESSAGE = "Deep search was interrupted. Try again."
_ERROR_PREFIX = re.compile(r"^[A-Za-z]+Error: |^(BadRequest|NotFound|Conflict): ")


def _friendly(error: str | None) -> str:
    return _ERROR_PREFIX.sub("", error or "Deep search failed.", count=1)


def _deps(
    settings: Settings, conn: psycopg.Connection, client: httpx.Client, profile_id: str
) -> PrepDeps | None:
    chains = get_prep_chains(settings)
    if chains is None:
        return None
    now = datetime.now(UTC)
    maps_key = settings.google_maps_api_key.get_secret_value()
    tavily_key = settings.tavily_api_key.get_secret_value()
    places_used = prep_repo.places_calls_since(conn, profile_id, prep_repo.month_start_nz(now))
    return PrepDeps(
        conn=conn,
        chains=chains,
        places=PlacesClient(client, maps_key) if maps_key else None,
        reader=WebsiteReader(client),
        search=TavilySearch(client, tavily_key) if tavily_key else None,
        now=now,
        usd_to_nzd=settings.usd_to_nzd,
        places_allowed=places_used < settings.max_prep_places_calls_per_month,
        places_remaining=max(settings.max_prep_places_calls_per_month - places_used, 0),
    )


def process_prep_queue(settings: Settings) -> int:
    """Run every queued deep search, oldest first. Returns how many were attempted. Never raises."""
    attempted: list[str] = []
    try:
        with connect(settings.database_url) as conn, httpx.Client(
            timeout=HTTP_TIMEOUT_SECONDS
        ) as client:
            prep_repo.fail_stale(conn, STALE_MINUTES, INTERRUPTED_MESSAGE)
            conn.commit()
            while True:
                row = prep_repo.next_queued(conn, attempted)
                conn.commit()
                if row is None:
                    break
                pack_id = str(row["id"])
                attempted.append(pack_id)
                deps = _deps(settings, conn, client, str(row["profile_id"]))
                if deps is None:
                    prep_repo.fail(conn, pack_id, NO_KEY_MESSAGE)
                    conn.commit()
                    continue
                if not prep_repo.mark_running(conn, pack_id):
                    conn.commit()
                    continue  # another worker took it
                conn.commit()
                graph_input = {"pack_id": pack_id, "application_id": str(row["application_id"])}
                try:
                    result = run_graph("prep", graph_input, deps)
                except Conflict:
                    prep_repo.requeue(conn, pack_id)
                    conn.commit()
                    attempted.pop()
                    break  # another worker is running and will continue the queue
                if result.status == "error":
                    prep_repo.fail(conn, pack_id, _friendly(result.error))
                    conn.commit()
    except Exception:
        logger.exception("The deep search queue stopped")
    return len(attempted)
