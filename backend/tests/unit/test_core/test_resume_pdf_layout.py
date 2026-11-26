"""Role titles and dates in the PDF: a long title wraps inside the space left of the dates."""

import io

from pypdf import PdfReader

from app.core.resume_pdf import render_resume_pdf
from app.schemas.tailoring import BaseSections, Bullet, ContactDetails, RoleSection

LONG_TITLE = (
    "Senior Data Engineer and Analytics Platform Lead for Retail Operations, Customer "
    "Insights and Supply Chain Reporting"
)
DATES = "Mar 2022 – Present"


def _pdf_lines(title: str, tmp_path) -> list[str]:
    sections = BaseSections(
        headline="Data Engineer",
        roles=[
            RoleSection(
                title=title,
                employer="Example Retail Ltd",
                dates=DATES,
                bullets=[Bullet(id="r0b0", text="Built pipelines with Python.")],
            )
        ],
        skills=["Python"],
    )
    path = tmp_path / "cv.pdf"
    render_resume_pdf(ContactDetails(name="Sample Person"), sections, path)
    reader = PdfReader(io.BytesIO(path.read_bytes()))
    return "\n".join(page.extract_text(extraction_mode="layout") for page in reader.pages).splitlines()


def test_a_long_title_wraps_and_does_not_run_into_the_dates(tmp_path):
    assert len(LONG_TITLE) >= 110

    lines = _pdf_lines(LONG_TITLE, tmp_path)

    date_line = next(line for line in lines if DATES in line)
    assert "Senior" in date_line  # the title starts on the same line as the dates
    last_word = LONG_TITLE.split()[-1]
    assert last_word not in date_line  # the rest of the title wraps below
    assert any(last_word in line for line in lines[lines.index(date_line) + 1:])


def test_a_normal_title_stays_on_one_line_with_its_dates(tmp_path):
    lines = _pdf_lines("Data Engineer", tmp_path)

    date_line = next(line for line in lines if DATES in line)
    assert "Data Engineer" in date_line
