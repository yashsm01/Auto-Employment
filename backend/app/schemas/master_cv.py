from typing import Literal

from pydantic import BaseModel, model_validator

from app.schemas.tailoring import BaseSections, ContactDetails

TemplateId = Literal["classic", "modern", "compact", "executive"]
TEMPLATE_IDS: tuple[str, ...] = ("classic", "modern", "compact", "executive")

MAX_ROLES = 20
MAX_BULLETS = 20
MAX_SKILLS = 80
MAX_EDUCATION = 20
MAX_TEXT = 2000


class _CVFields(BaseModel):
    contact: ContactDetails
    sections: BaseSections
    template: TemplateId = "classic"


def _check_count(field: str, count: int, limit: int) -> None:
    if count > limit:
        raise ValueError(f"{field} has {count} items; the limit is {limit}.")


def _check_text(field: str, text: str) -> None:
    if len(text) > MAX_TEXT:
        raise ValueError(f"{field} is {len(text)} characters; the limit is {MAX_TEXT}.")


def check_limits(sections: BaseSections) -> None:
    """Size limits for a CV the user sends. Each message names the field that is too big."""
    _check_count("sections.roles", len(sections.roles), MAX_ROLES)
    _check_count("sections.skills", len(sections.skills), MAX_SKILLS)
    _check_count("sections.education", len(sections.education), MAX_EDUCATION)
    for name in ("headline", "summary", "interests", "referees"):
        _check_text(f"sections.{name}", getattr(sections, name))
    for index, skill in enumerate(sections.skills):
        _check_text(f"sections.skills[{index}]", skill)
    for index, line in enumerate(sections.education):
        _check_text(f"sections.education[{index}]", line)
    for index, role in enumerate(sections.roles):
        prefix = f"sections.roles[{index}]"
        _check_count(f"{prefix}.bullets", len(role.bullets), MAX_BULLETS)
        for name in ("title", "employer", "location", "dates"):
            _check_text(f"{prefix}.{name}", getattr(role, name))
        for position, bullet in enumerate(role.bullets):
            _check_text(f"{prefix}.bullets[{position}].text", bullet.text)


class MasterCV(_CVFields):
    """The PUT body. Size limits are checked here, not when a saved CV is read back."""

    @model_validator(mode="after")
    def _within_limits(self) -> "MasterCV":
        check_limits(self.sections)
        return self


class AtsItem(BaseModel):
    label: str
    ok: bool
    detail: str = ""


class AtsReport(BaseModel):
    """Rule-based checks an applicant tracking system can trip on, plus the text it would read."""

    items: list[AtsItem]
    text: str
    pages: int
    pdf_bytes: int
    docx_bytes: int


class MasterCVView(_CVFields):
    """The GET and PUT response. `source` says where the sections came from.

    No size check: a CV the AI cached must always load, even if it is larger than the limits.
    """

    source: Literal["resume", "ai", "empty"]
    ats: AtsReport | None = None
