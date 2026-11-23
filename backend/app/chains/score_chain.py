"""Job scoring chains. An LLM chain can replace KeywordScoreChain behind ScoreChain."""

from typing import Protocol

from app.core.normalize import contains_term
from app.schemas.job import JobDraft, ScoreResult
from app.schemas.resume import ResumeProfile

SKILL_WEIGHT = 70
TITLE_WEIGHT = 30
SKILLS_FOR_FULL_CREDIT = 3

KNOWN_SKILLS = (
    "Python", "Java", "JavaScript", "TypeScript", "C#", ".NET", "Go", "Rust", "PHP", "Ruby",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "FastAPI", "Django", "Flask", "Node.js",
    "React", "Angular", "Vue", "REST API", "GraphQL", "AWS", "Azure", "GCP", "Docker",
    "Kubernetes", "Terraform", "Linux", "Git", "Excel", "Power BI", "Tableau", "Spark",
    "Airflow", "Kafka", "MuleSoft", "Salesforce", "SAP",
)


class ScoreChain(Protocol):
    def run(self, resume: ResumeProfile, job: JobDraft) -> ScoreResult: ...


def _title_match(titles: list[str], job_title: str) -> float:
    best = 0.0
    for title in titles:
        words = title.split()
        if words:
            found = sum(contains_term(job_title, word) for word in words)
            best = max(best, found / len(words))
    return best


class KeywordScoreChain:
    """Free, offline scoring from skill and title overlap."""

    def run(self, resume: ResumeProfile, job: JobDraft) -> ScoreResult:
        text = job.search_text()
        names = resume.all_skill_names()
        matched = [name for name in names if contains_term(text, name)]
        owned = {name.casefold() for name in names}
        missing = [
            skill
            for skill in KNOWN_SKILLS
            if skill.casefold() not in owned and contains_term(text, skill)
        ]

        needed = len(matched) + len(missing)
        coverage = len(matched) / needed if needed else 0.0
        title_match = _title_match(resume.titles, job.title)
        # One shared skill is weak evidence unless the job title also fits.
        evidence = max(min(len(matched) / SKILLS_FOR_FULL_CREDIT, 1.0), title_match)
        raw = SKILL_WEIGHT * coverage * evidence + TITLE_WEIGHT * title_match
        score = int(raw + 0.5)

        reason = f"Matches {', '.join(matched)}." if matched else "No shared skills found."
        if missing:
            reason += f" Missing {', '.join(missing)}."
        return ScoreResult(
            score=score, matched_skills=matched, missing_skills=missing, reason=reason
        )
