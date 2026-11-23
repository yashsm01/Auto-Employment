"""The application lifecycle and the data behind the Pipeline and Shortlist screens."""

from typing import Any
from uuid import UUID

import psycopg

from app.core.errors import Conflict, NotFound
from app.core.normalize import contains_term
from app.repositories import applications_repo, events_repo, runs_repo
from app.schemas.application import (
    BoardCard,
    BoardColumn,
    DecisionResponse,
    Pipeline,
    PipelineStats,
    ShortlistItem,
)
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
_DECISIONS = {"approve": ("tailoring", "approved"), "skip": ("closed", "skipped")}


def record_rejected(conn: psycopg.Connection, profile_id: str, jobs: list[StoredJob]) -> None:
    result = ScoreResult(score=0, reason="No skills in common with your resume.")
    for job in jobs:
        applications_repo.record_score(conn, profile_id, job.job_id, result, "closed")


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
    application_id = applications_repo.record_score(conn, profile_id, job.job_id, result, status)
    events_repo.add(conn, "found", application_id=application_id, payload={"score": result.score})
    return application_id if passed else None


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
            source=_SOURCE_LABELS.get(row["source"], row["source"]),
            matched_skills=row["matched_skills"],
            missing_skills=row["missing_skills"],
            reason=row["score_reason"] or "",
            url=row["url"],
            is_example=row["source"] == "example",
        )
        for row in rows
    ]
