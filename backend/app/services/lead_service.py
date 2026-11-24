"""Rules for turning a resume into searches and cleaning the jobs that come back."""

import hashlib
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg

from app.core.errors import NotFound, ProviderError
from app.core.normalize import contains_term
from app.core.nz_places import fold_place, is_nz_location
from app.providers.jobs.base import JobSource
from app.repositories import jobs_repo, profiles_repo
from app.schemas.job import JobDraft
from app.schemas.resume import ResumeProfile, SearchPreferences

DEFAULT_QUERY_LIMIT = 10
NO_SOURCES_MESSAGE = (
    "No job sources are connected yet. Connect Google Maps, Gmail alerts or Trade Me, "
    "or add a company careers board on your profile."
)


def load_context(
    conn: psycopg.Connection, profile_id: UUID | str
) -> tuple[ResumeProfile, SearchPreferences]:
    context = profiles_repo.load_search_context(conn, profile_id)
    if context is None:
        raise NotFound("No resume profile found. Add a base resume first.")
    return context


def fetch_all(
    sources: Sequence[JobSource], queries: Iterable[str], regions: list[str]
) -> tuple[list[JobDraft], list[str], list[dict[str, Any]]]:
    """Search every source. A failing source is reported and the others continue."""
    if not sources:
        return [], [NO_SOURCES_MESSAGE], []
    keywords = list(dict.fromkeys(keywords_for(query, regions) for query in queries))
    jobs: list[JobDraft] = []
    errors: list[str] = []
    report: list[dict[str, Any]] = []
    for source in sources:
        found: set[tuple[str, str]] = set()
        problem: str | None = None
        for words in keywords:
            try:
                results = source.search(words)
            except ProviderError as error:
                problem = str(error)
                errors.append(problem)
                break
            jobs.extend(results)
            found.update((job.source, job.external_id) for job in results)
        report.append(
            {
                "source": getattr(source, "label", source.name),
                "jobs": len(found),
                "status": "error" if problem else "ok",
                "detail": problem,
            }
        )
    return jobs, errors, report


def clean(
    conn: psycopg.Connection,
    jobs: Iterable[JobDraft],
    prefs: SearchPreferences,
    now: datetime,
) -> list[JobDraft]:
    """Remove unwanted jobs, repeats, and anything already stored."""
    unique = dedupe_jobs(drop_unwanted(jobs, prefs, now))
    stored = jobs_repo.existing_hashes(conn, [job_hash(job) for job in unique])
    return [job for job in unique if job_hash(job) not in stored]


def build_queries(
    resume: ResumeProfile, prefs: SearchPreferences, limit: int = DEFAULT_QUERY_LIMIT
) -> list[str]:
    """Use the queries the user saved, or combine resume titles and skills with regions."""
    if resume.search_queries:
        return resume.search_queries[:limit]

    terms = [*resume.titles, *(skill.name for skill in resume.skills)]
    if not prefs.regions:  # all of New Zealand
        return list({term.casefold(): term for term in reversed(terms)}.values())[::-1][:limit]

    queries: dict[str, str] = {}
    for term in terms:
        for region in prefs.regions:
            query = f"{term} {region}"
            queries.setdefault(query.casefold(), query)
    if len(queries) <= limit:
        return list(queries.values())

    # Location is filtered after fetching, so many towns must not crowd out a job title.
    chosen = {f"{title} {prefs.regions[0]}".casefold() for title in resume.titles[:limit]}
    for key in queries:
        if len(chosen) >= limit:
            break
        chosen.add(key)
    return [query for key, query in queries.items() if key in chosen]


def keywords_for(query: str, regions: Iterable[str]) -> str:
    """Remove a trailing region, because location is filtered after fetching."""
    for region in regions:
        if query.casefold().endswith(f" {region.casefold()}"):
            return query[: -len(region) - 1].strip()
    return query


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def dedupe_hash(title: str, company: str, location: str) -> str:
    """Same title, company and city counts as one job."""
    city = location.split(",")[0]
    key = "|".join(_normalise(part) for part in (title, company, city))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def job_hash(job: JobDraft) -> str:
    return dedupe_hash(job.title, job.company, job.location)


def dedupe_jobs(jobs: Iterable[JobDraft], seen: Iterable[str] = ()) -> list[JobDraft]:
    known = set(seen)
    kept = []
    for job in jobs:
        key = job_hash(job)
        if key not in known:
            known.add(key)
            kept.append(job)
    return kept


def _in_regions(job: JobDraft, regions: list[str]) -> bool:
    # Global company boards list jobs in other countries, some in same-named places.
    if job.source == "ats" and not is_nz_location(job.location, regions):
        return False
    if not regions:  # all of New Zealand
        return True

    place = fold_place(f"{job.location} {job.region}")
    for region in regions:
        wanted = fold_place(region)
        if wanted.startswith("remote"):
            if contains_term(f"{place} {fold_place(job.title)}", "remote"):
                return True
        elif contains_term(place, wanted):
            return True
    return False


def _is_wanted(job: JobDraft, prefs: SearchPreferences, now: datetime) -> bool:
    if job.closes_at is not None and job.closes_at <= now:
        return False
    if any(contains_term(job.title, word) for word in prefs.avoid_keywords):
        return False
    if prefs.salary_min is not None:
        top_pay = job.salary_max if job.salary_max is not None else job.salary_min
        if top_pay is not None and top_pay < prefs.salary_min:
            return False
    return _in_regions(job, prefs.regions)


def drop_unwanted(
    jobs: Iterable[JobDraft], prefs: SearchPreferences, now: datetime
) -> list[JobDraft]:
    """Remove expired jobs, avoided titles, low pay and jobs outside preferred regions."""
    return [job for job in jobs if _is_wanted(job, prefs, now)]
