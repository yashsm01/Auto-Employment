"""One lead search run. Used by both the Run button and the daily schedule."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
import psycopg

from app.chains.manager import get_chain, get_speculative_chain
from app.core.config import Settings
from app.graphs.lead.deps import LeadDeps
from app.graphs.runner import GraphRunResult, run_graph
from app.providers.jobs.employer_sites import EmployerSitesSource
from app.providers.llm.factory import build_embedder
from app.repositories import profiles_repo
from app.services import (
    application_service,
    auto_service,
    employer_service,
    lead_service,
    notify_service,
    prospect_service,
    source_service,
)
from app.services.resume_service import connections

SOURCE_TIMEOUT_SECONDS = 20
_NOT_CONNECTED = (
    ("trademe", "Trade Me"),
    ("gmail", "Gmail job alerts"),
    ("places", employer_service.MAPS_LABEL),
)


def _not_connected(settings: Settings) -> list[dict[str, Any]]:
    connected = connections(settings)
    return [
        {"source": label, "jobs": 0, "status": "not_connected", "detail": None}
        for key, label in _NOT_CONNECTED
        if not connected[key]
    ]


def run_lead_search(
    conn: psycopg.Connection, settings: Settings, profile_id: UUID
) -> GraphRunResult:
    with httpx.Client(timeout=SOURCE_TIMEOUT_SECONDS) as client:
        use_examples = profiles_repo.has_example_resume(conn, profile_id)
        notes = _not_connected(settings)

        places = source_service.build_places(settings, client)
        if places and not use_examples:
            resume, prefs = lead_service.load_context(conn, profile_id)
            today = datetime.now(ZoneInfo("Pacific/Auckland")).date()
            notes.insert(
                0,
                employer_service.discover(
                    conn,
                    profile_id,
                    places,
                    resume,
                    prefs,
                    today,
                    settings.max_discovery_searches_per_run,
                    settings.max_nearby_searches_per_day,
                    business_types=auto_service.get_settings(conn, profile_id).business_types,
                ),
            )

        sources = source_service.build_sources(
            settings,
            client,
            profiles_repo.load_boards(conn, profile_id),
            use_examples=use_examples,
            employers=employer_service.employers_to_check(
                conn, profile_id, settings.max_employer_sites_per_run
            ),
        )
        decisions = application_service.load_decisions(conn, profile_id)
        conn.commit()  # end the read transaction before the graph opens its own
        now = datetime.now(UTC)
        deps = LeadDeps(
            conn=conn,
            sources=sources,
            score_chain=get_chain("score", settings, decisions),
            now=now,
            embedder=build_embedder(settings, client),
            keep_similarity=settings.embedding_keep_similarity,
            employer_tools=source_service.build_employer_tools(settings, client),
            max_employer_profiles=settings.max_employer_profiles_per_run,
            source_notes=notes,
        )
        result = run_graph("lead", {"profile_id": str(profile_id)}, deps)

        if result.status == "ok":
            shortlisted = result.output.get("shortlisted", 0)
            if shortlisted:
                notify_service.notify(
                    conn, settings, profile_id, "shortlist",
                    f"{shortlisted} new job{'s' if shortlisted > 1 else ''} shortlisted. "
                    "Open the Shortlist to review.",
                    f"shortlist:{result.id}",
                )
            for source in sources:
                if isinstance(source, EmployerSitesSource) and source.checked:
                    employer_service.mark_checked(conn, profile_id, source.checked, now)
            conn.commit()
        return result


def run_prospecting(
    conn: psycopg.Connection, settings: Settings, profile_id: UUID
) -> dict[str, int] | None:
    """Google Maps outreach for the daily run. None unless Auto mode and its switch are on."""
    auto = auto_service.get_settings(conn, profile_id)
    if not (auto.enabled and auto.prospects_enabled):
        return None
    with httpx.Client(timeout=SOURCE_TIMEOUT_SECONDS) as client:
        tools = source_service.build_contact_tools(settings, client)
        chain = get_speculative_chain(settings)
        return prospect_service.run_daily(
            conn, settings, profile_id, tools, chain, datetime.now(UTC)
        )
