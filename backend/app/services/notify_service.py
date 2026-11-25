"""WhatsApp updates to the user only. Nothing is ever sent to employers on WhatsApp."""

import logging
from datetime import datetime
from typing import Protocol
from uuid import UUID

import psycopg

from app.core.config import Settings
from app.core.errors import ProviderError
from app.repositories import notifications_repo

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
TEST_MESSAGE = "Test message from NZ Job Autopilot."


class WhatsApp(Protocol):
    def send(self, to: str, text: str) -> None: ...


def configured(settings: Settings) -> bool:
    return bool(
        settings.whatsapp_enabled and settings.whatsapp_service_url and settings.whatsapp_to
    )


def masked(number: str) -> str:
    return f"{number[:3]} {number[3:5]} *** *{number[-3:]}" if len(number) > 8 else "***"


def notify(conn: psycopg.Connection, settings: Settings, profile_id: UUID | str, kind: str,
           text: str, dedupe_key: str) -> None:
    """Queue an update for the next outbox run. Kept only when WhatsApp is switched on."""
    if configured(settings):
        notifications_repo.add(conn, profile_id, kind, text, dedupe_key)


def job_label(conn: psycopg.Connection, application_id: UUID | str) -> dict | None:
    return conn.execute(
        """
        select a.profile_id, j.title, coalesce(c.name, 'the employer') as company
        from applications a join jobs j on j.id = a.job_id
        left join companies c on c.id = j.company_id
        where a.id = %s
        """,
        (application_id,),
    ).fetchone()


def deliver(conn: psycopg.Connection, settings: Settings, whatsapp: WhatsApp | None,
            now: datetime) -> int:
    if not configured(settings) or whatsapp is None:
        return 0
    sent = 0
    for row in notifications_repo.queued(conn):
        try:
            whatsapp.send(settings.whatsapp_to, row["text"])
        except ProviderError as error:
            notifications_repo.record_failure(conn, row["id"], str(error), MAX_ATTEMPTS)
            conn.commit()
            logger.warning("WhatsApp update failed: %s", error)
            break  # the service is probably down; try again next run
        notifications_repo.mark_sent(conn, row["id"], now)
        conn.commit()
        sent += 1
    return sent
