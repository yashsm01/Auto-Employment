"""Tailors resumes for approved jobs, one application at a time."""

import logging
from datetime import UTC, datetime

import psycopg

from app.chains.manager import get_tailoring_chains
from app.core.config import Settings
from app.core.errors import Conflict
from app.db.client import connect
from app.graphs.resume.deps import ResumeDeps
from app.graphs.runner import run_graph
from app.repositories import applications_repo
from app.services import notify_service

logger = logging.getLogger(__name__)


def _deps(settings: Settings, conn: psycopg.Connection) -> ResumeDeps:
    sections, tailor, check = get_tailoring_chains(settings)
    return ResumeDeps(
        conn=conn,
        sections_chain=sections,
        tailor_chain=tailor,
        check_chain=check,
        upload_dir=settings.upload_dir,
        now=datetime.now(UTC),
    )


def _notify_ready(conn: psycopg.Connection, settings: Settings, application_id: str) -> None:
    label = notify_service.job_label(conn, application_id)
    if label:
        notify_service.notify(
            conn, settings, label["profile_id"], "resume_ready",
            f"Tailored resume ready for review: {label['title']} at {label['company']}.",
            f"ready:{application_id}:{datetime.now(UTC).date()}",
        )
        conn.commit()


def tailor_one(settings: Settings, application_id: str) -> None:
    """Tailor one application now, for Retry and Regenerate. Never raises."""
    try:
        with connect(settings.database_url) as conn:
            run_graph("resume", {"application_id": application_id}, _deps(settings, conn))
    except Conflict:
        logger.info("A resume is already being tailored; the queue will pick this one up")
    except Exception:
        logger.exception("Tailoring failed for %s", application_id)


def process_tailoring_queue(settings: Settings, only_untried: bool = True) -> int:
    """Tailor every application waiting in 'tailoring'. Returns how many were attempted.

    Applications that already failed are left for the Retry button, so a broken key does not
    spend money every 15 minutes.
    """
    attempted: list[str] = []
    try:
        with connect(settings.database_url) as conn:
            while True:
                row = applications_repo.next_tailoring(conn, attempted, only_untried)
                conn.commit()
                if row is None:
                    break
                application_id = str(row["id"])
                attempted.append(application_id)
                try:
                    result = run_graph(
                        "resume", {"application_id": application_id}, _deps(settings, conn)
                    )
                    if result.status == "ok":
                        _notify_ready(conn, settings, application_id)
                except Conflict:
                    attempted.pop()
                    break  # another worker is running and will continue the queue
    except Exception:
        logger.exception("The tailoring queue stopped")
    return len(attempted)
