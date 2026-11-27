"""Google Maps outreach: one speculative application for each saved employer with no advert.

Only employers in the chosen areas are considered, oldest saved first. Each record gets the
master CV in the chosen design and a short cover note. Nothing is sent here: Task 6 queues the
emails. The daily cap counts this profile's speculative records since local midnight in NZ.
"""

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from psycopg.pq import TransactionStatus

from app.chains.speculative_chain import SpeculativeChain
from app.core.config import Settings
from app.core.documents import ai_resume_json, contact_for_text, redact_contact_details
from app.core.errors import AppError
from app.core.resume_docx import render_resume_docx
from app.core.resume_pdf import render_resume_pdf
from app.core.workdays import nz_day_start
from app.repositories import (
    applications_repo,
    employers_repo,
    events_repo,
    jobs_repo,
    outreach_repo,
    profiles_repo,
    resumes_repo,
    skills_repo,
)
from app.schemas.job import JobDraft
from app.schemas.tailoring import BaseSections, ContactDetails
from app.services import (
    auto_service,
    contact_service,
    lead_service,
    master_cv_service,
    notify_service,
    resume_build_service,
    tailoring_service,
)
from app.services.contact_service import ContactTools

logger = logging.getLogger(__name__)
NZ_TIME = ZoneInfo("Pacific/Auckland")
JOB_TITLE = "Speculative application"
# One Google Maps run at a time per profile: the startup catch-up can overlap the daily run.
PROSPECT_LOCK_KEY = 73_032_027
NO_ROLES_KIND = "prospect_no_roles"
NO_ROLES_TEXT = "Add your work history in the Resume builder to start Google Maps outreach."
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


def _standard_body(name: str) -> str:
    """Used when AI is not connected, or its note is not usable."""
    return (
        f"I'm getting in touch to ask whether {name} has any work coming up. My resume is "
        "attached, and I'd welcome the chance to talk about how I could help."
    )


def _town(address: str | None) -> str:
    """The town from a Maps address such as '1 Main St, Timaru 7910, New Zealand'."""
    parts = [part.strip() for part in (address or "").split(",") if part.strip()]
    parts = [part for part in parts if part.casefold() != "new zealand"]
    if not parts:
        return ""
    return re.sub(r"\s*\d+\s*$", "", parts[-1]).strip()


def _employer_facts(company: dict[str, Any]) -> dict[str, object]:
    """What an AI model may see of the employer: no emails, phones or website."""
    about = _URL.sub("", redact_contact_details(company["about"] or ""))
    return {
        "name": company["name"],
        "about": about.strip(),
        "types": [company["industry"]] if company["industry"] else [],
        "town": _town(company["address"]),
    }


def _keep_supported(body: str, source: str, declined: list[str], declared: str) -> str:
    """Drop sentences that add a number or skill the CV does not have, or a declined skill."""
    kept = []
    for sentence in _SENTENCE_END.split(body.strip()):
        if tailoring_service.unsupported_sentence(sentence, source):
            continue
        kept.append(sentence)
    text = " ".join(kept).strip()
    cleaned, _ = tailoring_service.drop_declined_sentences(text, declined, declared)
    return cleaned


def _cover_note(
    chain: SpeculativeChain | None,
    sections: BaseSections,
    contact: ContactDetails,
    raw_text: str,
    company: dict[str, Any],
    declined: list[str],
) -> tuple[str, bool]:
    """(the framed note, whether AI wrote it). Greeting and sign-off are always added here."""
    name = contact.name
    employer = _employer_facts(company)
    if chain is not None:
        try:
            body = chain.run(ai_resume_json(sections, contact), employer)
        except Exception:  # a bad AI answer must not stop the other employers
            logger.warning("Speculative note could not be written by AI", exc_info=True)
            body = ""
        body = redact_contact_details(tailoring_service.cover_note_body(body, name))
        if body:
            source = " ".join([
                tailoring_service.source_text(raw_text, sections),
                company["name"], str(employer["about"]), str(employer["town"]),
            ])
            declared = tailoring_service.master_text(sections)
            body = _keep_supported(body, source, declined, declared)
            if body:
                return tailoring_service.frame_cover_note(body, name), True
    return tailoring_service.frame_cover_note(_standard_body(company["name"]), name), False


def _job_for(conn: psycopg.Connection, company: dict[str, Any], town: str) -> UUID:
    """The Maps job for this employer. Jobs are shared, so an existing one is reused."""
    existing = outreach_repo.nearby_job(conn, company["id"])
    if existing:
        return existing
    job = JobDraft(
        source="nearby",
        external_id=str(company["id"]),
        title=JOB_TITLE,
        company=company["name"],
        location=town,
        company_website=company["website"],
        company_address=company["address"],
    )
    dedupe = f"nearby|{company['id']}"
    stored = jobs_repo.insert(conn, job, company["id"], hashlib.sha256(dedupe.encode()).hexdigest())
    return stored or outreach_repo.nearby_job(conn, company["id"])


def _render(
    settings: Settings, contact: ContactDetails, sections: BaseSections, raw_text: str,
    template: str,
) -> Path:
    """The CV as PDF, with the Word file beside it. A failed Word file does not lose the PDF."""
    path = resume_build_service.new_pdf_path(settings.upload_dir)
    try:
        render_resume_pdf(contact, sections, path, fallback_text=raw_text, template=template)
    except Exception:
        path.unlink(missing_ok=True)  # a half-written PDF is never kept
        raise
    docx_path = path.with_suffix(".docx")
    try:
        render_resume_docx(contact, sections, docx_path, template=template,
                           fallback_text=raw_text)
    except Exception as error:
        logger.warning("Word file could not be written: %s", type(error).__name__)
        docx_path.unlink(missing_ok=True)
    return path


def _create(
    conn: psycopg.Connection,
    settings: Settings,
    profile_id: UUID,
    company: dict[str, Any],
    contact: ContactDetails,
    sections: BaseSections,
    raw_text: str,
    template: str,
    note: tuple[str, bool],
    now: datetime,
) -> None:
    cover, ai_used = note
    pdf = _render(settings, contact, sections, raw_text, template)
    try:
        with conn.transaction():
            job_id = _job_for(conn, company, _town(company["address"]))
            application_id = outreach_repo.insert_speculative(conn, profile_id, job_id, now)
            resume_id = resumes_repo.insert_tailored(
                conn,
                profile_id,
                application_id,
                {
                    "base": sections.model_dump(),
                    "tailored": None,
                    "cover_note": cover,
                    "notes": [],
                    "ai_used": ai_used,
                    "changed_ids": [],
                    "template": template,
                },
                str(pdf),
                [],
            )
            applications_repo.set_resume(conn, application_id, resume_id, "approved")
            events_repo.add(
                conn, "note", application_id=application_id, company_id=company["id"],
                payload={"text": "Speculative application ready to send"},
            )
    except Exception:
        pdf.unlink(missing_ok=True)
        pdf.with_suffix(".docx").unlink(missing_ok=True)
        raise


def _saved_company_ids(conn: psycopg.Connection, profile_id: UUID) -> list[UUID]:
    entries = employers_repo.load_data(conn, profile_id).get("saved_employers") or []
    return [UUID(entry["company_id"]) for entry in entries]


def run_daily(
    conn: psycopg.Connection,
    settings: Settings,
    profile_id: UUID,
    tools: ContactTools,
    chain: SpeculativeChain | None,
    now: datetime,
) -> dict[str, int]:
    """Create today's speculative applications for this profile. Returns the counts.

    Only one run holds the profile's lock at a time, so two runs cannot both count the
    day's cap before either creates its records. A run that finds the lock held does nothing.
    """
    report = {"created": 0, "skipped_no_email": 0, "blocked": 0}
    locked = conn.execute(
        "select pg_try_advisory_lock(%s, hashtext(%s)) as ok",
        (PROSPECT_LOCK_KEY, str(profile_id)),
    ).fetchone()["ok"]
    conn.commit()
    if not locked:
        logger.info("Google Maps outreach is already running for this profile; skipped")
        return report
    try:
        return _create_up_to_cap(conn, settings, profile_id, tools, chain, now, report)
    finally:
        if conn.info.transaction_status == TransactionStatus.INERROR:
            conn.rollback()
        conn.execute("select pg_advisory_unlock(%s, hashtext(%s))",
                     (PROSPECT_LOCK_KEY, str(profile_id)))
        conn.commit()


def _create_up_to_cap(
    conn: psycopg.Connection,
    settings: Settings,
    profile_id: UUID,
    tools: ContactTools,
    chain: SpeculativeChain | None,
    now: datetime,
    report: dict[str, int],
) -> dict[str, int]:
    context = profiles_repo.load_search_context(conn, profile_id)
    if context is None or profiles_repo.has_example_resume(conn, profile_id):
        return report
    _, prefs = context
    auto = auto_service.get_settings(conn, profile_id)
    since = nz_day_start(now)
    remaining = auto.prospects_per_day - outreach_repo.created_since(conn, profile_id, since)
    if remaining <= 0:
        return report

    master = master_cv_service.load(conn, profile_id, None)
    sections = master.sections
    has_roles = bool(sections.roles)
    base = resumes_repo.latest_base(conn, profile_id)
    raw_text = base["content"].get("text") or ""
    ai_contact = contact_for_text(master.contact, raw_text)
    declined = skills_repo.declined_names(conn, profile_id)
    blocked = outreach_repo.blocked(conn, profile_id)

    for company_id in _saved_company_ids(conn, profile_id):
        if report["created"] >= remaining:
            break
        company = outreach_repo.company_for_outreach(conn, company_id)
        if company is None or company_id in blocked:
            continue
        if not company["address"] or not lead_service.place_in_regions(
            company["address"], prefs.regions
        ):
            continue
        if employers_repo.applies_to_company(conn, profile_id, company_id):
            continue
        if not has_roles:
            notify_service.notify(
                conn, settings, profile_id, NO_ROLES_KIND, NO_ROLES_TEXT,
                f"{NO_ROLES_KIND}:{profile_id}:{now.astimezone(NZ_TIME).date()}",
            )
            conn.commit()
            break

        conn.commit()  # no transaction is open while the employer's site is read
        try:
            outcome = _prospect(conn, settings, profile_id, company_id, company, tools, chain,
                                now, master, sections, raw_text, ai_contact, declined)
        except Exception:
            # One employer's failure is logged; the other employers are still prospected.
            logger.exception("Speculative outreach failed for one employer")
            conn.rollback()
            continue
        if outcome:
            report[outcome] += 1
    return report


def _prospect(
    conn: psycopg.Connection,
    settings: Settings,
    profile_id: UUID,
    company_id: UUID,
    company: dict[str, Any],
    tools: ContactTools,
    chain: SpeculativeChain | None,
    now: datetime,
    master,
    sections: BaseSections,
    raw_text: str,
    ai_contact: ContactDetails,
    declined: list[str],
) -> str | None:
    """Prospect one employer. Returns the report key to count, or None when nothing counts."""
    try:
        with conn.transaction():
            contact_service.lookup(conn, company_id, tools, now)
    except (AppError, psycopg.Error):
        logger.warning("Contact lookup failed for speculative outreach", exc_info=True)
        return None
    if outreach_repo.has_no_unsolicited(conn, company_id):
        outreach_repo.block(conn, profile_id, company_id, "no_unsolicited")
        conn.commit()
        return "blocked"
    found = contact_service.view(conn, company_id)
    if not (found.hiring_emails or found.emails):
        return "skipped_no_email"

    note = _cover_note(chain, sections, ai_contact, raw_text, company, declined)
    _create(conn, settings, profile_id, company, master.contact, sections, raw_text,
            master.template, note, now)
    conn.commit()
    return "created"
