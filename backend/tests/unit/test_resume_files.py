import pytest
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pypdf import PdfReader

from app.core.resume_docx import render_resume_docx
from app.core.resume_pdf import render_resume_pdf
from app.schemas.tailoring import BaseSections, Bullet, ContactDetails, RoleSection

HEADINGS = ["Profile", "Key skills", "Work history", "Education and certifications", "Referees"]
DESIGN_FONTS = {
    "classic": {"Georgia"},
    "modern": {"Calibri"},
    "compact": {"Arial"},
    "executive": {"Cambria", "Calibri"},
}
TEMPLATES = ["classic", "modern", "compact", "executive"]


def _contact() -> ContactDetails:
    return ContactDetails(
        name="Tāne Mahuta",
        email="tane.mahuta@example.invalid",
        phone="021 000 0000",
        location="Tāmaki Makaurau",
        whatsapp="+64 21 000 0000",
        work_rights="NZ citizen",
    )


def _sections(bullets: int = 3, text_size: int = 60) -> BaseSections:
    filler = "Delivered measurable outcomes for the finance team – every quarter. " * (
        text_size // 10
    )
    return BaseSections(
        headline="Data Engineer",
        summary="Builds reliable data pipelines. “Quoted” phrasing – kept.",
        roles=[
            RoleSection(
                title="Data Engineer",
                employer="Example Retail Ltd",
                location="Whangārei",
                dates="Mar 2022 – Present",
                bullets=[
                    Bullet(id=f"r0b{i}", text=f"{filler} Item {i}.") for i in range(bullets)
                ],
            )
        ],
        skills=["Python", "SQL", "Power BI"],
        education=["BSc Computer Science, Example University"],
        interests="Surfing",
    )


def _pdf_text(path) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(str(path)).pages)


@pytest.mark.parametrize("template", TEMPLATES)
def test_pdf_text_has_name_first_and_headings_in_order(template, tmp_path):
    path = tmp_path / "cv.pdf"

    render_resume_pdf(_contact(), _sections(), path, template=template)

    text = _pdf_text(path).casefold()
    assert text.lstrip().startswith("tāne mahuta")
    positions = [text.index(heading.casefold()) for heading in HEADINGS]
    assert positions == sorted(positions)
    assert "interests" in text
    assert "tāmaki makaurau" in text
    assert "–" in _pdf_text(path)


@pytest.mark.parametrize("template", TEMPLATES)
def test_docx_has_no_tables_headers_or_images_and_uses_the_design_font(template, tmp_path):
    path = tmp_path / "cv.docx"

    render_resume_docx(_contact(), _sections(), path, template=template)

    doc = Document(str(path))
    assert doc.tables == []
    assert len(doc.inline_shapes) == 0
    section = doc.sections[0]
    assert not section.header.paragraphs or all(not p.text for p in section.header.paragraphs)
    assert all(not p.text for p in section.footer.paragraphs)
    runs = [run for paragraph in doc.paragraphs for run in paragraph.runs]
    assert runs
    assert all(run.font.name in DESIGN_FONTS[template] for run in runs)
    texts = [paragraph.text for paragraph in doc.paragraphs]
    headings = [text for text in texts if text.casefold() in {h.casefold() for h in HEADINGS}]
    assert headings == HEADINGS


def test_files_stay_under_2_5_mb(tmp_path):
    big = _sections(bullets=20, text_size=2000)
    pdf_path = tmp_path / "big.pdf"
    docx_path = tmp_path / "big.docx"

    render_resume_pdf(_contact(), big, pdf_path, template="compact")
    render_resume_docx(_contact(), big, docx_path, template="executive")

    limit = 2_621_440
    assert pdf_path.stat().st_size < limit
    assert docx_path.stat().st_size < limit


def test_pdf_fallback_text_still_renders(tmp_path):
    path = tmp_path / "fallback.pdf"

    render_resume_pdf(_contact(), None, path, fallback_text="Raw resume line\n\nSecond line")

    text = _pdf_text(path)
    assert "Raw resume line" in text
    assert "Second line" in text


def _cv_with_bullets(count: int) -> BaseSections:
    return BaseSections(
        headline="Data Engineer",
        summary="Short profile.",
        roles=[
            RoleSection(
                title="Data Engineer",
                employer="Example Retail Ltd",
                location="",
                dates="2022",
                bullets=[
                    Bullet(id=f"b{i}", text=f"Item {i} delivered outcomes.") for i in range(count)
                ],
            )
        ],
        skills=["Python"],
        education=["BSc Computer Science, Example University"],
    )


@pytest.mark.parametrize("template", TEMPLATES)
def test_docx_bullets_and_body_are_left_aligned(template, tmp_path):
    path = tmp_path / "align.docx"
    render_resume_docx(_contact(), _sections(), path, template=template)

    paragraphs = Document(str(path)).paragraphs
    body_texts = {
        "Builds reliable data pipelines. “Quoted” phrasing – kept.",
        "Python, SQL, Power BI",
        "BSc Computer Science, Example University",
        "Profile",
    }
    checked = [p for p in paragraphs if p.text in body_texts or p.text.startswith("Python")]
    bullets = [p for p in paragraphs if p.style.name == "List Bullet"]
    assert len(checked) == len(body_texts)
    assert len(bullets) == 3
    for paragraph in checked + bullets:
        assert paragraph.alignment in (None, WD_ALIGN_PARAGRAPH.LEFT), paragraph.text


def test_classic_docx_centres_only_the_name(tmp_path):
    path = tmp_path / "classic.docx"
    render_resume_docx(_contact(), _sections(), path, template="classic")

    name = next(p for p in Document(str(path)).paragraphs if p.text == "Tāne Mahuta")
    assert name.alignment == WD_ALIGN_PARAGRAPH.CENTER


@pytest.mark.parametrize("template", TEMPLATES)
def test_pdf_heading_never_ends_a_page(template, tmp_path):
    """Sweeps the bullet count so a heading lands at every position near a page break."""
    heading_set = {h.casefold() for h in HEADINGS}
    for count in range(1, 90):
        path = tmp_path / f"{template}-{count}.pdf"
        render_resume_pdf(_contact(), _cv_with_bullets(count), path, template=template)
        pages = PdfReader(str(path)).pages
        for number, page in enumerate(pages[:-1], start=1):
            lines = [line.strip() for line in page.extract_text().splitlines() if line.strip()]
            assert lines[-1].casefold() not in heading_set, (template, count, number)


def test_docx_fallback_text_still_renders(tmp_path):
    path = tmp_path / "fallback.docx"

    render_resume_docx(_contact(), None, path, fallback_text="Raw resume line\n\nSecond line")

    document = Document(path)
    texts = [p.text for p in document.paragraphs]
    assert "Tāne Mahuta" in texts
    assert "Raw resume line" in texts
    assert "Second line" in texts
    assert document.tables == []
