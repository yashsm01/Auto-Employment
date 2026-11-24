from typing import Any, TypedDict
from uuid import UUID

from app.schemas.job import JobDraft
from app.schemas.tailoring import BaseSections, ContactDetails, TailoredResume


class ResumeState(TypedDict, total=False):
    application_id: str
    profile_id: str
    company_id: UUID | None
    job: JobDraft
    base_resume_id: UUID
    raw_text: str
    cached_sections: dict[str, Any] | None
    contact: ContactDetails
    facts: list[str]
    sections: BaseSections | None
    tailored: TailoredResume | None
    cover_note: str
    notes: list[str]
    ai_used: bool
    pdf_path: str
    resume_id: UUID
