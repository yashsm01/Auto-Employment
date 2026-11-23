"""Rules for turning a resume into searches and cleaning the jobs that come back."""

import hashlib
from collections.abc import Iterable, Sequence
from datetime import datetime
from uuid import UUID

import psycopg

from app.core.errors import NotFound, ProviderError
from app.core.normalize import contains_term
from app.providers.jobs.base import JobSource
from app.repositories import jobs_repo, profiles_repo
from app.schemas.job import JobDraft
from app.schemas.resume import ResumeProfile, SearchPreferences

DEFAULT_QUERY_LIMIT = 10


def load_context(
    conn: psycopg.Connection, profile_id: UUID | str
) -> tuple[ResumeProfile, SearchPreferences]:
    context = profiles_repo.load_search_context(conn, profile_id)
    if context is None:
        raise NotFound("No resume profile found. Add a base resume first.")
    return context


def fetch_all(
    sources: Sequence[JobSource], queries: Iterable[str], regions: list[str]
) -> tuple[list[JobDraft], list[str]]:
    """Search every source. A failing source is reported and the others continue."""
    keywords = list(dict.fromkeys(keywords_for(query, regions) for query in queries))
    jobs: list[JobDraft] = []
    errors: list[str] = []
    for source in sources:
        for words in keywords:
            try:
                jobs.extend(source.search(words))
            except ProviderError as error:
                errors.append(str(error))
                break
    return jobs, errors


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

    regions = prefs.regions or ["New Zealand"]
    terms = [*resume.titles, *(skill.name for skill in resume.skills)]
    queries: dict[str, str] = {}
    for term in terms:
        for region in regions:
            query = f"{term} {region}"
            queries.setdefault(query.casefold(), query)
    return list(queries.values())[:limit]


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
    if not regions:
        return True
    place = f"{job.location} {job.region}"
    for region in regions:
        if region.casefold().startswith("remote"):
            if contains_term(f"{place} {job.title}", "remote"):
                return True
        elif contains_term(place, region):
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
