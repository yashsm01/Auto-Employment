from app.core.resume_layout import Block, contact_line, cv_file_name, layout_blocks
from app.schemas.tailoring import BaseSections, Bullet, ContactDetails, RoleSection


def _contact(**overrides) -> ContactDetails:
    values = {
        "name": "Alex Morgan",
        "email": "alex.morgan@example.invalid",
        "phone": "+64 21 000 0000",
        "location": "Auckland",
        "linkedin": "linkedin.com/in/alex-morgan",
    }
    values.update(overrides)
    return ContactDetails(**values)


def _sections(**overrides) -> BaseSections:
    values = {
        "headline": "Data Engineer",
        "summary": "Builds reliable data pipelines.",
        "roles": [
            RoleSection(
                title="Data Engineer",
                employer="Example Retail Ltd",
                location="Tāmaki Makaurau",
                dates="Mar 2022 – Present",
                bullets=[Bullet(id="r0b0", text="Built pipelines for 3 teams.")],
            )
        ],
        "skills": ["Python", "SQL"],
        "education": ["BSc Computer Science, Example University"],
    }
    values.update(overrides)
    return BaseSections(**values)


def test_blocks_follow_the_nz_order_with_exact_headings():
    blocks = layout_blocks(_contact(), _sections())

    headings = [block.text for block in blocks if block.kind == "heading"]
    assert headings == [
        "Profile",
        "Key skills",
        "Work history",
        "Education and certifications",
        "Referees",
    ]
    assert blocks[0] == Block(kind="name", text="Alex Morgan")
    role = next(block for block in blocks if block.kind == "role")
    assert role == Block(
        kind="role",
        text="Data Engineer",
        right="Mar 2022 – Present",
        sub="Example Retail Ltd, Tāmaki Makaurau",
    )
    assert Block(kind="text", text="Available on request.") in blocks


def test_interests_heading_only_when_filled():
    without = layout_blocks(_contact(), _sections(interests=""))
    with_interests = layout_blocks(_contact(), _sections(interests="Surfing, chess"))

    assert "Interests" not in [block.text for block in without if block.kind == "heading"]
    headings = [block.text for block in with_interests if block.kind == "heading"]
    assert headings[-2:] == ["Interests", "Referees"]
    assert Block(kind="text", text="Surfing, chess") in with_interests


def test_whatsapp_shown_only_when_it_differs_from_the_phone():
    same = contact_line(_contact(phone="021 000 0000", whatsapp="+64 21 000 0000"))
    different = contact_line(_contact(phone="021 000 0000", whatsapp="022 111 2222"))

    assert "WhatsApp" not in same
    assert same == (
        "Auckland · 021 000 0000 · alex.morgan@example.invalid · linkedin.com/in/alex-morgan"
    )
    assert "WhatsApp 022 111 2222" in different


def test_skills_join_with_the_design_separator():
    comma = [b.text for b in layout_blocks(_contact(), _sections()) if b.kind == "text"]
    dotted = [
        b.text
        for b in layout_blocks(_contact(), _sections(), skill_separator=" · ")
        if b.kind == "text"
    ]

    assert "Python, SQL" in comma
    assert "Python · SQL" in dotted


def test_cv_file_name_ascii_folds_the_name():
    assert cv_file_name(_contact(name="Alex Morgan"), "pdf") == "Alex-Morgan-CV.pdf"
    assert cv_file_name(_contact(name="Tāne Mahuta"), "docx") == "Tane-Mahuta-CV.docx"
    assert cv_file_name(_contact(name="  Mary-Jane  O'Neil "), "pdf") == "Mary-Jane-O-Neil-CV.pdf"


def test_cv_file_name_without_a_usable_name():
    assert cv_file_name(_contact(name=None), "pdf") == "CV.pdf"
    assert cv_file_name(_contact(name="  —  "), "docx") == "CV.docx"
