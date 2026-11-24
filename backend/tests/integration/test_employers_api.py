from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_places, get_settings
from app.core.errors import ProviderError
from app.main import create_app
from app.providers.company.places import PlaceMatch
from app.providers.jobs.employer_sites import SiteEmployer
from app.services import employer_service
from app.services.source_service import build_sources

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"


def _place(name="Acme Software", website="https://acme.co.nz/") -> PlaceMatch:
    return PlaceMatch(
        place_id=f"place-{name}",
        address="1 Stafford St, Timaru 7910, New Zealand",
        lat=-44.39,
        lng=171.25,
        website=website,
        phone="03 000 0000",
        name=name,
    )


class FakePlaces:
    def __init__(self, *places, error=None) -> None:
        self.places = list(places) or [_place()]
        self.error = error
        self.queries: list[str] = []

    def search(self, query: str, limit: int = 20):
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.places


def _make_client(database_url, tmp_path, places, **settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=database_url, upload_dir=tmp_path, _env_file=None, **settings
    )
    app.dependency_overrides[get_places] = lambda: places
    return TestClient(app)


@pytest.fixture
def places():
    return FakePlaces()


@pytest.fixture
def client(database_url, tmp_path, places):
    with _make_client(database_url, tmp_path, places) as test_client:
        yield test_client


def _search(client, business="software company", town="Timaru"):
    return client.post("/employers/search", json={"business": business, "town": town})


def _save(client, place: PlaceMatch | None = None):
    place = place or _place()
    return client.post(
        "/employers",
        json={
            "place_id": place.place_id,
            "name": place.name,
            "address": place.address,
            "phone": place.phone,
            "website": place.website,
            "lat": place.lat,
            "lng": place.lng,
        },
    )


def test_search_finds_employers_in_a_town(client, places):
    body = _search(client).json()

    assert places.queries == ["software company in Timaru"]
    employer = body["results"][0]
    assert employer["name"] == "Acme Software"
    assert employer["phone"] == "03 000 0000"
    assert employer["saved"] is False
    assert "google.com/maps" in employer["map_url"]


def test_search_counts_against_a_daily_limit(database_url, tmp_path, places):
    with _make_client(database_url, tmp_path, places, max_nearby_searches_per_day=2) as client:
        assert _search(client).json()["searches_left"] == 1
        assert _search(client).json()["searches_left"] == 0

        refused = _search(client)

    assert refused.status_code == 409
    assert "limit" in refused.json()["detail"].lower()
    assert len(places.queries) == 2


def test_a_failed_search_does_not_use_up_the_limit(database_url, tmp_path):
    failing = FakePlaces(error=ProviderError("places", "HTTP 403"))
    with _make_client(database_url, tmp_path, failing, max_nearby_searches_per_day=1) as client:
        assert _search(client).status_code == 502
        failing.error = None

        assert _search(client).status_code == 200


def test_saving_an_employer_keeps_it_with_sources(client, conn):
    assert _save(client).status_code == 200

    saved = client.get("/employers").json()["items"]
    assert [item["name"] for item in saved] == ["Acme Software"]
    assert saved[0]["last_checked"] is None
    facts = conn.execute("select field, source, confidence from company_facts").fetchall()
    assert {"field": "phone", "source": "places", "confidence": "high"} in facts


def test_search_marks_employers_already_saved(client):
    _save(client).raise_for_status()

    assert _search(client).json()["results"][0]["saved"] is True


def test_saving_twice_keeps_one_employer(client):
    _save(client).raise_for_status()
    _save(client).raise_for_status()

    assert len(client.get("/employers").json()["items"]) == 1


def test_removing_a_saved_employer(client):
    _save(client).raise_for_status()
    employer_id = client.get("/employers").json()["items"][0]["id"]

    assert client.delete(f"/employers/{employer_id}").status_code == 200

    assert client.get("/employers").json()["items"] == []


def test_an_unsafe_website_is_not_saved(client):
    _save(client, _place(website="javascript:alert(1)")).raise_for_status()

    assert client.get("/employers").json()["items"][0]["website"] is None


@pytest.mark.parametrize("body", [{"business": "", "town": "Timaru"}, {"business": "x"}])
def test_search_rejects_incomplete_input(client, body):
    assert client.post("/employers/search", json=body).status_code == 422


def test_search_without_a_maps_key_explains_what_is_missing(database_url, tmp_path):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=database_url, upload_dir=tmp_path, _env_file=None
    )
    with TestClient(app) as client:
        response = _search(client)

    assert response.status_code == 400
    assert "GOOGLE_MAPS_API_KEY" in response.json()["detail"]


def test_another_website_cannot_delete_employers(client):
    url = "/employers/00000000-0000-4000-8000-00000000ffff"

    assert client.delete(url, headers={"Origin": "https://evil.example"}).status_code == 403


def test_saved_employers_count_as_a_job_source():
    employer = SiteEmployer(uuid4(), "Acme", "https://acme.co.nz/", None)
    http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500)))

    sources = build_sources(
        Settings(_env_file=None), http, [], use_examples=True, employers=[employer]
    )

    assert [source.name for source in sources] == ["employer_sites"]


def test_employers_to_check_prefers_the_longest_unchecked(conn):
    from datetime import UTC, datetime
    from uuid import UUID

    profile_id = UUID(PROFILE_ID)
    first = employer_service.save(conn, profile_id, _body("First Co"))
    second = employer_service.save(conn, profile_id, _body("Second Co"))
    employer_service.mark_checked(conn, profile_id, [first.id], datetime(2026, 11, 24, tzinfo=UTC))

    chosen = employer_service.employers_to_check(conn, profile_id, limit=1)

    assert [employer.company_id for employer in chosen] == [second.id]


def test_employers_without_a_readable_website_are_not_checked(conn):
    from uuid import UUID

    profile_id = UUID(PROFILE_ID)
    employer_service.save(
        conn, profile_id, _body("Social Co", website="https://www.facebook.com/socialco")
    )

    assert employer_service.employers_to_check(conn, profile_id, limit=5) == []


def _body(name: str, website: str = "https://acme.co.nz/"):
    from app.schemas.employer import SaveEmployer

    return SaveEmployer(
        place_id=f"place-{name}",
        name=name,
        address="1 Stafford St, Timaru 7910, New Zealand",
        phone=None,
        website=website,
        lat=None,
        lng=None,
    )
