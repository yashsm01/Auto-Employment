"""Phase 3: queue approved applications, follow up, and track replies."""

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from app.core.config import Settings
from app.core.documents import extract_contact_details
from app.core.emails import find_emails, is_valid_email
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.phones import nz_e164
from app.core.workdays import add_working_days, nz_day_start, nz_today
from app.repositories import calls_repo, events_repo, outbox_repo, resumes_repo
from app.schemas.outbox import (
    DoneItem,
    FollowUpSettings,
    OutboxItem,
    OutboxView,
    ToSendItem,
    WaitingItem,
)
from app.schemas.tailoring import ContactDetails
from app.services import resume_review_service
from app.services.advert_contact import applies_on_site_only
from app.services.application_service import safe_url

NOT_VALID = "That is not a valid email address."
SITE_ONLY = "This advert asks you to apply on the job site."
MAX_ATTEMPTS = 3
RETRY_AFTER = timedelta(minutes=15)
FOLLOW_UP_WORKING_DAYS = 5
# Speculative enquiries get one follow-up; adverts get two.
_MAX_FOLLOW_UPS = {"advert": 2, "speculative": 1}
STOP_LINE = "If you'd rather I didn't contact you again, just reply and I won't."
CANCELLED_BY = {
    "replied": "Cancelled: the employer replied.",
    "closed": "Cancelled: you closed the job.",
    "stop_follow_ups": "Cancelled: you stopped follow-ups.",
}
_FILE_UNSAFE = re.compile(r'[\\/:*?"<>|]+')


def contact_details(conn: psycopg.Connection, profile_id: UUID | str) -> ContactDetails:
    """The user's own contact from the base resume: stored details, else read from its text."""
    base = resumes_repo.latest_base(conn, profile_id)
    content = base["content"] if base else {}
    contact = content.get("contact")
    if contact:
        return ContactDetails(**contact)
    text = content.get("text")
    return extract_contact_details(text) if text else ContactDetails()


def contact_name(conn: psycopg.Connection, profile_id: UUID | str) -> str | None:
    return contact_details(conn, profile_id).name


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _same_number(a: str, b: str) -> bool:
    """The same NZ number written two ways; other formats are compared by their digits."""
    e164_a, e164_b = nz_e164(a), nz_e164(b)
    if e164_a and e164_b:
        return e164_a == e164_b
    return bool(_digits(a)) and _digits(a) == _digits(b)


def _name_line(name: str | None) -> str:
    return f"Ngā mihi,\n{name}" if name else "Ngā mihi"


def signature(contact: ContactDetails) -> str:
    """The sign-off for a message from the user: the name, then phone and WhatsApp."""
    name = (contact.name or "").strip() or None
    phone = (contact.phone or "").strip()
    whatsapp = (contact.whatsapp or "").strip()
    lines = [_name_line(name)]
    if phone and whatsapp and _same_number(phone, whatsapp):
        lines.append(f"Phone and WhatsApp: {phone}")
    else:
        if phone:
            lines.append(f"Phone: {phone}")
        if whatsapp:
            lines.append(f"WhatsApp: {whatsapp}")
    return "\n".join(lines)


def sign_cover_note(body: str, contact: ContactDetails) -> str:
    """Swap the cover note's sign-off for the full signature. A note with no usual sign-off
    gets the phone and WhatsApp lines added at the end instead."""
    name = (contact.name or "").strip() or None
    ending = _name_line(name)
    text = body.rstrip()
    if text.endswith(ending):
        return text[: -len(ending)] + signature(contact)
    numbers = signature(contact)[len(ending):]
    return f"{text}\n\n{numbers.strip()}" if numbers.strip() else body


def _one_line(text: str | None) -> str:
    """Job titles come from alerts and web pages; headers must never carry line breaks."""
    return " ".join((text or "").split())


def subject_for(title: str, name: str | None) -> str:
    title, name = _one_line(title), _one_line(name)
    return f"Application for {title} – {name}" if name else f"Application for {title}"


def attachment_name(title: str, name: str | None) -> str:
    stem = f"{_one_line(name)} - {_one_line(title)}" if name else f"Resume - {_one_line(title)}"
    return f"{_one_line(_FILE_UNSAFE.sub(' ', stem))}.pdf"


def max_follow_ups(kind: str) -> int:
    return _MAX_FOLLOW_UPS.get(kind, _MAX_FOLLOW_UPS["advert"])


def speculative_subject(company: str, name: str | None) -> str:
    company, name = _one_line(company), _one_line(name)
    stem = f"Enquiry about opportunities at {company}"
    return f"{stem} – {name}" if name else stem


def speculative_attachment_name(name: str | None) -> str:
    stem = f"{_one_line(name)} - CV" if name else "CV"
    return f"{_one_line(_FILE_UNSAFE.sub(' ', stem))}.pdf"


def speculative_body(cover_note: str, contact: ContactDetails) -> str:
    """The cover note with the full signature, then the line that stops further emails."""
    return f"{sign_cover_note(cover_note, contact)}\n\n{STOP_LINE}"


def speculative_follow_up_body(company: str, sent_on: date, contact: ContactDetails) -> str:
    return (
        "Kia ora,\n\n"
        f"I'm following up on my earlier email about opportunities at {_one_line(company)}, "
        f"sent on {sent_on.strftime('%d %B %Y').lstrip('0')}. I'm still interested and would "
        "welcome the chance to talk. My CV is attached to that email.\n\n"
        f"{signature(contact)}\n\n{STOP_LINE}"
    )


def follow_up_body(title: str, sent_on: date, contact: ContactDetails, number: int) -> str:
    opening = (
        f"I'm following up on my application for the {title} role, sent on "
        f"{sent_on.strftime('%d %B %Y').lstrip('0')}."
        if number == 1
        else f"I'm following up once more on my application for the {title} role."
    )
    return (
        f"Kia ora,\n\n{opening} I'm still very interested and would welcome the chance to "
        f"talk. My resume is attached to my earlier email below.\n\n{signature(contact)}"
    )


def suggested_address(conn: psycopg.Connection, row: dict[str, Any]) -> str | None:
    """An address the employer published: the advert first, then who they name for hiring."""
    found = find_emails(row["description"] or "")
    if found:
        return found[0]
    company_id = row["company_id"]
    candidates = [
        *outbox_repo.hiring_emails(conn, company_id),
        *outbox_repo.recruiter_emails(conn, company_id),
        row["company_email"],
        *outbox_repo.company_emails(conn, company_id),
    ]
    for address in candidates:
        if address and is_valid_email(address.strip().casefold()):
            return address.strip().casefold()
    return None


def _application(conn, profile_id, application_id) -> dict[str, Any]:
    row = outbox_repo.application(conn, profile_id, application_id)
    if row is None:
        raise NotFound("Application not found")
    return row


def queue_email(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    application_id: UUID | str,
    to: str,
    settings: Settings,
    now: datetime,
) -> None:
    address = to.strip().casefold()
    if not is_valid_email(address):
        raise BadRequest(NOT_VALID)
    with conn.transaction():
        row = _application(conn, profile_id, application_id)
        if row["kind"] == "advert" and applies_on_site_only(row["description"] or "", row["url"]):
            raise BadRequest(SITE_ONLY)
        if row["status"] != "approved":
            raise Conflict(f"This job is {row['status']}, so its application can't be sent.")
        if row["apply_method"] is not None:
            raise Conflict("This application is already queued or applied for.")
        if row["resume_id"] is None:
            raise Conflict("This job has no tailored resume yet.")
        pdf = resume_review_service.pdf_path(conn, profile_id, row["resume_id"],
                                             settings.upload_dir)
        resume = resumes_repo.get_tailored(conn, profile_id, row["resume_id"])
        contact = contact_details(conn, profile_id)
        cover = resume["content"].get("cover_note") or ""
        if row["kind"] == "speculative":
            subject = speculative_subject(row["company"], contact.name)
            body = speculative_body(cover, contact)
            file_name = speculative_attachment_name(contact.name)
        else:
            subject = subject_for(row["title"], contact.name)
            body = sign_cover_note(cover, contact)
            file_name = attachment_name(row["title"], contact.name)
        outbox_repo.queue(
            conn,
            application_id=application_id,
            kind="application",
            to=address,
            subject=subject,
            body=body,
            attachment_path=pdf,
            attachment_name=file_name,
            reply_to_message_id=None,
            scheduled_at=now,
        )
        outbox_repo.set_method(conn, application_id, "email")
        events_repo.add(conn, "note", application_id=application_id,
                        payload={"text": f"Email queued to {address}"})


def mark_applied_manually(conn: psycopg.Connection, profile_id: UUID | str,
                          application_id: UUID | str, now: datetime) -> None:
    with conn.transaction():
        row = _application(conn, profile_id, application_id)
        if row["status"] != "approved" or row["apply_method"] is not None:
            raise Conflict(f"This job is {row['status']}, so it can't be marked as applied.")
        next_date = add_working_days(nz_today(now), FOLLOW_UP_WORKING_DAYS)
        outbox_repo.mark_applied(conn, application_id, "manual", now, next_date)
        events_repo.add(conn, "note", application_id=application_id,
                        payload={"text": "Applied on the job site"})


def record_outcome(conn: psycopg.Connection, profile_id: UUID | str,
                   application_id: UUID | str, action: str, now: datetime) -> None:
    with conn.transaction():
        row = _application(conn, profile_id, application_id)
        status = row["status"]
        if action in ("replied", "closed"):
            if status not in ("approved", "sent", "followed_up"):
                raise Conflict(f"This job is {status}.")
            outbox_repo.cancel_pending_follow_ups(conn, application_id)
            outbox_repo.set_outcome(conn, application_id, action)
            calls_repo.cancel_queued(conn, application_id, CANCELLED_BY[action])
            if action == "replied":
                events_repo.add(conn, "replied", application_id=application_id,
                                payload={"text": "Marked as replied"})
            else:
                events_repo.add(conn, "note", application_id=application_id,
                                payload={"text": "Closed by you"})
            return
        if status not in ("sent", "followed_up"):
            raise Conflict("Follow-ups apply only to applications already sent.")
        if action == "stop_follow_ups":
            outbox_repo.cancel_pending_follow_ups(conn, application_id)
            outbox_repo.stop_follow_ups(conn, application_id)
            calls_repo.cancel_queued(conn, application_id, CANCELLED_BY[action])
            return
        count = row["follow_ups"] + 1
        next_date = (
            add_working_days(nz_today(now), FOLLOW_UP_WORKING_DAYS)
            if count < max_follow_ups(row["kind"])
            else None
        )
        outbox_repo.mark_followed_up(conn, application_id, next_date)
        events_repo.add(conn, "note", application_id=application_id,
                        payload={"text": "Followed up"})


def cancel(conn: psycopg.Connection, profile_id: UUID | str, outbox_id: UUID | str) -> None:
    with conn.transaction():
        row = outbox_repo.get(conn, profile_id, outbox_id)
        if row is None:
            raise NotFound("Email not found")
        # Lock the application first, then read the email again: a send that finished in the
        # meantime must not be overwritten by this cancel.
        application = outbox_repo.application(conn, profile_id, row["application_id"])
        row = outbox_repo.get(conn, profile_id, outbox_id)
        if row is None:
            raise NotFound("Email not found")
        not_cancellable = row["status"] not in ("queued", "failed", "draft") or (
            row["kind"] == "application" and application["status"] != "approved"
        )
        if not_cancellable:
            raise Conflict("Only emails that have not been sent can be cancelled.")
        outbox_repo.set_status(conn, outbox_id, "cancelled")
        if row["kind"] == "application" and (
            outbox_repo.application_kind(conn, row["application_id"]) == "speculative"
        ):
            # A cancelled enquiry is closed, so auto mode never re-sends it.
            outbox_repo.set_outcome(conn, row["application_id"], "closed")
            events_repo.add(conn, "note", application_id=row["application_id"],
                            payload={"text": "Closed: you cancelled the enquiry"})
        elif row["kind"] == "application":
            outbox_repo.set_method(conn, row["application_id"], None)
        else:
            outbox_repo.stop_follow_ups(conn, row["application_id"])


def send_draft(conn: psycopg.Connection, profile_id: UUID | str, outbox_id: UUID | str,
               now: datetime) -> None:
    """Approve a follow-up that was waiting for the user: it goes out on the next run."""
    with conn.transaction():
        row = outbox_repo.get(conn, profile_id, outbox_id)
        if row is None or row["status"] != "draft":
            raise NotFound("Follow-up not found")
        outbox_repo.release_draft(conn, outbox_id, now)


def follow_up_settings(conn: psycopg.Connection, profile_id: UUID | str) -> FollowUpSettings:
    stored = outbox_repo.follow_up_settings(conn, profile_id)
    return FollowUpSettings(mode="ask" if stored.get("mode") == "ask" else "auto")


def save_follow_up_settings(conn: psycopg.Connection, profile_id: UUID | str,
                            value: FollowUpSettings) -> FollowUpSettings:
    outbox_repo.save_follow_up_settings(conn, profile_id, {"mode": value.mode})
    return value


def retry(conn: psycopg.Connection, profile_id: UUID | str, outbox_id: UUID | str,
          now: datetime) -> None:
    row = outbox_repo.get(conn, profile_id, outbox_id)
    if row is None:
        raise NotFound("Email not found")
    if row["status"] != "failed":
        raise Conflict("Only failed emails can be tried again.")
    outbox_repo.retry(conn, outbox_id, now)


def save_daily_limit(conn: psycopg.Connection, profile_id: UUID | str, limit: int) -> None:
    outbox_repo.set_daily_limit(conn, profile_id, limit)


def _item(row: dict[str, Any]) -> OutboxItem:
    return OutboxItem(
        id=row["id"], application_id=row["application_id"], title=row["title"],
        company=row["company"], kind=row["kind"],
        application_kind=row["application_kind"], to=row["to_address"],
        subject=row["subject"] or "", scheduled_at=row["scheduled_at"],
        attempts=row["attempts"], error=row["error"],
    )


def view(conn: psycopg.Connection, profile_id: UUID | str, settings: Settings,
         now: datetime) -> OutboxView:
    today = nz_today(now)
    to_send = [
        ToSendItem(
            application_id=row["id"], title=row["title"], company=row["company"],
            application_kind=row["kind"],
            suggested_to=suggested_address(conn, row), job_url=safe_url(row["url"]),
            pdf_url=f"/resumes/{row['resume_id']}/pdf" if row["resume_id"] else None,
            cover_note=row["cover_note"],
        )
        for row in outbox_repo.to_send_rows(conn, profile_id)
    ]
    from app.services.calls_service import latest_calls

    calls = latest_calls(conn)
    waiting = [
        WaitingItem(
            application_id=row["id"], title=row["title"], company=row["company"],
            apply_method=row["apply_method"] or "manual",
            application_kind=row["application_kind"], to=row["to_address"],
            applied_at=row["applied_at"], follow_ups=row["follow_ups"],
            next_follow_up=row["next_follow_up"],
            follow_up_due=bool(row["next_follow_up"] and row["next_follow_up"] <= today),
            job_url=safe_url(row["url"]),
            call_status=calls.get(str(row["id"]), {}).get("status"),
            captured_email=(calls.get(str(row["id"]), {}).get("extracted") or {}).get(
                "captured_email"
            ),
        )
        for row in outbox_repo.waiting_rows(conn, profile_id)
    ]
    return OutboxView(
        sending_enabled=sending_configured(settings),
        reading_enabled=reading_configured(settings),
        daily_limit=outbox_repo.daily_limit(conn, profile_id),
        sent_today=outbox_repo.sent_since(conn, profile_id, nz_day_start(now)),
        to_send=to_send,
        queued=[_item(r) for r in outbox_repo.outbox_rows(conn, profile_id, "queued")],
        failed=[_item(r) for r in outbox_repo.outbox_rows(conn, profile_id, "failed")],
        waiting=waiting,
        drafts=[_item(r) for r in outbox_repo.outbox_rows(conn, profile_id, "draft")],
        replied=[
            DoneItem(application_id=r["id"], title=r["title"], company=r["company"],
                     status=r["status"], updated_at=r["updated_at"])
            for r in outbox_repo.replied_rows(conn, profile_id)
        ],
    )


GOOGLE_MAPS_OFF = "Closed: Google Maps outreach was turned off"


def stop_speculative_outreach(conn: psycopg.Connection, profile_id: UUID | str) -> None:
    """Google Maps outreach is off. Enquiries not sent yet are cancelled, approved ones that were
    never sent are closed, and sent ones stop their follow-ups. They stay sent, so a reply or a
    bounce is still seen and still blocks the employer."""
    outbox_repo.cancel_speculative_pending(conn, profile_id)
    for application_id in outbox_repo.speculative_ids(conn, profile_id, ["approved"]):
        outbox_repo.set_outcome(conn, application_id, "closed")
        events_repo.add(conn, "note", application_id=application_id,
                        payload={"text": GOOGLE_MAPS_OFF})
    for application_id in outbox_repo.speculative_ids(conn, profile_id,
                                                      ["sent", "followed_up"]):
        outbox_repo.stop_follow_ups(conn, application_id)


def sending_configured(settings: Settings) -> bool:
    return bool(
        settings.email_send_enabled
        and settings.email_address
        and settings.email_app_password.get_secret_value()
    )


def reading_configured(settings: Settings) -> bool:
    return bool(
        settings.email_enabled
        and settings.email_address
        and settings.email_app_password.get_secret_value()
    )


def attachment(row: dict[str, Any]) -> Path | None:
    return Path(row["attachment_path"]) if row["attachment_path"] else None
