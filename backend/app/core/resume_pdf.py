"""Renders a CV as a PDF in one of four looks. The bundled DejaVu font covers macrons and quotes."""

from pathlib import Path

from fpdf import FPDF

from app.core.resume_layout import LOOKS, Block, Look, contact_line, layout_blocks
from app.schemas.master_cv import TemplateId
from app.schemas.tailoring import BaseSections, ContactDetails

FONT_DIR = Path(__file__).parents[1] / "assets" / "fonts"
FONT = "DejaVu"
INK = (15, 23, 42)
MUTED = (91, 100, 120)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


class _CvPdf(FPDF):
    """Default FPDF header() and footer() are empty, so nothing is printed on the page edges."""

    def __init__(self) -> None:
        super().__init__(format="A4")
        self.set_margins(18, 16, 18)
        self.set_auto_page_break(True, margin=16)
        self.add_font(FONT, "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font(FONT, "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.add_page()

    @property
    def text_width(self) -> float:
        return self.w - self.l_margin - self.r_margin


def _font(pdf: _CvPdf, size: float, bold: bool = False, color=INK) -> None:
    pdf.set_font(FONT, "B" if bold else "", size)
    pdf.set_text_color(*color)


def _draw_block(pdf: _CvPdf, look: Look, block: Block, align: str) -> None:
    body = look.body_size
    if block.kind == "name":
        _font(pdf, look.name_size, bold=True)
        pdf.multi_cell(
            0, look.name_size * 0.5, block.text, align=align, new_x="LMARGIN", new_y="NEXT"
        )
    elif block.kind in ("headline", "contact", "rights"):
        size = body + 1 if block.kind == "headline" else body - 0.5
        _font(pdf, size, color=INK if block.kind == "headline" else MUTED)
        pdf.multi_cell(0, size * 0.5, block.text, align=align, new_x="LMARGIN", new_y="NEXT")
    elif block.kind == "heading":
        pdf.ln(3)
        text = block.text.upper() if look.heading_upper else block.text
        _font(pdf, look.heading_size, bold=True, color=_rgb(look.accent))
        pdf.multi_cell(0, look.heading_size * 0.5, text, new_x="LMARGIN", new_y="NEXT")
        if look.heading_rule:
            y = pdf.get_y() + 0.5
            pdf.set_draw_color(*_rgb(look.accent))
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.ln(2)
    elif block.kind == "role":
        if block.right:
            _role_with_dates(pdf, look, block)
        else:
            _font(pdf, body + 1, bold=True)
            pdf.multi_cell(0, 5, block.text, new_x="LMARGIN", new_y="NEXT")
        if block.sub:
            _font(pdf, body - 0.5, color=MUTED)
            pdf.multi_cell(0, 4.5, block.sub, new_x="LMARGIN", new_y="NEXT")
    elif block.kind == "bullet":
        _font(pdf, body)
        pdf.cell(4, body * 0.5, "•")
        pdf.multi_cell(0, body * 0.5, block.text, new_x="LMARGIN", new_y="NEXT")
    else:  # text and entry: always left-aligned
        _font(pdf, body)
        pdf.multi_cell(0, body * 0.5, block.text, align="L", new_x="LMARGIN", new_y="NEXT")


def _role_with_dates(pdf: _CvPdf, look: Look, block: Block) -> None:
    """The dates sit on the first line, right-aligned. The title wraps inside the space left of
    them, so a long title never runs into the dates."""
    body = look.body_size
    _font(pdf, body - 0.5, color=MUTED)
    right_width = pdf.get_string_width(block.right) + 2
    left_width = pdf.text_width - right_width
    top = pdf.get_y()
    pdf.set_xy(pdf.l_margin + left_width, top)
    pdf.cell(right_width, 5, block.right, align="R")
    _font(pdf, body + 1, bold=True)
    pdf.set_xy(pdf.l_margin, top)
    pdf.multi_cell(left_width, 5, block.text, new_x="LMARGIN", new_y="NEXT")


def _first_line_mm(look: Look, block: Block) -> float:
    """Height of the first line a block prints, in mm. Used to keep headings with their content."""
    if block.kind == "name":
        return look.name_size * 0.5
    if block.kind == "heading":
        return 3 + look.heading_size * 0.5 + 3  # space above, the line, space below
    if block.kind == "role":
        return 5
    return look.body_size * 0.5


def _keep_with_next(pdf: _CvPdf, look: Look, block: Block, following: Block | None) -> None:
    """Start a new page when a heading or role line would be left alone at the foot of a page."""
    needed = _first_line_mm(look, block)
    if following is not None:
        needed += _first_line_mm(look, following)
    if pdf.get_y() + needed > pdf.h - pdf.b_margin:
        pdf.add_page()


def _draw(pdf: _CvPdf, look: Look, blocks: list[Block]) -> None:
    align = "C" if look.name_center else "L"
    seen_heading = False
    for index, block in enumerate(blocks):
        if block.kind in ("heading", "role"):
            following = blocks[index + 1] if index + 1 < len(blocks) else None
            _keep_with_next(pdf, look, block, following)
        if block.kind == "heading" and not seen_heading:
            seen_heading = True
            if look.contact_rule:
                pdf.ln(1)
                pdf.set_draw_color(*_rgb(look.accent))
                y = pdf.get_y()
                pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
                pdf.ln(1)
        _draw_block(pdf, look, block, align)


def render_resume_pdf(
    contact: ContactDetails,
    resume: BaseSections | None,
    path: Path,
    fallback_text: str = "",
    template: TemplateId = "classic",
) -> None:
    """Write the PDF. Without parsed sections, the resume text is laid out as it is."""
    look = LOOKS[template]
    pdf = _CvPdf()
    if resume is None:
        blocks = [Block("name", contact.name or ""), Block("contact", contact_line(contact))]
        blocks = [block for block in blocks if block.text]
        lines = [line.strip() for line in fallback_text.splitlines()]
        blocks += [Block("text", line) for line in lines if line]
        align = "C" if look.name_center else "L"
        for block in blocks:
            _draw_block(pdf, look, block, align)
    else:
        _draw(pdf, look, layout_blocks(contact, resume, look.skill_separator))
    pdf.output(str(path))
