from collections.abc import Sequence

from app.chains.resume_profile_chain import ResumeChain, ResumeProfileChain
from app.chains.resume_sections_chain import ResumeSectionsChain
from app.chains.score_chain import (
    FallbackScoreChain,
    KeywordScoreChain,
    LLMScoreChain,
    ScoreChain,
)
from app.chains.tailor_chain import FactCheckChain, TailorChain
from app.core.config import Settings
from app.providers.llm.factory import build_claude
from app.schemas.feedback import Decision


def get_resume_chain(settings: Settings) -> ResumeChain | None:
    """The AI resume reader, or None when no Claude key is configured."""
    llm = build_claude(settings, settings.resume_model, effort="medium")
    return ResumeProfileChain(llm) if llm else None


def get_chain(
    name: str, settings: Settings | None = None, decisions: Sequence[Decision] = ()
) -> ScoreChain:
    """Build a chain. Without a Claude key, scoring is free keyword matching."""
    if name != "score":
        raise ValueError(f"Unknown chain: {name}")
    llm = build_claude(settings, settings.scoring_model, effort="low") if settings else None
    if llm is None:
        return KeywordScoreChain()
    return FallbackScoreChain(
        LLMScoreChain(llm, decisions), KeywordScoreChain(), llm, settings.max_ai_scores_per_run
    )


def get_tailoring_chains(
    settings: Settings,
) -> tuple[ResumeSectionsChain | None, TailorChain | None, FactCheckChain | None]:
    """Chains for tailoring. All None without a Claude key."""
    sections_llm = build_claude(settings, settings.resume_model, effort="medium")
    tailor_llm = build_claude(settings, settings.tailor_model, effort="medium")
    check_llm = build_claude(settings, settings.scoring_model, effort="low")
    return (
        ResumeSectionsChain(sections_llm) if sections_llm else None,
        TailorChain(tailor_llm) if tailor_llm else None,
        FactCheckChain(check_llm) if check_llm else None,
    )
