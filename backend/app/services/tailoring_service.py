"""Builds a tailored resume from the model's draft and removes anything not in the original."""

import re

from app.chains.score_chain import KNOWN_SKILLS
from app.chains.tailor_chain import FactCheckResult, TailorDraft
from app.core.normalize import contains_term
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
        summary=draft.summary.strip() or base.summary,
        roles=roles,
        skills=skills,
        education=base.education,
        cover_note=draft.cover_note.strip(),
    )


def _new_numbers(text: str, source: str) -> list[str]:
    allowed = set(_NUMBER.findall(source))
    return [number for number in _NUMBER.findall(text) if number not in allowed]


def _new_skills(text: str, source: str) -> list[str]:
    return [s for s in KNOWN_SKILLS if contains_term(text, s) and not contains_term(source, s)]


def _role_text(role: RoleSection) -> str:
    return " ".join([role.title, *(bullet.text for bullet in role.bullets)])


def check_facts(
    base: BaseSections, raw_text: str, tailored: TailoredResume
) -> tuple[TailoredResume, list[str]]:
    """Revert any line that adds a number or a skill its source does not have."""
    notes: list[str] = []
    roles = []
    for base_role, role in zip(base.roles, tailored.roles, strict=True):
        originals = {bullet.id: bullet.text for bullet in base_role.bullets}
        context = _role_text(base_role)
        bullets = []
        for bullet in role.bullets:
            source = originals[bullet.id]
            numbers = _new_numbers(bullet.text, source)
            skills = _new_skills(bullet.text, context)
            if numbers or skills:
                added = ", ".join([*numbers, *skills])
                notes.append(
                    f"Kept your original wording at {base_role.employer}: the rewrite added "
                    f"{added}, which that part of your resume doesn't mention."
                )
                bullets.append(Bullet(id=bullet.id, text=source))
            else:
                bullets.append(bullet)
        roles.append(role.model_copy(update={"bullets": bullets}))

    summary = tailored.summary
    added = [*_new_numbers(summary, raw_text), *_new_skills(summary, raw_text)]
    if added:
        notes.append(
            f"Kept your original summary: the rewrite added {', '.join(added)}, "
            "which your resume doesn't mention."
        )
        summary = base.summary
    return tailored.model_copy(update={"roles": roles, "summary": summary}), notes


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
