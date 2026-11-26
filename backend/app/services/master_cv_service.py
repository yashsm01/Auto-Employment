"""The master CV: the user's own resume content, edited in the app and used for every design."""

import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg

from app.chains.resume_sections_chain import ResumeSectionsChain
from app.core.documents import extract_contact_details
from app.core.errors import BadRequest
from app.core.resume_docx import render_resume_docx
from app.core.resume_pdf import render_resume_pdf
from app.repositories import profiles_repo, resumes_repo, skills_repo
from app.schemas.master_cv import TEMPLATE_IDS, AtsItem, AtsReport, MasterCV, MasterCVView
from app.schemas.resume import SkillEntry
from app.schemas.tailoring import BaseSections, ContactDetails
from app.services import ats_check
from app.services.resume_build_service import ensure_sections

logger = logging.getLogger(__name__)
NEEDS_RESUME = "Upload your resume first, then build on it here."


def _base(conn: psycopg.Connection, profile_id: UUID | str) -> dict[str, Any]:
    base = resumes_repo.latest_base(conn, profile_id)
    if base is None or base["content"].get("example"):
        raise BadRequest(NEEDS_RESUME)
    return base


def load(
    conn: psycopg.Connection, profile_id: UUID | str, sections_chain: ResumeSectionsChain | None
) -> MasterCVView:
    base = _base(conn, profile_id)
    content = base["content"]
    text = content.get("text") or ""
    contact = ContactDetails(
        **(content.get("contact") or extract_contact_details(text).model_dump())
    )

    cached = content.get("sections")
    if cached:
        sections, source = BaseSections(**cached), "resume"
    elif sections_chain is not None and text:
        sections = ensure_sections(conn, base["id"], None, text, sections_chain, contact)
        sections, source = sections or BaseSections(), "ai"
    else:
        # Nothing to show and no AI to read it: the Key skills start from the profile's skills.
        # This is display only. Nothing is saved until the user presses Save CV.
        names = skills_repo.profile_skill_names(conn, profile_id)
        sections, source = BaseSections(skills=names), "empty"

    template = content.get("template")
    return MasterCVView(
        contact=contact,
        sections=sections,
        template=template if template in TEMPLATE_IDS else "classic",
        source=source,
    )


def save(conn: psycopg.Connection, profile_id: UUID | str, cv: MasterCV) -> MasterCVView:
    base = _base(conn, profile_id)
    resumes_repo.save_master(
        conn, base["id"], cv.sections.model_dump(), cv.contact.model_dump(), cv.template
    )
    _add_to_resume_profile(conn, profile_id, base["id"], cv)
    return load(conn, profile_id, None)


def _add_to_resume_profile(
    conn: psycopg.Connection, profile_id: UUID | str, resume_id: UUID, cv: MasterCV
) -> None:
    """Search terms only grow here: new skills and the headline are added, nothing is removed."""
    terms = profiles_repo.resume_terms(conn, resume_id)
    if terms is not None:
        titles = list(terms["titles"] or [])
        headline = cv.sections.headline.strip()
        if headline and headline.casefold() not in {t.casefold() for t in titles}:
            titles.append(headline)
        skills = list(terms["skills"] or [])
        tools = list(terms["tools"] or [])
        known = {s["name"].casefold() for s in skills} | {t.casefold() for t in tools}
        for skill in cv.sections.skills:
            name = skill.strip()
            if name and name.casefold() not in known:
                skills.append(SkillEntry(name=name).model_dump())
                known.add(name.casefold())
        profiles_repo.write_resume_terms(conn, resume_id, titles, skills, tools)
    if cv.contact.name:
        profiles_repo.set_full_name(conn, profile_id, cv.contact.name)


def with_ats(view: MasterCVView, upload_dir: Path, profile_id: UUID) -> MasterCVView:
    """Render the PDF and Word previews, then attach the ATS report. The previews are replaced.

    Each call renders to unique temporary names and moves them into place only after the check
    has run, so concurrent requests never read a half-written file. A failure is reported as a
    single item rather than raised, so the CV page and saves still work.

    Kept out of load and save, which are reused internally and must not render files.
    """
    directory = upload_dir / "previews"
    token = uuid4().hex
    temp_pdf = directory / f"{profile_id}-{token}.pdf"
    temp_docx = directory / f"{profile_id}-{token}.docx"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        render_resume_pdf(view.contact, view.sections, temp_pdf, template=view.template)
        render_resume_docx(view.contact, view.sections, temp_docx, template=view.template)
        report = ats_check.check(view, temp_pdf, temp_docx)
        os.replace(temp_pdf, directory / f"{profile_id}.pdf")
        os.replace(temp_docx, directory / f"{profile_id}.docx")
    except Exception as error:
        logger.warning("ATS check could not run: %s", type(error).__name__)
        temp_pdf.unlink(missing_ok=True)
        temp_docx.unlink(missing_ok=True)
        report = AtsReport(
            items=[
                AtsItem(
                    label="ATS check could not run",
                    ok=False,
                    detail=f"Try again after saving. ({type(error).__name__})",
                )
            ],
            text="",
            pages=0,
            pdf_bytes=0,
            docx_bytes=0,
        )
    return view.model_copy(update={"ats": report})


def sections_are_blank(sections: BaseSections | None) -> bool:
    """True when there is no CV content: no sections at all, or none of the CV parts are filled.

    Interests and referees do not count as CV content.
    """
    if sections is None:
        return True
    return not (
        sections.headline.strip()
        or sections.summary.strip()
        or sections.roles
        or sections.skills
        or sections.education
    )


def _sections_to_edit(
    conn: psycopg.Connection, profile_id: UUID | str, sections_chain: ResumeSectionsChain | None
) -> BaseSections | None:
    """The master CV sections to edit, or None when there is no CV content to edit.

    Saved sections are used as they are. Otherwise they are read first (with AI when available).
    A blank CV is None, so skill changes never save an empty skeleton as the CV.
    """
    base = _base(conn, profile_id)
    cached = base["content"].get("sections")
    if cached:
        sections = BaseSections(**cached)
    else:
        view = load(conn, profile_id, sections_chain)
        if view.source != "ai":
            return None
        sections = view.sections
    return None if sections_are_blank(sections) else sections


def has_skill(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    skill: str,
    sections_chain: ResumeSectionsChain | None = None,
) -> bool:
    """True when the resume profile or the master CV already lists the skill."""
    name = skill.strip().casefold()
    if name in {s.casefold() for s in skills_repo.profile_skill_names(conn, profile_id)}:
        return True
    sections = _sections_to_edit(conn, profile_id, sections_chain)
    return sections is not None and name in {s.casefold() for s in sections.skills}


def _add_profile_skill(
    conn: psycopg.Connection, profile_id: UUID | str, resume_id: UUID, name: str
) -> bool:
    terms = profiles_repo.resume_terms(conn, resume_id)
    if terms is None:
        return False
    skills = list(terms["skills"] or [])
    tools = list(terms["tools"] or [])
    known = {s["name"].casefold() for s in skills} | {t.casefold() for t in tools}
    if name.casefold() in known:
        return False
    skills.append(SkillEntry(name=name).model_dump())
    profiles_repo.write_resume_terms(conn, resume_id, list(terms["titles"] or []), skills, tools)
    return True


def _remove_profile_skill(
    conn: psycopg.Connection, profile_id: UUID | str, resume_id: UUID, target: str
) -> bool:
    terms = profiles_repo.resume_terms(conn, resume_id)
    if terms is None:
        return False
    skills = list(terms["skills"] or [])
    kept = [s for s in skills if s["name"].casefold() != target]
    if len(kept) == len(skills):
        return False
    profiles_repo.write_resume_terms(
        conn, resume_id, list(terms["titles"] or []), kept, list(terms["tools"] or [])
    )
    return True


def add_skill(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    skill: str,
    sections_chain: ResumeSectionsChain | None = None,
) -> bool:
    """Add a skill to the resume profile and, when there is CV content, to the master CV skills.

    Returns True only when something really changed. Matching ignores case, so "power bi" matches
    "Power BI". With no CV content (and no AI to read one), only the resume profile changes.
    """
    name = skill.strip()
    if not name:
        return False
    base = _base(conn, profile_id)
    changed = _add_profile_skill(conn, profile_id, base["id"], name)
    sections = _sections_to_edit(conn, profile_id, sections_chain)
    if sections is None:
        return changed
    if name.casefold() not in {s.casefold() for s in sections.skills}:
        sections.skills.append(name)
        resumes_repo.save_sections(conn, base["id"], sections.model_dump())
        changed = True
    return changed


def remove_skill(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    skill: str,
    sections_chain: ResumeSectionsChain | None = None,
) -> bool:
    """Remove a skill from the resume profile skills and from the master CV skills. Tools stay."""
    target = skill.strip().casefold()
    base = _base(conn, profile_id)
    changed = _remove_profile_skill(conn, profile_id, base["id"], target)
    sections = _sections_to_edit(conn, profile_id, sections_chain)
    if sections is None:
        return changed
    kept = [s for s in sections.skills if s.casefold() != target]
    if len(kept) != len(sections.skills):
        sections.skills = kept
        resumes_repo.save_sections(conn, base["id"], sections.model_dump())
        changed = True
    return changed
