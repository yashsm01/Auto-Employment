import json

import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.company.places import PlacesClient
from app.providers.company.website_reader import WebsiteReader, is_allowed_url
from app.providers.search.tavily import TavilySearch


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _place(name="Example Freight Tech Ltd"):
    return {
        "id": "place-1",
        "displayName": {"text": name, "languageCode": "en"},
        "formattedAddress": "12 Example St, Auckland 1010, New Zealand",
        "location": {"latitude": -36.85, "longitude": 174.76},
        "websiteUri": "https://example.invalid/",
        "nationalPhoneNumber": "09 000 0000",
    }


def test_places_requests_only_the_needed_fields():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["mask"] = request.headers["x-goog-fieldmask"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"places": [_place()]})

    PlacesClient(_client(handler), "KEY").find("Example Freight Tech", "Auckland")

    assert seen["url"] == "https://places.googleapis.com/v1/places:searchText"
    assert seen["key"] == "KEY"
    assert set(seen["mask"].split(",")) == {
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.googleMapsUri",
        "places.rating",
        "places.userRatingCount",
        "places.regularOpeningHours",
        "places.primaryTypeDisplayName",
        "places.businessStatus",
    }
    assert seen["body"] == {
        "textQuery": "Example Freight Tech Auckland New Zealand",
        "regionCode": "NZ",
        "pageSize": 1,
    }


def test_places_maps_a_matching_business():
    client = _client(lambda _: httpx.Response(200, json={"places": [_place()]}))

    place = PlacesClient(client, "KEY").find("Example Freight Tech", "Auckland")

    assert place.place_id == "place-1"
    assert place.address == "12 Example St, Auckland 1010, New Zealand"
    assert (place.lat, place.lng) == (-36.85, 174.76)
    assert place.website == "https://example.invalid/"
    assert place.phone == "09 000 0000"


def test_places_returns_hours_rating_and_type():
    place = _place()
    place.update(
        {
            "googleMapsUri": "https://maps.google.com/?cid=1",
            "rating": 4.6,
            "userRatingCount": 38,
            "regularOpeningHours": {
                "weekdayDescriptions": ["Monday: 9:00 AM – 5:00 PM", "Sunday: Closed"]
            },
            "primaryTypeDisplayName": {"text": "Software company", "languageCode": "en"},
            "businessStatus": "OPERATIONAL",
        }
    )
    client = _client(lambda _: httpx.Response(200, json={"places": [place]}))

    match = PlacesClient(client, "KEY").find("Example Freight Tech", "Auckland")

    assert match.maps_url == "https://maps.google.com/?cid=1"
    assert match.rating == 4.6
    assert match.rating_count == 38
    assert match.hours == ("Monday: 9:00 AM – 5:00 PM", "Sunday: Closed")
    assert match.business_type == "Software company"
    assert match.business_status == "OPERATIONAL"


def test_places_new_details_are_optional():
    match = PlacesClient(
        _client(lambda _: httpx.Response(200, json={"places": [_place()]})), "KEY"
    ).find("Example Freight Tech", "Auckland")

    assert match.maps_url is None
    assert match.rating is None
    assert match.rating_count is None
    assert match.hours == ()
    assert match.business_type is None
    assert match.business_status is None


def test_save_employer_accepts_rating_and_hours_and_old_bodies():
    from pydantic import ValidationError

    from app.schemas.employer import SaveEmployer

    base = {"place_id": "place-1", "name": "Example Freight Tech Ltd"}

    old = SaveEmployer(**base)
    assert old.rating is None
    assert old.rating_count is None
    assert old.hours == []

    new = SaveEmployer(
        **base, rating=4.2, rating_count=12, hours=["Monday: 9:00 AM – 5:00 PM"]
    )
    assert (new.rating, new.rating_count, new.hours) == (4.2, 12, ["Monday: 9:00 AM – 5:00 PM"])

    with pytest.raises(ValidationError):
        SaveEmployer(**base, hours=["x"] * 8)
    with pytest.raises(ValidationError):
        SaveEmployer(**base, hours=["x" * 121])


def test_places_ignores_a_different_business():
    client = _client(lambda _: httpx.Response(200, json={"places": [_place("Joe's Fish Shop")]}))

    assert PlacesClient(client, "KEY").find("Example Freight Tech", "Auckland") is None


def test_places_with_no_result_returns_none():
    client = _client(lambda _: httpx.Response(200, json={}))

    assert PlacesClient(client, "KEY").find("Example", "Auckland") is None


def test_places_error_hides_the_key():
    client = _client(lambda _: httpx.Response(403, text="SECRETKEY rejected"))

    with pytest.raises(ProviderError) as caught:
        PlacesClient(client, "SECRETKEY").find("Example", "Auckland")

    assert "SECRETKEY" not in str(caught.value)


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://example.co.nz/about", True),
        ("http://example.co.nz", True),
        ("https://www.seek.co.nz/job/1", False),
        ("https://nz.linkedin.com/company/x", False),
        ("https://nz.indeed.com/viewjob", False),
        ("ftp://example.co.nz", False),
        ("javascript:alert(1)", False),
        ("http://localhost:8000/profile", False),
        ("http://127.0.0.1/admin", False),
        ("http://169.254.169.254/latest", False),
        ("http://[::1]/", False),
        ("not a url", False),
    ],
)
def test_website_reader_url_rules(url, allowed):
    assert is_allowed_url(url) is allowed


def test_website_reader_uses_reader_with_robots_check():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["robots"] = request.headers.get("x-robots-txt")
        seen["dnt"] = request.headers.get("dnt")
        return httpx.Response(200, text="We build freight software.")

    text = WebsiteReader(_client(handler)).read("https://example.co.nz/about")

    assert text == "We build freight software."
    assert seen["url"] == "https://r.jina.ai/https://example.co.nz/about"
    assert seen["robots"]
    assert seen["dnt"] == "1"


def test_website_reader_never_requests_a_blocked_site():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, text="page")

    with pytest.raises(ProviderError):
        WebsiteReader(_client(handler)).read("https://www.linkedin.com/company/example")

    assert calls == []


def test_tavily_sends_a_basic_search():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "About",
                        "url": "https://example.co.nz",
                        "content": "Ships.",
                        "score": 0.9,
                    },
                    {
                        "title": "Profile",
                        "url": "https://linkedin.com/x",
                        "content": "No.",
                        "score": 0.8,
                    },
                ]
            },
        )

    hits = TavilySearch(_client(handler), "KEY").search("Example NZ")

    assert seen["auth"] == "Bearer KEY"
    assert seen["body"] == {
        "query": "Example NZ",
        "search_depth": "basic",
        "max_results": 3,
        "topic": "general",
    }
    assert [hit.url for hit in hits] == ["https://example.co.nz"]


def test_website_reader_treats_a_blocked_site_as_a_failure():
    blocked = (
        "Title: Just a moment...\n\nURL Source: https://example.co.nz/\n\n"
        "Warning: Target URL returned error 403: Forbidden\n\nMarkdown Content:\nVerifying..."
    )
    client = _client(lambda _: httpx.Response(200, text=blocked))

    with pytest.raises(ProviderError, match="403"):
        WebsiteReader(client).read("https://example.co.nz/")


def test_website_reader_keeps_the_end_of_a_long_page():
    page = "Intro. " + "Text. " * 5000 + "[Careers](/careers)"
    client = _client(lambda _: httpx.Response(200, text=page))

    assert WebsiteReader(client).read("https://example.co.nz/").endswith("[Careers](/careers)")


def test_glassdoor_is_blocked():
    assert not is_allowed_url("https://www.glassdoor.co.nz/Reviews/x")
    assert not is_allowed_url("https://glassdoor.com/job")
