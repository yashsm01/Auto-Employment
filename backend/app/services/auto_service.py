"""Phase 5: auto mode. Approves strong matches, their resumes, and queues the email.

It only acts for a profile that switched it on and uploaded its own resume. It approves at most
`daily_limit` jobs a NZ day, best score first, and only approves resumes for jobs it approved
itself. Sending, follow-ups and calls keep their own switches and limits.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings
from app.core.errors import AppError
from app.core.workdays import nz_day_start
from app.repositories import events_repo, outbox_repo, resumes_repo
from app.schemas.auto import AutoModeSettings, AutoModeView
from app.services import (
    application_service,
    calls_service,
    notify_service,
    outbox_service,
    prep_service,
    resume_review_service,
)

logger = logging.getLogger(__name__)


def get_settings(conn: psycopg.Connection, profile_id: UUID | str) -> AutoModeSettings:
    row = conn.execute(
        """
        select p.auto_mode, s.ai -> 'auto' as auto
        from profiles p left join settings s on s.profile_id = p.id
        where p.id = %s
        """,
        (profile_id,),
    ).fetchone()
    stored = (row["auto"] if row else None) or {}
    return AutoModeSettings(enabled=bool(row and row["auto_mode"]), **{
        key: stored[key] for key in ("min_score", "daily_limit") if key in stored
    })


def save_settings(conn: psycopg.Connection, profile_id: UUID | str,
                  value: AutoModeSettings) -> None:
    conn.execute("update profiles set auto_mode = %s where id = %s", (value.enabled, profile_id))
    conn.execute(
        """
        insert into settings (profile_id, ai) values (%s, %s)
        on conflict (profile_id) do update set ai = settings.ai || excluded.ai, updated_at = now()
        """,
        (profile_id, Jsonb({"auto": {"min_score": value.min_score,
                                     "daily_limit": value.daily_limit}})),
    )


def approved_today(conn: psycopg.Connection, profile_id: UUID | str, now: datetime) -> int:
    return conn.execute(
        "select count(*) as n from applications where profile_id = %s "
        "and auto_approved_at >= %s",
        (profile_id, nz_day_start(now)),
    ).fetchone()["n"]


def view(conn: psycopg.Connection, profile_id: UUID | str, settings: Settings,
         now: datetime) -> AutoModeView:
    return AutoModeView(
        **get_settings(conn, profile_id).model_dump(),
        approved_today=approved_today(conn, profile_id, now),
        sending_enabled=outbox_service.sending_configured(settings),
        calls_enabled=calls_service.automatic(settings),
    )


def _has_own_resume(conn: psycopg.Connection, profile_id: UUID | str) -> bool:
    base = resumes_repo.latest_base(conn, profile_id)
    content = base["content"] if base else {}
    return bool(content.get("text")) and not content.get("example")


def _candidates(conn, profile_id, min_score: int, limit: int) -> list[dict[str, Any]]:
    return conn.execute(
        """
        select a.id from applications a join jobs j on j.id = a.job_id
        where a.profile_id = %s and a.status = 'shortlisted' and a.score >= %s
          and j.source <> 'example'
        order by a.score desc, a.created_at
        limit %s
        """,
        (profile_id, min_score, limit),
    ).fetchall()


def _approve_jobs(conn, settings, profile_id, options: AutoModeSettings, now) -> int:
    remaining = options.daily_limit - approved_today(conn, profile_id, now)
    approved = 0
    for row in _candidates(conn, profile_id, options.min_score, max(remaining, 0)):
        application_service.decide(conn, profile_id, row["id"], "approve", "auto mode")
        conn.execute("update applications set auto_approved_at = %s where id = %s",
                     (now, row["id"]))
        events_repo.add(conn, "note", application_id=row["id"],
                        payload={"text": "Approved by auto mode"})
        prep_service.on_approved(conn, profile_id, row["id"], settings, now)
        conn.commit()
        approved += 1
    return approved


def _approve_resumes(conn, profile_id) -> int:
    rows = conn.execute(
        "select id from applications where profile_id = %s and status = 'ready' "
        "and auto_approved_at is not null",
        (profile_id,),
    ).fetchall()
    for row in rows:
        resume_review_service.decide(conn, profile_id, row["id"], "approve")
        events_repo.add(conn, "note", application_id=row["id"],
                        payload={"text": "Resume approved by auto mode"})
        conn.commit()
    return len(rows)


def _queue_emails(conn, settings, profile_id, now) -> int:
    queued = 0
    for row in outbox_repo.to_send_rows(conn, profile_id):
        auto = conn.execute(
            "select auto_approved_at from applications where id = %s", (row["id"],)
        ).fetchone()["auto_approved_at"]
        if auto is None:
            continue
        address = outbox_service.suggested_address(conn, row)
        if address is None:
            notify_service.notify(
                conn, settings, profile_id, "auto_apply_yourself",
                f"Auto mode approved {row['title']} at {row['company']}. The advert has no "
                "email address, so apply on the job site from the Outbox.",
                f"auto-apply-yourself:{row['id']}",
            )
            conn.commit()
            continue
        outbox_service.queue_email(conn, profile_id, row["id"], address, settings, now)
        notify_service.notify(
            conn, settings, profile_id, "auto_sent",
            f"Auto mode is sending your application for {row['title']} at {row['company']} "
            f"to {address}.",
            f"auto-sent:{row['id']}",
        )
        conn.commit()
        queued += 1
    return queued


def run(conn: psycopg.Connection, settings: Settings, now: datetime) -> dict[str, int]:
    report = {"auto_approved": 0, "auto_resumes": 0, "auto_queued": 0}
    profiles = conn.execute("select id from profiles where auto_mode").fetchall()
    for profile in profiles:
        profile_id = profile["id"]
        if not _has_own_resume(conn, profile_id):
            continue
        options = get_settings(conn, profile_id)
        try:
            report["auto_approved"] += _approve_jobs(conn, settings, profile_id, options, now)
            report["auto_resumes"] += _approve_resumes(conn, profile_id)
            report["auto_queued"] += _queue_emails(conn, settings, profile_id, now)
        except AppError:
            conn.rollback()
            logger.warning("Auto mode stopped for this run", exc_info=True)
    return report
