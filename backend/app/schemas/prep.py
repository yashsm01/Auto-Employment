"""Deep search: the preparation pack, its sources, and the shapes the models return."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

FactKind = Literal["about", "news", "pay", "practical", "interview"]
PageKind = Literal["job_post", "website", "search", "places", "user"]


class PageSource(BaseModel):
    """One page the run read. Its text is untrusted data, never instructions."""

    id: str
    url: str | None = None
    title: str
    kind: PageKind
    text: str


class Fact(BaseModel):
    kind: FactKind
    text: str
    source_id: str
    quote: str


class PlanResult(BaseModel):
    queries: list[str] = Field(default_factory=list)
    needs: list[FactKind] = Field(default_factory=list)


class ExtractResult(BaseModel):
    facts: list[Fact] = Field(default_factory=list)


class ExploreStep(BaseModel):
    action: Literal["search", "read", "place", "done"]
    argument: str = ""
    reason: str = ""


class EvidenceItem(BaseModel):
    requirement: str
    evidence: str | None = None
    status: Literal["matched", "gap", "check"]


class SourcedLine(BaseModel):
    text: str
    source_ids: list[str] = Field(default_factory=list)
    quote: str | None = None  # the words on the source page that support the line


class WriteDraft(BaseModel):
    """What the writing model returns. Employer, pay and practical lines are built by code
    from verified facts, so the model cannot add claims to them."""

    evidence: list[EvidenceItem] = Field(default_factory=list)
    interview_stages: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    brush_up: list[str] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class PrepPack(BaseModel):
    evidence: list[EvidenceItem] = Field(default_factory=list)
    interview_stages: list[str] = Field(default_factory=list)
    pay: SourcedLine | None = None
    employer: list[SourcedLine] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    brush_up: list[str] = Field(default_factory=list)
    practical: list[SourcedLine] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    could_not_verify: list[str] = Field(default_factory=list)
    directions_url: str | None = None


class SourceLink(BaseModel):
    id: str
    title: str
    url: str | None = None
    kind: str


class DeepSearchSettings(BaseModel):
    enabled: bool = False
    monthly_limit: int = Field(30, ge=0, le=500)


class DeepSearchView(DeepSearchSettings):
    used_this_month: int
    available: bool


class PrepRequest(BaseModel):
    extra: str | None = Field(None, max_length=20000)


class PrepView(BaseModel):
    application_id: UUID
    status: Literal["none", "queued", "running", "done", "failed"]
    pack: PrepPack | None = None
    sources: list[SourceLink] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    cost_nzd: float | None = None
    finished_at: datetime | None = None
    error: str | None = None
    available: bool
    used_this_month: int
    monthly_limit: int
