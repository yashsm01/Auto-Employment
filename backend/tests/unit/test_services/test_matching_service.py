import pytest

from app.chains.score_chain import KeywordScoreChain
from app.schemas.job import ScoreResult
from app.schemas.resume import SkillEntry
from app.services.matching_service import apply_blockers, find_blockers, passes_prefilter
from tests.factories import make_job, make_resume


def test_keyword_score_weighs_skill_coverage_and_title():
    job = make_job(
        title="Junior Python Developer",
        description="Python, FastAPI and SQL services on AWS.",
    )

    result = KeywordScoreChain().run(make_resume(), job)

    # Skills: 3 matched of 4 needed = 0.75 * 70 = 52.5. Title fully matches = 30.
    assert result.score == 83
    assert result.matched_skills == ["Python", "FastAPI", "SQL"]
    assert result.missing_skills == ["AWS"]


def test_keyword_score_is_zero_when_nothing_overlaps():
    job = make_job(title="Registered Nurse", description="Care for patients on the ward.")

    assert KeywordScoreChain().run(make_resume(), job).score == 0


def test_keyword_score_does_not_count_a_resume_skill_as_missing():
    resume = make_resume(skills=[SkillEntry(name="aws")])
    job = make_job(title="Cloud Engineer", description="Work with AWS.")

    assert KeywordScoreChain().run(resume, job).missing_skills == []


def _developer_resume():
    return make_resume(
        titles=["Python Developer", "Backend Developer", "Automation Engineer"],
        skills=[
            SkillEntry(name=name)
            for name in ("Python", "FastAPI", "SQL", "REST API", "Git", "Excel")
        ],
    )


def test_unrelated_job_mentioning_one_skill_is_not_shortlisted():
    job = make_job(title="Office Administrator", description="Strong Excel skills needed.")

    # One skill of three needed for full credit: 70 / 3 = 23.3. No title match.
    assert KeywordScoreChain().run(_developer_resume(), job).score == 23


def test_partial_title_with_one_skill_is_not_shortlisted():
    job = make_job(
        title="Process Automation Technician", description="PLC work and Excel reporting."
    )

    # Half the title matches, so skills earn half credit: 35 + 15.
    assert KeywordScoreChain().run(_developer_resume(), job).score == 50


def test_exact_title_with_a_short_ad_is_still_a_strong_match():
    job = make_job(title="Python Developer", description="Join us to write Python.")

    assert KeywordScoreChain().run(_developer_resume(), job).score == 100


def test_prefilter_keeps_a_job_sharing_a_skill():
    assert passes_prefilter(make_resume(), make_job(title="Analyst", description="Uses SQL."))


def test_prefilter_drops_a_job_with_no_shared_skill():
    job = make_job(title="Registered Nurse", description="Care for patients.")

    assert not passes_prefilter(make_resume(), job)


@pytest.mark.parametrize(
    ("description", "work_rights", "blocked"),
    [
        ("Must be a New Zealand citizen.", "open_visa", True),
        ("Must be a New Zealand citizen.", "resident", True),
        ("Must be a New Zealand citizen.", "citizen", False),
        ("NZ citizenship required.", "resident", True),
        ("Must be an NZ citizen or permanent resident.", "open_visa", True),
        ("Must be an NZ citizen or permanent resident.", "resident", False),
        ("Must have the right to work in New Zealand.", "needs_sponsorship", True),
        ("Must have the right to work in New Zealand.", "open_visa", False),
        ("Must have the right to work in New Zealand.", None, False),
        ("We welcome all applicants.", "needs_sponsorship", False),
    ],
)
def test_find_blockers_checks_work_rights(description, work_rights, blocked):
    job = make_job(description=description)

    assert bool(find_blockers(make_resume(), work_rights, job)) is blocked


def test_find_blockers_flags_a_driver_licence_missing_from_the_resume():
    job = make_job(description="A full NZ driver's licence is essential.")

    assert find_blockers(make_resume(), "citizen", job) == ["Driver licence"]


def test_find_blockers_accepts_a_driver_licence_on_the_resume():
    resume = make_resume(tools=["Driver licence"])
    job = make_job(description="A full NZ driver's licence is essential.")

    assert find_blockers(resume, "citizen", job) == []


def test_find_blockers_flags_security_clearance():
    job = make_job(description="Security clearance required.")

    assert find_blockers(make_resume(), "citizen", job) == ["Security clearance"]


def test_apply_blockers_caps_score_at_40_and_lists_the_blocker():
    raw = ScoreResult(score=90, matched_skills=["Python"], missing_skills=[], reason="Good")

    capped = apply_blockers(raw, ["Driver licence"])

    assert capped.score == 40
    assert capped.missing_skills == ["Driver licence"]


def test_apply_blockers_keeps_a_lower_score():
    raw = ScoreResult(score=25, matched_skills=[], missing_skills=[], reason="Weak")

    assert apply_blockers(raw, ["Driver licence"]).score == 25


def test_apply_blockers_changes_nothing_without_blockers():
    raw = ScoreResult(score=90, matched_skills=["Python"], missing_skills=[], reason="Good")

    assert apply_blockers(raw, []) == raw
