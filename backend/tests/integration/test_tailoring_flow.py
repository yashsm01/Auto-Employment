import io
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from pypdf import PdfReader

from app.chains.manager import get_chain
from app.chains.resume_sections_chain import ResumeSectionsChain, SectionsExtraction
from app.chains.tailor_chain import (
    BulletRewrite,
    FactCheckChain,
    FactCheckResult,
    TailorChain,
    TailorDraft,
)
from app.core.config import Settings
from app.core.deps import get_settings
from app.graphs.lead.deps import LeadDeps
from app.graphs.resume.deps import ResumeDeps
from app.graphs.resume.nodes import render_pdf
from app.graphs.runner import run_graph
from app.main import create_app
from app.repositories import runs_repo, skills_repo
from app.schemas.tailoring import BaseSections, Bullet, RoleSection
from app.services import coverage_service, resume_review_service
from app.workers.tailor_job import process_tailoring_queue
from tests.documents import make_pdf
from tests.factories import NOW, make_job
from tests.fakes import ScriptedLLM

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"
RESUME_LINES = (
    "Sample Person",
    "sample.person@example.invalid | +64 21 000 0000",
    "Data Engineer",
    "Example Retail Ltd",
    "Built data pipelines with Python and Airflow for 3 teams.",
    "Wrote SQL reports for the finance team.",
    "Skills: Python, SQL, Docker, Airflow",
)


class OneSource:
    name = "one"

    def __init__(self, job) -> None:
        self.job = job

    def search(self, keywords):
        return [self.job]


@pytest.fixture
def settings(database_url, tmp_path) -> Settings:
    return Settings(database_url=database_url, upload_dir=tmp_path, _env_file=None)


@pytest.fixture
def client(settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client


def _upload_resume(client):
    client.post(
        "/profile/resume", files={"file": ("resume.pdf", make_pdf(*RESUME_LINES))}
    ).raise_for_status()


def _shortlist_job(conn, **job_fields) -> str:
    fields = {
        "external_id": "tailor-1",
        "title": "Data Engineer",
        "company": "Example Freight Tech",
        "description": "Build pipelines with Python, SQL and Airflow.",
        **job_fields,
    }
    deps = LeadDeps(
        conn=conn, sources=[OneSource(make_job(**fields))], score_chain=get_chain("score"), now=NOW
    )
    run_graph("lead", {"profile_id": PROFILE_ID}, deps)
    return str(conn.execute("select id from applications").fetchone()["id"])


def _approve(client, application_id):
    response = client.post(f"/applications/{application_id}/decision", json={"action": "approve"})
    response.raise_for_status()


def test_approving_a_job_prepares_a_resume_and_cover_note(client, conn):
    _upload_resume(client)
    application_id = _shortlist_job(conn)

    _approve(client, application_id)

    view = client.get(f"/applications/{application_id}/resume").json()
    assert view["status"] == "ready"
    assert view["ai_used"] is False
    assert "Data Engineer" in view["cover_note"]
    assert "Example Freight Tech" in view["cover_note"]
    assert "Sample Person" in view["cover_note"]
    pdf = client.get(view["pdf_url"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")


def test_resume_review_lists_resumes_waiting_for_review(client, conn):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    _approve(client, application_id)

    items = client.get("/resume-review").json()["items"]

    assert [(item["application_id"], item["status"]) for item in items] == [
        (application_id, "ready")
    ]
    assert items[0]["title"] == "Data Engineer"


def test_the_example_profile_cannot_be_tailored(client, conn):
    application_id = _shortlist_job(
        conn, title="Python Developer", description="Python, FastAPI and SQL."
    )

    _approve(client, application_id)

    item = client.get("/resume-review").json()["items"][0]
    assert item["status"] == "tailoring"
    assert "Upload your resume" in item["error"]


def test_editing_the_cover_note_is_saved(client, conn):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    _approve(client, application_id)

    saved = client.put(
        f"/applications/{application_id}/resume", json={"cover_note": "Kia ora,\n\nEdited."}
    )

    assert saved.status_code == 200
    assert client.get(f"/applications/{application_id}/resume").json()["cover_note"] == (
        "Kia ora,\n\nEdited."
    )


def test_approving_the_resume_marks_it_ready_to_send(client, conn):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    _approve(client, application_id)

    response = client.post(
        f"/applications/{application_id}/resume-decision", json={"action": "approve"}
    )

    assert response.json()["status"] == "approved"
    assert conn.execute("select count(*) as n from outbox").fetchone()["n"] == 0  # Phase 3


def test_rejecting_the_resume_closes_the_job_without_lowering_future_scores(client, conn):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    _approve(client, application_id)
    skips_before = conn.execute(
        "select count(*) as n from feedback where action = 'skip'"
    ).fetchone()["n"]

    response = client.post(
        f"/applications/{application_id}/resume-decision", json={"action": "reject"}
    )

    assert response.json()["status"] == "closed"
    skips_after = conn.execute(
        "select count(*) as n from feedback where action = 'skip'"
    ).fetchone()["n"]
    assert skips_after == skips_before


def test_a_resume_decision_needs_a_resume_ready_for_review(client, conn):
    application_id = _shortlist_job(conn)

    response = client.post(
        f"/applications/{application_id}/resume-decision", json={"action": "approve"}
    )

    assert response.status_code == 409


def test_regenerating_makes_a_new_version(client, conn):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    _approve(client, application_id)
    first = client.get(f"/applications/{application_id}/resume").json()["resume_id"]

    response = client.post(f"/applications/{application_id}/tailor")

    assert response.status_code == 200
    second = client.get(f"/applications/{application_id}/resume").json()
    assert second["resume_id"] != first
    assert second["status"] == "ready"


def test_a_pdf_outside_the_upload_folder_is_never_served(client, conn, tmp_path):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    _approve(client, application_id)
    view = client.get(f"/applications/{application_id}/resume").json()
    outside = Path(tmp_path).parent / "outside.pdf"
    conn.execute(
        "update resumes set file_path = %s where id = %s", (str(outside), view["resume_id"])
    )
    conn.commit()

    assert client.get(view["pdf_url"]).status_code == 404


def test_an_unknown_pdf_is_404(client):
    assert client.get("/resumes/00000000-0000-4000-8000-00000000ffff/pdf").status_code == 404


def _sections() -> SectionsExtraction:
    return SectionsExtraction(
        summary="",
        roles=[
            {
                "title": "Data Engineer",
                "employer": "Example Retail Ltd",
                "bullets": [
                    "Built data pipelines with Python and Airflow for 3 teams.",
                    "Wrote SQL reports for the finance team.",
                ],
            }
        ],
        skills=["Python", "SQL", "Docker", "Airflow"],
    )


def _draft() -> TailorDraft:
    return TailorDraft(
        summary="",
        bullets=[
            BulletRewrite(id="r0b1", text="Wrote SQL reports on AWS for the finance team."),
            BulletRewrite(id="r0b0", text="Built Python and Airflow pipelines used by 3 teams."),
        ],
        skills_order=["Airflow", "Python"],
        cover_note="Kia ora,\n\nI build data pipelines. I won an award.\n\nSample Person",
    )


def test_tailoring_with_ai_keeps_only_supported_changes(client, conn, settings):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    conn.execute("update applications set status = 'tailoring' where id = %s", (application_id,))
    company_id = conn.execute("select id from companies").fetchone()["id"]
    conn.execute(
        "insert into company_facts (company_id, field, value, source, confidence) values "
        "(%s, 'about', 'Builds freight software.', 'website', 'medium'), "
        "(%s, 'recent_news', 'Unverified rumour.', 'tavily', 'check')",
        (company_id, company_id),
    )
    conn.commit()
    tailor_llm = ScriptedLLM(_draft())
    check = FactCheckResult(unsupported_cover_note_sentences=["I won an award."])
    deps = ResumeDeps(
        conn=conn,
        sections_chain=ResumeSectionsChain(ScriptedLLM(_sections())),
        tailor_chain=TailorChain(tailor_llm),
        check_chain=FactCheckChain(ScriptedLLM(check)),
        upload_dir=settings.upload_dir,
        now=datetime(2026, 11, 24, tzinfo=UTC),
    )

    result = run_graph("resume", {"application_id": application_id}, deps)

    assert result.status == "ok"
    view = client.get(f"/applications/{application_id}/resume").json()
    bullets = [b["text"] for b in view["tailored"]["roles"][0]["bullets"]]
    assert bullets == [
        "Wrote SQL reports for the finance team.",  # AWS was added, so it was reverted
        "Built Python and Airflow pipelines used by 3 teams.",
    ]
    assert "I won an award." not in view["cover_note"]
    assert len(view["notes"]) == 2
    assert view["ai_used"] is True
    assert view["facts_used"] == ["Builds freight software."]  # "check" facts are not used
    assert "Unverified rumour." not in tailor_llm.calls[0]["user"]


def test_the_queue_skips_jobs_that_already_failed(conn, settings):
    # The example profile can't be tailored, so this attempt fails.
    application_id = _shortlist_job(
        conn, title="Python Developer", description="Python, FastAPI and SQL."
    )
    conn.execute("update applications set status = 'tailoring' where id = %s", (application_id,))
    conn.commit()

    assert process_tailoring_queue(settings) == 1
    assert process_tailoring_queue(settings) == 0


def test_a_regenerate_request_that_never_ran_is_picked_up_by_the_queue(client, conn, settings):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    _approve(client, application_id)
    # Ask for a new version, but its run never starts, for example because another run held
    # the lock or the backend restarted.
    conn.commit()  # start a fresh transaction, as each API request does, so now() is current
    resume_review_service.request_tailoring(conn, UUID(PROFILE_ID), UUID(application_id))
    conn.commit()

    assert client.get(f"/applications/{application_id}/resume").json()["error"] is None
    assert process_tailoring_queue(settings) == 1
    assert client.get(f"/applications/{application_id}/resume").json()["status"] == "ready"


def test_trying_again_hides_the_old_error(client, conn):
    # The example profile can't be tailored, so the first attempt fails.
    application_id = _shortlist_job(
        conn, title="Python Developer", description="Python, FastAPI and SQL."
    )
    _approve(client, application_id)
    assert client.get(f"/applications/{application_id}/resume").json()["error"]

    conn.commit()  # start a fresh transaction, as each API request does, so now() is current
    resume_review_service.request_tailoring(conn, UUID(PROFILE_ID), UUID(application_id))
    conn.commit()

    assert client.get(f"/applications/{application_id}/resume").json()["error"] is None


def test_a_stuck_tailoring_run_is_cleared_after_ten_minutes(conn):
    for graph in ("resume", "lead"):
        conn.execute(
            "insert into graph_runs (graph, status, input, started_at) "
            "values (%s, 'running', '{}', now() - interval '11 minutes')",
            (graph,),
        )

    assert runs_repo.start(conn, "resume", {}) is not None
    assert runs_repo.start(conn, "lead", {}) is None


def test_contact_details_are_read_from_the_resume_and_editable(client):
    _upload_resume(client)
    profile = client.get("/profile").json()
    assert {key: profile["contact"][key] for key in ("name", "email", "phone")} == {
        "name": "Sample Person",
        "email": "sample.person@example.invalid",
        "phone": "+64 21 000 0000",
    }

    body = {
        key: profile[key]
        for key in (
            "titles",
            "skills",
            "tools",
            "search_queries",
            "regions",
            "work_rights",
            "salary_min",
            "avoid_keywords",
            "shortlist_threshold",
            "boards",
        )
    }
    body["contact"] = {"name": "Sam Person", "email": "sam@example.invalid", "phone": None}
    client.put("/profile", json=body).raise_for_status()

    assert client.get("/profile").json()["contact"]["name"] == "Sam Person"


def test_profile_id_constant_matches_seed():
    assert UUID(PROFILE_ID)


def _seed_base_sections(conn, template: str | None = None) -> None:
    sections = BaseSections(
        summary="",
        roles=[
            RoleSection(
                title="Data Engineer",
                employer="Example Retail Ltd",
                dates="2022 - 2024",
                bullets=[
                    Bullet(id="r0b0", text="Built data pipelines with Python and Airflow."),
                    Bullet(id="r0b1", text="Wrote SQL reports for the finance team."),
                ],
            )
        ],
        skills=["Python", "SQL", "Docker", "Airflow"],
    )
    patch = {"sections": sections.model_dump()}
    if template:
        patch["template"] = template
    conn.execute(
        "update resumes set content = content || %s::jsonb where kind = 'base'",
        (Jsonb(patch),),
    )
    conn.commit()


def _ai_deps(conn, settings, draft: TailorDraft) -> ResumeDeps:
    return ResumeDeps(
        conn=conn,
        sections_chain=ResumeSectionsChain(ScriptedLLM(_sections())),
        tailor_chain=TailorChain(ScriptedLLM(draft)),
        check_chain=None,
        upload_dir=settings.upload_dir,
        now=datetime(2026, 11, 24, tzinfo=UTC),
    )


def test_tailored_files_use_the_chosen_design(client, conn, settings):
    _upload_resume(client)
    _seed_base_sections(conn, template="modern")
    application_id = _shortlist_job(conn)

    _approve(client, application_id)

    view = client.get(f"/applications/{application_id}/resume").json()
    content = conn.execute(
        "select content, file_path from resumes where id = %s", (view["resume_id"],)
    ).fetchone()
    assert content["content"]["template"] == "modern"
    assert Path(content["file_path"]).with_suffix(".docx").is_file()
    assert view["docx_url"] == f"/resumes/{view['resume_id']}/docx"


def test_docx_route_serves_the_word_file_for_this_profile_only(client, conn, settings):
    _upload_resume(client)
    _seed_base_sections(conn)
    application_id = _shortlist_job(conn)
    _approve(client, application_id)
    view = client.get(f"/applications/{application_id}/resume").json()

    response = client.get(view["docx_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert response.content.startswith(b"PK")
    assert client.get("/resumes/00000000-0000-4000-8000-00000000ffff/docx").status_code == 404
    outside = Path(settings.upload_dir).parent / "outside.pdf"
    conn.execute(
        "update resumes set file_path = %s where id = %s", (str(outside), view["resume_id"])
    )
    conn.commit()
    assert client.get(view["docx_url"]).status_code == 404


def test_a_declined_skill_is_removed_from_the_cover_note_and_bullets(client, conn, settings):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    conn.execute("update applications set status = 'tailoring' where id = %s", (application_id,))
    skills_repo.set_decision(conn, PROFILE_ID, "Looker", "no")
    conn.commit()
    draft = TailorDraft(
        summary="",
        bullets=[
            BulletRewrite(id="r0b0", text="Built Python and Airflow pipelines with Looker."),
            BulletRewrite(id="r0b1", text="Wrote SQL reports for the finance team."),
        ],
        skills_order=["Python"],
        cover_note="Kia ora,\n\nI build data pipelines. I know Looker well.\n\nSample Person",
    )

    deps = _ai_deps(conn, settings, draft)
    result = run_graph("resume", {"application_id": application_id}, deps)

    assert result.status == "ok"
    view = client.get(f"/applications/{application_id}/resume").json()
    assert "Looker" not in view["tailored"]["roles"][0]["bullets"][0]["text"]
    assert "Looker" not in view["cover_note"]
    assert "I build data pipelines." in view["cover_note"]
    assert view["notes"].count("Removed a mention of Looker, which you said you don't have.") == 1


def test_review_view_includes_coverage_of_the_tailored_version(client, conn, settings):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    conn.execute(
        "update applications set required_skills = %s, requirements_split = true where id = %s",
        (["Airflow", "Looker", "Kubernetes"], application_id),
    )
    conn.execute("update applications set status = 'tailoring' where id = %s", (application_id,))
    skills_repo.set_decision(conn, PROFILE_ID, "Looker", "no")
    conn.commit()
    _seed_base_sections(conn)
    draft = TailorDraft(
        summary="",
        bullets=[BulletRewrite(id="r0b0", text="Built Python and Airflow pipelines for 3 teams.")],
        skills_order=["Python"],
        cover_note="Kia ora,\n\nI build data pipelines.\n\nSample Person",
    )

    run_graph("resume", {"application_id": application_id}, _ai_deps(conn, settings, draft))

    view = client.get(f"/applications/{application_id}/resume").json()
    statuses = {item["name"]: item["status"] for item in view["coverage"]["required"]}
    assert statuses == {"Airflow": "shown", "Looker": "declined", "Kubernetes": "missing"}
    assert view["coverage"]["required_text"] == "1 of 3"


def test_a_failed_word_file_does_not_stop_the_tailored_resume(client, conn, settings, monkeypatch):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    conn.execute("update applications set status = 'tailoring' where id = %s", (application_id,))
    conn.commit()
    _seed_base_sections(conn)

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(render_pdf, "render_resume_docx", broken)
    draft = TailorDraft(
        summary="",
        bullets=[BulletRewrite(id="r0b0", text="Built Python and Airflow pipelines for 3 teams.")],
        skills_order=["Python"],
        cover_note="Kia ora,\n\nI build data pipelines.\n\nSample Person",
    )

    deps = _ai_deps(conn, settings, draft)
    result = run_graph("resume", {"application_id": application_id}, deps)

    assert result.status == "ok"
    view = client.get(f"/applications/{application_id}/resume").json()
    assert view["status"] == "ready"
    assert view["docx_url"] is None
    assert client.get(view["pdf_url"]).status_code == 200
    assert "The Word file could not be made this time. The PDF is ready." in view["notes"]


def test_tailored_resume_without_parsed_sections_still_gets_a_word_file(client, conn):
    _upload_resume(client)
    application_id = _shortlist_job(conn)

    _approve(client, application_id)

    view = client.get(f"/applications/{application_id}/resume").json()
    assert view["tailored"] is None
    assert view["pdf_url"] is not None
    assert view["docx_url"] == f"/resumes/{view['resume_id']}/docx"
    assert client.get(view["docx_url"]).status_code == 200


def _skeleton_cv(conn) -> None:
    """A saved master CV with skills but no roles, as a blank form or "I have this" leaves it."""
    conn.execute(
        "update resumes set content = content || %s::jsonb where kind = 'base'",
        (Jsonb({"sections": {"skills": ["Python", "SQL"]}}),),
    )
    conn.commit()


def test_a_saved_cv_without_roles_is_not_used_for_the_tailored_resume(client, conn, settings):
    _upload_resume(client)
    _skeleton_cv(conn)
    application_id = _shortlist_job(conn)
    conn.execute("update applications set status = 'tailoring' where id = %s", (application_id,))
    conn.commit()
    sections_llm = ScriptedLLM(_sections())
    tailor_llm = ScriptedLLM(TailorDraft(summary="", bullets=[], cover_note="Unused."))
    deps = ResumeDeps(
        conn=conn,
        sections_chain=ResumeSectionsChain(sections_llm),
        tailor_chain=TailorChain(tailor_llm),
        check_chain=None,
        upload_dir=settings.upload_dir,
        now=datetime(2026, 11, 24, tzinfo=UTC),
    )

    result = run_graph("resume", {"application_id": application_id}, deps)

    assert result.status == "ok"
    assert sections_llm.calls == []  # the saved skeleton is not replaced by a fresh split
    assert tailor_llm.calls == []
    view = client.get(f"/applications/{application_id}/resume").json()
    assert view["tailored"] is None
    assert "Data Engineer" in view["cover_note"]
    pdf = client.get(view["pdf_url"])
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Built data pipelines with Python and Airflow for 3 teams." in text
    assert "Wrote SQL reports for the finance team." in text


def test_review_coverage_matches_the_shortlist_when_the_cv_is_blank(client, conn):
    _upload_resume(client)
    application_id = _shortlist_job(conn)
    conn.execute(
        "update applications set required_skills = %s, requirements_split = true where id = %s",
        (["Airflow", "Looker", "Kubernetes"], application_id),
    )
    conn.commit()
    _approve(client, application_id)

    view = client.get(f"/applications/{application_id}/resume").json()

    shortlist = coverage_service.for_application(conn, PROFILE_ID, application_id)
    assert view["tailored"] is None
    assert view["coverage"]["required_text"] == shortlist.required_text == "1 of 3"
