from typing import TypedDict
from uuid import UUID

from app.schemas.job import JobDraft
from app.schemas.prep import ExploreStep, Fact, PageSource, PlanResult, PrepPack
from app.schemas.tailoring import BaseSections, ContactDetails


class PrepState(TypedDict, total=False):
    pack_id: str
    application_id: str
    profile_id: str
    company_id: UUID | None
    job: JobDraft
    job_url: str | None
    employer: str
    website: str | None
    address: str | None
    origin: str | None
    extra: str | None
    raw_text: str
    contact: ContactDetails  # for redacting what the AI sees; never shown on a pack
    sections: BaseSections | None
    reused: bool
    pages: list[PageSource]  # pages read in this run, ids s1, s2, ...
    reused_sources: list[PageSource]  # sources of reused facts, ids r1, r2, ... (no text)
    extracted: list[str]  # page ids already sent to the extract step
    facts: list[Fact]  # verified facts only
    dropped: list[Fact]  # facts whose quote did not check out
    plan: PlanResult
    missing: list[str]
    explore_next: bool
    explore_history: list[ExploreStep]
    notes: list[str]
    places_calls: int
    pack: PrepPack
    cost_usd: float
    stopped_by: str | None
