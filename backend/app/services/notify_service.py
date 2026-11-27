"""WhatsApp updates to the user only. Nothing is ever sent to employers on WhatsApp."""

import logging
from datetime import date, datetime, time, timedelta
from typing import Protocol
from uuid import UUID

import psycopg

from app.core.config import Settings
from app.core.errors import ProviderError
from app.core.workdays import NZ_TIME, nz_today
from app.repositories import notifications_repo, profiles_repo

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


def _nz_window(day: date) -> tuple[datetime, datetime]:
    """[midnight, next midnight) in New Zealand. Built from wall-clock times so DST days hold."""
    start = datetime.combine(day, time(), NZ_TIME)
    end = datetime.combine(day + timedelta(days=1), time(), NZ_TIME)
    return start, end


def _count(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def daily_summary(conn: psycopg.Connection, profile_id: UUID | str, day: date) -> str | None:
    """One line about the user's own activity on this New Zealand day, or None if it was quiet.
    Employer addresses and phone numbers never appear in it."""
    start, end = _nz_window(day)
    sent = conn.execute(
        """
        select count(*) filter (where o.kind = 'application' and a.kind = 'advert') as applications,
               count(*) filter (where o.kind = 'application' and a.kind = 'speculative')
                   as speculative,
               count(*) filter (where o.kind = 'follow_up') as follow_ups
        from outbox o join applications a on a.id = o.application_id
        where a.profile_id = %s and o.sent_at >= %s and o.sent_at < %s
        """,
        (profile_id, start, end),
    ).fetchone()
    replies = conn.execute(
        """
        select count(*) as n from events e join applications a on a.id = e.application_id
        where a.profile_id = %s and e.type = 'replied' and e.created_at >= %s and e.created_at < %s
        """,
        (profile_id, start, end),
    ).fetchone()["n"]
    notices = conn.execute(
        """
        select kind, count(*) as n from notifications
        where profile_id = %s and kind in ('bounced', 'auto_apply_yourself')
          and created_at >= %s and created_at < %s
        group by kind
        """,
        (profile_id, start, end),
    ).fetchall()
    by_kind = {row["kind"]: row["n"] for row in notices}
    bounced = by_kind.get("bounced", 0)
    to_apply = by_kind.get("auto_apply_yourself", 0)

    parts = [
        (sent["applications"], "application sent", "applications sent"),
        (sent["follow_ups"], "follow-up", "follow-ups"),
        (replies, "reply", "replies"),
        (bounced, "bounced email", "bounced emails"),
        (sent["speculative"], "Google Maps employer emailed", "Google Maps employers emailed"),
        (to_apply, "job to apply for on its site", "jobs to apply for on their sites"),
    ]
    shown = [_count(n, singular, plural) for n, singular, plural in parts if n]
    if not shown:
        return None
    return "Today: " + ", ".join(shown) + "."


def send_daily_summaries(conn: psycopg.Connection, settings: Settings,
                         now: datetime) -> int:
    """Queue today's summary for every profile that had activity. Returns how many were queued.
    The dedupe key is per profile and per day, so a second run the same day queues nothing."""
    if not configured(settings):
        return 0
    day = nz_today(now)
    queued = 0
    for profile_id in profiles_repo.all_profile_ids(conn):
        text = daily_summary(conn, profile_id, day)
        if text is None:
            continue
        notify(conn, settings, profile_id, "daily_summary", text,
               f"daily-summary:{profile_id}:{day.isoformat()}")
        queued += 1
    conn.commit()
    return queued
