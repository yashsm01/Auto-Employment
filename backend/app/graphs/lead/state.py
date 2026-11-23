from typing import TypedDict
from uuid import UUID

from app.schemas.job import JobDraft, StoredJob
from app.schemas.resume import ResumeProfile, SearchPreferences


class LeadState(TypedDict, total=False):
    profile_id: str
    resume: ResumeProfile
    prefs: SearchPreferences
    queries: list[str]
    fetched: list[JobDraft]
    clean_jobs: list[JobDraft]
    stored: list[StoredJob]
    candidates: list[StoredJob]
    scored_count: int
    passed_ids: list[UUID]
    errors: list[str]
