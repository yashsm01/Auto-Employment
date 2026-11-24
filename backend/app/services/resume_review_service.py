"""The Resume review screen: what is waiting, what changed, and your decision."""

from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from app.core.errors import Conflict, NotFound
from app.repositories import applications_repo, events_repo, resumes_repo, runs_repo
from app.schemas.tailoring import (
    BaseSections,
    ReviewItem,
    ReviewList,
    StatusResponse,
    TailoredResume,
    TailoredResumeView,
)


def _error(conn: psycopg.Connection, row: dict[str, Any]) -> str | None:
    """The latest attempt's error, unless tailoring was requested again after it."""
    if row["status"] != "tailoring":
        return None
    run = runs_repo.latest_for_application(conn, "resume", row["id"])
    if run is None or run["status"] != "error" or run["started_at"] < row["updated_at"]:
        return None
    return run["error"]


def review_list(conn: psycopg.Connection, profile_id: UUID) -> ReviewList:
    return ReviewList(
        items=[
            ReviewItem(
                application_id=row["id"],
                status=row["status"],
                title=row["title"],
                company=row["company"],
                resume_id=row["resume_id"],
                error=_error(conn, row),
            )
            for row in applications_repo.review_rows(conn, profile_id)
        ]
    )


def view(conn: psycopg.Connection, profile_id: UUID, application_id: UUID) -> TailoredResumeView:
    row = applications_repo.review_row(conn, profile_id, application_id)
    if row is None:
        raise NotFound("Application not found")
    resume = (
        resumes_repo.get_tailored(conn, profile_id, row["resume_id"]) if row["resume_id"] else None
    )
    content = resume["content"] if resume else {}
    return TailoredResumeView(
        application_id=row["id"],
        status=row["status"],
        title=row["title"],
        company=row["company"],
        resume_id=resume["id"] if resume else None,
        base=BaseSections(**content["base"]) if content.get("base") else None,
        tailored=TailoredResume(**content["tailored"]) if content.get("tailored") else None,
        changed_ids=content.get("changed_ids", []),
        notes=content.get("notes", []),
        cover_note=content.get("cover_note", ""),
        facts_used=resume["facts_used"] if resume else [],
        ai_used=content.get("ai_used", False),
        pdf_url=f"/resumes/{resume['id']}/pdf" if resume else None,
        error=_error(conn, row),
    )


def _ready_resume_id(conn: psycopg.Connection, profile_id: UUID, application_id: UUID) -> UUID:
    row = applications_repo.lock(conn, profile_id, application_id)
    if row is None:
        raise NotFound("Application not found")
    if row["status"] != "ready":
        raise Conflict(f"This resume is not ready for review (status: {row['status']})")
    current = applications_repo.review_row(conn, profile_id, application_id)
    return current["resume_id"]


def update_cover_note(
    conn: psycopg.Connection, profile_id: UUID, application_id: UUID, cover_note: str
) -> None:
    with conn.transaction():
        resume_id = _ready_resume_id(conn, profile_id, application_id)
        resumes_repo.update_cover_note(conn, resume_id, cover_note.strip())


def decide(
    conn: psycopg.Connection, profile_id: UUID, application_id: UUID, action: str
) -> StatusResponse:
    """Approve to queue for sending in Phase 3, or reject. Rejecting is not a skip, so it
    does not lower this employer's future scores."""
    with conn.transaction():
        _ready_resume_id(conn, profile_id, application_id)
        status = "approved" if action == "approve" else "closed"
        status_word = "approved" if action == "approve" else "rejected"
        applications_repo.set_status(conn, application_id, status)
        events_repo.add(
            conn,
            "note",
            application_id=application_id,
            payload={"text": f"Tailored resume {status_word}"},
        )
    return StatusResponse(id=application_id, status=status)


def request_tailoring(conn: psycopg.Connection, profile_id: UUID, application_id: UUID) -> None:
    """Retry a failed tailoring, or make a new version of a ready one."""
    with conn.transaction():
        row = applications_repo.lock(conn, profile_id, application_id)
        if row is None:
            raise NotFound("Application not found")
        if row["status"] not in ("tailoring", "ready"):
            raise Conflict(f"This job is {row['status']}, so its resume can't be regenerated")
        applications_repo.set_status(conn, application_id, "tailoring")


def pdf_path(
    conn: psycopg.Connection, profile_id: UUID, resume_id: UUID, upload_dir: Path
) -> Path:
    """Only tailored PDFs inside the upload folder are ever served."""
    resume = resumes_repo.get_tailored(conn, profile_id, resume_id)
    if resume is None or not resume["file_path"]:
        raise NotFound("Resume not found")
    path = Path(resume["file_path"]).resolve()
    if not path.is_relative_to(Path(upload_dir).resolve()) or not path.is_file():
        raise NotFound("Resume not found")
    return path
