"""Rules that apply to every match score, whichever model produced it."""

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.chains.score_chain import ScoreChain
from app.core.errors import ProviderError
from app.core.normalize import contains_term
from app.providers.llm.gemini import Embedder
from app.schemas.feedback import Decision
from app.schemas.job import JobDraft, ScoreResult, StoredJob
from app.schemas.resume import ResumeProfile, SearchPreferences, WorkRights

HARD_REQUIREMENT_CAP = 40
MAX_FEEDBACK_ADJUSTMENT = 10
COMPANY_FEEDBACK_POINTS = 3
TITLE_WORD_FEEDBACK_POINTS = 2
_GENERIC_TITLE_WORDS = {
    "a", "an", "and", "for", "of", "the", "to", "in", "junior", "mid", "graduate", "intermediate",
    "developer", "engineer", "analyst", "manager", "specialist", "officer", "consultant", "lead",
    "senior", "role",
}
_WORDS = re.compile(r"[a-z0-9+#.]+")

_SENTENCES = re.compile(r"[.!?\n]+")
_REQUIRED = re.compile(r"\b(?:must|requires?|required|essential|needs?\s+to)\b", re.IGNORECASE)
_LICENCE_QUALIFIER = re.compile(r"\b(?:full|clean|valid|current)\b", re.IGNORECASE)
_NZ_CITIZEN = re.compile(r"\b(?:nz|new zealand)\s+citizen(?:ship)?\b", re.IGNORECASE)
_CITIZEN_OR_RESIDENT = re.compile(
    r"\b(?:nz|new zealand)\s+citizen(?:ship)?\s*(?:or|/|and)\s*(?:permanent\s+)?residen",
    re.IGNORECASE,
)
_RIGHT_TO_WORK = re.compile(
    r"\b(?:right|eligible|entitled)\s+to\s+work\s+in\s+(?:nz|new zealand)\b", re.IGNORECASE
)
_DRIVER_LICENCE = re.compile(r"\bdriv(?:er|ing)(?:['’]?s)?\s+licen[cs]e\b", re.IGNORECASE)
_SECURITY_CLEARANCE = re.compile(r"\bsecurity\s+clearance\b", re.IGNORECASE)


def passes_prefilter(resume: ResumeProfile, job: JobDraft) -> bool:
    """Cheap check before scoring: the job must mention at least one resume skill."""
    text = job.search_text()
    return any(contains_term(text, name) for name in resume.all_skill_names())


def _resume_has(resume: ResumeProfile, pattern: re.Pattern[str]) -> bool:
    return any(pattern.search(name) for name in resume.all_skill_names())


def find_blockers(
    resume: ResumeProfile, work_rights: WorkRights | None, job: JobDraft
) -> list[str]:
    """List hard requirements in the job that the candidate does not meet."""
    blockers: list[str] = []
    for sentence in _SENTENCES.split(job.search_text()):
        required = _REQUIRED.search(sentence) is not None

        if required and _CITIZEN_OR_RESIDENT.search(sentence):
            if work_rights not in ("citizen", "resident"):
                blockers.append("NZ citizenship or residency")
        elif required and _NZ_CITIZEN.search(sentence):
            if work_rights != "citizen":
                blockers.append("NZ citizenship")

        if required and _RIGHT_TO_WORK.search(sentence) and work_rights == "needs_sponsorship":
            blockers.append("Right to work in NZ")

        if (
            _DRIVER_LICENCE.search(sentence)
            and (required or _LICENCE_QUALIFIER.search(sentence))
            and not _resume_has(resume, _DRIVER_LICENCE)
        ):
            blockers.append("Driver licence")

        if (
            required
            and _SECURITY_CLEARANCE.search(sentence)
            and not _resume_has(resume, _SECURITY_CLEARANCE)
        ):
            blockers.append("Security clearance")

    return list(dict.fromkeys(blockers))


@dataclass(frozen=True)
class FeedbackWeights:
    companies: Counter = field(default_factory=Counter)
    words: Counter = field(default_factory=Counter)


def _title_words(title: str) -> set[str]:
    return set(_WORDS.findall(title.casefold())) - _GENERIC_TITLE_WORDS


def build_feedback(decisions: Iterable[Decision]) -> FeedbackWeights:
    """Summarise past approvals (+1) and skips (-1) by company and title word."""
    weights = FeedbackWeights()
    for decision in decisions:
        direction = 1 if decision.action == "approve" else -1
        weights.companies[decision.company.strip().casefold()] += direction
        for word in _title_words(decision.title):
            weights.words[word] += direction
    return weights


def apply_feedback(result: ScoreResult, job: JobDraft, weights: FeedbackWeights) -> ScoreResult:
    """Move a score by a small, limited amount based on past decisions."""
    raw = COMPANY_FEEDBACK_POINTS * weights.companies[job.company.strip().casefold()]
    raw += TITLE_WORD_FEEDBACK_POINTS * sum(weights.words[w] for w in _title_words(job.title))
    change = max(-MAX_FEEDBACK_ADJUSTMENT, min(MAX_FEEDBACK_ADJUSTMENT, raw))
    if change == 0:
        return result
    return result.model_copy(
        update={
            "score": max(0, min(100, result.score + change)),
            "reason": f"{result.reason} Adjusted by {change:+d} from your past decisions.".strip(),
        }
    )


def score_job(
    chain: ScoreChain,
    resume: ResumeProfile,
    prefs: SearchPreferences,
    job: JobDraft,
    feedback: FeedbackWeights | None = None,
) -> ScoreResult:
    """Score a job. Hard requirements are applied last, so nothing can lift past the cap."""
    result = chain.run(resume, job)
    if feedback is not None and not result.used_ai:  # AI scoring already saw the decisions
        result = apply_feedback(result, job, feedback)
    return apply_blockers(result, find_blockers(resume, prefs.work_rights, job))


@dataclass
class RankedJobs:
    candidates: list[StoredJob]
    rejected: list[StoredJob]
    errors: list[str] = field(default_factory=list)


def _profile_text(resume: ResumeProfile) -> str:
    """A summary without personal details, because this text goes to an embedding provider."""
    return "\n".join(
        [
            f"Roles: {', '.join(resume.titles)}",
            f"Skills: {', '.join(resume.all_skill_names())}",
            f"Industries: {', '.join(resume.industries)}",
        ]
    )


def _by_keyword(resume: ResumeProfile, jobs: list[StoredJob], errors: list[str]) -> RankedJobs:
    candidates, rejected = [], []
    for job in jobs:
        (candidates if passes_prefilter(resume, job.draft) else rejected).append(job)
    return RankedJobs(candidates, rejected, errors)


def rank_candidates(
    resume: ResumeProfile,
    jobs: list[StoredJob],
    embedder: Embedder | None,
    keep_similarity: float,
) -> RankedJobs:
    """Best matches first. A job sharing a skill is never dropped by embeddings alone."""
    if embedder is None or not jobs:
        return _by_keyword(resume, jobs, [])
    try:
        query = embedder.embed(_profile_text(resume), "RETRIEVAL_QUERY")
        scored = []
        for job in jobs:
            vector = embedder.embed(job.draft.search_text(), "RETRIEVAL_DOCUMENT")
            similarity = sum(a * b for a, b in zip(query, vector, strict=True))
            scored.append(job.model_copy(update={"similarity": similarity}))
    except ProviderError as error:
        return _by_keyword(resume, jobs, [f"Embeddings: {error}"])

    scored.sort(key=lambda job: job.similarity, reverse=True)
    candidates, rejected = [], []
    for job in scored:
        keep = job.similarity >= keep_similarity or passes_prefilter(resume, job.draft)
        (candidates if keep else rejected).append(job)
    return RankedJobs(candidates, rejected)


def apply_blockers(result: ScoreResult, blockers: list[str]) -> ScoreResult:
    """A job needing something the candidate lacks can never score above the cap."""
    if not blockers:
        return result
    missing = list(dict.fromkeys([*result.missing_skills, *blockers]))
    return result.model_copy(
        update={
            "score": min(result.score, HARD_REQUIREMENT_CAP),
            "missing_skills": missing,
            "reason": f"Needs {', '.join(blockers)}. {result.reason}".strip(),
        }
    )
