"""How many of a job's skills the master CV shows, and the user's answer for the others."""

from collections.abc import Iterator, Mapping
from typing import Any
from uuid import UUID

import psycopg

from app.chains.resume_sections_chain import ResumeSectionsChain
from app.core import skill_synonyms
from app.core.errors import BadRequest, NotFound, ProviderError
from app.core.normalize import mentions_term
from app.repositories import applications_repo, skills_repo
from app.schemas.coverage import Coverage, SkillCoverage
from app.schemas.tailoring import BaseSections
from app.services import master_cv_service

COVERED = ("shown", "added")
ADDED_EVIDENCE = "Added by you to Key skills"
DECLINED_EVIDENCE = "You said you don't have this."
MISSING_EVIDENCE = "Not in your CV yet"


def _key(skill: str) -> str:
    return skill.strip().casefold()


def _locations(sections: BaseSections) -> Iterator[tuple[str, str, bool]]:
    """Each place a skill can appear, in search order: (text, evidence, is_key_skill)."""
    for role in sections.roles:
        evidence = f"Shown in: {role.title}, {role.dates}"
        yield role.title, evidence, False
        for bullet in role.bullets:
            yield bullet.text, evidence, False
    yield sections.headline, "Shown in: Profile", False
    yield sections.summary, "Shown in: Profile", False
    for skill in sections.skills:
        yield skill, "Shown in: Key skills", True
    for line in sections.education:
        yield line, "Shown in: Education", False


def _check(sections: BaseSections, skill: str, decision: str | None) -> SkillCoverage:
    names = skill_synonyms.variants(skill)
    for text, evidence, is_key_skill in _locations(sections):
        for index, name in enumerate(names):
            if not mentions_term(text, name):
                continue
            matched_as = name if index else None
            if is_key_skill and decision == "have":
                return SkillCoverage(
                    name=skill, status="added", evidence=ADDED_EVIDENCE, matched_as=matched_as
                )
            return SkillCoverage(
                name=skill, status="shown", evidence=evidence, matched_as=matched_as
            )
    if decision == "no":
        return SkillCoverage(name=skill, status="declined", evidence=DECLINED_EVIDENCE)
    return SkillCoverage(name=skill, status="missing", evidence=MISSING_EVIDENCE)


def covered(items: list[SkillCoverage]) -> int:
    return sum(1 for item in items if item.status in COVERED)


def _count_text(items: list[SkillCoverage]) -> str:
    return f"{covered(items)} of {len(items)}"


def coverage(
    sections: BaseSections,
    required: list[str],
    preferred: list[str],
    split: bool,
    decisions: dict[str, str],
) -> Coverage:
    required_items = [_check(sections, s, decisions.get(_key(s))) for s in required]
    preferred_items = [_check(sections, s, decisions.get(_key(s))) for s in preferred]
    return Coverage(
        required=required_items,
        preferred=preferred_items,
        split=split,
        required_text=_count_text(required_items),
        preferred_text=_count_text(preferred_items),
    )


def requirements(row: Mapping[str, Any]) -> tuple[list[str], list[str], bool]:
    """The required and preferred skills of an application, as (required, preferred, split).

    Applications scored before the split existed have no required or preferred skills and no
    split flag. For those, every matched and missing skill counts as required. A row that was
    split but has empty lists counts "0 of 0", not the matched and missing skills.
    """
    required = list(row["required_skills"] or [])
    preferred = list(row["preferred_skills"] or [])
    split = bool(row["requirements_split"])
    if required or preferred or split:
        return required, preferred, split
    seen: dict[str, str] = {}
    for name in [*(row["matched_skills"] or []), *(row["missing_skills"] or [])]:
        cleaned = name.strip()
        if cleaned:
            seen.setdefault(cleaned.casefold(), cleaned)
    return list(seen.values()), [], False


def key_sections(
    conn: psycopg.Connection, profile_id: UUID | str, sections_chain: ResumeSectionsChain | None
) -> BaseSections:
    """The master CV sections the skills are checked against, read once per call.

    With no CV content at all (from any source, including an AI read that found nothing), the
    resume profile's skills stand in as the Key skills list.
    With no base resume either, the list is empty and coverage still counts.
    """
    try:
        view = master_cv_service.load(conn, profile_id, sections_chain)
    except (BadRequest, ProviderError):
        # A failed AI read must not fail the Shortlist: the profile's skills stand in instead.
        view = None
    sections = view.sections if view else BaseSections()
    if master_cv_service.sections_are_blank(sections):
        names = skills_repo.profile_skill_names(conn, profile_id)
        sections = sections.model_copy(update={"skills": names})
    return sections


def decide(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    skill: str,
    decision: str | None,
    sections_chain: ResumeSectionsChain | None = None,
) -> None:
    """Record the user's answer for a skill and keep the master CV in step with it.

    "have" adds the skill to the master CV and resume profile. Only a "have" that really adds the
    skill is remembered as added. Undoing it, or changing it to "no", removes the skill again, but
    only when it was added here: a skill the user already had stays. The caller commits.
    """
    previous = skills_repo.decisions(conn, profile_id).get(_key(skill))
    was_added = previous == "have" and skills_repo.was_added(conn, profile_id, skill)
    if decision == "have":
        if previous == "have":
            added = was_added
        else:
            added = not master_cv_service.has_skill(conn, profile_id, skill, sections_chain)
        master_cv_service.add_skill(conn, profile_id, skill, sections_chain)
        skills_repo.set_decision(conn, profile_id, skill, "have", added=added)
        return
    if was_added:
        master_cv_service.remove_skill(conn, profile_id, skill, sections_chain)
    skills_repo.set_decision(conn, profile_id, skill, decision)


def for_application(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    application_id: UUID | str,
    sections_chain: ResumeSectionsChain | None = None,
) -> Coverage:
    row = applications_repo.requirement_row(conn, profile_id, application_id)
    if row is None:
        raise NotFound("Application not found")
    required, preferred, split = requirements(row)
    return coverage(
        key_sections(conn, profile_id, sections_chain),
        required,
        preferred,
        split,
        skills_repo.decisions(conn, profile_id),
    )
