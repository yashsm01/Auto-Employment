"""Database steps for tailoring one application's resume."""

import secrets
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from app.chains.resume_sections_chain import ResumeSectionsChain
from app.core.documents import contact_for_text, extract_contact_details
from app.core.errors import BadRequest, NotFound
from app.repositories import applications_repo, companies_repo, events_repo, resumes_repo
from app.schemas.job import JobDraft
from app.schemas.master_cv import TEMPLATE_IDS
from app.schemas.tailoring import BaseSections, ContactDetails, TailoredResume
from app.services.tailoring_service import frame_cover_note

NOTE_FIELDS = ("about", "recent_news")
TRUSTED = ("high", "medium")


def load_context(conn: psycopg.Connection, application_id: str) -> dict[str, Any]:
    row = applications_repo.tailoring_context(conn, application_id)
    if row is None:
        raise NotFound("Application not found")
    base = resumes_repo.latest_base(conn, row["profile_id"])
    content = base["content"] if base else {}
    if not base or content.get("example") or not content.get("text"):
        raise BadRequest("Upload your resume first, on My resume profile.")

    facts = []
    if row["company_id"]:
        facts = [
            fact["value"]
            for fact in companies_repo.list_facts(conn, row["company_id"])
            if fact["field"] in NOTE_FIELDS and fact["confidence"] in TRUSTED
        ]
    stored = ContactDetails(**content["contact"]) if content.get("contact") else None
    contact = stored or extract_contact_details(content["text"])
    template = content.get("template")
    return {
        "profile_id": str(row["profile_id"]),
        "company_id": row["company_id"],
        "job": JobDraft(
            source=row["source"],
            external_id=row["external_id"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            description=row["description"],
        ),
        "base_resume_id": base["id"],
        "raw_text": content["text"],
        "cached_sections": content.get("sections"),
        "contact": contact,
        # What AI models may see the redaction of: the stored contact, blanks filled from the text.
        "ai_contact": contact_for_text(stored, content["text"]),
        "facts": facts,
        "template": template if template in TEMPLATE_IDS else "classic",
    }


def usable_sections(cached: dict[str, Any] | None) -> BaseSections | None:
    """The master CV sections, but only when they have at least one role.

    A saved skeleton (a blank form, or skills alone) is not the CV, so tailoring and the
    prep pack then use the uploaded text, as they did before sections were saved.
    """
    if not cached:
        return None
    sections = BaseSections(**cached)
    return sections if sections.roles else None


def ensure_sections(
    conn: psycopg.Connection,
    resume_id: UUID,
    cached: dict[str, Any] | None,
    raw_text: str,
    chain: ResumeSectionsChain | None,
    contact: ContactDetails | None = None,
) -> BaseSections | None:
    """Split the resume into parts once, and keep the result for later jobs.

    Saved sections are never replaced here: a saved skeleton gives None, not a fresh split.
    """
    if cached:
        return usable_sections(cached)
    if chain is None:
        return None
    sections = chain.run(raw_text, contact)
    resumes_repo.save_sections(conn, resume_id, sections.model_dump())
    return sections


def plain_cover_body(job: JobDraft) -> str:
    return (
        f"I'm applying for the {job.title} role at {job.company}. "
        "My resume is attached, and I'd welcome the chance to talk about it."
    )


def plain_cover_note(job: JobDraft, name: str | None) -> str:
    """Used when AI is not connected."""
    return frame_cover_note(plain_cover_body(job), name)


def new_pdf_path(upload_dir: Path) -> Path:
    directory = Path(upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"tailored-{secrets.token_hex(12)}.pdf"


def changed_ids(base: BaseSections | None, tailored: TailoredResume | None) -> list[str]:
    if base is None or tailored is None:
        return []
    originals = {b.id: b.text for role in base.roles for b in role.bullets}
    return [b.id for role in tailored.roles for b in role.bullets if b.text != originals.get(b.id)]


def save(
    conn: psycopg.Connection,
    state: dict[str, Any],
    pdf_path: Path,
) -> UUID:
    tailored: TailoredResume | None = state.get("tailored")
    sections: BaseSections | None = state.get("sections")
    content = {
        "base": sections.model_dump() if sections else None,
        "tailored": tailored.model_dump() if tailored else None,
        "cover_note": state["cover_note"],
        "notes": state.get("notes", []),
        "ai_used": state.get("ai_used", False),
        "changed_ids": changed_ids(sections, tailored),
        "template": state.get("template", "classic"),
    }
    resume_id = resumes_repo.insert_tailored(
        conn, state["profile_id"], state["application_id"], content, str(pdf_path), state["facts"]
    )
    applications_repo.set_resume(conn, state["application_id"], resume_id, "ready")
    events_repo.add(
        conn,
        "note",
        application_id=state["application_id"],
        company_id=state.get("company_id"),
        payload={"text": "Tailored resume ready for review"},
    )
    return resume_id
