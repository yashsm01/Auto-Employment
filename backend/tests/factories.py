"""Small builders for test data. Everything here is invented example data."""

from datetime import UTC, datetime

from app.schemas.job import JobDraft
from app.schemas.resume import ResumeProfile, SearchPreferences, SkillEntry

NOW = datetime(2026, 11, 24, 7, 0, tzinfo=UTC)


def make_resume(**overrides) -> ResumeProfile:
    values = {
        "titles": ["Python Developer"],
        "skills": [
            SkillEntry(name="Python", years=2),
            SkillEntry(name="FastAPI", years=1),
            SkillEntry(name="SQL", years=2),
            SkillEntry(name="Git", years=2),
        ],
        "tools": [],
        "industries": ["Logistics"],
        "seniority": "junior",
        "search_queries": [],
    }
    values.update(overrides)
    return ResumeProfile(**values)


def make_prefs(**overrides) -> SearchPreferences:
    values = {
        "regions": ["Auckland", "Wellington"],
        "work_rights": "open_visa",
        "salary_min": None,
        "avoid_keywords": ["senior", "lead", "sales"],
        "shortlist_threshold": 70,
    }
    values.update(overrides)
    return SearchPreferences(**values)


def make_job(**overrides) -> JobDraft:
    values = {
        "source": "example",
        "external_id": "1",
        "title": "Junior Python Developer",
        "company": "Example Freight Tech",
        "location": "Auckland City, Auckland",
        "region": "Auckland",
        "description": "Build services with Python, FastAPI and SQL.",
    }
    values.update(overrides)
    return JobDraft(**values)
