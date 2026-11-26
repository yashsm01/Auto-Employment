"""Employer records: free facts for every job, deeper research for shortlisted ones."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import psycopg

from app.chains.company_summary_chain import CompanySummaryChain
from app.core.errors import NotFound, ProviderError
from app.providers.company.places import PlaceMatch
from app.providers.company.website_reader import PageReader
from app.providers.search.tavily import SearchHit
from app.repositories import companies_repo, jobs_repo
from app.schemas.job import JobDraft, StoredJob
from app.services import contact_service
from app.services.contact_service import ContactTools
from app.services.lead_service import job_hash


def store_jobs(conn: psycopg.Connection, jobs: list[JobDraft]) -> list[StoredJob]:
    stored = []
    for job in jobs:
        company_id = companies_repo.upsert_from_job(conn, job)
        companies_repo.add_job_post_facts(conn, company_id, job)
        job_id = jobs_repo.insert(conn, job, company_id, job_hash(job))
        if job_id is not None:
            stored.append(StoredJob(job_id=job_id, draft=job))
    return stored


class PlaceFinder(Protocol):
    def find(self, name: str, city: str) -> PlaceMatch | None: ...


class WebSearch(Protocol):
    def search(self, query: str) -> list[SearchHit]: ...


@dataclass
class EmployerTools:
    places: PlaceFinder | None = None
    reader: PageReader | None = None
    search: WebSearch | None = None
    summary: CompanySummaryChain | None = None
    contacts: ContactTools | None = None


def _add_place_facts(conn, company_id: UUID, place: PlaceMatch) -> None:
    companies_repo.apply_place(conn, company_id, place)
    for field, value in (
        ("address", place.address),
        ("phone", place.phone),
        ("website", place.website),
    ):
        if value:
            companies_repo.add_fact(conn, company_id, field, value, "places", "high")
    companies_repo.add_place_details(
        conn, company_id, place.hours, place.rating, place.rating_count
    )


def _research(
    conn: psycopg.Connection,
    row: dict[str, Any],
    tools: EmployerTools,
    errors: dict[str, None],
    now: datetime,
) -> None:
    company_id, name = row["id"], row["name"]
    city = row["region"] or row["location"].split(",")[0].strip()
    website = row["website"]

    if tools.places:
        try:
            place = tools.places.find(name, city)
        except ProviderError as error:
            errors[str(error)] = None
        else:
            if place:
                _add_place_facts(conn, company_id, place)
                website = website or place.website

    sources: list[tuple[str, str]] = []
    if tools.reader and website:
        try:
            sources.append(("website", tools.reader.read(website)))
        except ProviderError as error:
            errors[str(error)] = None

    if tools.contacts is not None:
        # A savepoint: a failed lookup is undone and the rest of research carries on.
        try:
            with conn.transaction():
                contact_service.lookup(conn, company_id, tools.contacts, now)
        except (ProviderError, NotFound, psycopg.Error) as error:
            errors[str(error)] = None

    if tools.search:
        try:
            hits = tools.search.search(f'"{name}" New Zealand company news')
        except ProviderError as error:
            errors[str(error)] = None
        else:
            for hit in hits:
                sources.append(("search", f"{hit.title}\n{hit.content}"))
            if hits:
                companies_repo.add_fact(
                    conn,
                    company_id,
                    "recent_news",
                    f"{hits[0].title}: {hits[0].content[:300]}",
                    "tavily",
                    "check",
                    hits[0].url,
                )

    if tools.summary and sources:
        try:
            about = tools.summary.run(name, sources)
        except ProviderError as error:
            errors[str(error)] = None
        else:
            if about:
                source = "website" if sources[0][0] == "website" else "tavily"
                companies_repo.set_about(conn, company_id, about)
                companies_repo.add_fact(conn, company_id, "about", about, source, "medium")


def research_employers(
    conn: psycopg.Connection,
    application_ids: list[UUID],
    tools: EmployerTools,
    limit: int,
    now: datetime,
) -> tuple[int, list[str]]:
    """Research new shortlisted employers. A failing tool is reported and the run continues."""
    rows = companies_repo.needing_research(conn, application_ids, limit)
    errors: dict[str, None] = {}
    for row in rows:
        _research(conn, row, tools, errors, now)
    return len(rows), list(errors)
