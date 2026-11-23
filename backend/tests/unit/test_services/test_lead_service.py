from datetime import timedelta

from app.schemas.resume import SkillEntry
from app.services.lead_service import (
    build_queries,
    dedupe_hash,
    dedupe_jobs,
    drop_unwanted,
    keywords_for,
)
from tests.factories import NOW, make_job, make_prefs, make_resume


def test_build_queries_combines_each_title_with_each_region():
    resume = make_resume(titles=["Python Developer", "Backend Developer"], skills=[])
    prefs = make_prefs(regions=["Auckland", "Wellington"])

    assert build_queries(resume, prefs) == [
        "Python Developer Auckland",
        "Python Developer Wellington",
        "Backend Developer Auckland",
        "Backend Developer Wellington",
    ]


def test_build_queries_adds_top_skills_after_titles_up_to_the_limit():
    resume = make_resume(
        titles=["Python Developer"],
        skills=[SkillEntry(name="FastAPI"), SkillEntry(name="SQL")],
    )
    prefs = make_prefs(regions=["Auckland", "Wellington"])

    assert build_queries(resume, prefs, limit=3) == [
        "Python Developer Auckland",
        "Python Developer Wellington",
        "FastAPI Auckland",
    ]


def test_build_queries_prefers_queries_the_user_saved():
    resume = make_resume(search_queries=["API developer Wellington"])

    assert build_queries(resume, make_prefs()) == ["API developer Wellington"]


def test_keywords_for_removes_the_trailing_region():
    regions = ["Auckland", "Remote NZ"]

    assert keywords_for("Python Developer Auckland", regions) == "Python Developer"
    assert keywords_for("FastAPI developer remote nz", regions) == "FastAPI developer"
    assert keywords_for("Data Engineer", regions) == "Data Engineer"


def test_dedupe_hash_ignores_case_spacing_and_suburb():
    first = dedupe_hash("Python  Developer", "Example Ltd", "Auckland, Parnell")
    second = dedupe_hash("python developer", "EXAMPLE LTD", "auckland")

    assert first == second


def test_dedupe_hash_differs_for_another_company():
    assert dedupe_hash("Dev", "One Ltd", "Auckland") != dedupe_hash("Dev", "Two Ltd", "Auckland")


def test_dedupe_jobs_keeps_first_copy_and_drops_already_stored_jobs():
    first = make_job(external_id="1", source="trademe")
    copy = make_job(external_id="2", source="serpapi")
    stored = make_job(external_id="3", title="Data Analyst")

    kept = dedupe_jobs([first, copy, stored], seen={dedupe_hash(stored.title, stored.company,
                                                                stored.location)})

    assert [job.external_id for job in kept] == ["1"]


def test_drop_unwanted_removes_expired_jobs():
    expired = make_job(external_id="old", closes_at=NOW - timedelta(minutes=1))
    open_job = make_job(external_id="open", closes_at=NOW + timedelta(days=1))

    kept = drop_unwanted([expired, open_job], make_prefs(), NOW)

    assert [job.external_id for job in kept] == ["open"]


def test_drop_unwanted_checks_avoid_words_in_title_only():
    senior = make_job(external_id="senior", title="Senior Python Developer")
    mentions = make_job(external_id="ok", description="You report to our senior engineer.")

    kept = drop_unwanted([senior, mentions], make_prefs(), NOW)

    assert [job.external_id for job in kept] == ["ok"]


def test_drop_unwanted_keeps_only_preferred_regions():
    auckland = make_job(external_id="akl")
    dunedin = make_job(external_id="dud", location="Dunedin, Otago", region="Otago")

    kept = drop_unwanted([auckland, dunedin], make_prefs(regions=["Auckland"]), NOW)

    assert [job.external_id for job in kept] == ["akl"]


def test_drop_unwanted_matches_remote_jobs_for_remote_preference():
    remote = make_job(external_id="r", location="Remote", region="")
    onsite = make_job(external_id="o", location="Hamilton, Waikato", region="Waikato")

    kept = drop_unwanted([remote, onsite], make_prefs(regions=["Remote NZ"]), NOW)

    assert [job.external_id for job in kept] == ["r"]


def test_drop_unwanted_removes_jobs_paying_below_the_floor():
    low = make_job(external_id="low", salary_min=50000, salary_max=60000)
    fair = make_job(external_id="fair", salary_min=60000, salary_max=75000)
    unlisted = make_job(external_id="unlisted")

    kept = drop_unwanted([low, fair, unlisted], make_prefs(salary_min=65000), NOW)

    assert [job.external_id for job in kept] == ["fair", "unlisted"]
