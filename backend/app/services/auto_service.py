"""Phase 5: auto mode. Approves strong matches, their resumes, and queues the email.

It only acts for a profile that switched it on and uploaded its own resume. It approves at most
`daily_limit` jobs a NZ day, best score first, and only approves resumes for jobs it approved
itself. Sending, follow-ups and calls keep their own switches and limits.
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings
from app.core.errors import AppError, BadRequest
from app.core.workdays import nz_day_start
from app.repositories import (
    contacts_repo,
    events_repo,
    outbox_repo,
    outreach_repo,
    profiles_repo,
    resumes_repo,
)
from app.schemas.auto import (
    MAX_BUSINESS_TYPE_LENGTH,
    MAX_BUSINESS_TYPES,
    AutoModeSettings,
    AutoModeView,
    clean_business_types,
)
from app.services import (
    application_service,
    calls_service,
    contact_service,
    notify_service,
    outbox_contacts,
    outbox_service,
    prep_service,
    resume_review_service,
)
from app.services.advert_contact import applies_on_site_only
from app.services.contact_service import ContactTools

logger = logging.getLogger(__name__)

# A job waiting on an unread website is retried at most this often, and given up on after a day.
RETRY_EVERY = timedelta(hours=1)
GIVE_UP_AFTER = timedelta(hours=24)


def get_settings(conn: psycopg.Connection, profile_id: UUID | str) -> AutoModeSettings:
    row = conn.execute(
        """
        select p.auto_mode, p.business_types, p.prospects_enabled, p.prospects_per_day,
               s.ai -> 'auto' as auto
        from profiles p left join settings s on s.profile_id = p.id
        where p.id = %s
        """,
        (profile_id,),
    ).fetchone()
    stored = (row["auto"] if row else None) or {}
    return AutoModeSettings(
        enabled=bool(row and row["auto_mode"]),
        prospects_enabled=bool(row and row["prospects_enabled"]),
        prospects_per_day=row["prospects_per_day"] if row else 5,
        business_types=list(row["business_types"] or []) if row else [],
        **{key: stored[key] for key in ("min_score", "daily_limit") if key in stored},
    )


def save_settings(conn: psycopg.Connection, profile_id: UUID | str,
                  value: AutoModeSettings) -> None:
    if value.prospects_enabled and not value.enabled:
        raise BadRequest("Turn on Auto mode first.")
    was_on = prospects_on(conn, profile_id)
    will_be_on = value.enabled and value.prospects_enabled
    conn.execute(
        """
        update profiles set auto_mode = %s, business_types = %s, prospects_enabled = %s,
                             prospects_per_day = %s
        where id = %s
        """,
        (value.enabled, value.business_types, will_be_on, value.prospects_per_day, profile_id),
    )
    conn.execute(
        """
        insert into settings (profile_id, ai) values (%s, %s)
        on conflict (profile_id) do update set ai = settings.ai || excluded.ai, updated_at = now()
        """,
        (profile_id, Jsonb({"auto": {"min_score": value.min_score,
                                     "daily_limit": value.daily_limit}})),
    )
    if was_on and not will_be_on:
        # Turning Google Maps outreach off (or Auto mode, which turns it off) stops it all now.
        outbox_service.stop_speculative_outreach(conn, profile_id)


def prospects_on(conn: psycopg.Connection, profile_id: UUID | str) -> bool:
    """Whether Google Maps outreach is switched on (only ever true with Auto mode on)."""
    row = conn.execute(
        "select prospects_enabled from profiles where id = %s", (profile_id,)
    ).fetchone()
    return bool(row and row["prospects_enabled"])


def approved_today(conn: psycopg.Connection, profile_id: UUID | str, now: datetime) -> int:
    return conn.execute(
        "select count(*) as n from applications where profile_id = %s "
        "and kind = 'advert' and auto_approved_at >= %s",
        (profile_id, nz_day_start(now)),
    ).fetchone()["n"]


def _suggested_business_types(conn: psycopg.Connection, profile_id: UUID | str) -> list[str]:
    context = profiles_repo.load_search_context(conn, profile_id)
    if context is None:
        return []
    usable = [item for item in clean_business_types(context[0].industries)
              if len(item) <= MAX_BUSINESS_TYPE_LENGTH]
    return usable[:MAX_BUSINESS_TYPES]


def view(conn: psycopg.Connection, profile_id: UUID | str, settings: Settings,
         now: datetime) -> AutoModeView:
    current = get_settings(conn, profile_id)
    return AutoModeView(
        **current.model_dump(),
        approved_today=approved_today(conn, profile_id, now),
        sending_enabled=outbox_service.sending_configured(settings),
        calls_enabled=calls_service.automatic(settings),
        business_types_suggested=[] if current.business_types
        else _suggested_business_types(conn, profile_id),
    )


def _has_own_resume(conn: psycopg.Connection, profile_id: UUID | str) -> bool:
    base = resumes_repo.latest_base(conn, profile_id)
    content = base["content"] if base else {}
    return bool(content.get("text")) and not content.get("example")


def enabled(conn: psycopg.Connection) -> bool:
    """Whether any profile has auto mode on."""
    return bool(conn.execute(
        "select exists (select 1 from profiles where auto_mode) as on"
    ).fetchone()["on"])


def _candidates(conn, profile_id, min_score: int, limit: int) -> list[dict[str, Any]]:
    return conn.execute(
        """
        select a.id, j.company_id from applications a join jobs j on j.id = a.job_id
        where a.profile_id = %s and a.status = 'shortlisted' and a.score >= %s
          and j.source <> 'example'
        order by a.score desc, a.created_at
        limit %s
        """,
        (profile_id, min_score, limit),
    ).fetchall()


def _look_up_contacts(conn, company_id, tools: ContactTools, now: datetime) -> None:
    """Find the employer's contacts before their advert is judged. A failure never stops a run."""
    try:
        with conn.transaction():
            contact_service.lookup(conn, company_id, tools, now)
    except (AppError, psycopg.Error):
        logger.warning("Contact lookup failed during auto mode", exc_info=True)


def _approve_jobs(conn, settings, profile_id, options: AutoModeSettings, now,
                  contact_tools: ContactTools | None) -> int:
    remaining = options.daily_limit - approved_today(conn, profile_id, now)
    approved = 0
    for row in _candidates(conn, profile_id, options.min_score, max(remaining, 0)):
        application_service.decide(conn, profile_id, row["id"], "approve", "auto mode")
        conn.execute("update applications set auto_approved_at = %s where id = %s",
                     (now, row["id"]))
        events_repo.add(conn, "note", application_id=row["id"],
                        payload={"text": "Approved by auto mode"})
        prep_service.on_approved(conn, profile_id, row["id"], settings, now)
        conn.commit()  # the approval is saved before any employer site is read
        if contact_tools is not None and row["company_id"] is not None:
            _look_up_contacts(conn, row["company_id"], contact_tools, now)
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


def _contacts_unchecked(conn, company_id) -> bool:
    """An employer with a website whose contacts have not been checked yet."""
    if company_id is None:
        return False
    company = contacts_repo.get_company(conn, company_id)
    return bool(company and company["website"] and company["contacts_checked_at"] is None)


def _lookup_due(conn, company_id, now: datetime) -> bool:
    """No read yet, or the last attempt was more than an hour ago."""
    attempted = contacts_repo.get_company(conn, company_id)["contacts_attempted_at"]
    return attempted is None or now - attempted > RETRY_EVERY


def _notify_apply_yourself(conn, settings, profile_id, row, reason: str) -> None:
    notify_service.notify(
        conn, settings, profile_id, "auto_apply_yourself",
        f"Auto mode approved {row['title']} at {row['company']}. {reason}",
        f"auto-apply-yourself:{row['id']}",
    )
    conn.commit()


def _queue_speculative(conn, settings, profile_id, row, now) -> int:
    """A speculative enquiry goes to the address the employer published. There is no advert,
    job site, contact lookup or apply-yourself step, and it never waits for one."""
    if not prospects_on(conn, profile_id):
        outbox_service.stop_speculative_outreach(conn, profile_id)
        conn.commit()
        return 0
    if row["company_id"] in outreach_repo.blocked(conn, profile_id):
        outbox_repo.set_outcome(conn, row["id"], "closed")
        events_repo.add(conn, "note", application_id=row["id"],
                        payload={"text": "Closed: the employer is blocked from enquiries"})
        conn.commit()
        return 0
    address = outbox_service.suggested_address(conn, row)
    if address is None:
        outbox_repo.set_outcome(conn, row["id"], "closed")
        events_repo.add(conn, "note", application_id=row["id"],
                        payload={"text": "Closed: no email address published"})
        conn.commit()
        return 0
    outbox_service.queue_email(conn, profile_id, row["id"], address, settings, now)
    notify_service.notify(
        conn, settings, profile_id, "auto_sent",
        f"Auto mode is sending your enquiry to {row['company']} to {address}.",
        f"auto-sent:{row['id']}",
    )
    conn.commit()
    return 1


def _queue_emails(conn, settings, profile_id, now, contact_tools: ContactTools | None) -> int:
    queued = 0
    for row in outbox_repo.to_send_rows(conn, profile_id):
        auto = conn.execute(
            "select auto_approved_at from applications where id = %s", (row["id"],)
        ).fetchone()["auto_approved_at"]
        if auto is None:
            continue
        if row["kind"] == "speculative":
            queued += _queue_speculative(conn, settings, profile_id, row, now)
            continue
        if applies_on_site_only(row["description"] or "", row["url"]):
            _notify_apply_yourself(conn, settings, profile_id, row,
                                   "The advert asks for applications on the job site only, "
                                   "so apply on the job site from the Outbox.")
            continue
        address = outbox_service.suggested_address(conn, row)
        waiting = (address is None and _contacts_unchecked(conn, row["company_id"])
                   and now - auto <= GIVE_UP_AFTER)
        if waiting:
            if contact_tools is not None and _lookup_due(conn, row["company_id"], now):
                conn.commit()  # no transaction is held open while the employer's site is read
                _look_up_contacts(conn, row["company_id"], contact_tools, now)
                conn.commit()
                address = outbox_service.suggested_address(conn, row)
            if address is None and _contacts_unchecked(conn, row["company_id"]):
                continue  # the employer's site is not read yet; try again on a later pass
        if address is None:
            # The same reason the Outbox's contacts list gives for this application.
            contact_row = outbox_repo.contact_rows(conn, profile_id,
                                                   application_id=row["id"])[0]
            reason = outbox_contacts.missing_reason(contact_row)
            _notify_apply_yourself(conn, settings, profile_id, row,
                                   f"No email address found ({reason}). Apply on the job site "
                                   "from the Outbox.")
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


def run(conn: psycopg.Connection, settings: Settings, now: datetime,
        contact_tools: ContactTools | None = None) -> dict[str, int]:
    report = {"auto_approved": 0, "auto_resumes": 0, "auto_queued": 0}
    profiles = conn.execute("select id from profiles where auto_mode").fetchall()
    for profile in profiles:
        profile_id = profile["id"]
        if not _has_own_resume(conn, profile_id):
            continue
        options = get_settings(conn, profile_id)
        try:
            report["auto_approved"] += _approve_jobs(conn, settings, profile_id, options, now,
                                                      contact_tools)
            report["auto_resumes"] += _approve_resumes(conn, profile_id)
            report["auto_queued"] += _queue_emails(conn, settings, profile_id, now,
                                                   contact_tools)
        except AppError:
            conn.rollback()
            logger.warning("Auto mode stopped for this run", exc_info=True)
    return report
