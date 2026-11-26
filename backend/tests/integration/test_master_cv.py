import pytest
from fastapi.testclient import TestClient

from app.chains.resume_sections_chain import ResumeSectionsChain, SectionsExtraction
from app.core.config import Settings
from app.core.deps import get_sections_chain, get_settings
from app.main import create_app
from app.repositories import profiles_repo, resumes_repo
from app.schemas.master_cv import MasterCV
from app.schemas.resume import ResumeProfile, SkillEntry
from app.schemas.tailoring import BaseSections, Bullet, ContactDetails, RoleSection
from app.services import master_cv_service
from tests.fakes import ScriptedLLM

pytestmark = pytest.mark.postgres

EMAIL = "sample.person@example.invalid"
PHONE = "+64 21 000 0000"
RESUME_TEXT = f"""Sample Person
{EMAIL} · {PHONE} · Auckland
Data Engineer with Python and SQL experience.

Experience
Data Engineer, Example Retail Ltd, Tāmaki Makaurau
Mar 2022 – Present
Built data pipelines with Python and Airflow for 3 teams.
Wrote SQL reports for the finance team.

Skills
Python, SQL, Airflow, Power BI

Education
BSc Computer Science, Example University
"""
NEEDS_RESUME = "Upload your resume first, then build on it here."


def _sections() -> BaseSections:
    return BaseSections(
        summary="",
        roles=[
            RoleSection(
                title="Data Engineer",
                employer="Example Retail Ltd",
                location="Tāmaki Makaurau",
                dates="Mar 2022 – Present",
                bullets=[
                    Bullet(
                        id="r0b0", text="Built data pipelines with Python and Airflow for 3 teams."
                    ),
                    Bullet(id="r0b1", text="Wrote SQL reports for the finance team."),
                ],
            )
        ],
        skills=["Python", "SQL", "Airflow", "Power BI"],
        education=["BSc Computer Science, Example University"],
    )


def _extraction() -> SectionsExtraction:
    return SectionsExtraction(
        roles=[
            {
                "title": "Data Engineer",
                "employer": "Example Retail Ltd",
                "location": "Tāmaki Makaurau",
                "dates": "Mar 2022 – Present",
                "bullets": [
                    "Built data pipelines with Python and Airflow for 3 teams.",
                    "Wrote SQL reports for the finance team.",
                ],
            }
        ],
        skills=["Python", "SQL", "Airflow", "Power BI"],
        education=["BSc Computer Science, Example University"],
    )


def _add_resume(conn, content, skills=("Python", "SQL", "Power BI"), titles=("Data Engineer",)):
    profile_id = profiles_repo.first_profile_id(conn)
    profiles_repo.add_base_resume(
        conn,
        profile_id,
        content,
        "resume.pdf",
        ResumeProfile(titles=list(titles), skills=[SkillEntry(name=s) for s in skills]),
    )
    conn.commit()
    return profile_id


def _terms(conn, profile_id):
    base = resumes_repo.latest_base(conn, profile_id)
    row = conn.execute(
        "select titles, skills, tools from resume_profiles where resume_id = %s", (base["id"],)
    ).fetchone()
    return row["titles"], [skill["name"] for skill in row["skills"]]


@pytest.fixture
def client(database_url, tmp_path):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=database_url, upload_dir=tmp_path, _env_file=None
    )
    app.dependency_overrides[get_sections_chain] = lambda: None
    with TestClient(app) as test_client:
        yield test_client


def test_master_cv_reads_cached_sections_and_contact(conn):
    profile_id = _add_resume(
        conn,
        {
            "text": RESUME_TEXT,
            "contact": {"name": "Sample Person", "email": EMAIL, "location": "Auckland"},
            "sections": _sections().model_dump(),
        },
    )

    view = master_cv_service.load(conn, profile_id, None)

    assert view.source == "resume"
    assert view.contact.location == "Auckland"
    assert view.sections.roles[0].title == "Data Engineer"


def test_old_cached_sections_load_with_new_defaults(conn):
    profile_id = _add_resume(
        conn,
        {
            "text": RESUME_TEXT,
            "sections": {"summary": "", "roles": [], "skills": ["Python"], "education": []},
        },
    )

    view = master_cv_service.load(conn, profile_id, None)

    assert view.sections.referees == "Available on request."
    assert view.sections.headline == ""
    assert view.sections.skills == ["Python"]


def test_master_cv_without_sections_or_ai_shows_the_profile_skills_and_saves_nothing(conn):
    profile_id = _add_resume(
        conn, {"text": RESUME_TEXT, "contact": {"name": "Sample Person", "email": EMAIL}}
    )

    view = master_cv_service.load(conn, profile_id, None)

    assert view.source == "empty"
    assert view.sections == BaseSections(skills=["Python", "SQL", "Power BI"])
    assert view.contact.email == EMAIL
    # Display only: loading never writes the sections.
    saved = resumes_repo.latest_base(conn, profile_id)
    assert "sections" not in saved["content"]


def test_contact_falls_back_to_the_resume_text_when_none_is_stored(conn):
    profile_id = _add_resume(conn, {"text": RESUME_TEXT})

    view = master_cv_service.load(conn, profile_id, None)

    assert view.contact.name == "Sample Person"
    assert view.contact.email == EMAIL


def test_sections_are_read_by_ai_once_and_contact_is_not_sent(conn):
    profile_id = _add_resume(conn, {"text": RESUME_TEXT})
    llm = ScriptedLLM(_extraction())
    chain = ResumeSectionsChain(llm)

    first = master_cv_service.load(conn, profile_id, chain)
    second = master_cv_service.load(conn, profile_id, chain)

    assert first.source == "ai"
    assert second.source == "resume"
    assert second.sections.roles[0].title == "Data Engineer"
    assert len(llm.calls) == 1
    assert EMAIL not in llm.calls[0]["user"]
    assert PHONE not in llm.calls[0]["user"]


def test_saving_keeps_titles_dates_and_bullets_exactly(conn):
    profile_id = _add_resume(conn, {"text": RESUME_TEXT})
    cv = MasterCV(
        contact=ContactDetails(name="Sample Person", email=EMAIL, location="Tāmaki Makaurau"),
        sections=_sections(),
        template="modern",
    )

    saved = master_cv_service.save(conn, profile_id, cv)
    loaded = master_cv_service.load(conn, profile_id, None)

    assert saved.template == "modern"
    assert loaded.template == "modern"
    assert loaded.source == "resume"
    role = loaded.sections.roles[0]
    assert role.dates == "Mar 2022 – Present"
    assert role.location == "Tāmaki Makaurau"
    assert [b.text for b in role.bullets] == [
        "Built data pipelines with Python and Airflow for 3 teams.",
        "Wrote SQL reports for the finance team.",
    ]
    assert loaded.contact.location == "Tāmaki Makaurau"


def test_saving_adds_new_skills_and_headline_to_the_resume_profile(conn):
    profile_id = _add_resume(conn, {"text": RESUME_TEXT})
    sections = _sections().model_copy(
        update={"headline": "Senior Data Engineer", "skills": ["Python", "dbt"]}
    )

    master_cv_service.save(
        conn, profile_id, MasterCV(contact=ContactDetails(name="Sample Person"), sections=sections)
    )

    titles, skills = _terms(conn, profile_id)
    assert "Senior Data Engineer" in titles
    assert "Data Engineer" in titles
    assert "dbt" in skills
    assert {"Python", "SQL", "Power BI"} <= set(skills)


def test_add_skill_ignores_case_and_remove_skill_reverses_it(conn):
    cached = BaseSections(skills=["Power BI"]).model_dump()
    profile_id = _add_resume(conn, {"text": RESUME_TEXT, "sections": cached}, skills=("Power BI",))

    assert master_cv_service.add_skill(conn, profile_id, "power bi") is False
    assert master_cv_service.add_skill(conn, profile_id, "dbt") is True
    assert "dbt" in _terms(conn, profile_id)[1]

    assert master_cv_service.remove_skill(conn, profile_id, "DBT") is True
    assert "dbt" not in _terms(conn, profile_id)[1]
    assert master_cv_service.remove_skill(conn, profile_id, "DBT") is False
    assert "Power BI" in _terms(conn, profile_id)[1]


def test_master_cv_needs_a_resume(client):
    body = {"contact": {"name": "Sample Person"}, "sections": {}}

    get = client.get("/master-cv")
    assert get.status_code == 400
    assert get.json()["detail"] == NEEDS_RESUME
    put = client.put("/master-cv", json=body)
    assert put.status_code == 400
    assert put.json()["detail"] == NEEDS_RESUME


def test_ai_sections_are_kept_after_the_request_ends(client, conn):
    _add_resume(conn, {"text": RESUME_TEXT})
    llm = ScriptedLLM(_extraction())
    client.app.dependency_overrides[get_sections_chain] = lambda: ResumeSectionsChain(llm)

    assert client.get("/master-cv").json()["source"] == "ai"
    assert client.get("/master-cv").json()["source"] == "resume"
    assert len(llm.calls) == 1


def test_saving_the_profile_contact_keeps_the_master_cv_only_fields(client, conn):
    _add_resume(conn, {"text": RESUME_TEXT})
    client.put(
        "/master-cv",
        json={"contact": {"name": "Sample Person", "location": "Auckland"}, "sections": {}},
    ).raise_for_status()

    profile = client.get("/profile").json()
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

    master = client.get("/master-cv").json()
    assert master["contact"]["name"] == "Sam Person"
    assert master["contact"]["location"] == "Auckland"


def test_name_linkedin_and_whatsapp_are_not_sent_to_ai(conn):
    text = "Alex Morgan\nlinkedin.com/in/alex-morgan-nz · WhatsApp 021 555 0101\n" + RESUME_TEXT
    contact = {
        "name": "Alex Morgan",
        "email": EMAIL,
        "linkedin": "linkedin.com/in/alex-morgan-nz",
        "whatsapp": "021 555 0101",
    }
    profile_id = _add_resume(conn, {"text": text, "contact": contact})
    llm = ScriptedLLM(_extraction())

    master_cv_service.load(conn, profile_id, ResumeSectionsChain(llm))

    user = llm.calls[0]["user"]
    assert "alex morgan" not in user.casefold()
    assert "alex-morgan-nz" not in user.casefold()
    assert "0215550101" not in "".join(c for c in user if c.isdigit())
    assert EMAIL not in user
    assert "Data Engineer" in user


def test_a_cv_cached_with_more_than_the_limits_still_loads(client, conn):
    bullets = [Bullet(id=f"r0b{i}", text=f"Did thing {i}.") for i in range(25)]
    sections = BaseSections(
        roles=[RoleSection(title="Data Engineer", employer="Example Ltd", bullets=bullets)]
    )
    _add_resume(conn, {"text": RESUME_TEXT, "sections": sections.model_dump()})

    response = client.get("/master-cv")

    assert response.status_code == 200
    assert len(response.json()["sections"]["roles"][0]["bullets"]) == 25


def test_a_put_over_the_limits_is_422_naming_the_field(client, conn):
    _add_resume(conn, {"text": RESUME_TEXT})
    role = {"title": "Data Engineer", "employer": "Example Ltd", "bullets": []}
    body = {"contact": {"name": "Sample Person"}, "sections": {"roles": [role] * 21}}

    response = client.put("/master-cv", json=body)

    assert response.status_code == 422
    assert "sections.roles" in response.text


def test_a_skill_added_without_ai_shows_on_the_master_cv(client, conn):
    profile_id = _add_resume(conn, {"text": RESUME_TEXT})

    assert master_cv_service.add_skill(conn, profile_id, "dbt") is True
    conn.commit()

    body = client.get("/master-cv").json()
    assert body["sections"]["skills"] == ["Python", "SQL", "Power BI", "dbt"]


def test_adding_a_skill_reads_the_sections_with_ai_first(conn):
    profile_id = _add_resume(conn, {"text": RESUME_TEXT})
    llm = ScriptedLLM(_extraction())

    master_cv_service.add_skill(conn, profile_id, "dbt", ResumeSectionsChain(llm))
    view = master_cv_service.load(conn, profile_id, None)

    assert "dbt" in view.sections.skills
    assert "Airflow" in view.sections.skills
    assert len(llm.calls) == 1


def test_download_route_names_the_file_from_the_contact(client, conn, tmp_path):
    _add_resume(
        conn,
        {
            "text": RESUME_TEXT,
            "contact": {"name": "Tāne Mahuta", "email": EMAIL, "location": "Auckland"},
            "sections": _sections().model_dump(),
            "template": "modern",
        },
    )

    docx = client.get("/master-cv/file", params={"format": "docx"})
    pdf = client.get("/master-cv/file", params={"format": "pdf"})

    assert docx.status_code == 200
    assert docx.headers["content-disposition"] == 'attachment; filename="Tane-Mahuta-CV.docx"'
    assert pdf.headers["content-disposition"] == 'attachment; filename="Tane-Mahuta-CV.pdf"'
    assert pdf.content.startswith(b"%PDF")
    assert docx.content.startswith(b"PK")
    assert list(tmp_path.glob("master-cv-*")) == []


def test_download_route_rejects_unknown_formats(client):
    response = client.get("/master-cv/file", params={"format": "txt"})

    assert response.status_code == 422


def test_download_route_without_a_base_resume_is_a_bad_request(client):
    response = client.get("/master-cv/file", params={"format": "pdf"})

    assert response.status_code == 400


def test_get_and_put_attach_the_ats_report_and_write_previews(client, conn, tmp_path):
    _add_resume(
        conn,
        {
            "text": RESUME_TEXT,
            "contact": {"name": "Sample Person", "email": EMAIL},
            "sections": _sections().model_dump(),
        },
    )

    get = client.get("/master-cv").json()
    put = client.put(
        "/master-cv",
        json={
            "contact": {"name": "Sample Person", "email": EMAIL, "work_rights": "NZ citizen"},
            "sections": _sections().model_dump(),
            "template": "compact",
        },
    ).json()

    assert get["ats"]["pages"] == 1
    assert len(get["ats"]["items"]) == 9
    assert put["ats"]["items"][0]["label"] == "One column, no tables, text boxes or images"
    assert len(list((tmp_path / "previews").glob("*.pdf"))) == 1
    assert len(list((tmp_path / "previews").glob("*.docx"))) == 1


def test_get_still_loads_when_the_ats_check_fails(client, conn, monkeypatch):
    _add_resume(conn, {"text": RESUME_TEXT, "sections": _sections().model_dump()})

    def broken(*args, **kwargs):
        raise RuntimeError("renderer down")

    monkeypatch.setattr(master_cv_service, "render_resume_pdf", broken)

    response = client.get("/master-cv")

    assert response.status_code == 200
    assert [item["label"] for item in response.json()["ats"]["items"]] == [
        "ATS check could not run"
    ]


def test_a_put_is_saved_even_when_the_ats_check_fails(client, conn, monkeypatch):
    _add_resume(conn, {"text": RESUME_TEXT, "sections": _sections().model_dump()})

    def broken(*args, **kwargs):
        raise RuntimeError("renderer down")

    monkeypatch.setattr(master_cv_service, "render_resume_pdf", broken)
    put = client.put(
        "/master-cv",
        json={"contact": {"name": "Renamed Person"}, "sections": _sections().model_dump()},
    )
    monkeypatch.undo()

    assert put.status_code == 200
    assert put.json()["ats"]["items"][0]["ok"] is False
    assert client.get("/master-cv").json()["contact"]["name"] == "Renamed Person"
