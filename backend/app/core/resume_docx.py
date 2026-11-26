"""Renders a CV as a Word document in one of four looks. Plain paragraphs only: no tables,
text boxes, images, or header and footer content."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from docx.text.paragraph import Paragraph

from app.core.resume_layout import LOOKS, Block, Look, contact_line, layout_blocks
from app.schemas.master_cv import TemplateId
from app.schemas.tailoring import BaseSections, ContactDetails

_ALIGN = {"C": WD_ALIGN_PARAGRAPH.CENTER, "L": WD_ALIGN_PARAGRAPH.LEFT}
INK = "0F172A"
MUTED = "5B6478"
PAGE_WIDTH = Mm(210)
PAGE_HEIGHT = Mm(297)
MARGIN = Mm(18)
MARGIN_TOP = Mm(16)

# Child elements of w:pPr that must follow w:pBdr, in schema order.
_AFTER_PBDR = (
    "w:shd", "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap", "w:overflowPunct",
    "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi", "w:adjustRightInd",
    "w:snapToGrid", "w:spacing", "w:ind", "w:contextualSpacing", "w:mirrorIndents",
    "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment", "w:textboxTightWrap",
    "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange",
)


def _bottom_rule(paragraph: Paragraph, hex_color: str) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    settings = (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", hex_color))
    for name, value in settings:
        bottom.set(qn(name), value)
    borders.append(bottom)
    p_pr.insert_element_before(borders, *_AFTER_PBDR)


def _run(paragraph: Paragraph, text: str, font: str, size: float, **style) -> None:
    run = paragraph.add_run(text)
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = style.get("bold", False)
    run.font.all_caps = style.get("caps", False)
    run.font.color.rgb = RGBColor.from_string(style.get("color", INK))


def _paragraph(doc: Document, align: str, before: float = 0, after: float = 2) -> Paragraph:
    paragraph = doc.add_paragraph()
    paragraph.alignment = _ALIGN[align]
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)
    return paragraph


def _write(doc: Document, look: Look, width, block: Block, align: str) -> None:
    """Only the name and the lines above the headings take the look's alignment.

    Headings, body text, entries, role lines and bullets are always left-aligned.
    """
    body = look.body_size
    font = look.word_body_font
    heading_font = look.word_heading_font
    if block.kind == "name":
        p = _paragraph(doc, align, after=2)
        _run(p, block.text, heading_font, look.name_size, bold=True)
    elif block.kind == "headline":
        p = _paragraph(doc, align, after=2)
        _run(p, block.text, font, body + 1, color=MUTED)
    elif block.kind in ("contact", "rights"):
        p = _paragraph(doc, align, after=4 if block.kind == "rights" else 2)
        _run(p, block.text, font, body - 0.5, color=MUTED)
        if block.kind == "contact" and look.contact_rule:
            p.paragraph_format.space_after = Pt(8)
            _bottom_rule(p, look.accent)
    elif block.kind == "heading":
        p = _paragraph(doc, "L", before=10, after=3)
        p.paragraph_format.keep_with_next = True
        _run(
            p, block.text, heading_font, look.heading_size,
            bold=True, caps=look.heading_upper, color=look.accent,
        )
        if look.heading_rule:
            _bottom_rule(p, look.accent)
    elif block.kind == "role":
        p = _paragraph(doc, "L", before=5, after=0)
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        _run(p, block.text, font, body + 1, bold=True)
        if block.right:
            _run(p, "\t" + block.right, font, body - 0.5, color=MUTED)
    elif block.kind == "bullet":
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = _ALIGN["L"]
        p.paragraph_format.space_after = Pt(1)
        _run(p, block.text, font, body)
    else:  # text, entry and the sub line under a role
        p = _paragraph(doc, "L", after=2)
        _run(p, block.text, font, body)
    if block.sub:
        sub = _paragraph(doc, "L", after=2)
        _run(sub, block.sub, font, body - 0.5, color=MUTED)


def _fallback_blocks(contact: ContactDetails, fallback_text: str) -> list[Block]:
    """Without parsed sections, the resume text is laid out as plain lines, as the PDF does."""
    blocks = [Block("name", contact.name or ""), Block("contact", contact_line(contact))]
    blocks = [block for block in blocks if block.text]
    lines = [line.strip() for line in fallback_text.splitlines()]
    return blocks + [Block("text", line) for line in lines if line]


def render_resume_docx(
    contact: ContactDetails,
    resume: BaseSections | None,
    path: Path,
    template: TemplateId = "classic",
    fallback_text: str = "",
) -> None:
    look = LOOKS[template]
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = PAGE_WIDTH, PAGE_HEIGHT
    section.left_margin = section.right_margin = MARGIN
    section.top_margin = section.bottom_margin = MARGIN_TOP
    text_width = section.page_width - section.left_margin - section.right_margin

    normal = doc.styles["Normal"]
    normal.font.name = look.word_body_font
    normal.font.size = Pt(look.body_size)

    align = "C" if look.name_center else "L"
    if resume is None:
        blocks = _fallback_blocks(contact, fallback_text)
    else:
        blocks = layout_blocks(contact, resume, look.skill_separator)
    for block in blocks:
        _write(doc, look, text_width, block, align)

    doc.core_properties.title = "CV"
    doc.core_properties.author = ""
    doc.save(str(path))
