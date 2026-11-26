from datetime import datetime

from pydantic import BaseModel, Field


class Recruiter(BaseModel):
    name: str
    role: str
    email: str | None = None
    phone: str | None = None
    source_url: str | None = None


class EmployerContacts(BaseModel):
    phone: str | None = None
    phone_source: str | None = None
    emails: list[str] = Field(default_factory=list)
    hiring_emails: list[str] = Field(default_factory=list)
    website: str | None = None
    contact_page: str | None = None
    careers_page: str | None = None
    linkedin: str | None = None
    hours: list[str] = Field(default_factory=list)
    rating: float | None = None
    rating_count: int | None = None
    recruiters: list[Recruiter] = Field(default_factory=list)
    checked_at: datetime | None = None
    notes: list[str] = Field(default_factory=list)
