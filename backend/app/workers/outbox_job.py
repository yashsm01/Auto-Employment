"""Every 15 minutes: notice replies, queue follow-ups, and send within the daily limit."""

import logging
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
import psycopg

from app.core.config import Settings
from app.core.errors import ProviderError
from app.core.workdays import add_working_days, nz_day_start, nz_today
from app.db.client import connect
from app.providers.channels.smtp_sender import SmtpSender
from app.providers.channels.whatsapp_service import WhatsAppService
from app.providers.jobs.gmail_alerts import ImapMailReader
from app.providers.voice.omnidim import OmniDimClient
from app.repositories import calls_repo, events_repo, outbox_repo, outreach_repo
from app.services import auto_service, calls_service, notify_service, outbox_service, source_service
from app.services.contact_service import ContactTools
from app.services.outbox_service import (
    FOLLOW_UP_WORKING_DAYS,
    MAX_ATTEMPTS,
    RETRY_AFTER,
    max_follow_ups,
)

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_SECONDS = 30
SIGN_IN_REFUSED = "app password was refused"
# Only one outbox run at a time, so the same email is never sent twice.
LOCK_KEY = 73_032_026


class Sender(Protocol):
    def send(self, **email: Any) -> str: ...


class ReplyReader(Protocol):
    def list_ids(self, query: str, limit: int) -> list[str]: ...

    def read(self, message_id: str) -> Any: ...

    def close(self) -> None: ...


def _check_bounces(conn: psycopg.Connection, mail: ReplyReader, settings: Settings) -> int:
    bounced = 0
    for row in outbox_repo.awaiting_reply(conn):
        since = nz_today(row["applied_at"]).strftime("%Y/%m/%d")
        query = f'from:(mailer-daemon OR postmaster) after:{since} "{row["to_address"]}"'
        try:
            found = mail.list_ids(query, 1)
        except ProviderError:
            logger.warning("Could not check for bounced emails", exc_info=True)
            return bounced
        if not found:
            continue
        error = f"Bounced: {row['to_address']} does not accept email."
        outbox_repo.cancel_pending_follow_ups(conn, row["id"])
        calls_repo.cancel_queued(conn, row["id"], "Cancelled: the email bounced.")
        outbox_repo.mark_bounced(conn, row["outbox_id"], row["id"], error)
        if row["kind"] == "speculative":
            # Nothing else is sent to this employer: the enquiry is closed, not re-queued.
            outbox_repo.set_outcome(conn, row["id"], "closed")
            outreach_repo.block(conn, row["profile_id"], row["company_id"], "bounced")
            message = f"Your enquiry to {row['company']} bounced, so it was not sent again."
        else:
            message = (f"Your email about {row['title']} at {row['company']} bounced. "
                       "Choose another address in the Outbox.")
        events_repo.add(conn, "note", application_id=row["id"], payload={"text": error})
        notify_service.notify(
            conn, settings, row["profile_id"], "bounced", message,
            f"bounced:{row['outbox_id']}",
        )
        conn.commit()
        bounced += 1
    return bounced


def _is_real_reply(mail: ReplyReader, ids: list[str]) -> bool:
    """At least one answer that isn't an out-of-office or other automatic reply."""
    for message_id in ids:
        try:
            if not mail.read(message_id).auto_reply:
                return True
        except ProviderError:
            return True  # can't tell, so treat it as a reply rather than keep following up
    return False


def _check_replies(conn: psycopg.Connection, mail: ReplyReader, settings: Settings) -> int:
    replies = 0
    for row in outbox_repo.awaiting_reply(conn):
        since = nz_today(row["applied_at"]).strftime("%Y/%m/%d")
        try:
            found = mail.list_ids(f"from:{row['to_address']} after:{since}", 5)
        except ProviderError:
            logger.warning("Could not check replies", exc_info=True)
            return replies
        if not found or not _is_real_reply(mail, found):
            continue
        outbox_repo.cancel_pending_follow_ups(conn, row["id"])
        outbox_repo.set_outcome(conn, row["id"], "replied")
        calls_repo.cancel_queued(conn, row["id"], outbox_service.CANCELLED_BY["replied"])
        events_repo.add(conn, "replied", application_id=row["id"],
                        payload={"from": row["to_address"]})
        if row["kind"] == "speculative":
            outreach_repo.block(conn, row["profile_id"], row["company_id"], "replied")
            message = f"Reply received: your enquiry to {row['company']}."
        else:
            message = f"{row['company']} replied about {row['title']}."
        notify_service.notify(conn, settings, row["profile_id"], "replied", message,
                              f"replied:{row['id']}")
        conn.commit()
        replies += 1
    return replies


def _schedule_follow_ups(
    conn: psycopg.Connection, now: datetime, settings: Settings
) -> tuple[int, int, int]:
    queued = closed = drafts = 0
    for row in outbox_repo.manual_follow_ups_due(conn, nz_today(now)):
        notify_service.notify(
            conn, settings, row["profile_id"], "follow_up_due",
            f"Follow up today: {row['title']} at {row['company']}.",
            f"follow-up:{row['id']}:{row['next_follow_up']}",
        )
        conn.commit()
    for row in outbox_repo.follow_ups_due(conn, nz_today(now)):
        if row["kind"] == "speculative" and not auto_service.prospects_on(conn, row["profile_id"]):
            outbox_service.stop_speculative_outreach(conn, row["profile_id"])
            conn.commit()
            continue
        if row["follow_ups"] >= max_follow_ups(row["kind"]):
            # A speculative enquiry never queues a call: it closes after its one follow-up.
            speculative = row["kind"] == "speculative"
            if not speculative and calls_service.queue_after_follow_ups(
                conn, settings, row["id"], row["profile_id"], now
            ):
                conn.commit()
                continue
            outbox_repo.set_outcome(conn, row["id"], "closed")
            events_repo.add(conn, "note", application_id=row["id"], payload={"text": (
                "Closed: no reply after one follow-up" if speculative
                else "Closed: no reply after two follow-ups")})
            conn.commit()
            closed += 1
            continue
        if outbox_repo.pending(conn, row["id"], "follow_up"):
            continue
        first = outbox_repo.first_sent(conn, row["id"])
        if first is None:
            continue
        contact = outbox_service.contact_details(conn, row["profile_id"])
        asking = outbox_service.follow_up_settings(conn, row["profile_id"]).mode == "ask"
        sent_on = nz_today(first["sent_at"])
        if row["kind"] == "speculative":
            body = outbox_service.speculative_follow_up_body(row["company"], sent_on, contact)
        else:
            body = outbox_service.follow_up_body(row["title"], sent_on, contact,
                                                 row["follow_ups"] + 1)
        outbox_repo.queue(
            conn,
            application_id=row["id"],
            kind="follow_up",
            to=first["to_address"],
            subject=f"Re: {first['subject']}",
            body=body,
            attachment_path=None,
            attachment_name=None,
            reply_to_message_id=first["message_id"],
            scheduled_at=now,
            status="draft" if asking else "queued",
        )
        if asking:
            # Waits for Send or Skip. Clearing the date means no second draft is made.
            outbox_repo.stop_follow_ups(conn, row["id"])
            notify_service.notify(
                conn, settings, row["profile_id"], "follow_up_due",
                f"Follow up today: {row['title']} at {row['company']}.",
                f"follow-up:{row['id']}:{row['next_follow_up']}",
            )
            conn.commit()
            drafts += 1
            continue
        conn.commit()
        queued += 1
    return queued, closed, drafts


def _send_due(
    conn: psycopg.Connection, sender: Sender, now: datetime, settings: Settings
) -> tuple[int, int]:
    sent = failed = 0
    skip: list[str] = []
    today = nz_today(now)
    while True:
        row = outbox_repo.next_due(conn, now, skip)
        if row is None:
            break
        outbox_id = str(row["id"])
        if row["application_kind"] == "speculative" and not auto_service.prospects_on(
            conn, row["profile_id"]
        ):
            outbox_service.stop_speculative_outreach(conn, row["profile_id"])
            conn.commit()
            skip.append(outbox_id)  # cancelled above; never sent
            continue
        limit = outbox_repo.daily_limit(conn, row["profile_id"])
        if outbox_repo.sent_since(conn, row["profile_id"], nz_day_start(now)) >= limit:
            skip.append(outbox_id)
            continue
        path = outbox_service.attachment(row)
        try:
            if path is not None and not path.is_file():
                raise ProviderError("email", "the resume PDF is missing; regenerate it")
            message_id = sender.send(
                to=row["to_address"],
                subject=row["subject"] or "",
                body=row["body"],
                attachment=path,
                attachment_name=row["attachment_name"],
                reply_to_message_id=row["reply_to_message_id"],
                from_name=outbox_service.contact_name(conn, row["profile_id"]),
            )
        except ProviderError as error:
            status = outbox_repo.record_failure(
                conn, outbox_id, str(error), MAX_ATTEMPTS, now + RETRY_AFTER
            )
            if status == "failed":
                notify_service.notify(
                    conn, settings, row["profile_id"], "send_failed",
                    f"Couldn't send your email about {row['title']}: {error}",
                    f"failed:{outbox_id}",
                )
            conn.commit()
            skip.append(outbox_id)
            failed += status == "failed"
            if SIGN_IN_REFUSED in str(error):
                break  # every other email would fail the same way
            continue

        outbox_repo.mark_sent(conn, outbox_id, message_id, now)
        next_date = add_working_days(today, FOLLOW_UP_WORKING_DAYS)
        if row["kind"] == "application":
            outbox_repo.mark_applied(conn, row["application_id"], "email", now, next_date)
        elif row["kind"] == "follow_up":
            outbox_repo.mark_followed_up(conn, row["application_id"], next_date)
        events_repo.add(conn, "emailed", application_id=row["application_id"],
                        payload={"to": row["to_address"], "kind": row["kind"]})
        conn.commit()
        sent += 1
    return sent, failed


def process_outbox(
    settings: Settings,
    sender: Sender | None = None,
    mail: ReplyReader | None = None,
    now: datetime | None = None,
    omni: calls_service.Dialler | None = None,
    whatsapp: notify_service.WhatsApp | None = None,
    contact_tools: ContactTools | None = None,
) -> dict[str, int]:
    """One pass over the outbox. Never raises."""
    now = now or datetime.now(UTC)
    report = {"sent": 0, "failed": 0, "follow_ups": 0, "drafts": 0, "closed": 0, "replies": 0,
              "skipped": 0, "bounced": 0,
              "calls": 0, "call_results": 0, "updates": 0,
              "auto_approved": 0, "auto_resumes": 0, "auto_queued": 0}
    password = settings.email_app_password.get_secret_value()
    try:
        with connect(settings.database_url) as conn:
            if not conn.execute("select pg_try_advisory_lock(%s) as ok", (LOCK_KEY,)).fetchone()[
                "ok"
            ]:
                report["skipped"] = 1  # another run is busy and will finish the work
                return report
            conn.commit()
            try:
                with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as http:
                    omni = omni or (
                        OmniDimClient(http, settings.omnidim_api_key.get_secret_value(),
                                      settings.omnidim_base_url)
                        if calls_service.configured(settings) else None
                    )
                    whatsapp = whatsapp or (
                        WhatsAppService(
                            http, settings.whatsapp_service_url,
                            settings.whatsapp_service_token.get_secret_value(),
                            settings.whatsapp_to_field, settings.whatsapp_text_field,
                        )
                        if notify_service.configured(settings) else None
                    )
                    tools = contact_tools
                    if tools is None and auto_service.enabled(conn):
                        tools = source_service.build_contact_tools(settings, http)
                    _run(conn, settings, sender, mail, now, password, report, omni, whatsapp,
                         tools)
            finally:
                conn.execute("select pg_advisory_unlock(%s)", (LOCK_KEY,))
                conn.commit()
    except Exception:
        logger.exception("The outbox stopped")
    return report


def _run(
    conn: psycopg.Connection,
    settings: Settings,
    sender: Sender | None,
    mail: ReplyReader | None,
    now: datetime,
    password: str,
    report: dict[str, int],
    omni: calls_service.Dialler | None,
    whatsapp: notify_service.WhatsApp | None,
    contact_tools: ContactTools | None = None,
) -> None:
    """Auto mode first, then replies (so nobody who answered gets a follow-up), follow-ups,
    sending, calls and WhatsApp updates."""
    report.update(auto_service.run(conn, settings, now, contact_tools))
    if outbox_service.reading_configured(settings):
        reader = mail or ImapMailReader(
            settings.email_address, password, host=settings.email_imap_host
        )
        try:
            report["bounced"] = _check_bounces(conn, reader, settings)
            report["replies"] = _check_replies(conn, reader, settings)
        finally:
            reader.close()
    report["follow_ups"], report["closed"], report["drafts"] = _schedule_follow_ups(
        conn, now, settings
    )
    if outbox_service.sending_configured(settings):
        smtp = sender or SmtpSender(
            settings.email_smtp_host, settings.email_smtp_port, settings.email_address, password
        )
        report["sent"], report["failed"] = _send_due(conn, smtp, now, settings)
    if omni is not None:
        report["call_results"] = calls_service.poll_results(conn, settings, omni, now)
        report["calls"] = calls_service.dispatch_due(conn, settings, omni, now)
    report["updates"] = notify_service.deliver(conn, settings, whatsapp, now)
