from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.chains.resume_sections_chain import ResumeSectionsChain, SectionsExtraction
from app.core.config import Settings
from app.core.deps import get_sections_chain, get_settings
from app.core.errors import NotFound
from app.main import create_app
from app.repositories import (
    applications_repo,
    companies_repo,
    jobs_repo,
    profiles_repo,
    resumes_repo,
    skills_repo,
)
from app.schemas.job import ScoreResult
from app.schemas.resume import ResumeProfile, SkillEntry
from app.schemas.tailoring import BaseSections, Bullet, RoleSection
from app.services import coverage_service, master_cv_service
from tests.factories import make_job
from tests.fakes import ScriptedLLM

pytestmark = pytest.mark.postgres

RESUME_TEXT = "Sample Person\nData Engineer with Python and SQL experience."


def _sections() -> BaseSections:
    return BaseSections(
        headline="Data Engineer",
        summary="",
        roles=[
            RoleSection(
                title="Data Engineer",
                employer="Example Retail Ltd",
                dates="Mar 2022 – Present",
                bullets=[
                    Bullet(id="r0b0", text="Built pipelines with Python and Airflow."),
                    Bullet(id="r0b1", text="Moved reporting onto Amazon Web Services."),
                ],
            )
        ],
        skills=["Python", "SQL"],
        education=["BSc Computer Science, Example University"],
    )


@pytest.fixture
def client(database_url, tmp_path):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=database_url, upload_dir=tmp_path, _env_file=None
    )
    app.dependency_overrides[get_sections_chain] = lambda: None
    with TestClient(app) as test_client:
        yield test_client


def _setup(conn):
    profile_id = profiles_repo.first_profile_id(conn)
    profiles_repo.add_base_resume(
        conn,
        profile_id,
        {"text": RESUME_TEXT, "contact": {"name": "Sample Person"},
         "sections": _sections().model_dump()},
        "resume.pdf",
        ResumeProfile(titles=["Data Engineer"],
                      skills=[SkillEntry(name="Python"), SkillEntry(name="SQL")]),
    )
    conn.commit()
    return profile_id


def _application(conn, profile_id, required=(), preferred=(), split=True, matched=(), missing=()):
    job = make_job(external_id=uuid4().hex)
    company_id = companies_repo.upsert_from_job(conn, job)
    job_id = jobs_repo.insert(conn, job, company_id, uuid4().hex)
    result = ScoreResult(
        score=80,
        matched_skills=list(matched),
        missing_skills=list(missing),
        required_skills=list(required),
        preferred_skills=list(preferred),
        requirements_split=split,
        reason="Good fit.",
    )
    application_id = applications_repo.record_score(
        conn, profile_id, job_id, result, "shortlisted"
    )
    conn.commit()
    return application_id


def test_have_adds_to_the_master_cv_and_profile_once(conn):
    profile_id = _setup(conn)

    coverage_service.decide(conn, profile_id, "Kubernetes", "have")
    coverage_service.decide(conn, profile_id, "Kubernetes", "have")

    view = master_cv_service.load(conn, profile_id, None)
    assert view.sections.skills.count("Kubernetes") == 1
    terms = skills_repo.profile_skill_names(conn, profile_id)
    assert terms.count("Kubernetes") == 1
    assert skills_repo.decisions(conn, profile_id) == {"kubernetes": "have"}


def test_undo_have_removes_the_skill_again(conn):
    profile_id = _setup(conn)
    coverage_service.decide(conn, profile_id, "Kubernetes", "have")

    coverage_service.decide(conn, profile_id, "Kubernetes", None)

    view = master_cv_service.load(conn, profile_id, None)
    assert "Kubernetes" not in view.sections.skills
    assert "Kubernetes" not in skills_repo.profile_skill_names(conn, profile_id)
    assert skills_repo.decisions(conn, profile_id) == {}


def test_another_profiles_coverage_is_not_found(conn):
    profile_id = _setup(conn)
    other_profile = conn.execute(
        "insert into profiles (full_name) values ('Other Person') returning id"
    ).fetchone()["id"]
    conn.commit()
    other_application = _application(conn, other_profile, required=["Python"])

    with pytest.raises(NotFound):
        coverage_service.for_application(conn, profile_id, other_application)


def test_shortlist_items_carry_required_counts(conn):
    from app.services import application_service

    profile_id = _setup(conn)
    _application(
        conn, profile_id, required=["Python", "AWS", "Kubernetes"], preferred=["Go"]
    )
    _application(conn, profile_id, required=(), split=False,
                 matched=["Python"], missing=["Kubernetes"])

    items = application_service.shortlist_items(conn, profile_id)

    split_item = next(item for item in items if item.requirements_split)
    assert (split_item.required_covered, split_item.required_total) == (2, 3)
    legacy_item = next(item for item in items if not item.requirements_split)
    assert (legacy_item.required_covered, legacy_item.required_total) == (1, 2)


def test_coverage_endpoint_counts_and_decisions(client, conn):
    profile_id = _setup(conn)
    application_id = _application(conn, profile_id, required=["Python", "Kubernetes"])

    body = client.get(f"/applications/{application_id}/coverage").json()
    assert body["required_text"] == "1 of 2"
    assert [skill["status"] for skill in body["required"]] == ["shown", "missing"]

    response = client.post("/skills/decision", json={"skill": "Kubernetes", "decision": "have"})
    assert response.json() == {"ok": True}
    body = client.get(f"/applications/{application_id}/coverage").json()
    assert body["required_text"] == "2 of 2"
    assert body["required"][1]["status"] == "added"

    client.post("/skills/decision", json={"skill": "Kubernetes", "decision": None})
    body = client.get(f"/applications/{application_id}/coverage").json()
    assert body["required_text"] == "1 of 2"


def test_decision_body_is_checked(client, conn):
    _setup(conn)

    blank = {"skill": "   ", "decision": "have"}
    assert client.post("/skills/decision", json=blank).status_code == 422
    too_long = {"skill": "x" * 81, "decision": "no"}
    assert client.post("/skills/decision", json=too_long).status_code == 422


def test_another_profiles_coverage_is_404_over_http(client, conn):
    _setup(conn)
    other_profile = conn.execute(
        "insert into profiles (full_name) values ('Other Person') returning id"
    ).fetchone()["id"]
    conn.commit()
    other_application = _application(conn, other_profile, required=["Python"])

    assert client.get(f"/applications/{other_application}/coverage").status_code == 404


def _setup_without_sections(conn):
    """A base resume with no cached master CV sections, so no AI chain means the CV is empty."""
    profile_id = profiles_repo.first_profile_id(conn)
    profiles_repo.add_base_resume(
        conn,
        profile_id,
        {"text": RESUME_TEXT, "contact": {"name": "Sample Person"}},
        "resume.pdf",
        ResumeProfile(titles=["Data Engineer"],
                      skills=[SkillEntry(name="Python"), SkillEntry(name="SQL")]),
    )
    conn.commit()
    return profile_id


def test_have_without_sections_keeps_profile_skills_counting(conn):
    profile_id = _setup_without_sections(conn)
    application_id = _application(conn, profile_id, required=["Python", "Kubernetes"])
    before = coverage_service.for_application(conn, profile_id, application_id)
    assert before.required[0].status == "shown"
    assert before.required_text == "1 of 2"
    covered_before = coverage_service.covered(before.required)

    coverage_service.decide(conn, profile_id, "Kubernetes", "have")
    conn.commit()

    after = coverage_service.for_application(conn, profile_id, application_id)
    assert coverage_service.covered(after.required) == covered_before + 1
    assert after.required[0].status == "shown"


def test_have_without_ai_on_a_blank_cv_writes_no_sections(client, conn):
    profile_id = _setup_without_sections(conn)

    response = client.post("/skills/decision", json={"skill": "Kubernetes", "decision": "have"})
    assert response.json() == {"ok": True}

    saved = resumes_repo.latest_base(conn, profile_id)
    assert "sections" not in saved["content"]
    assert "Kubernetes" in skills_repo.profile_skill_names(conn, profile_id)


def test_the_builder_form_shows_profile_skills_after_have_without_ai(client, conn):
    _setup_without_sections(conn)
    client.post("/skills/decision", json={"skill": "Kubernetes", "decision": "have"})

    view = client.get("/master-cv").json()

    assert view["source"] == "empty"
    assert view["sections"]["skills"] == ["Python", "SQL", "Kubernetes"]


def test_have_on_a_blank_cv_keeps_the_counts_steady(conn):
    profile_id = _setup_without_sections(conn)
    application_id = _application(conn, profile_id, required=["Python", "Kubernetes"])
    before = coverage_service.for_application(conn, profile_id, application_id)

    coverage_service.decide(conn, profile_id, "Kubernetes", "have")
    conn.commit()

    after = coverage_service.for_application(conn, profile_id, application_id)
    assert after.required_text == "2 of 2"
    assert coverage_service.covered(after.required) >= coverage_service.covered(before.required)
    assert after.required[1].status == "added"


def test_undo_keeps_a_skill_the_user_already_had(conn):
    profile_id = _setup(conn)

    coverage_service.decide(conn, profile_id, "Python", "have")
    coverage_service.decide(conn, profile_id, "Python", None)

    assert "Python" in skills_repo.profile_skill_names(conn, profile_id)
    assert "Python" in master_cv_service.load(conn, profile_id, None).sections.skills


def test_undo_removes_a_skill_it_added_after_a_repeated_have(conn):
    profile_id = _setup(conn)

    coverage_service.decide(conn, profile_id, "Kubernetes", "have")
    coverage_service.decide(conn, profile_id, "Kubernetes", "have")
    coverage_service.decide(conn, profile_id, "Kubernetes", None)

    assert "Kubernetes" not in skills_repo.profile_skill_names(conn, profile_id)
    assert "Kubernetes" not in master_cv_service.load(conn, profile_id, None).sections.skills


def test_changing_a_skill_it_already_had_to_no_keeps_it(conn):
    profile_id = _setup(conn)

    coverage_service.decide(conn, profile_id, "SQL", "have")
    coverage_service.decide(conn, profile_id, "SQL", "no")

    assert "SQL" in skills_repo.profile_skill_names(conn, profile_id)
    assert skills_repo.decisions(conn, profile_id) == {"sql": "no"}


def test_shortlist_counts_survive_a_failed_ai_read(conn):
    from app.core.errors import ProviderError
    from app.services import application_service

    profile_id = _setup_without_sections(conn)
    _application(conn, profile_id, required=["Python", "Kubernetes"])
    chain = ResumeSectionsChain(ScriptedLLM(ProviderError("sections", "service is down")))

    items = application_service.shortlist_items(conn, profile_id, chain)

    assert [(item.required_covered, item.required_total) for item in items] == [(1, 2)]


def test_shortlist_endpoint_returns_counts_when_the_ai_read_fails(client, conn):
    from app.core.errors import ProviderError

    profile_id = _setup_without_sections(conn)
    _application(conn, profile_id, required=["Python", "Kubernetes"])
    chain = ResumeSectionsChain(ScriptedLLM(ProviderError("sections", "service is down")))
    client.app.dependency_overrides[get_sections_chain] = lambda: chain

    response = client.get("/shortlist")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert (item["required_covered"], item["required_total"]) == (1, 2)


def test_blank_ai_sections_keep_profile_skills_counting(conn):
    profile_id = _setup_without_sections(conn)
    chain = ResumeSectionsChain(ScriptedLLM(SectionsExtraction()))
    application_id = _application(conn, profile_id, required=["Python", "Kubernetes"])
    before = coverage_service.for_application(conn, profile_id, application_id, chain)
    assert before.required[0].status == "shown"
    assert before.required_text == "1 of 2"

    coverage_service.decide(conn, profile_id, "Kubernetes", "have", chain)
    conn.commit()

    after = coverage_service.for_application(conn, profile_id, application_id, chain)
    assert after.required[0].status == "shown"
    assert after.required_text == "2 of 2"


def _setup_with_cv_text(conn, text, content_sections=None):
    profile_id = profiles_repo.first_profile_id(conn)
    content = {"text": text, "contact": {"name": "Sample Person"}}
    if content_sections is not None:
        content["sections"] = content_sections
    profiles_repo.add_base_resume(
        conn,
        profile_id,
        content,
        "resume.pdf",
        ResumeProfile(titles=["Data Engineer"], skills=[SkillEntry(name="Python")]),
    )
    conn.commit()
    return profile_id


def test_coverage_counts_skills_of_a_fresh_read_without_roles(conn):
    profile_id = _setup_with_cv_text(conn, "Sample Person\nKubernetes and Python skills.")
    chain = ResumeSectionsChain(ScriptedLLM(SectionsExtraction(skills=["Kubernetes"])))
    application_id = _application(conn, profile_id, required=["Kubernetes"])

    coverage = coverage_service.for_application(conn, profile_id, application_id, chain)

    assert coverage.required[0].status == "shown"
    assert coverage.required[0].evidence == "Shown in: Key skills"


def test_coverage_counts_skills_of_a_cached_read_without_roles(conn):
    profile_id = _setup_with_cv_text(
        conn,
        "Sample Person\nKubernetes and Python skills.",
        {"summary": "", "roles": [], "skills": ["Kubernetes"], "education": []},
    )
    application_id = _application(conn, profile_id, required=["Kubernetes"])

    coverage = coverage_service.for_application(conn, profile_id, application_id)

    assert coverage.required[0].status == "shown"
    assert coverage.required[0].evidence == "Shown in: Key skills"
