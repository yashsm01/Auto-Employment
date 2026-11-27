"""Builds a tailored resume from the model's draft and removes anything not in the original."""

import re
from collections.abc import Sequence

from app.chains.score_chain import KNOWN_SKILLS
from app.chains.tailor_chain import FactCheckResult, TailorDraft
from app.core import skill_synonyms
from app.core.normalize import contains_term, mentions_term
from app.schemas.tailoring import BaseSections, Bullet, RoleSection, TailoredResume

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_GREETING = re.compile(
    r"^\s*(?:(?:kia ora|tēnā koe|tena koe|hello|hi)\b[^\S\n]*[,!]?|dear\b[^,\n]{0,40},)\s*",
    re.IGNORECASE,
)
_SIGN_OFF = re.compile(
    r"\n\s*(?:ngā mihi|nga mihi|(?:kind |best |warm )?regards|cheers|thanks|thank you"
    r"|yours sincerely|sincerely)[^\S\n]*[,.!]?[^\S\n]*(?:\n[^\n]*)?\s*$",
    re.IGNORECASE,
)


def cover_note_body(note: str, name: str | None) -> str:
    """The model is asked for the body only. Drop a greeting or sign-off it adds anyway."""
    body = _SIGN_OFF.sub("", _GREETING.sub("", note.strip(), count=1)).strip()
    lines = body.splitlines()
    if name and lines and lines[-1].strip().casefold() == name.strip().casefold():
        body = "\n".join(lines[:-1]).strip()
    return body


def frame_cover_note(body: str, name: str | None) -> str:
    """Greeting and sign-off are added in code so the fact check can never remove them."""
    sign_off = f"Ngā mihi,\n{name}" if name else "Ngā mihi"
    return f"Kia ora,\n\n{body.strip()}\n\n{sign_off}"


def assemble(base: BaseSections, draft: TailorDraft) -> TailoredResume:
    """Titles, employers and dates always come from the base resume, never from the model."""
    rewrites = {r.id: r.text.strip() for r in draft.bullets if r.text.strip()}
    order = list(dict.fromkeys(r.id for r in draft.bullets))
    roles = []
    for role in base.roles:
        originals = {bullet.id: bullet.text for bullet in role.bullets}
        ids = [i for i in order if i in originals] + [i for i in originals if i not in order]
        roles.append(
            role.model_copy(
                update={
                    "bullets": [Bullet(id=i, text=rewrites.get(i, originals[i])) for i in ids]
                }
            )
        )

    by_key = {skill.casefold(): skill for skill in base.skills}
    first = [by_key[s.casefold()] for s in draft.skills_order if s.casefold() in by_key]
    skills = list(dict.fromkeys([*first, *base.skills]))
    return TailoredResume(
        headline=base.headline,
        summary=draft.summary.strip() or base.summary,
        roles=roles,
        skills=skills,
        education=base.education,
        interests=base.interests,
        referees=base.referees,
        cover_note=draft.cover_note.strip(),
    )


def _new_numbers(text: str, source: str) -> list[str]:
    allowed = set(_NUMBER.findall(source))
    return [number for number in _NUMBER.findall(text) if number not in allowed]


def _new_skills(text: str, source: str) -> list[str]:
    return [s for s in KNOWN_SKILLS if contains_term(text, s) and not contains_term(source, s)]


def _role_text(role: RoleSection) -> str:
    return " ".join([role.title, *(bullet.text for bullet in role.bullets)])


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def master_text(sections: BaseSections) -> str:
    """Everything the master CV states, so skills and numbers in it count as supported."""
    parts = [sections.headline, sections.summary]
    for role in sections.roles:
        parts.append(role.title)
        parts.extend(bullet.text for bullet in role.bullets)
    parts.extend(sections.skills)
    parts.extend(sections.education)
    parts.append(sections.interests)
    return "\n".join(part for part in parts if part)


def source_text(raw_text: str, sections: BaseSections) -> str:
    """The uploaded resume plus the master CV: the only text a tailored claim may rely on."""
    return f"{raw_text}\n{master_text(sections)}"


def _declined_in(text: str, declared: str, declined: Sequence[str]) -> list[str]:
    """Declined skills the text mentions (any variant) that the declared text does not mention.

    `declared` is the master CV text the user keeps. Uploaded text alone does not count.
    """
    hits = []
    for skill in declined:
        names = skill_synonyms.variants(skill)
        if any(mentions_term(text, name) for name in names) and not any(
            mentions_term(declared, name) for name in names
        ):
            hits.append(skill)
    return hits


def _declined_note(skill: str) -> str:
    return f"Removed a mention of {skill}, which you said you don't have."


def drop_declined_sentences(
    cover_note: str, declined: Sequence[str], declared: str
) -> tuple[str, list[str]]:
    """Remove cover-note sentences that mention a declined skill the declared text does not have."""
    if not declined:
        return cover_note, []
    notes: list[str] = []
    lines = []
    for line in cover_note.splitlines():
        kept = []
        for sentence in _SENTENCE_END.split(line):
            hits = _declined_in(sentence, declared, declined)
            if hits:
                notes.extend(_declined_note(skill) for skill in hits)
            else:
                kept.append(sentence)
        lines.append(" ".join(kept).strip())
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return cleaned, list(dict.fromkeys(notes))


def unsupported_sentence(sentence: str, source: str) -> bool:
    """True when a cover-note sentence adds a number or a skill the source does not have."""
    return bool(_new_numbers(sentence, source) or _new_skills(sentence, source))


def check_facts(
    base: BaseSections,
    source: str,
    tailored: TailoredResume,
    declined: Sequence[str] = (),
    declared: str | None = None,
) -> tuple[TailoredResume, list[str]]:
    """Revert any line that adds a number or a skill its source does not have, or that mentions
    a declined skill the master CV does not show.

    `source` is the uploaded resume text plus the master CV text (see source_text). `declared`
    is the master CV text alone (see master_text), which is what a declined skill may match.
    """
    declared = master_text(base) if declared is None else declared
    notes: list[str] = []
    roles = []
    for base_role, role in zip(base.roles, tailored.roles, strict=True):
        originals = {bullet.id: bullet.text for bullet in base_role.bullets}
        context = _role_text(base_role)
        bullets = []
        for bullet in role.bullets:
            source_bullet = originals[bullet.id]
            numbers = _new_numbers(bullet.text, source_bullet)
            skills = _new_skills(bullet.text, context)
            declined_hits = _declined_in(bullet.text, declared, declined)
            notes.extend(_declined_note(skill) for skill in declined_hits)
            if numbers or skills or declined_hits:
                if numbers or skills:
                    added = ", ".join([*numbers, *skills])
                    notes.append(
                        f"Kept your original wording at {base_role.employer}: the rewrite added "
                        f"{added}, which that part of your resume doesn't mention."
                    )
                bullets.append(Bullet(id=bullet.id, text=source_bullet))
            else:
                bullets.append(bullet)
        roles.append(role.model_copy(update={"bullets": bullets}))

    summary = tailored.summary
    added = [*_new_numbers(summary, source), *_new_skills(summary, source)]
    declined_hits = _declined_in(summary, declared, declined)
    notes.extend(_declined_note(skill) for skill in declined_hits)
    if added or declined_hits:
        if added:
            notes.append(
                f"Kept your original summary: the rewrite added {', '.join(added)}, "
                "which your resume doesn't mention."
            )
        summary = base.summary

    cover_note, cover_notes = drop_declined_sentences(tailored.cover_note, declined, declared)
    notes.extend(cover_notes)
    # A declined skill stays out of the skills list unless the master CV itself lists it.
    skills = [skill for skill in tailored.skills if not _declined_in(skill, declared, declined)]
    result = tailored.model_copy(
        update={"roles": roles, "summary": summary, "cover_note": cover_note, "skills": skills}
    )
    return result, list(dict.fromkeys(notes))


def apply_ai_check(
    base: BaseSections, tailored: TailoredResume, result: FactCheckResult
) -> tuple[TailoredResume, list[str]]:
    """Revert whatever the checking model flagged."""
    notes: list[str] = []
    flagged = set(result.unsupported_bullet_ids)
    roles = []
    for base_role, role in zip(base.roles, tailored.roles, strict=True):
        originals = {bullet.id: bullet.text for bullet in base_role.bullets}
        bullets = []
        for bullet in role.bullets:
            if bullet.id in flagged and bullet.text != originals[bullet.id]:
                notes.append(f"Kept your original wording for a line at {base_role.employer}.")
                bullets.append(Bullet(id=bullet.id, text=originals[bullet.id]))
            else:
                bullets.append(bullet)
        roles.append(role.model_copy(update={"bullets": bullets}))

    summary = tailored.summary
    if result.summary_unsupported and summary != base.summary:
        notes.append("Kept your original summary.")
        summary = base.summary

    cover_note = tailored.cover_note
    for sentence in result.unsupported_cover_note_sentences:
        if sentence.strip() and sentence.strip() in cover_note:
            cover_note = cover_note.replace(sentence.strip(), "")
            notes.append(f"Removed from the cover note: “{sentence.strip()}”")
    cover_note = "\n".join(" ".join(line.split()) for line in cover_note.splitlines())
    return (
        tailored.model_copy(
            update={"roles": roles, "summary": summary, "cover_note": cover_note.strip()}
        ),
        notes,
    )
