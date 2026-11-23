from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BoardCard(BaseModel):
    id: UUID
    title: str
    company: str
    city: str
    score: int | None
    meta: str
    is_example: bool


class BoardColumn(BaseModel):
    key: str
    name: str
    count: int
    cards: list[BoardCard]


class PipelineStats(BaseModel):
    found_today: int
    shortlisted: int
    ready_to_send: int
    replies_this_week: int


class Pipeline(BaseModel):
    stats: PipelineStats
    columns: list[BoardColumn]
    last_run_at: datetime | None


class ShortlistItem(BaseModel):
    id: UUID
    score: int
    title: str
    company: str
    city: str
    salary: str
    source: str
    matched_skills: list[str]
    missing_skills: list[str]
    reason: str
    url: str | None
    is_example: bool


class Shortlist(BaseModel):
    items: list[ShortlistItem]


class DecisionRequest(BaseModel):
    action: Literal["approve", "skip"]
    reason: str | None = Field(default=None, max_length=500)


class DecisionResponse(BaseModel):
    id: UUID
    status: str


class RunResponse(BaseModel):
    id: UUID
    status: str
    output: dict[str, Any]
    error: str | None
