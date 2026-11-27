"""Google Maps outreach: speculative applications for saved employers with no advert."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.chains.speculative_chain import SpeculativeChain, SpeculativeNote
from app.core.config import Settings
from app.db.client import connect
from app.repositories import employers_repo, outbox_repo, outreach_repo, profiles_repo
from app.schemas.auto import AutoModeSettings
from app.schemas.tailoring import BaseSections, Bullet, RoleSection
from app.services import auto_service, contact_service, employer_service, prospect_service
from app.services.contact_service import ContactTools
from app.workers import scheduler
from app.workers.lead_job import run_prospecting
from tests.factories import make_prefs, make_resume
from tests.fakes import ScriptedLLM
from tests.integration.test_contacts import FakeReader
from tests.integration.test_source_report import FakePlaces

pytestmark = pytest.mark.postgres

NOW = datetime(2026, 11, 24, 7, 0, tzinfo=UTC)  # 8 pm in New Zealand on 24 November
NZ_NEXT_DAY = NOW + timedelta(days=1)
ADDRESS = "1 Main St, Timaru 7910, New Zealand"
CV_EMAIL = "sample.person@example.invalid"
CV_PHONE = "+64 21 000 0000"
PROSPECT_LOCK_KEY = 73_032_027  # the run lock for one profile, with hashtext(profile id)
NO_ROLES = "Add your work history in the Resume builder to start Google Maps outreach."


def _website(name: str) -> str:
    return f"https://{name.casefold().replace(' ', '')}.co.nz"


def _sections() -> BaseSections:
    return BaseSections(
        summary="Data analyst with reporting experience.",
        roles=[
            RoleSection(
                title="Data Analyst", employer="Example Retail Ltd", location="Timaru",
                dates="2022 - 2024",
                bullets=[Bullet(id="r0b0", text="Built monthly sales reports in Power BI.")],
            )
        ],
        skills=["Power BI", "SQL"],
    )


def _profile(conn, roles: bool = True) -> UUID:
    """The seeded profile with its own resume, in Timaru. Its master CV has roles unless asked."""
    profile_id = profiles_repo.first_profile_id(conn)
    content = {
        "text": f"Sample Person\n{CV_EMAIL} {CV_PHONE} Timaru\nData analyst.",
        "contact": {"name": "Sample Person", "email": CV_EMAIL, "phone": CV_PHONE,
                    "location": "Timaru"},
    }
    if roles:
        content["sections"] = _sections().model_dump()
    profiles_repo.add_base_resume(
        conn, profile_id, content, "resume.pdf",
        make_resume(titles=["Data Analyst"], skills=[]),
    )
    conn.execute("update profiles set regions = %s where id = %s", (["Timaru"], profile_id))
    conn.commit()
    return profile_id


def _switch_on(conn, profile_id, per_day: int = 2, business_types=()) -> None:
    auto_service.save_settings(
        conn, profile_id,
        AutoModeSettings(enabled=True, prospects_enabled=True, prospects_per_day=per_day,
                         business_types=list(business_types)),
    )
    conn.commit()


def _employer(conn, profile_id, name: str, address: str | None = ADDRESS) -> UUID:
    """A saved employer with its own website. Returns the company id."""
    row = conn.execute(
        "insert into companies (name, website, address) values (%s, %s, %s) returning id",
        (name, _website(name), address),
    ).fetchone()
    saved = list(employers_repo.load_data(conn, profile_id).get("saved_employers") or [])
    saved.append({"company_id": str(row["id"]), "last_checked": None})
    employers_repo.update_data(conn, profile_id, {"saved_employers": saved})
    conn.commit()
    return row["id"]


def _with_email(name: str) -> tuple[str, str]:
    """(website URL, its home page text) for an employer that publishes a general email."""
    return _website(name), f"Welcome to {name}. Email hello@{_website(name)[8:]} today."


def _tools(pages: dict[str, str]) -> ContactTools:
    return ContactTools(reader=FakeReader(pages), recruiter=None)


def _settings(database_url, tmp_path) -> Settings:
    return Settings(database_url=database_url, upload_dir=tmp_path, whatsapp_enabled=True,
                    whatsapp_service_url="http://127.0.0.1:9/send", whatsapp_to="+64224379369",
                    _env_file=None)


def _run(conn, settings, profile_id, tools, chain, now=NOW):
    report = prospect_service.run_daily(conn, settings, profile_id, tools, chain, now)
    conn.commit()
    return report


def _speculative_count(conn, profile_id) -> int:
    return conn.execute(
        "select count(*) as n from applications where profile_id = %s and kind = 'speculative'",
        (profile_id,),
    ).fetchone()["n"]


def test_prospecting_creates_speculative_records_up_to_the_daily_cap(conn, database_url, tmp_path):
    profile_id = _profile(conn)
    _switch_on(conn, profile_id, per_day=2)
    pages = {}
    for name in ("Timaru Trades", "Timaru Builders", "Timaru Joinery"):
        _employer(conn, profile_id, name)
        url, text = _with_email(name)
        pages[url] = text
    tools = _tools(pages)
    chain = SpeculativeChain(ScriptedLLM(*[SpeculativeNote(body="A note about my work.")] * 3))
    settings = _settings(database_url, tmp_path)

    first = _run(conn, settings, profile_id, tools, chain)
    second = _run(conn, settings, profile_id, tools, chain)

    assert first["created"] == 2
    assert second["created"] == 0
    assert _speculative_count(conn, profile_id) == 2
    # The next New Zealand day allows the third employer.
    third = _run(conn, settings, profile_id, tools, chain, NZ_NEXT_DAY)
    assert third["created"] == 1
    assert _speculative_count(conn, profile_id) == 3


def test_an_employer_without_a_published_email_is_skipped(conn, database_url, tmp_path):
    profile_id = _profile(conn)
    _switch_on(conn, profile_id)
    _employer(conn, profile_id, "Quiet Trades")
    tools = _tools({_website("Quiet Trades"): "Welcome. Call us at the yard."})

    report = _run(conn, _settings(database_url, tmp_path), profile_id, tools,
                  SpeculativeChain(ScriptedLLM()))

    assert report == {"created": 0, "skipped_no_email": 1, "blocked": 0}
    assert _speculative_count(conn, profile_id) == 0


def test_no_unsolicited_on_their_site_blocks_the_employer(conn, database_url, tmp_path):
    profile_id = _profile(conn)
    _switch_on(conn, profile_id)
    company_id = _employer(conn, profile_id, "Shy Trades")
    tools = _tools({_website("Shy Trades"):
                    "We do not accept unsolicited CVs. Email hello@shytrades.co.nz"})
    settings = _settings(database_url, tmp_path)

    report = _run(conn, settings, profile_id, tools, SpeculativeChain(ScriptedLLM()))
    again = _run(conn, settings, profile_id, tools, SpeculativeChain(ScriptedLLM()), NZ_NEXT_DAY)

    assert report == {"created": 0, "skipped_no_email": 0, "blocked": 1}
    assert again == {"created": 0, "skipped_no_email": 0, "blocked": 0}
    row = conn.execute(
        "select reason from outreach_blocks where profile_id = %s and company_id = %s",
        (profile_id, company_id),
    ).fetchone()
    assert row["reason"] == "no_unsolicited"
    # The published email stays a contact; the no-unsolicited statement never is.
    contacts = contact_service.view(conn, company_id)
    assert contacts.emails == ["hello@shytrades.co.nz"]
    assert "unsolicited" not in contacts.model_dump_json().lower()


def test_an_employer_with_an_advert_application_is_never_prospected(conn, database_url, tmp_path):
    profile_id = _profile(conn)
    _switch_on(conn, profile_id)
    company_id = _employer(conn, profile_id, "Advert Trades")
    job = conn.execute(
        "insert into jobs (company_id, source, external_id, title, dedupe_hash) "
        "values (%s, 'gmail_alert', 'advert-1', 'Plumber', 'advert-hash') returning id",
        (company_id,),
    ).fetchone()
    conn.execute(
        "insert into applications (profile_id, job_id, status) values (%s, %s, 'found')",
        (profile_id, job["id"]),
    )
    conn.commit()
    url, text = _with_email("Advert Trades")
    tools = _tools({url: text})

    report = _run(conn, _settings(database_url, tmp_path), profile_id, tools,
                  SpeculativeChain(ScriptedLLM()))

    assert report == {"created": 0, "skipped_no_email": 0, "blocked": 0}
    assert _speculative_count(conn, profile_id) == 0


def test_a_cv_without_roles_starts_no_outreach_and_says_so(conn, database_url, tmp_path):
    profile_id = _profile(conn, roles=False)
    _switch_on(conn, profile_id)
    _employer(conn, profile_id, "Timaru Trades")
    url, text = _with_email("Timaru Trades")

    report = _run(conn, _settings(database_url, tmp_path), profile_id, _tools({url: text}),
                  SpeculativeChain(ScriptedLLM()))

    assert report == {"created": 0, "skipped_no_email": 0, "blocked": 0}
    assert _speculative_count(conn, profile_id) == 0
    texts = [row["text"] for row in conn.execute("select text from notifications").fetchall()]
    assert texts == [NO_ROLES]


def test_prospecting_needs_auto_mode_and_the_switch(conn, database_url, tmp_path):
    profile_id = _profile(conn)
    _employer(conn, profile_id, "Timaru Trades")
    settings = _settings(database_url, tmp_path)

    assert run_prospecting(conn, settings, profile_id) is None  # Auto mode is off

    auto_service.save_settings(
        conn, profile_id, AutoModeSettings(enabled=True, prospects_enabled=False)
    )
    conn.commit()
    assert run_prospecting(conn, settings, profile_id) is None  # the switch is off
    assert _speculative_count(conn, profile_id) == 0


def test_speculative_note_never_contains_contact_details(conn, database_url, tmp_path):
    profile_id = _profile(conn)
    _switch_on(conn, profile_id)
    _employer(conn, profile_id, "Timaru Trades")
    url, text = _with_email("Timaru Trades")
    llm = ScriptedLLM(SpeculativeNote(
        body="I write reports. Reach me at hello@timarutrades.co.nz or 021 000 0000."
    ))

    _run(conn, _settings(database_url, tmp_path), profile_id, _tools({url: text}),
         SpeculativeChain(llm))

    sent = llm.calls[0]["user"]
    for private in (CV_EMAIL, CV_PHONE, "Sample Person", "hello@", "timarutrades.co.nz"):
        assert private not in sent
    note = conn.execute(
        "select content ->> 'cover_note' as note from resumes where kind = 'tailored'"
    ).fetchone()["note"]
    assert "@" not in note and "timarutrades.co.nz" not in note


def test_the_record_is_approved_with_a_resume_and_no_tailoring(conn, database_url, tmp_path):
    profile_id = _profile(conn)
    _switch_on(conn, profile_id)
    _employer(conn, profile_id, "Timaru Trades")
    url, text = _with_email("Timaru Trades")

    _run(conn, _settings(database_url, tmp_path), profile_id, _tools({url: text}), None)

    row = conn.execute(
        "select a.status, a.kind, a.auto_approved_at, a.created_at, a.resume_id, j.source "
        "from applications a join jobs j on j.id = a.job_id where a.profile_id = %s",
        (profile_id,),
    ).fetchone()
    assert row["status"] == "approved" and row["kind"] == "speculative"
    assert row["auto_approved_at"] == NOW and row["created_at"] == NOW
    assert row["resume_id"] is not None and row["source"] == "nearby"
    note = conn.execute("select content ->> 'cover_note' as note from resumes where id = %s",
                        (row["resume_id"],)).fetchone()["note"]
    assert note.startswith("Kia ora,") and note.endswith("Sample Person")


def test_speculative_records_do_not_use_up_the_advert_limit_or_send_as_adverts(
    conn, database_url, tmp_path
):
    profile_id = _profile(conn)
    _switch_on(conn, profile_id)
    _employer(conn, profile_id, "Timaru Trades")
    url, text = _with_email("Timaru Trades")
    _run(conn, _settings(database_url, tmp_path), profile_id, _tools({url: text}), None)

    assert auto_service.approved_today(conn, profile_id, NOW) == 0
    assert [row["kind"] for row in outbox_repo.to_send_rows(conn, profile_id)] == ["speculative"]


def test_business_types_drive_the_maps_queries(conn):
    profile_id = _profile(conn)
    places = FakePlaces()

    employer_service.discover(
        conn, profile_id, places, make_resume(titles=["Data Analyst"], skills=[]),
        make_prefs(regions=["Timaru", "Oamaru"]), NOW.date(), 2, 10,
        business_types=["Plumber"],
    )

    assert places.queries == ["Plumber in Timaru", "Plumber in Oamaru"]


def test_a_complete_read_without_the_phrase_clears_the_fact(conn):
    profile_id = _profile(conn)
    company_id = _employer(conn, profile_id, "Shy Trades")
    tools = _tools({_website("Shy Trades"): "We do not accept unsolicited CVs."})
    contact_service.lookup(conn, company_id, tools, NOW)
    assert outreach_repo.has_no_unsolicited(conn, company_id)

    later = _tools({_website("Shy Trades"): "Welcome. Email hello@shytrades.co.nz"})
    contact_service.lookup(conn, company_id, later, NOW, force=True)

    assert not outreach_repo.has_no_unsolicited(conn, company_id)


def test_the_scheduler_prospects_after_the_daily_search_and_survives_its_failure(
    monkeypatch, database_url
):
    calls: list[str] = []

    def search(conn, settings, profile_id):
        calls.append("search")
        return SimpleNamespace(status="ok")

    def prospect(conn, settings, profile_id):
        calls.append("prospect")
        raise RuntimeError("maps is down")

    monkeypatch.setattr(scheduler, "run_lead_search", search)
    monkeypatch.setattr(scheduler, "run_prospecting", prospect)
    settings = Settings(database_url=database_url, _env_file=None)

    scheduler.run_scheduled_search(settings)

    assert calls == ["search", "prospect"]


def test_one_employers_failure_does_not_stop_the_others(
    conn, database_url, tmp_path, monkeypatch
):
    profile_id = _profile(conn)
    _switch_on(conn, profile_id, per_day=2)
    pages = {}
    for name in ("Timaru Trades", "Timaru Builders"):
        _employer(conn, profile_id, name)
        url, text = _with_email(name)
        pages[url] = text
    real_render = prospect_service.render_resume_pdf
    calls = []

    def flaky_render(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            # Leave a half-written file behind, as a real failure might.
            args[2].write_bytes(b"%PDF-partial")
            raise RuntimeError("renderer broke")
        return real_render(*args, **kwargs)

    monkeypatch.setattr(prospect_service, "render_resume_pdf", flaky_render)

    report = _run(conn, _settings(database_url, tmp_path), profile_id, _tools(pages), None)

    assert report["created"] == 1
    assert _speculative_count(conn, profile_id) == 1
    assert len(list(tmp_path.rglob("*.pdf"))) == 1  # the failed employer left no file


def test_a_run_creates_nothing_while_another_run_holds_the_profile_lock(
    conn, database_url, tmp_path
):
    profile_id = _profile(conn)
    _switch_on(conn, profile_id, per_day=2)
    url, text = _with_email("Timaru Trades")
    _employer(conn, profile_id, "Timaru Trades")
    tools = _tools({url: text})
    chain = SpeculativeChain(ScriptedLLM(SpeculativeNote(body="A note about my work.")))
    settings = _settings(database_url, tmp_path)
    key = str(profile_id)

    with connect(database_url) as other_run:
        other_run.execute("select pg_try_advisory_lock(%s, hashtext(%s))",
                          (PROSPECT_LOCK_KEY, key))
        other_run.commit()
        held = _run(conn, settings, profile_id, tools, chain)
        other_run.execute("select pg_advisory_unlock(%s, hashtext(%s))",
                          (PROSPECT_LOCK_KEY, key))
        other_run.commit()

    assert held == {"created": 0, "skipped_no_email": 0, "blocked": 0}
    assert _speculative_count(conn, profile_id) == 0
    released = _run(conn, settings, profile_id, tools, chain)
    assert released["created"] == 1
