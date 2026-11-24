from typing import Any, TypedDict
from uuid import UUID

from app.schemas.job import JobDraft, StoredJob
from app.schemas.resume import ResumeProfile, SearchPreferences


class LeadState(TypedDict, total=False):
    profile_id: str
    resume: ResumeProfile
    prefs: SearchPreferences
    queries: list[str]
    fetched: list[JobDraft]
    source_report: list[dict[str, Any]]
    clean_jobs: list[JobDraft]
    stored: list[StoredJob]
    candidates: list[StoredJob]
    scored_count: int
    score_report: dict[str, Any]
    passed_ids: list[UUID]
    employers_researched: int
    errors: list[str]
