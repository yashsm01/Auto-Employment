from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class JobDraft(BaseModel):
    """A job as read from a source, before it is stored."""

    source: str
    external_id: str
    title: str
    company: str
    location: str = ""
    region: str = ""
    salary_min: int | None = None
    salary_max: int | None = None
    url: str | None = None
    description: str = ""
    posted_at: datetime | None = None
    closes_at: datetime | None = None
    company_website: str | None = None
    company_phone: str | None = None
    company_email: str | None = None
    company_address: str | None = None

    def search_text(self) -> str:
        return f"{self.title}\n{self.description}"


class AlertJob(BaseModel):
    """One job listed in an alert email."""

    title: str
    company: str
    location: str = ""
    url: str | None = None
    summary: str = ""


class StoredJob(BaseModel):
    job_id: UUID
    draft: JobDraft
    similarity: float | None = None


class ScoreResult(BaseModel):
    score: int = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    requirements_split: bool = False
    reason: str = ""
    used_ai: bool = False
