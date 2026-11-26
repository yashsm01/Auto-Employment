import pytest
from pydantic import ValidationError

from app.schemas.master_cv import MasterCV, MasterCVView
from app.schemas.tailoring import BaseSections, Bullet, ContactDetails, RoleSection


def _cv(sections: BaseSections) -> dict:
    return {"contact": ContactDetails(name="Sample Person"), "sections": sections}


def _role(bullets: int = 1) -> RoleSection:
    return RoleSection(
        title="Data Engineer",
        employer="Example Retail Ltd",
        bullets=[Bullet(id=f"b{i}", text="Built pipelines.") for i in range(bullets)],
    )


def test_a_cv_at_the_limits_is_accepted():
    sections = BaseSections(
        roles=[_role(20) for _ in range(20)], skills=["Python"] * 80, education=["BSc"] * 20
    )

    cv = MasterCV(**_cv(sections))

    assert cv.template == "classic"


@pytest.mark.parametrize(
    ("sections", "field"),
    [
        (BaseSections(roles=[_role() for _ in range(21)]), "sections.roles"),
        (BaseSections(roles=[_role(21)]), "sections.roles[0].bullets"),
        (BaseSections(skills=["Python"] * 81), "sections.skills"),
        (BaseSections(education=["BSc"] * 21), "sections.education"),
        (BaseSections(interests="x" * 2001), "sections.interests"),
        (BaseSections(roles=[RoleSection(title="t" * 2001, employer="Example")]),
         "sections.roles[0].title"),
    ],
)
def test_a_cv_over_a_limit_is_rejected_and_the_error_names_the_field(sections, field):
    with pytest.raises(ValidationError) as error:
        MasterCV(**_cv(sections))

    assert field in str(error.value)


def test_an_unknown_template_is_rejected():
    with pytest.raises(ValidationError):
        MasterCV(**_cv(BaseSections()), template="fancy")


def test_a_saved_view_is_never_size_checked():
    """A CV the AI cached can be bigger than the PUT limits. It must still load."""
    view = MasterCVView(
        contact=ContactDetails(name="Sample Person"),
        sections=BaseSections(roles=[_role(25)]),
        source="resume",
    )

    assert len(view.sections.roles[0].bullets) == 25
