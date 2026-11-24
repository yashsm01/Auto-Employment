"""Payload shapes were checked against live public boards. The values here are invented."""

from datetime import UTC, datetime

import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.jobs.ats import BoardSource, parse_ashby, parse_greenhouse, parse_lever
from app.schemas.resume import BoardEntry


def board(platform: str) -> BoardEntry:
    return BoardEntry(platform=platform, token="exampleco", company="Example Co")


GREENHOUSE = {
    "jobs": [
        {
            "id": 101,
            "title": "Backend Developer",
            "absolute_url": "https://example.invalid/jobs/101",
            "location": {"name": "Auckland, New Zealand"},
            "content": (
                "&lt;p&gt;Build &lt;strong&gt;Python&lt;/strong&gt; "
                "services &amp;amp; APIs.&lt;/p&gt;"
            ),
            "updated_at": "2026-11-20T08:00:00-05:00",
            "first_published": "2026-11-01T00:00:00Z",
            "company_name": "Parent Group",
        }
    ],
    "meta": {"total": 1},
}

LEVER = [
    {
        "id": "abc-1",
        "text": "Data Engineer",
        "categories": {"location": "Wellington, New Zealand", "commitment": "Full time"},
        "hostedUrl": "https://example.invalid/lever/abc-1",
        "descriptionPlain": "Build data pipelines.",
        "lists": [{"text": "You have", "content": "<li>SQL</li><li>Airflow</li>"}],
        "additionalPlain": "Hybrid work.",
        "salaryRange": {
            "min": 90000,
            "max": 110000,
            "currency": "NZD",
            "interval": "per-year-salary",
        },
        "createdAt": 1795392000000,
    },
    {
        "id": "abc-2",
        "text": "US Engineer",
        "categories": {"location": "Atlanta, Georgia"},
        "hostedUrl": "https://example.invalid/lever/abc-2",
        "descriptionPlain": "Build things.",
        "lists": [],
        "salaryRange": {
            "min": 85000,
            "max": 175000,
            "currency": "USD",
            "interval": "per-year-salary",
        },
        "createdAt": 1795392000000,
    },
]

ASHBY = {
    "apiVersion": "1",
    "jobs": [
        {
            "id": "ash-1",
            "title": "Automation Engineer",
            "location": "New Zealand",
            "isRemote": True,
            "isListed": True,
            "jobUrl": "https://example.invalid/ashby/ash-1",
            "descriptionPlain": "Automate operations with Python.",
            "publishedAt": "2026-11-23T00:00:00.000+00:00",
            "compensation": {"scrapeableCompensationSalarySummary": "NZ$80K - NZ$95K"},
        },
        {
            "id": "ash-2",
            "title": "Hidden Role",
            "location": "Auckland",
            "isRemote": False,
            "isListed": False,
            "jobUrl": "https://example.invalid/ashby/ash-2",
            "descriptionPlain": "Unlisted.",
        },
        {
            "id": "ash-3",
            "title": "EU Role",
            "location": "Remote - European Union",
            "isRemote": True,
            "isListed": True,
            "jobUrl": "https://example.invalid/ashby/ash-3",
            "descriptionPlain": "Euro pay.",
            "compensation": {"scrapeableCompensationSalarySummary": "€150K - €250K"},
        },
    ],
}


def test_greenhouse_maps_a_job_and_cleans_its_html():
    job = parse_greenhouse(GREENHOUSE, board("greenhouse"))[0]

    assert job.source == "ats"
    assert job.external_id == "greenhouse:exampleco:101"
    assert job.title == "Backend Developer"
    assert job.company == "Example Co"
    assert job.location == "Auckland, New Zealand"
    assert job.url == "https://example.invalid/jobs/101"
    assert job.description == "Build Python services & APIs."
    assert job.posted_at == datetime(2026, 11, 1, tzinfo=UTC)


def test_lever_combines_all_description_sections():
    job = parse_lever(LEVER, board("lever"))[0]

    assert job.external_id == "lever:exampleco:abc-1"
    assert job.title == "Data Engineer"
    assert job.location == "Wellington, New Zealand"
    assert job.url == "https://example.invalid/lever/abc-1"
    for text in ("Build data pipelines.", "You have", "SQL", "Airflow", "Hybrid work."):
        assert text in job.description
    assert "<li>" not in job.description
    assert job.posted_at == datetime(2026, 11, 23, tzinfo=UTC)


def test_lever_keeps_nz_pay_and_ignores_other_currencies():
    nz_job, us_job = parse_lever(LEVER, board("lever"))

    assert (nz_job.salary_min, nz_job.salary_max) == (90000, 110000)
    assert (us_job.salary_min, us_job.salary_max) == (None, None)


def test_ashby_maps_a_listed_job():
    job = parse_ashby(ASHBY, board("ashby"))[0]

    assert job.external_id == "ashby:exampleco:ash-1"
    assert job.location == "Remote, New Zealand"
    assert job.description == "Automate operations with Python."
    assert (job.salary_min, job.salary_max) == (80000, 95000)
    assert job.posted_at == datetime(2026, 11, 23, tzinfo=UTC)


def test_ashby_skips_unlisted_jobs():
    ids = [job.external_id for job in parse_ashby(ASHBY, board("ashby"))]

    assert "ashby:exampleco:ash-2" not in ids


def test_ashby_ignores_pay_in_another_currency():
    job = parse_ashby(ASHBY, board("ashby"))[1]

    assert (job.salary_min, job.salary_max) == (None, None)


@pytest.mark.parametrize(
    ("platform", "payload", "host", "path"),
    [
        ("greenhouse", GREENHOUSE, "boards-api.greenhouse.io", "/v1/boards/exampleco/jobs"),
        ("lever", LEVER, "api.lever.co", "/v0/postings/exampleco"),
        ("ashby", ASHBY, "api.ashbyhq.com", "/posting-api/job-board/exampleco"),
    ],
)
def test_board_source_calls_the_public_url_once_per_run(platform, payload, host, path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = BoardSource(client, board(platform))

    first = source.search("Python Developer")
    second = source.search("Backend Developer")

    assert first
    assert second == []
    assert len(seen) == 1
    assert (seen[0].host, seen[0].path) == (host, path)


def test_board_failure_names_the_board():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(404)))
    source = BoardSource(client, board("greenhouse"))

    with pytest.raises(ProviderError, match="exampleco.*404"):
        source.search("Python")


def test_board_with_an_unexpected_format_is_a_provider_error():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"unexpected": True}))
    )
    source = BoardSource(client, board("lever"))

    with pytest.raises(ProviderError):
        source.search("Python")
