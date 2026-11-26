"""What the AI models are sent from a resume: no contact details, role locations or referees."""

from app.chains.prep_chains import WriteChain
from app.chains.tailor_chain import FactCheckChain, FactCheckResult, TailorChain, TailorDraft
from app.schemas.prep import PrepPack
from app.schemas.tailoring import BaseSections, Bullet, ContactDetails, RoleSection, TailoredResume
from tests.factories import make_job
from tests.fakes import ScriptedLLM

CONTACT = ContactDetails(
    name="Alex Morgan",
    email="alex.morgan@example.invalid",
    phone="021 555 0199",
    linkedin="https://www.linkedin.com/in/alexmorgan",
    whatsapp="+64 27 555 0188",
)
REFEREE = "Pat Referee, pat.referee@example.invalid, 027 555 0123"
ROLE_LOCATION = "Hamilton"
SECRETS = [
    "Alex Morgan",
    "alex.morgan@example.invalid",
    "021 555 0199",
    "alexmorgan",
    "027 555 0123",
    "555 0188",
    "pat.referee@example.invalid",
    "Pat Referee",
    ROLE_LOCATION,
]


def _sections() -> BaseSections:
    return BaseSections(
        headline="Data Engineer",
        summary="Alex Morgan builds data pipelines for retail teams.",
        roles=[
            RoleSection(
                title="Data Engineer",
                employer="Example Retail Ltd",
                location=ROLE_LOCATION,
                dates="2022 - 2024",
                bullets=[Bullet(id="r0b0", text="Built pipelines with Python and Airflow.")],
            )
        ],
        skills=["Python", "Airflow"],
        referees=REFEREE,
    )


def _assert_no_secrets(payload: str) -> None:
    for secret in SECRETS:
        assert secret not in payload, secret


def test_prep_write_sends_no_contact_details_from_the_raw_resume_text():
    raw_text = (
        "Alex Morgan\nalex.morgan@example.invalid | 021 555 0199\n"
        "linkedin.com/in/alexmorgan\nWhatsApp +64 27 555 0188\n"
        "Data Engineer at Example Retail Ltd, built pipelines with Python."
    )
    llm = ScriptedLLM(PrepPack())

    WriteChain(llm, "m").run(
        make_job(), None, raw_text, [], [], None, contact=CONTACT
    )

    user = llm.calls[0]["user"]
    assert "built pipelines with Python" in user
    for secret in ["Alex Morgan", "alex.morgan@example.invalid", "021 555 0199",
                   "alexmorgan", "555 0188"]:
        assert secret not in user, secret


def test_prep_write_sends_sections_without_role_locations_or_referees():
    llm = ScriptedLLM(PrepPack())

    WriteChain(llm, "m").run(make_job(location="Dunedin"), _sections(), "", [], [], None,
                             contact=CONTACT)

    user = llm.calls[0]["user"]
    assert "Built pipelines with Python and Airflow." in user
    _assert_no_secrets(user)


def test_tailor_sends_no_contact_details_locations_or_referees():
    llm = ScriptedLLM(TailorDraft(summary="Data engineer.", cover_note="I build pipelines."))

    TailorChain(llm).run(_sections(), make_job(location="Dunedin"), [], contact=CONTACT)

    user = llm.calls[0]["user"]
    assert "Built pipelines with Python and Airflow." in user
    _assert_no_secrets(user)


def test_fact_check_sends_no_contact_details_locations_or_referees():
    original = _sections()
    tailored = TailoredResume(**original.model_dump(), cover_note="I build pipelines.")
    llm = ScriptedLLM(FactCheckResult())

    FactCheckChain(llm).run(original, tailored, [], make_job(location="Dunedin"), contact=CONTACT)

    user = llm.calls[0]["user"]
    assert "Built pipelines with Python and Airflow." in user
    _assert_no_secrets(user)
