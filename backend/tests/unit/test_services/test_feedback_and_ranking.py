from uuid import uuid4

import pytest

from app.core.errors import ProviderError
from app.schemas.feedback import Decision
from app.schemas.job import ScoreResult, StoredJob
from app.services.lead_service import drop_unwanted, fetch_all
from app.services.matching_service import (
    apply_feedback,
    build_feedback,
    rank_candidates,
    score_job,
)
from tests.factories import NOW, make_job, make_prefs, make_resume


def _result(score=60, used_ai=False) -> ScoreResult:
    return ScoreResult(score=score, reason="Base.", used_ai=used_ai)


def test_skipping_a_company_lowers_its_later_jobs():
    weights = build_feedback([Decision(action="skip", title="Tester", company="Skip Co")])

    result = apply_feedback(
        _result(), make_job(title="Python Developer", company="skip co"), weights
    )

    assert result.score == 57
    assert "past decisions" in result.reason


def test_approving_a_company_raises_its_later_jobs():
    weights = build_feedback([Decision(action="approve", title="Tester", company="Good Co")])

    result = apply_feedback(
        _result(), make_job(title="Python Developer", company="Good Co"), weights
    )

    assert result.score == 63


def test_skipping_a_kind_of_work_lowers_similar_titles():
    weights = build_feedback([Decision(action="skip", title="Support Engineer", company="A")])

    result = apply_feedback(_result(), make_job(title="Support Analyst", company="B"), weights)

    assert result.score == 58


def test_common_role_words_do_not_carry_feedback():
    weights = build_feedback([Decision(action="skip", title="Support Engineer", company="A")])

    result = apply_feedback(_result(), make_job(title="Platform Engineer", company="B"), weights)

    assert result.score == 60


def test_feedback_adjustment_is_limited():
    decisions = [Decision(action="skip", title="Tester", company="Skip Co")] * 20
    weights = build_feedback(decisions)

    result = apply_feedback(_result(), make_job(company="Skip Co"), weights)

    assert result.score == 50


def test_feedback_keeps_the_score_in_range():
    decisions = [Decision(action="approve", title="Tester", company="Good Co")] * 5
    weights = build_feedback(decisions)

    assert apply_feedback(_result(95), make_job(company="Good Co"), weights).score == 100


def test_no_decisions_changes_nothing():
    original = _result()

    assert apply_feedback(original, make_job(), build_feedback([])) == original


class StaticChain:
    def __init__(self, result: ScoreResult) -> None:
        self.result = result

    def run(self, resume, job) -> ScoreResult:
        return self.result


def test_feedback_is_not_applied_twice_to_ai_scores():
    weights = build_feedback([Decision(action="skip", title="Tester", company="Skip Co")])
    chain = StaticChain(_result(used_ai=True))

    result = score_job(chain, make_resume(), make_prefs(), make_job(company="Skip Co"), weights)

    assert result.score == 60


def test_feedback_cannot_lift_a_job_past_the_hard_requirement_cap():
    decisions = [Decision(action="approve", title="Tester", company="Good Co")] * 5
    job = make_job(company="Good Co", description="Python. Must be a New Zealand citizen.")

    result = score_job(
        StaticChain(_result(90)), make_resume(), make_prefs(), job, build_feedback(decisions)
    )

    assert result.score == 40


class FakeEmbedder:
    """Maps a word in the text to a direction, so similarity is easy to derive by hand."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.texts: list[str] = []

    def embed(self, text: str, task_type: str) -> list[float]:
        self.texts.append(text)
        if self.error:
            raise self.error
        if "Close" in text:
            return [0.9, 0.43589]
        if "Middle" in text:
            return [0.7, 0.71414]
        if "Far" in text:
            return [0.0, 1.0]
        return [1.0, 0.0]


def _stored(title: str, description: str = "No shared words.") -> StoredJob:
    return StoredJob(job_id=uuid4(), draft=make_job(title=title, description=description))


def test_ranking_keeps_a_similar_job_with_no_exact_skill_and_sorts_by_similarity():
    jobs = [_stored("Middle Role"), _stored("Close Role"), _stored("Far Role")]

    ranked = rank_candidates(make_resume(), jobs, FakeEmbedder(), keep_similarity=0.6)

    assert [job.draft.title for job in ranked.candidates] == ["Close Role", "Middle Role"]
    assert ranked.candidates[0].similarity == pytest.approx(0.9)
    assert [job.draft.title for job in ranked.rejected] == ["Far Role"]


def test_ranking_never_drops_a_job_with_a_shared_skill():
    jobs = [_stored("Far Role", "Uses Python daily.")]

    ranked = rank_candidates(make_resume(), jobs, FakeEmbedder(), keep_similarity=0.6)

    assert [job.draft.title for job in ranked.candidates] == ["Far Role"]


def test_ranking_without_embeddings_uses_shared_skills():
    jobs = [_stored("Analyst", "Uses SQL."), _stored("Nurse", "Cares for patients.")]

    ranked = rank_candidates(make_resume(), jobs, None, keep_similarity=0.6)

    assert [job.draft.title for job in ranked.candidates] == ["Analyst"]
    assert [job.draft.title for job in ranked.rejected] == ["Nurse"]
    assert ranked.errors == []


def test_ranking_falls_back_when_embeddings_fail():
    jobs = [_stored("Analyst", "Uses SQL."), _stored("Nurse", "Cares for patients.")]
    embedder = FakeEmbedder(ProviderError("gemini", "HTTP 400"))

    ranked = rank_candidates(make_resume(), jobs, embedder, keep_similarity=0.6)

    assert [job.draft.title for job in ranked.candidates] == ["Analyst"]
    assert ranked.errors == ["Embeddings: gemini: HTTP 400"]
    assert len(embedder.texts) == 1


def test_ranking_sends_the_profile_summary_not_the_raw_resume():
    embedder = FakeEmbedder()

    rank_candidates(make_resume(), [_stored("Close Role")], embedder, keep_similarity=0.6)

    assert "Python Developer" in embedder.texts[0]
    assert "FastAPI" in embedder.texts[0]


def test_remote_preference_rejects_foreign_remote_board_jobs():
    foreign = make_job(external_id="us", source="ats", location="Remote, United States", region="")
    local = make_job(external_id="nz", source="ats", location="Remote, New Zealand", region="")

    kept = drop_unwanted([foreign, local], make_prefs(regions=["Remote NZ"]), NOW)

    assert [job.external_id for job in kept] == ["nz"]


def test_fetch_all_explains_when_no_source_is_connected():
    jobs, errors, report = fetch_all([], ["Python Developer"], [])

    assert jobs == []
    assert "No job sources" in errors[0]
    assert report == []
