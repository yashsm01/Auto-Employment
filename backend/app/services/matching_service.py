"""Rules that apply to every match score, whichever model produced it."""

import re

from app.chains.score_chain import ScoreChain
from app.core.normalize import contains_term
from app.schemas.job import JobDraft, ScoreResult
from app.schemas.resume import ResumeProfile, SearchPreferences, WorkRights

HARD_REQUIREMENT_CAP = 40

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


def score_job(
    chain: ScoreChain, resume: ResumeProfile, prefs: SearchPreferences, job: JobDraft
) -> ScoreResult:
    return apply_blockers(chain.run(resume, job), find_blockers(resume, prefs.work_rights, job))


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
