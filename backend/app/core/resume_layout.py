"""The CV content in NZ order, plus the four looks. Both the PDF and Word renderers read this.

Each design prints the same blocks in the same order; a look only changes how they look.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from app.core.phones import nz_e164
from app.schemas.master_cv import TemplateId
from app.schemas.tailoring import BaseSections, ContactDetails

BlockKind = Literal[
    "name", "headline", "contact", "rights", "heading", "text", "role", "entry", "bullet"
]

PROFILE = "Profile"
KEY_SKILLS = "Key skills"
WORK_HISTORY = "Work history"
EDUCATION = "Education and certifications"
INTERESTS = "Interests"
REFEREES = "Referees"


@dataclass(frozen=True)
class Block:
    kind: BlockKind
    text: str
    right: str = ""
    sub: str = ""


@dataclass(frozen=True)
class Look:
    """How one design prints. Sizes are points; colours are hex strings."""

    accent: str
    name_center: bool
    name_size: float
    body_size: float
    heading_size: float
    heading_upper: bool
    heading_rule: bool
    contact_rule: bool
    skill_separator: str
    word_body_font: str
    word_heading_font: str


LOOKS: dict[TemplateId, Look] = {
    "classic": Look(
        accent="000000",
        name_center=True,
        name_size=20,
        body_size=9.5,
        heading_size=9.5,
        heading_upper=True,
        heading_rule=True,
        contact_rule=False,
        skill_separator=", ",
        word_body_font="Georgia",
        word_heading_font="Georgia",
    ),
    "modern": Look(
        accent="0F5C5C",
        name_center=False,
        name_size=20,
        body_size=9.5,
        heading_size=9.5,
        heading_upper=True,
        heading_rule=True,
        contact_rule=False,
        skill_separator=", ",
        word_body_font="Calibri",
        word_heading_font="Calibri",
    ),
    "compact": Look(
        accent="1F3A5F",
        name_center=False,
        name_size=15,
        body_size=8.5,
        heading_size=8.5,
        heading_upper=True,
        heading_rule=True,
        contact_rule=False,
        skill_separator=" · ",
        word_body_font="Arial",
        word_heading_font="Arial",
    ),
    "executive": Look(
        accent="1F3A5F",
        name_center=False,
        name_size=20,
        body_size=9.5,
        heading_size=11,
        heading_upper=False,
        heading_rule=False,
        contact_rule=True,
        skill_separator=", ",
        word_body_font="Calibri",
        word_heading_font="Cambria",
    ),
}


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _same_number(a: str | None, b: str | None) -> bool:
    first, second = nz_e164(a), nz_e164(b)
    if first and second:
        return first == second
    return bool(_digits(a)) and _digits(a) == _digits(b)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def contact_line(contact: ContactDetails) -> str:
    """City, phone, email and LinkedIn; WhatsApp only when it is a different number."""
    parts = [_clean(contact.location), _clean(contact.phone), _clean(contact.email)]
    parts.append(_clean(contact.linkedin))
    shown = [part for part in parts if part]
    whatsapp = _clean(contact.whatsapp)
    if whatsapp and not _same_number(whatsapp, contact.phone):
        shown.append(f"WhatsApp {whatsapp}")
    return " · ".join(shown)


def layout_blocks(
    contact: ContactDetails, resume: BaseSections, skill_separator: str = ", "
) -> list[Block]:
    blocks: list[Block] = []
    if _clean(contact.name):
        blocks.append(Block("name", _clean(contact.name)))
    if _clean(resume.headline):
        blocks.append(Block("headline", _clean(resume.headline)))
    if line := contact_line(contact):
        blocks.append(Block("contact", line))
    if _clean(contact.work_rights):
        blocks.append(Block("rights", _clean(contact.work_rights)))

    blocks.append(Block("heading", PROFILE))
    if _clean(resume.summary):
        blocks.append(Block("text", _clean(resume.summary)))

    blocks.append(Block("heading", KEY_SKILLS))
    skills = [_clean(skill) for skill in resume.skills if _clean(skill)]
    if skills:
        blocks.append(Block("text", skill_separator.join(skills)))

    blocks.append(Block("heading", WORK_HISTORY))
    for role in resume.roles:
        employer_place = ", ".join(v for v in (_clean(role.employer), _clean(role.location)) if v)
        blocks.append(Block("role", _clean(role.title), _clean(role.dates), employer_place))
        for bullet in role.bullets:
            if _clean(bullet.text):
                blocks.append(Block("bullet", _clean(bullet.text)))

    blocks.append(Block("heading", EDUCATION))
    for line in resume.education:
        if _clean(line):
            blocks.append(Block("entry", _clean(line)))

    if _clean(resume.interests):
        blocks.append(Block("heading", INTERESTS))
        blocks.append(Block("text", _clean(resume.interests)))

    blocks.append(Block("heading", REFEREES))
    if _clean(resume.referees):
        blocks.append(Block("text", _clean(resume.referees)))
    return blocks


def cv_file_name(contact: ContactDetails, ext: str) -> str:
    """"First-Last-CV.pdf" from the contact name, ASCII only. "CV.pdf" when no name is usable."""
    extension = ext.lstrip(".")
    folded = unicodedata.normalize("NFKD", _clean(contact.name))
    ascii_name = "".join(ch for ch in folded if not unicodedata.combining(ch))
    ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_name).strip("-")
    return f"{slug}-CV.{extension}" if slug else f"CV.{extension}"
