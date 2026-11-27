from datetime import date
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.chains.manager import get_chain
from app.core.config import Settings
from app.core.deps import get_settings
from app.core.errors import ProviderError
from app.graphs.lead.deps import LeadDeps
from app.graphs.runner import run_graph
from app.main import create_app
from app.providers.company.places import PlaceMatch
from app.services import employer_service
from app.services.employer_service import discovery_queries
from tests.factories import NOW, make_job, make_prefs, make_resume

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"
TODAY = date(2026, 11, 24)


class LabelledSource:
    def __init__(self, name, label, jobs=(), error=None) -> None:
        self.name = name
        self.label = label
        self.jobs = list(jobs)
        self.error = error

    def search(self, keywords):
        if self.error:
            raise self.error
        return self.jobs


def _deps(conn, *sources, notes=()) -> LeadDeps:
    return LeadDeps(
        conn=conn,
        sources=list(sources),
        score_chain=get_chain("score"),
        now=NOW,
        source_notes=list(notes),
    )


def _run(conn, *sources, notes=()):
    return run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, *sources, notes=notes))


@pytest.fixture
def client(database_url, tmp_path):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=database_url, upload_dir=tmp_path, _env_file=None
    )
    with TestClient(app) as test_client:
        yield test_client


def test_run_reports_what_each_source_found(conn):
    good = LabelledSource("trademe", "Trade Me", [make_job(source="trademe")])
    broken = LabelledSource(
        "gmail_alert", "Gmail job alerts", error=ProviderError("gmail", "HTTP 500")
    )
    note = {"source": "Google Maps", "jobs": 0, "status": "not_connected", "detail": None}

    report = _run(conn, good, broken, notes=[note]).output["sources"]

    assert report == [
        note,
        {"source": "Trade Me", "jobs": 1, "status": "ok", "detail": None},
        {"source": "Gmail job alerts", "jobs": 0, "status": "error", "detail": "gmail: HTTP 500"},
    ]


def test_a_job_returned_for_many_searches_counts_once(conn):
    source = LabelledSource("trademe", "Trade Me", [make_job(source="trademe")])

    assert _run(conn, source).output["sources"][0]["jobs"] == 1


def test_a_failed_maps_note_also_appears_in_errors(conn):
    note = {"source": "Google Maps", "jobs": 0, "status": "error", "detail": "places: HTTP 403"}

    output = _run(conn, LabelledSource("x", "X"), notes=[note]).output

    assert "places: HTTP 403" in output["errors"]


def test_pipeline_shows_where_the_last_search_looked(client, conn):
    _run(conn, LabelledSource("trademe", "Trade Me", [make_job(source="trademe")]))

    sources = client.get("/pipeline").json()["last_sources"]

    assert sources == [{"source": "Trade Me", "jobs": 1, "status": "ok", "detail": None}]


@pytest.mark.parametrize(
    ("source", "external_id", "label"),
    [
        ("ats", "site:acme.co.nz:abc", "Employer website via Google Maps"),
        ("ats", "greenhouse:acme:1", "Greenhouse"),
        ("ats", "lever:acme:1", "Lever"),
        ("ats", "ashby:acme:1", "Ashby"),
        ("trademe", "1", "Trade Me"),
        ("gmail_alert", "m1:abc", "Job alert email"),
    ],
)
def test_every_job_names_where_it_came_from(client, conn, source, external_id, label):
    job = make_job(source=source, external_id=external_id, location="Auckland, New Zealand")
    _run(conn, LabelledSource("one", "One", [job]))

    item = client.get("/shortlist").json()["items"][0]
    card = client.get("/pipeline").json()["columns"][0]["cards"][0]
    detail = client.get(f"/applications/{item['id']}").json()

    assert (item["source"], card["source"], detail["source"]) == (label, label, label)


class FakePlaces:
    def __init__(self, error=None) -> None:
        self.queries: list[str] = []
        self.error = error

    def search(self, query: str, limit: int = 20):
        self.queries.append(query)
        if self.error:
            raise self.error
        number = len(self.queries)
        return [
            PlaceMatch(
                place_id=f"place-{number}",
                address="1 Main St, Timaru 7910, New Zealand",
                lat=None,
                lng=None,
                website=f"https://employer{number}.co.nz/",
                phone=None,
                name=f"Employer {number}",
            )
        ]


def _discover(conn, places, per_run=2, daily=30, regions=("Timaru", "Oamaru")):
    resume = make_resume(titles=["Python Developer", "Data Engineer"])
    return employer_service.discover(
        conn,
        UUID(PROFILE_ID),
        places,
        resume,
        make_prefs(regions=list(regions)),
        TODAY,
        per_run,
        daily,
    )


def test_discovery_saves_employers_from_google_maps(conn):
    places = FakePlaces()

    note = _discover(conn, places)

    assert len(places.queries) == 2
    assert note["source"] == "Google Maps"
    assert note["status"] == "ok"
    assert "2 employers" in note["detail"]
    names = [item.name for item in employer_service.list_saved(conn, UUID(PROFILE_ID)).items]
    assert names == ["Employer 1", "Employer 2"]


def test_discovery_stops_at_the_daily_limit(conn):
    places = FakePlaces()

    _discover(conn, places, per_run=5, daily=1)

    assert len(places.queries) == 1


def test_discovery_does_not_bring_back_a_removed_employer(conn):
    profile_id = UUID(PROFILE_ID)
    _discover(conn, FakePlaces(), per_run=1)
    saved = employer_service.list_saved(conn, profile_id).items[0]
    employer_service.remove(conn, profile_id, saved.id)

    _discover(conn, FakePlaces(), per_run=1)

    assert employer_service.list_saved(conn, profile_id).items == []


def test_discovery_reports_a_maps_failure(conn):
    note = _discover(conn, FakePlaces(ProviderError("places", "HTTP 403")))

    assert note["status"] == "error"
    assert note["detail"] == "places: HTTP 403"


def test_discovery_queries_cover_every_town_over_several_days():
    resume = make_resume(titles=["Python Developer"], skills=[])
    prefs = make_prefs(regions=["Timaru", "Oamaru", "Remote NZ"])

    seen = {
        query
        for start in range(4)
        for query in discovery_queries(resume, prefs, TODAY, 1, start=start)
    }

    assert seen == {"Python Developer company in Timaru", "Python Developer company in Oamaru"}


def test_discovery_queries_search_all_of_nz_when_no_town_is_chosen():
    resume = make_resume(titles=["Python Developer"], skills=[])

    assert discovery_queries(resume, make_prefs(regions=[]), TODAY, 3) == [
        "Python Developer company in New Zealand"
    ]


def test_the_saved_cursor_carries_the_search_round_to_the_next_day(conn):
    first, second = FakePlaces(), FakePlaces()
    _discover(conn, first, per_run=1, daily=30, regions=("Timaru", "Oamaru"))
    _discover(conn, second, per_run=1, daily=30, regions=("Timaru", "Oamaru"))

    assert first.queries == ["Python Developer company in Timaru"]
    assert second.queries == ["Data Engineer company in Timaru"]


def test_a_failed_search_moves_the_cursor_past_it(conn):
    _discover(conn, FakePlaces(ProviderError("places", "HTTP 403")), per_run=1)
    retry = FakePlaces()

    _discover(conn, retry, per_run=1)

    assert retry.queries == ["Data Engineer company in Timaru"]
