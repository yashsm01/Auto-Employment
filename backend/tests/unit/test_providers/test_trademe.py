import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.jobs.trademe import TradeMeSource, build_auth_header, parse_jobs

FIXTURE = Path(__file__).parents[2] / "fixtures" / "trademe_jobs_synthetic.json"


@pytest.fixture
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_auth_header_for_application_only_calls():
    assert build_auth_header("KEY", "SECRET") == (
        'OAuth oauth_consumer_key="KEY", oauth_signature_method="PLAINTEXT", '
        'oauth_signature="SECRET%26"'
    )


def test_auth_header_for_member_calls_signs_with_both_secrets():
    assert build_auth_header("KEY", "SECRET", "TOKEN", "TOKENSECRET") == (
        'OAuth oauth_consumer_key="KEY", oauth_token="TOKEN", '
        'oauth_signature_method="PLAINTEXT", oauth_signature="SECRET%26TOKENSECRET"'
    )


def test_parse_jobs_maps_a_complete_listing(payload):
    job = parse_jobs(payload)[0]

    assert job.source == "trademe"
    assert job.external_id == "1001"
    assert job.title == "Junior Python Developer"
    assert job.company == "Example Freight Tech"
    assert job.location == "Auckland City, Auckland"
    assert job.region == "Auckland"
    assert job.description == "Build Python and FastAPI services for NZ importers."
    assert (job.salary_min, job.salary_max) == (75000, 85000)
    assert job.url == "https://example.invalid/apply/1001"
    assert job.posted_at == datetime(2026, 11, 23, tzinfo=UTC)
    assert job.closes_at == datetime(2026, 12, 23, tzinfo=UTC)


def test_parse_jobs_does_not_give_a_recruiters_details_to_the_employer(payload):
    job = parse_jobs(payload)[0]

    assert job.company_phone == "09 000 0000"  # the listing's own application contact
    assert job.company_website is None
    assert job.company_email is None
    assert job.company_address is None


def test_parse_jobs_uses_agency_details_when_the_agency_is_the_employer(payload):
    job = parse_jobs(payload)[1]

    assert job.company_phone == "04 222 2222"
    assert job.company_website == "https://payments.example.invalid"


def test_parse_jobs_falls_back_when_optional_fields_are_missing(payload):
    job = parse_jobs(payload)[1]

    assert job.company == "Sample Payments Ltd"
    assert job.location == "Te Aro, Wellington"
    assert job.description == "Backend work with PostgreSQL."
    assert (job.salary_min, job.salary_max) == (90000, 110000)
    assert job.url == "https://example.invalid/trademe-apply/1002"
    assert job.posted_at == datetime(2026, 11, 20, 8, 30, tzinfo=UTC)
    assert job.closes_at is None


def test_parse_jobs_skips_a_listing_without_a_title(payload):
    assert [job.external_id for job in parse_jobs(payload)] == ["1001", "1002"]


def test_parse_jobs_handles_an_empty_list():
    assert parse_jobs({"TotalCount": 0, "List": None}) == []


def test_search_sends_keywords_and_auth(payload):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = TradeMeSource(client, consumer_key="KEY", consumer_secret="SECRET")

    jobs = source.search("Python Developer")

    assert seen["path"] == "/v1/Search/Jobs.json"
    assert seen["params"]["search_string"] == "Python Developer"
    assert seen["params"]["rows"] == "50"
    assert 'oauth_consumer_key="KEY"' in seen["auth"]
    assert len(jobs) == 2


@pytest.mark.parametrize("status", [401, 429, 500])
def test_search_raises_provider_error_on_a_bad_status(status):
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status)))
    source = TradeMeSource(client, consumer_key="KEY", consumer_secret="SECRET")

    with pytest.raises(ProviderError) as caught:
        source.search("Python")

    assert caught.value.provider == "trademe"
    assert str(status) in str(caught.value)


def test_search_raises_provider_error_when_the_network_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = TradeMeSource(client, consumer_key="KEY", consumer_secret="SECRET")

    with pytest.raises(ProviderError):
        source.search("Python")


def test_provider_errors_never_include_the_secret():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(401)))
    source = TradeMeSource(client, consumer_key="KEY", consumer_secret="TOPSECRET")

    with pytest.raises(ProviderError) as caught:
        source.search("Python")

    assert "TOPSECRET" not in str(caught.value)
