"""Renders a resume as a clean PDF. The bundled DejaVu font covers macrons and curly quotes."""

from pathlib import Path

from fpdf import FPDF

from app.schemas.tailoring import BaseSections, ContactDetails

FONT_DIR = Path(__file__).parents[1] / "assets" / "fonts"
FONT = "DejaVu"
INK = (15, 23, 42)
MUTED = (91, 100, 120)
ACCENT = (29, 78, 216)


class _ResumePdf(FPDF):
    def __init__(self) -> None:
        super().__init__(format="A4")
        self.set_margins(18, 16, 18)
        self.set_auto_page_break(True, margin=16)
        self.add_font(FONT, "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font(FONT, "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.add_page()

    def text_block(self, text: str, size: float = 9.5, bold: bool = False, color=INK) -> None:
        self.set_font(FONT, "B" if bold else "", size)
        self.set_text_color(*color)
        self.multi_cell(0, size * 0.5, text, new_x="LMARGIN", new_y="NEXT")

    def heading(self, text: str) -> None:
        self.ln(3)
        self.text_block(text.upper(), size=9, bold=True, color=ACCENT)
        y = self.get_y() + 0.5
        self.set_draw_color(*ACCENT)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(2)

    def bullet(self, text: str) -> None:
        self.set_font(FONT, "", 9.5)
        self.set_text_color(*INK)
        self.cell(4, 4.75, "•")
        self.multi_cell(0, 4.75, text, new_x="LMARGIN", new_y="NEXT")


def render_resume_pdf(
    contact: ContactDetails,
    resume: BaseSections | None,
    path: Path,
    fallback_text: str = "",
) -> None:
    """Write the PDF. Without parsed sections, the resume text is laid out as it is."""
    pdf = _ResumePdf()
    if contact.name:
        pdf.text_block(contact.name, size=18, bold=True)
    details = " · ".join(value for value in (contact.email, contact.phone) if value)
    if details:
        pdf.text_block(details, size=9.5, color=MUTED)

    if resume is None:
        pdf.ln(3)
        for line in fallback_text.splitlines():
            if line.strip():
                pdf.text_block(line.strip())
        pdf.output(str(path))
        return

    if resume.summary:
        pdf.heading("Summary")
        pdf.text_block(resume.summary)
    if resume.roles:
        pdf.heading("Experience")
        for role in resume.roles:
            pdf.text_block(f"{role.title} — {role.employer}", size=10.5, bold=True)
            meta = " · ".join(value for value in (role.location, role.dates) if value)
            if meta:
                pdf.text_block(meta, size=9, color=MUTED)
            pdf.ln(1)
            for bullet in role.bullets:
                pdf.bullet(bullet.text)
            pdf.ln(2)
    if resume.skills:
        pdf.heading("Skills")
        pdf.text_block(", ".join(resume.skills))
    if resume.education:
        pdf.heading("Education")
        for line in resume.education:
            pdf.text_block(line)
    pdf.output(str(path))
