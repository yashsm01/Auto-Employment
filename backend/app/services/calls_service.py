"""Phase 4: an AI phone call when two email follow-ups get no reply."""

from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

import psycopg

from app.core.config import Settings
from app.core.emails import find_emails, is_valid_email
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.phones import nz_e164
from app.core.workdays import in_nz_business_hours, nz_day_start, nz_today
from app.repositories import calls_repo, events_repo, outbox_repo, resumes_repo
from app.repositories.prep_repo import month_start_nz
from app.services import notify_service, outbox_service, resume_review_service

NO_RESULT_AFTER = timedelta(hours=2)
NOT_SET_UP = "AI calls need OMNIDIM_API_KEY and OMNIDIM_AGENT_ID in backend/.env."
NO_PHONE = "Add your phone number under Your details on My resume profile first."
_CONTACT_EMAIL_PROMPT = (
    "The email address the person asked for the resume to be sent to, exactly as given. "
    "Leave empty if none was given."
)


class Dialler(Protocol):
    def dispatch(self, **call: Any) -> str: ...

    def find_log(self, *, agent_id: int, app_call_id: str, pages: int = 3) -> dict | None: ...


def configured(settings: Settings) -> bool:
    return bool(settings.omnidim_api_key.get_secret_value() and settings.omnidim_agent_id)


def automatic(settings: Settings) -> bool:
    return settings.calls_enabled and configured(settings)


def used_this_month(conn: psycopg.Connection, profile_id: UUID | str, now: datetime) -> int:
    return calls_repo.count_since(conn, profile_id, month_start_nz(now))


def _employer_phone(conn: psycopg.Connection, application_id: UUID | str) -> str | None:
    row = conn.execute(
        """
        select c.id, c.phone from applications a join jobs j on j.id = a.job_id
        left join companies c on c.id = j.company_id where a.id = %s
        """,
        (application_id,),
    ).fetchone()
    if row is None or row["id"] is None:
        return None
    candidates = [row["phone"]] + [
        fact["value"] for fact in conn.execute(
            "select value from company_facts where company_id = %s and field = 'phone' "
            "order by fetched_at", (row["id"],)).fetchall()
    ]
    for raw in candidates:
        number = nz_e164(raw)
        if number:
            return number
    return None


def queue_after_follow_ups(conn: psycopg.Connection, settings: Settings,
                           application_id: UUID | str, profile_id: UUID | str,
                           now: datetime) -> bool:
    """Queue one call to the employer's published number. False when it can't, so the job
    closes as before."""
    if not automatic(settings) or calls_repo.exists_for_application(conn, application_id):
        return False
    if used_this_month(conn, profile_id, now) >= settings.max_calls_per_month:
        return False
    number = _employer_phone(conn, application_id)
    if number is None:
        return False
    calls_repo.queue(conn, profile_id=profile_id, application_id=application_id,
                     purpose="follow_up", to_number=number)
    outbox_repo.stop_follow_ups(conn, application_id)
    events_repo.add(conn, "note", application_id=application_id,
                    payload={"text": f"AI call queued to {number}"})
    return True


def _context(conn: psycopg.Connection, call: dict[str, Any], settings: Settings) -> dict:
    profile_id = call["profile_id"]
    base = resumes_repo.latest_base(conn, profile_id)
    contact = (base["content"].get("contact") if base else None) or {}
    context: dict[str, Any] = {
        "candidate_name": outbox_service.contact_name(conn, profile_id) or "the candidate",
        "candidate_email": contact.get("email") or settings.email_address or "",
        "purpose": call["purpose"],
    }
    if call["application_id"]:
        label = notify_service.job_label(conn, call["application_id"])
        application = conn.execute(
            "select applied_at, resume_id from applications where id = %s",
            (call["application_id"],),
        ).fetchone()
        context.update(job_title=label["title"], company=label["company"])
        if application["applied_at"]:
            context["applied_on"] = nz_today(application["applied_at"]).strftime("%d %B %Y")
        if application["resume_id"]:
            resume = resumes_repo.get_tailored(conn, profile_id, application["resume_id"])
            tailored = (resume["content"].get("tailored") or {}) if resume else {}
            if tailored.get("summary"):
                context["candidate_summary"] = tailored["summary"]
    return context


def _post_call_actions(settings: Settings) -> dict | None:
    if not settings.email_address:
        return None
    return {
        "email": {
            "enabled": True,
            "recipients": [settings.email_address],
            "include": ["summary", "extracted_variables", "fullConversation"],
            "extracted_variables": [{"key": "contact_email", "prompt": _CONTACT_EMAIL_PROMPT}],
        }
    }


def _dispatch(conn: psycopg.Connection, settings: Settings, dialler: Dialler,
              call: dict[str, Any], now: datetime) -> None:
    request_id = dialler.dispatch(
        agent_id=settings.omnidim_agent_id,
        to_number=call["to_number"],
        from_number_id=settings.omnidim_from_number_id,
        call_context=_context(conn, call, settings),
        metadata={"app_call_id": str(call["id"])},
        post_call_actions=_post_call_actions(settings),
    )
    calls_repo.mark_ringing(conn, call["id"], request_id, now)


def dispatch_due(conn: psycopg.Connection, settings: Settings, dialler: Dialler,
                 now: datetime) -> int:
    """Ring queued calls, only in NZ business hours."""
    if not configured(settings) or not in_nz_business_hours(now):
        return 0
    dispatched = 0
    for call in calls_repo.queued(conn):
        try:
            _dispatch(conn, settings, dialler, call, now)
        except Exception as error:  # noqa: BLE001 - one bad call must not stop the others
            calls_repo.fail(conn, call["id"], str(error), now)
            _notify_finished(conn, settings, call, "failed", str(error), None, None)
            conn.commit()
            continue
        conn.commit()
        dispatched += 1
    return dispatched


def _captured_email(extracted: dict[str, Any], transcript: str) -> str | None:
    for value in (extracted.get("contact_email"), *find_emails(transcript)):
        if value and is_valid_email(str(value).strip().casefold()):
            return str(value).strip().casefold()
    return None


def _notify_finished(conn, settings, call, status, error, duration, email) -> None:
    if call["application_id"]:
        label = notify_service.job_label(conn, call["application_id"])
        about = f"{label['company']} about {label['title']}"
    else:
        about = "your phone (test call)"
    if status == "done":
        minutes, seconds = divmod(duration or 0, 60)
        text = f"AI call to {about}: completed ({minutes}:{seconds:02d})."
        if email:
            text += f" Email given: {email}"
    else:
        text = f"AI call to {about} did not go through: {error}"
    notify_service.notify(conn, settings, call["profile_id"], "call", text, f"call:{call['id']}")


def poll_results(conn: psycopg.Connection, settings: Settings, dialler: Dialler,
                 now: datetime) -> int:
    finished = 0
    for call in calls_repo.ringing(conn):
        log = dialler.find_log(agent_id=settings.omnidim_agent_id, app_call_id=str(call["id"]))
        if log is None:
            if call["dispatched_at"] and now - call["dispatched_at"] > NO_RESULT_AFTER:
                error = "No call record came back from OmniDimension."
                calls_repo.fail(conn, call["id"], error, now)
                _notify_finished(conn, settings, call, "failed", error, None, None)
                conn.commit()
                finished += 1
            continue
        transcript = str(log.get("call_conversation") or "").replace("<br/>", "\n")
        extracted = dict(log.get("extracted_variables") or {})
        email = _captured_email(extracted, transcript)
        if email:
            extracted["captured_email"] = email
        call_status = str(log.get("call_status") or "")
        if log.get("is_voicemail"):
            status, error = "failed", "Reached voicemail."
        elif call_status == "completed":
            status, error = "done", None
        else:
            status, error = "failed", f"The call ended: {call_status or 'unknown'}."
        duration = log.get("call_duration_in_seconds")
        calls_repo.finish(
            conn, call["id"], status=status, log_id=str(log.get("id")) if log.get("id") else None,
            duration=int(duration) if duration is not None else None,
            transcript=transcript or None, extracted=extracted, error=error, now=now,
        )
        if call["application_id"]:
            events_repo.add(conn, "called", application_id=call["application_id"],
                            payload={"status": status, "duration": duration})
        _notify_finished(conn, settings, call, status, error, duration, email)
        conn.commit()
        finished += 1
    return finished


def test_call(conn: psycopg.Connection, settings: Settings, dialler: Dialler | None,
              profile_id: UUID | str, now: datetime) -> None:
    """Ring the user's own phone now, to hear the agent before any employer does."""
    if not configured(settings) or dialler is None:
        raise BadRequest(NOT_SET_UP)
    base = resumes_repo.latest_base(conn, profile_id)
    contact = (base["content"].get("contact") if base else None) or {}
    number = nz_e164(contact.get("phone"))
    if number is None:
        raise BadRequest(NO_PHONE)
    if used_this_month(conn, profile_id, now) >= settings.max_calls_per_month:
        raise Conflict(f"You have used all {settings.max_calls_per_month} calls this month.")
    call_id = calls_repo.queue(conn, profile_id=profile_id, application_id=None,
                               purpose="test", to_number=number)
    call = conn.execute("select * from calls where id = %s", (call_id,)).fetchone()
    _dispatch(conn, settings, dialler, call, now)


def send_after_call(conn: psycopg.Connection, profile_id: UUID | str,
                    application_id: UUID | str, to: str, settings: Settings,
                    now: datetime) -> None:
    """Email the resume to the address the employer gave on the call."""
    address = to.strip().casefold()
    if not is_valid_email(address):
        raise BadRequest(outbox_service.NOT_VALID)
    with conn.transaction():
        row = outbox_repo.application(conn, profile_id, application_id)
        if row is None:
            raise NotFound("Application not found")
        if row["status"] not in ("sent", "followed_up", "replied") or row["resume_id"] is None:
            raise Conflict("Only applications already sent can be emailed after a call.")
        pdf = resume_review_service.pdf_path(conn, profile_id, row["resume_id"],
                                             settings.upload_dir)
        name = outbox_service.contact_name(conn, profile_id)
        sign_off = f"Ngā mihi,\n{name}" if name else "Ngā mihi"
        outbox_repo.queue(
            conn,
            application_id=application_id,
            kind="after_call",
            to=address,
            subject=f"Following our call: {outbox_service.subject_for(row['title'], name)[16:]}",
            body=(
                f"Kia ora,\n\nThank you for speaking with my assistant about the "
                f"{' '.join(row['title'].split())} role. As discussed, my resume is attached, "
                f"and I'd welcome the chance to talk.\n\n{sign_off}"
            ),
            attachment_path=pdf,
            attachment_name=outbox_service.attachment_name(row["title"], name),
            reply_to_message_id=None,
            scheduled_at=now,
        )
        events_repo.add(conn, "note", application_id=application_id,
                        payload={"text": f"Resume queued to {address} after the call"})


def latest_calls(conn: psycopg.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        select distinct on (application_id) application_id, status, extracted, finished_at
        from calls where application_id is not null
        order by application_id, created_at desc
        """
    ).fetchall()
    return {str(row["application_id"]): row for row in rows}


def day_start(now: datetime) -> datetime:
    return nz_day_start(now)
