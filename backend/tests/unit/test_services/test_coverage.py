from app.core import skill_synonyms
from app.schemas.tailoring import BaseSections, Bullet, RoleSection
from app.services.coverage_service import coverage, requirements
from app.services.master_cv_service import sections_are_blank


def _sections() -> BaseSections:
    return BaseSections(
        headline="Data Engineer",
        summary="Builds data pipelines for retail teams.",
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


def test_role_evidence_wins_over_key_skills():
    result = coverage(_sections(), ["Python"], [], False, {})

    skill = result.required[0]
    assert skill.status == "shown"
    assert skill.evidence == "Shown in: Data Engineer, Mar 2022 – Present"
    assert skill.matched_as is None


def test_a_synonym_in_a_bullet_covers_the_skill_and_says_so():
    result = coverage(_sections(), ["AWS"], [], False, {})

    skill = result.required[0]
    assert skill.status == "shown"
    assert skill.matched_as == "Amazon Web Services"
    assert result.required_text == "1 of 1"


def test_have_counts_as_added_and_no_as_declined():
    sections = _sections()
    sections.skills.append("Kubernetes")
    result = coverage(
        sections,
        ["Kubernetes", "Go", "Ruby"],
        [],
        False,
        {"kubernetes": "have", "go": "no"},
    )

    statuses = [skill.status for skill in result.required]
    assert statuses == ["added", "declined", "missing"]
    assert result.required[0].evidence == "Added by you to Key skills"
    assert result.required[1].evidence == "You said you don't have this."
    assert result.required[2].evidence == "Not in your CV yet"
    assert result.required_text == "1 of 3"


def test_counts_text():
    result = coverage(_sections(), ["Python", "Go"], ["SQL"], True, {})

    assert result.required_text == "1 of 2"
    assert result.preferred_text == "1 of 1"
    assert result.split is True


def test_no_requirements_gives_0_of_0():
    result = coverage(_sections(), [], [], False, {})

    assert result.required == []
    assert result.preferred == []
    assert result.required_text == "0 of 0"
    assert result.preferred_text == "0 of 0"


def test_variants_go_both_ways_with_the_skill_first():
    assert skill_synonyms.variants("Microsoft Excel") == [
        "Microsoft Excel",
        "Excel",
        "MS Excel",
    ]
    assert skill_synonyms.variants("postgres") == ["postgres", "PostgreSQL"]
    assert skill_synonyms.variants("Python") == ["Python"]


def test_legacy_rows_use_matched_and_missing_as_required():
    row = {
        "required_skills": [],
        "preferred_skills": [],
        "requirements_split": False,
        "matched_skills": ["Python", "sql"],
        "missing_skills": ["SQL", "Go"],
    }

    assert requirements(row) == (["Python", "sql", "Go"], [], False)


def test_sections_are_blank_only_without_any_cv_content():
    assert sections_are_blank(None)
    assert sections_are_blank(BaseSections())
    assert sections_are_blank(BaseSections(referees="Available on request.", interests="Hiking"))
    assert not sections_are_blank(BaseSections(skills=["Python"]))
    assert not sections_are_blank(BaseSections(headline="Data Engineer"))
    assert not sections_are_blank(_sections())


def test_a_two_letter_skill_matches_only_in_its_own_case():
    lowercase_only = BaseSections(headline="Engineer", summary="We go live every week.")
    with_go = BaseSections(headline="Engineer", summary="Go and Python for services.")

    assert coverage(lowercase_only, ["Go"], [], False, {}).required[0].status == "missing"
    assert coverage(with_go, ["Go"], [], False, {}).required[0].status == "shown"


def test_an_ai_scored_row_with_empty_lists_counts_zero_of_zero():
    row = {
        "required_skills": [],
        "preferred_skills": [],
        "requirements_split": True,
        "matched_skills": ["Python"],
        "missing_skills": ["Go"],
    }

    assert requirements(row) == ([], [], True)
    result = coverage(_sections(), *requirements(row), {})
    assert result.required_text == "0 of 0"
