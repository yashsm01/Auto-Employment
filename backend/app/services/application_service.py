"""The application lifecycle and the data behind the Pipeline and Shortlist screens."""

from typing import Any
from urllib.parse import quote, urlsplit
from uuid import UUID

import psycopg

from app.core.errors import Conflict, NotFound
from app.core.normalize import contains_term
from app.repositories import applications_repo, companies_repo, events_repo, runs_repo
from app.schemas.application import (
    ApplicationDetail,
    BoardCard,
    BoardColumn,
    DecisionResponse,
    EmployerDetail,
    EmployerFact,
    Pipeline,
    PipelineStats,
    ShortlistItem,
    TimelineEvent,
)
from app.schemas.feedback import Decision
from app.schemas.job import ScoreResult, StoredJob

_COLUMNS = (
    ("shortlisted", "Shortlisted", ("shortlisted",)),
    ("resume_ready", "Resume ready", ("tailoring", "ready", "approved")),
    ("sent", "Sent", ("sent",)),
    ("followed_up", "Followed up", ("followed_up",)),
    ("replied", "Replied", ("replied",)),
)
_STATUS_META = {
    "tailoring": "Waiting for resume tailoring",
    "ready": "Ready for your review",
    "approved": "Approved to send",
    "sent": "Sent",
    "followed_up": "Followed up",
    "replied": "Replied",
}
_SOURCE_LABELS = {
    "trademe": "Trade Me",
    "gmail_alert": "Job alert email",
    "ats": "Company site",
    "serpapi": "Google Jobs",
    "example": "Example",
}
_BOARD_LABELS = {
    "site": "Employer website via Google Maps",
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "ashby": "Ashby",
}
_DECISIONS = {"approve": ("tailoring", "approved"), "skip": ("closed", "skipped")}


def record_rejected(conn: psycopg.Connection, profile_id: str, jobs: list[StoredJob]) -> None:
    result = ScoreResult(score=0, reason="No skills in common with your resume.")
    for job in jobs:
        applications_repo.record_score(
            conn, profile_id, job.job_id, result, "closed", job.similarity
        )


def record_scored(
    conn: psycopg.Connection,
    profile_id: str,
    job: StoredJob,
    result: ScoreResult,
    threshold: int,
) -> UUID | None:
    """Store a score. Returns the application id when the job passes the threshold."""
    passed = result.score >= threshold
    status = "found" if passed else "closed"
    application_id = applications_repo.record_score(
        conn, profile_id, job.job_id, result, status, job.similarity
    )
    events_repo.add(conn, "found", application_id=application_id, payload={"score": result.score})
    return application_id if passed else None


def load_decisions(conn: psycopg.Connection, profile_id: UUID | str) -> list[Decision]:
    return [Decision(**row) for row in applications_repo.recent_decisions(conn, profile_id)]


def shortlist(conn: psycopg.Connection, application_ids: list[UUID]) -> None:
    applications_repo.mark_shortlisted(conn, application_ids)
    for application_id in application_ids:
        events_repo.add(conn, "shortlisted", application_id=application_id)


def decide(
    conn: psycopg.Connection,
    profile_id: UUID,
    application_id: UUID,
    action: str,
    reason: str | None,
) -> DecisionResponse:
    """Apply the user's approve or skip. Only a shortlisted job can be decided."""
    with conn.transaction():
        row = applications_repo.lock(conn, profile_id, application_id)
        if row is None:
            raise NotFound("Application not found")
        if row["status"] != "shortlisted":
            raise Conflict(f"Application is already {row['status']}")

        status, event_type = _DECISIONS[action]
        applications_repo.set_status(conn, application_id, status)
        applications_repo.add_feedback(conn, application_id, action, reason)
        events_repo.add(
            conn, event_type, application_id=application_id, company_id=row["company_id"]
        )
    return DecisionResponse(id=application_id, status=status)


def format_salary(low: int | None, high: int | None) -> str:
    if low is None and high is None:
        return "Not listed"
    low = low if low is not None else high
    high = high if high is not None else low
    if low == high:
        return f"NZ${low / 1000:g}k"
    return f"NZ${low / 1000:g}–{high / 1000:g}k"


def _source_label(source: str, external_id: str) -> str:
    """Name exactly where a job came from."""
    if source == "ats":
        return _BOARD_LABELS.get(external_id.split(":", 1)[0], "Company site")
    return _SOURCE_LABELS.get(source, source)


def safe_url(url: str | None) -> str | None:
    """Links come from third parties, so only plain web links reach the browser."""
    if not url:
        return None
    try:
        return url if urlsplit(url).scheme in ("http", "https") else None
    except ValueError:
        return None


def _city(location: str, region: str) -> str:
    """The broad place to show and filter by, so suburbs do not split a city."""
    if contains_term(location, "remote"):
        return "Remote"
    return region.strip() or location.split(",")[0].strip() or "New Zealand"


def _card_meta(row: dict[str, Any]) -> str:
    if row["status"] != "shortlisted":
        return _STATUS_META[row["status"]]
    if row["missing_skills"]:
        return f"Missing: {', '.join(row['missing_skills'])}"
    return f"Matched: {', '.join(row['matched_skills'])}"


def _card(row: dict[str, Any]) -> BoardCard:
    return BoardCard(
        id=row["id"],
        title=row["title"],
        company=row["company"],
        city=_city(row["location"], row["region"]),
        score=row["score"],
        meta=_card_meta(row),
        source=_source_label(row["source"], row["external_id"]),
        is_example=row["source"] == "example",
    )


def pipeline(conn: psycopg.Connection, profile_id: UUID) -> Pipeline:
    columns = []
    for key, name, statuses in _COLUMNS:
        rows = applications_repo.list_by_status(conn, profile_id, list(statuses))
        columns.append(
            BoardColumn(key=key, name=name, count=len(rows), cards=[_card(row) for row in rows])
        )
    return Pipeline(
        stats=PipelineStats(**applications_repo.stats(conn, profile_id)),
        columns=columns,
        last_run_at=runs_repo.last_finished_at(conn, "lead"),
        last_sources=runs_repo.last_sources(conn, "lead"),
    )


def shortlist_items(conn: psycopg.Connection, profile_id: UUID) -> list[ShortlistItem]:
    rows = applications_repo.list_by_status(conn, profile_id, ["shortlisted"])
    return [
        ShortlistItem(
            id=row["id"],
            score=row["score"],
            title=row["title"],
            company=row["company"],
            city=_city(row["location"], row["region"]),
            salary=format_salary(row["salary_min"], row["salary_max"]),
            source=_source_label(row["source"], row["external_id"]),
            matched_skills=row["matched_skills"],
            missing_skills=row["missing_skills"],
            reason=row["score_reason"] or "",
            url=safe_url(row["url"]),
            is_example=row["source"] == "example",
        )
        for row in rows
    ]


def detail(
    conn: psycopg.Connection, profile_id: UUID, application_id: UUID
) -> ApplicationDetail:
    row = applications_repo.detail(conn, profile_id, application_id)
    if row is None:
        raise NotFound("Application not found")

    city = _city(row["location"], row["region"])
    place = row["address"] or f"{row['company']} {city} New Zealand"
    facts = companies_repo.list_facts(conn, row["company_id"]) if row["company_id"] else []
    employer = EmployerDetail(
        name=row["company"],
        website=safe_url(row["website"]),
        phone=row["phone"],
        email=row["email"],
        address=row["address"],
        about=row["about"],
        map_url=f"https://www.google.com/maps/search/?api=1&query={quote(place)}",
        facts=[
            EmployerFact(**{**fact, "source_url": safe_url(fact["source_url"])}) for fact in facts
        ],
    )
    return ApplicationDetail(
        id=row["id"],
        status=row["status"],
        score=row["score"],
        similarity=row["similarity"],
        title=row["title"],
        city=city,
        location=row["location"],
        salary=format_salary(row["salary_min"], row["salary_max"]),
        source=_source_label(row["source"], row["external_id"]),
        url=safe_url(row["url"]),
        description=row["description"],
        matched_skills=row["matched_skills"],
        missing_skills=row["missing_skills"],
        reason=row["score_reason"] or "",
        is_example=row["source"] == "example",
        employer=employer,
        timeline=[
            TimelineEvent(type=event["type"], created_at=event["created_at"])
            for event in events_repo.for_application(conn, application_id)
        ],
    )
