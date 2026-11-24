from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ContactDetails(BaseModel):
    """Shown on the resume header. Never sent to an AI model."""

    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)


class Bullet(BaseModel):
    id: str
    text: str


class RoleSection(BaseModel):
    title: str
    employer: str
    location: str = ""
    dates: str = ""
    bullets: list[Bullet] = Field(default_factory=list)


class BaseSections(BaseModel):
    """The base resume split into parts. Every part was checked against the resume text."""

    summary: str = ""
    roles: list[RoleSection] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class TailoredResume(BaseSections):
    cover_note: str = ""


class ReviewItem(BaseModel):
    application_id: UUID
    status: str
    title: str
    company: str
    resume_id: UUID | None
    error: str | None


class ReviewList(BaseModel):
    items: list[ReviewItem]


class TailoredResumeView(BaseModel):
    application_id: UUID
    status: str
    title: str
    company: str
    resume_id: UUID | None
    base: BaseSections | None
    tailored: TailoredResume | None
    changed_ids: list[str]
    notes: list[str]
    cover_note: str
    facts_used: list[str]
    ai_used: bool
    pdf_url: str | None
    error: str | None


class CoverNoteUpdate(BaseModel):
    cover_note: str = Field(min_length=1, max_length=5000)


class ResumeDecision(BaseModel):
    action: Literal["approve", "reject"]


class StatusResponse(BaseModel):
    id: UUID
    status: str
