import pytest
from fastapi.testclient import TestClient

from app.chains.company_summary_chain import CompanySummary, CompanySummaryChain
from app.chains.manager import get_chain
from app.core.config import Settings
from app.core.deps import get_settings
from app.core.errors import ProviderError
from app.graphs.lead.deps import LeadDeps
from app.graphs.runner import run_graph
from app.main import create_app
from app.providers.company.places import PlaceMatch
from app.providers.search.tavily import SearchHit
from app.services.enrich_service import EmployerTools
from tests.factories import NOW, make_job
from tests.fakes import ScriptedLLM

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"


class OneSource:
    name = "one"

    def __init__(self, *jobs) -> None:
        self.jobs = list(jobs)

    def search(self, keywords):
        return self.jobs


class FakePlaces:
    def __init__(self, error=None) -> None:
        self.calls = []
        self.error = error

    def find(self, name, city):
        self.calls.append(name)
        if self.error:
            raise self.error
        return PlaceMatch(
            place_id="place-1",
            address="12 Example St, Auckland",
            lat=-36.85,
            lng=174.76,
            website="https://example.co.nz",
            phone="09 000 0000",
        )


class FakeReader:
    def __init__(self) -> None:
        self.urls = []

    def read(self, url):
        self.urls.append(url)
        return "We build freight software."


class FakeSearch:
    def __init__(self, error=None) -> None:
        self.error = error

    def search(self, query):
        if self.error:
            raise self.error
        return [SearchHit(title="News", url="https://news.example.co.nz/a", content="New app.")]


def _deps(conn, source, tools, limit=10) -> LeadDeps:
    return LeadDeps(
        conn=conn,
        sources=[source],
        score_chain=get_chain("score"),
        now=NOW,
        employer_tools=tools,
        max_employer_profiles=limit,
    )


def _facts(conn) -> dict[tuple[str, str], str]:
    rows = conn.execute("select field, source, value, confidence from company_facts").fetchall()
    return {(row["field"], row["source"]): row["confidence"] for row in rows}


def _tools(places=None, search=None, llm=None) -> EmployerTools:
    llm = llm or ScriptedLLM(CompanySummary(about="Builds freight software in Auckland."))
    return EmployerTools(
        places=places or FakePlaces(),
        reader=FakeReader(),
        search=search or FakeSearch(),
        summary=CompanySummaryChain(llm),
    )


def test_shortlisted_employer_gets_details_with_sources(conn):
    result = run_graph(
        "lead", {"profile_id": PROFILE_ID}, _deps(conn, OneSource(make_job()), _tools())
    )

    assert result.output["employers_researched"] == 1
    company = conn.execute("select address, phone, website, lat from companies").fetchone()
    assert company["address"] == "12 Example St, Auckland"
    assert company["phone"] == "09 000 0000"
    assert company["website"] == "https://example.co.nz"
    facts = _facts(conn)
    assert facts[("address", "places")] == "high"
    assert facts[("about", "website")] == "medium"
    assert facts[("recent_news", "tavily")] == "check"


def test_only_shortlisted_employers_are_researched(conn):
    weak = make_job(
        external_id="weak",
        title="Support Analyst",
        company="Weak Co",
        description="Excel with Salesforce, SAP and Tableau.",
    )
    tools = _tools()

    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, OneSource(weak), tools))

    assert tools.places.calls == []


def test_research_respects_the_per_run_limit(conn):
    jobs = [make_job(external_id=str(index), company=f"Company {index}") for index in range(3)]
    tools = _tools(llm=ScriptedLLM(*[CompanySummary(about="A company.") for _ in range(3)]))

    result = run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, OneSource(*jobs), tools, 2))

    assert len(tools.places.calls) == 2
    assert result.output["employers_researched"] == 2


def test_an_employer_is_not_researched_twice(conn):
    tools = _tools(llm=ScriptedLLM(CompanySummary(about="A."), CompanySummary(about="B.")))
    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, OneSource(make_job()), tools))

    second = make_job(external_id="2", title="Backend Developer")
    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, OneSource(second), tools))

    assert len(tools.places.calls) == 1


def test_a_failing_research_tool_does_not_stop_the_run(conn):
    tools = _tools(
        places=FakePlaces(ProviderError("places", "HTTP 500")),
        search=FakeSearch(ProviderError("tavily", "HTTP 429")),
    )

    result = run_graph(
        "lead", {"profile_id": PROFILE_ID}, _deps(conn, OneSource(make_job()), tools)
    )

    assert result.status == "ok"
    assert result.output["shortlisted"] == 1
    assert "places: HTTP 500" in result.output["errors"]
    assert "tavily: HTTP 429" in result.output["errors"]


@pytest.fixture
def client(database_url, tmp_path):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=database_url, upload_dir=tmp_path, _env_file=None
    )
    with TestClient(app) as test_client:
        yield test_client


def test_job_detail_shows_the_job_employer_and_history(client, conn):
    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, OneSource(make_job()), _tools()))
    item = client.get("/shortlist").json()["items"][0]

    detail = client.get(f"/applications/{item['id']}").json()

    assert detail["title"] == "Junior Python Developer"
    assert detail["description"] == "Build services with Python, FastAPI and SQL."
    assert detail["employer"]["name"] == "Example Freight Tech"
    assert "api=1" in detail["employer"]["map_url"]
    assert {"field": "about", "source": "website", "confidence": "medium"}.items() <= next(
        fact for fact in detail["employer"]["facts"] if fact["field"] == "about"
    ).items()
    assert [event["type"] for event in detail["timeline"]] == ["found", "shortlisted"]


def test_job_detail_for_an_unknown_application_is_404(client):
    assert client.get("/applications/00000000-0000-4000-8000-00000000ffff").status_code == 404


def test_unsafe_job_links_are_not_sent_to_the_browser(client, conn):
    job = make_job(url="javascript:alert(1)")
    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, OneSource(job), None))

    item = client.get("/shortlist").json()["items"][0]

    assert item["url"] is None
    assert client.get(f"/applications/{item['id']}").json()["url"] is None
