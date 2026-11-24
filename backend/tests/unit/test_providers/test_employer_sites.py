import json
from uuid import uuid4

import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.company.careers import find_board, find_careers_link
from app.providers.company.places import PlacesClient
from app.providers.company.website_reader import is_allowed_url
from app.providers.jobs.employer_sites import EmployerSitesSource, SiteEmployer
from app.schemas.job import AlertJob


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        ("[Jobs](https://boards.greenhouse.io/acmenz)", ("greenhouse", "acmenz")),
        ("[Jobs](https://job-boards.greenhouse.io/acmenz/jobs/1)", ("greenhouse", "acmenz")),
        ("See https://jobs.lever.co/acme-nz/abc for roles", ("lever", "acme-nz")),
        ("[Open](https://jobs.ashbyhq.com/AcmeNZ)", ("ashby", "AcmeNZ")),
        ("[Contact](https://example.co.nz/contact)", None),
    ],
)
def test_find_board_detects_public_job_boards(page, expected):
    assert find_board(page) == expected


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        ("[Careers](/careers)", "https://acme.co.nz/careers"),
        ("[Join our team](https://acme.co.nz/join-us)", "https://acme.co.nz/join-us"),
        ("[Vacancies](https://www.acme.co.nz/vacancies)", "https://www.acme.co.nz/vacancies"),
        ("[About](/about) [Work with us](/work-with-us)", "https://acme.co.nz/work-with-us"),
        ("[Careers](https://other-company.co.nz/careers)", None),
        ("[Blog about jobs](https://facebook.com/acme)", None),
        ("[About](/about)", None),
    ],
)
def test_find_careers_link_stays_on_the_employers_site(page, expected):
    assert find_careers_link(page, "https://acme.co.nz/") == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://www.facebook.com/acme",
        "https://instagram.com/acme",
        "https://www.trademe.co.nz/a/jobs",
    ],
)
def test_social_and_job_board_sites_are_not_read(url):
    assert is_allowed_url(url) is False


class FakeReader:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def read(self, url: str) -> str:
        self.urls.append(url)
        if url not in self.pages:
            raise ProviderError("website", "HTTP 404")
        return self.pages[url]


def _employer(**overrides) -> SiteEmployer:
    values = {
        "company_id": uuid4(),
        "name": "Acme Software",
        "website": "https://acme.co.nz/",
        "address": "1 Stafford St, Timaru 7910, New Zealand",
    }
    values.update(overrides)
    return SiteEmployer(**values)


def _alert(**overrides) -> AlertJob:
    values = {
        "title": "Python Developer",
        "company": "Acme Software",
        "location": "Timaru",
        "url": "/careers/python-developer",
        "summary": "Build Python services.",
    }
    values.update(overrides)
    return AlertJob(**values)


HOME = "Welcome to Acme. [Careers](/careers)"
CAREERS = "Open roles: Python Developer in Timaru. Build Python services."


def _source(reader, extract, *employers, client=None) -> EmployerSitesSource:
    http = client or httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500)))
    return EmployerSitesSource(http, reader, extract, list(employers or [_employer()]))


def test_reads_jobs_from_an_employers_careers_page():
    reader = FakeReader({"https://acme.co.nz/": HOME, "https://acme.co.nz/careers": CAREERS})
    seen = []

    def extract(company, url, page):
        seen.append((company, url, page))
        return [_alert()]

    source = _source(reader, extract)
    job = source.search("Python")[0]

    assert seen == [("Acme Software", "https://acme.co.nz/careers", CAREERS)]
    assert job.source == "ats"
    assert job.external_id.startswith("site:acme.co.nz:")
    assert job.title == "Python Developer"
    assert job.company == "Acme Software"
    assert job.location == "Timaru, New Zealand"
    assert job.url == "https://acme.co.nz/careers/python-developer"
    assert job.description == "Build Python services."
    assert job.company_website == "https://acme.co.nz/"


def test_scans_each_employer_once_per_run():
    reader = FakeReader({"https://acme.co.nz/": HOME, "https://acme.co.nz/careers": CAREERS})
    source = _source(reader, lambda *_: [_alert()])

    assert source.search("Python")
    assert source.search("Backend") == []
    assert len(reader.urls) == 2


def test_drops_a_job_title_that_is_not_on_the_page():
    reader = FakeReader({"https://acme.co.nz/": HOME, "https://acme.co.nz/careers": CAREERS})
    source = _source(reader, lambda *_: [_alert(title="Chief Executive")])

    assert source.search("Python") == []


def test_uses_the_employer_address_when_a_job_has_no_location():
    reader = FakeReader({"https://acme.co.nz/": HOME, "https://acme.co.nz/careers": CAREERS})
    source = _source(reader, lambda *_: [_alert(location="")])

    assert source.search("Python")[0].location == "1 Stafford St, Timaru 7910, New Zealand"


def test_an_unsafe_job_link_falls_back_to_the_careers_page():
    reader = FakeReader({"https://acme.co.nz/": HOME, "https://acme.co.nz/careers": CAREERS})
    source = _source(reader, lambda *_: [_alert(url="javascript:alert(1)")])

    assert source.search("Python")[0].url == "https://acme.co.nz/careers"


def test_a_site_with_no_careers_page_makes_no_ai_call():
    reader = FakeReader({"https://acme.co.nz/": "Welcome. [About](/about)"})

    def extract(*_):
        raise AssertionError("AI should not be called")

    source = _source(reader, extract)

    assert source.search("Python") == []
    assert len(source.checked) == 1


def test_uses_a_linked_job_board_without_an_ai_call():
    reader = FakeReader({"https://acme.co.nz/": "[Jobs](https://boards.greenhouse.io/acmenz)"})
    payload = {
        "jobs": [
            {
                "id": 7,
                "title": "Backend Developer",
                "absolute_url": "https://boards.greenhouse.io/acmenz/jobs/7",
                "location": {"name": "Auckland, New Zealand"},
                "content": "Build APIs.",
            }
        ]
    }
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(200, content=json.dumps(payload))

    def extract(*_):
        raise AssertionError("AI should not be called")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    job = _source(reader, extract, client=client).search("Python")[0]

    assert requested == ["/v1/boards/acmenz/jobs"]
    assert job.external_id == "greenhouse:acmenz:7"
    assert job.company == "Acme Software"


def test_without_ai_only_linked_job_boards_are_used():
    reader = FakeReader({"https://acme.co.nz/": HOME, "https://acme.co.nz/careers": CAREERS})

    source = _source(reader, None)

    assert source.search("Python") == []
    assert reader.urls == ["https://acme.co.nz/"]


def test_one_failing_site_does_not_stop_the_others():
    good = _employer(name="Good Co", website="https://good.co.nz/")
    bad = _employer(name="Bad Co", website="https://bad.co.nz/")
    reader = FakeReader(
        {
            "https://good.co.nz/": "[Careers](/careers)",
            "https://good.co.nz/careers": CAREERS,
        }
    )

    jobs = _source(reader, lambda *_: [_alert()], bad, good).search("Python")

    assert [job.company for job in jobs] == ["Good Co"]


def test_reports_when_every_site_fails():
    with pytest.raises(ProviderError, match="404"):
        _source(FakeReader({}), lambda *_: []).search("Python")


def _place(name: str, address: str = "1 Main St, Timaru 7910, New Zealand") -> dict:
    return {
        "id": f"id-{name}",
        "displayName": {"text": name},
        "formattedAddress": address,
        "location": {"latitude": -44.39, "longitude": 171.25},
        "websiteUri": "https://example.co.nz/",
        "nationalPhoneNumber": "03 000 0000",
    }


def test_places_search_lists_nz_businesses():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        places = [_place("Acme"), _place("Overseas Ltd", "1 High St, Sydney NSW, Australia")]
        return httpx.Response(200, json={"places": places})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    results = PlacesClient(client, "KEY").search("software company in Timaru")

    assert seen["body"] == {
        "textQuery": "software company in Timaru, New Zealand",
        "regionCode": "NZ",
        "pageSize": 20,
    }
    assert [place.name for place in results] == ["Acme"]
    assert results[0].phone == "03 000 0000"


def test_places_search_keeps_nz_addresses_written_without_the_country():
    # With regionCode NZ, Google leaves the country off NZ addresses.
    places = [
        _place(
            "Wellington Co", "Level 1, 11 Customhouse Quay, Wellington Central, Wellington 6011"
        ),
        _place("Sydney Co", "1 High St, Sydney NSW 2000, Australia"),
        _place("No Postcode Co", "Queen Street, Auckland"),
    ]
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"places": places}))
    )

    names = [place.name for place in PlacesClient(client, "KEY").search("software in NZ")]

    assert names == ["Wellington Co", "No Postcode Co"]


def test_an_address_without_the_country_still_counts_as_new_zealand():
    reader = FakeReader({"https://acme.co.nz/": HOME, "https://acme.co.nz/careers": CAREERS})
    employer = _employer(address="Level 1, 11 Customhouse Quay, Wellington 6011")
    source = _source(reader, lambda *_: [_alert(location="")], employer)

    assert source.search("Python")[0].location == (
        "Level 1, 11 Customhouse Quay, Wellington 6011, New Zealand"
    )


def test_find_careers_link_prefers_the_main_careers_page():
    page = (
        "[Scholarships](/candc-careers/candc-open-source-scholarships) "
        "[Careers](/careers) [Contact](/contact)"
    )

    assert find_careers_link(page, "https://acme.co.nz/") == "https://acme.co.nz/careers"


@pytest.mark.parametrize(
    "href",
    [
        "https://acme.wd3.myworkdayjobs.com/External",
        "https://careers.smartrecruiters.com/AcmeNZ",
        "https://acme.applynow.net.nz/",
        "https://careers.acme.co.nz/",
    ],
)
def test_find_careers_link_follows_hiring_sites_and_careers_subdomains(href):
    assert find_careers_link(f"[Careers]({href})", "https://acme.co.nz/") == href


def test_find_careers_link_never_follows_job_boards_that_ban_scraping():
    page = "[Jobs](https://www.seek.co.nz/acme-jobs)"

    assert find_careers_link(page, "https://acme.co.nz/") is None


def test_a_careers_link_at_the_bottom_of_a_long_homepage_is_found():
    home = "Welcome. " + "News item. " * 4000 + "[Careers](/careers)"
    reader = FakeReader({"https://acme.co.nz/": home, "https://acme.co.nz/careers": CAREERS})

    jobs = _source(reader, lambda *_: [_alert()]).search("Python")

    assert [job.title for job in jobs] == ["Python Developer"]
