from pathlib import Path
from uuid import uuid4

from app.core.resume_docx import render_resume_docx
from app.core.resume_pdf import render_resume_pdf
from app.schemas.master_cv import MasterCV, MasterCVView
from app.schemas.tailoring import BaseSections, Bullet, ContactDetails, RoleSection
from app.services import ats_check, master_cv_service

PROFILE_TEXT = (
    "Data engineer with five years of experience building reliable pipelines for retail "
    "and finance teams. Works closely with analysts to turn messy source data into clear, "
    "tested models. Writes readable SQL and Python, documents decisions, and keeps dashboards "
    "accurate for managers who rely on them each week. Enjoys mentoring junior colleagues "
    "and improving how the team reviews code, plans work, and monitors production jobs "
    "every single day across the whole business."
)


def _contact(**overrides) -> ContactDetails:
    values = {
        "name": "Sample Person",
        "email": "sample.person@example.invalid",
        "phone": "021 000 0000",
        "location": "Auckland",
        "work_rights": "NZ citizen",
    }
    values.update(overrides)
    return ContactDetails(**values)


def _role(title="Data Engineer", dates="Mar 2022 – Present", bullets=2) -> RoleSection:
    return RoleSection(
        title=title,
        employer="Example Retail Ltd",
        location="Whangārei",
        dates=dates,
        bullets=[Bullet(id=f"b{i}", text="Built pipelines and tests.") for i in range(bullets)],
    )


def _sections(**overrides) -> BaseSections:
    values = {
        "headline": "Data Engineer",
        "summary": PROFILE_TEXT,
        "roles": [_role()],
        "skills": ["Python", "SQL", "Power BI"],
        "education": ["BSc Computer Science, Example University"],
        "interests": "Surfing",
        "referees": "Available on request.",
    }
    values.update(overrides)
    return BaseSections(**values)


def _check(tmp_path: Path, contact: ContactDetails, sections: BaseSections, template="classic"):
    pdf = tmp_path / "cv.pdf"
    docx = tmp_path / "cv.docx"
    render_resume_pdf(contact, sections, pdf, template=template)
    render_resume_docx(contact, sections, docx, template=template)
    cv = MasterCV(contact=contact, sections=sections, template=template)
    return ats_check.check(cv, pdf, docx)


def _item(report, label_start: str):
    matches = [item for item in report.items if item.label.startswith(label_start)]
    assert len(matches) == 1, label_start
    return matches[0]


def test_a_clean_cv_passes_every_item(tmp_path):
    report = _check(tmp_path, _contact(), _sections())

    assert [item.ok for item in report.items] == [True] * 9
    assert report.pages == 1
    assert report.pdf_bytes > 0 and report.docx_bytes > 0
    assert "WORK HISTORY" in report.text  # Classic prints headings in capitals
    assert _item(report, "Profile of 50").detail == f"{len(PROFILE_TEXT.split())} words"


def test_year_only_and_missing_dates_name_the_role(tmp_path):
    sections = _sections(
        roles=[
            _role(title="Data Engineer", dates="2022 – Present"),
            _role(title="Analyst", dates="", bullets=0),
            _role(title="Intern", dates="Jan 2019 – Dec 2019"),
        ]
    )

    report = _check(tmp_path, _contact(), sections)

    dates = _item(report, "Dates as month and year")
    assert dates.ok is False
    assert "Data Engineer" in dates.detail
    assert "Analyst" in dates.detail
    assert "Intern" not in dates.detail


def test_dates_are_ok_when_there_are_no_roles(tmp_path):
    report = _check(tmp_path, _contact(), _sections(roles=[]))

    dates = _item(report, "Dates as month and year")
    assert dates.ok is True
    assert dates.detail == "No roles yet."


def test_personal_details_are_flagged(tmp_path):
    sections = _sections(
        summary=PROFILE_TEXT + " Nationality: Sample. Marital status: single.",
    )

    report = _check(tmp_path, _contact(), sections)

    personal = _item(report, "No photo")
    assert personal.ok is False


def test_a_three_page_cv_is_flagged(tmp_path):
    roles = [_role(title=f"Role {n}", bullets=20) for n in range(6)]

    report = _check(tmp_path, _contact(), _sections(roles=roles))

    assert report.pages == 3
    assert _item(report, "2 pages").ok is False


def test_profile_word_count_is_reported(tmp_path):
    short = _check(tmp_path, _contact(), _sections(summary="Short profile."))
    empty = _check(tmp_path, _contact(), _sections(summary=""))

    short_item = _item(short, "Profile of 50")
    assert short_item.ok is False
    assert short_item.detail == "2 words"
    empty_item = _item(empty, "Profile of 50")
    assert empty_item.ok is False
    assert empty_item.detail == "0 words"


def test_missing_work_rights_is_flagged(tmp_path):
    report = _check(tmp_path, _contact(work_rights=None), _sections())

    assert _item(report, "Work rights stated").ok is False


def test_name_on_the_first_line_needs_an_email_or_phone(tmp_path):
    report = _check(tmp_path, _contact(email=None, phone=None), _sections())

    assert _item(report, "Name and contact").ok is False


def test_interests_heading_is_only_required_when_filled_in(tmp_path):
    report = _check(tmp_path, _contact(), _sections(interests=""))

    assert "Interests" not in report.text
    assert _item(report, "Standard section names").ok is True


def test_with_ats_writes_both_previews_and_attaches_the_report(tmp_path):
    view = MasterCVView(
        contact=_contact(), sections=_sections(), template="modern", source="resume"
    )
    profile_id = uuid4()

    result = master_cv_service.with_ats(view, tmp_path, profile_id)

    previews = tmp_path / "previews"
    assert (previews / f"{profile_id}.pdf").read_bytes().startswith(b"%PDF")
    assert (previews / f"{profile_id}.docx").read_bytes().startswith(b"PK")
    assert result.ats is not None
    assert result.ats.pages == 1
    assert result.ats.pdf_bytes == (previews / f"{profile_id}.pdf").stat().st_size
    assert view.ats is None


def test_field_words_in_ordinary_text_do_not_fail_the_personal_details_item(tmp_path):
    sections = _sections(
        interests="Gender equality programme volunteer",
        roles=[
            RoleSection(
                title="Analyst",
                employer="Nationality Insurance Ltd",
                dates="Jan 2020 – Dec 2021",
                bullets=[],
            )
        ],
    )

    report = _check(tmp_path, _contact(), sections)

    assert _item(report, "No photo").ok is True


def test_personal_detail_field_labels_are_flagged_and_named(tmp_path):
    sections = _sections(interests="Nationality: Indian\nDOB - 01/02/1990")

    report = _check(tmp_path, _contact(), sections)

    personal = _item(report, "No photo")
    assert personal.ok is False
    assert "Nationality" in personal.detail
    assert "DOB" in personal.detail


def test_heading_lines_ignore_extra_whitespace_and_case(tmp_path):
    report = _check(tmp_path, _contact(), _sections())

    assert _item(report, "Standard section names").ok is True


def test_a_failing_render_is_reported_as_one_item_and_leaves_no_temporary_files(
    tmp_path, monkeypatch
):
    def broken(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(master_cv_service, "render_resume_pdf", broken)
    view = MasterCVView(contact=_contact(), sections=_sections(), source="resume")

    result = master_cv_service.with_ats(view, tmp_path, uuid4())

    assert result.ats is not None
    assert len(result.ats.items) == 1
    item = result.ats.items[0]
    assert item.label == "ATS check could not run"
    assert item.ok is False
    assert item.detail == "Try again after saving. (ValueError)"
    assert list((tmp_path / "previews").glob("*")) == []


def test_previews_are_rendered_to_unique_names_then_moved_into_place(tmp_path, monkeypatch):
    rendered = []
    real_render = master_cv_service.render_resume_pdf

    def spy(contact, sections, path, **kwargs):
        rendered.append(Path(path))
        real_render(contact, sections, path, **kwargs)

    monkeypatch.setattr(master_cv_service, "render_resume_pdf", spy)
    profile_id = uuid4()
    view = MasterCVView(contact=_contact(), sections=_sections(), source="resume")

    result = master_cv_service.with_ats(view, tmp_path, profile_id)

    assert rendered and rendered[0].name != f"{profile_id}.pdf"
    assert sorted(p.name for p in (tmp_path / "previews").iterdir()) == [
        f"{profile_id}.docx",
        f"{profile_id}.pdf",
    ]
    assert result.ats is not None and result.ats.items[0].ok is True
