from datetime import UTC, datetime

import pytest
from psycopg.types.json import Jsonb

from app.chains.manager import PrepChains
from app.chains.prep_chains import ExploreChain, ExtractChain, PlanChain, WriteChain
from app.core.errors import ProviderError
from app.graphs.prep.deps import PrepDeps
from app.graphs.runner import run_graph
from app.providers.company.places import PlaceMatch
from app.providers.search.tavily import SearchHit
from app.repositories import prep_repo
from app.schemas.prep import (
    EvidenceItem,
    ExploreStep,
    ExtractResult,
    Fact,
    PlanResult,
    PrepPack,
    SourcedLine,
)
from app.schemas.tailoring import BaseSections, Bullet, RoleSection
from app.services.prep_service import Budget
from tests.fakes import ScriptedLLM

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"
NOW = datetime(2026, 11, 24, 7, 0, tzinfo=UTC)
HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
BULLET = "Built data pipelines with Python and Airflow for 3 teams."
RESUME_TEXT = (
    "Sample Person\nData Engineer, Example Retail Ltd, 2022 - 2024\n"
    "- Built data pipelines with Python and Airflow for 3 teams.\nSkills: Python, SQL"
)
SECTIONS = BaseSections(
    summary="Data engineer.",
    roles=[
        RoleSection(
            title="Data Engineer",
            employer="Example Retail Ltd",
            dates="2022 - 2024",
            bullets=[Bullet(id="r0b0", text=BULLET)],
        )
    ],
    skills=["Python", "SQL"],
)


class FakeReader:
    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.pages = pages or {}
        self.urls: list[str] = []

    def read(self, url: str) -> str:
        self.urls.append(url)
        if url not in self.pages:
            raise ProviderError("website", "HTTP 404")
        return self.pages[url]


class FakeSearch:
    def __init__(self, hits_for) -> None:
        self.hits_for = hits_for
        self.queries: list[str] = []

    def search(self, query: str) -> list[SearchHit]:
        self.queries.append(query)
        return self.hits_for(query)


class FakePlaces:
    def __init__(self, match: PlaceMatch | None) -> None:
        self.match = match
        self.calls: list[tuple[str, str]] = []

    def find(self, name: str, city: str) -> PlaceMatch | None:
        self.calls.append((name, city))
        return self.match


def hit(url: str, content: str = "Nothing useful here.") -> SearchHit:
    return SearchHit(title=f"Result {url}", url=url, content=content)


def empties(count: int) -> list[ExtractResult]:
    return [ExtractResult(facts=[]) for _ in range(count)]


def _setup(conn, *, description="Build pipelines with Python.", website=None, url=None,
           extra=None, resume=True) -> tuple[str, str, str]:
    if resume:
        conn.execute(
            "insert into resumes (profile_id, kind, content) values (%s, 'base', %s)",
            (PROFILE_ID, Jsonb({"text": RESUME_TEXT, "sections": SECTIONS.model_dump()})),
        )
    company_id = conn.execute(
        "insert into companies (name, website, address) values "
        "('Example Freight Tech', %s, '12 Example St, Dunedin') returning id",
        (website,),
    ).fetchone()["id"]
    job_id = conn.execute(
        "insert into jobs (company_id, source, external_id, title, location, url, description, "
        "dedupe_hash) values (%s, 'example', 'p1', 'Data Engineer', 'Dunedin', %s, %s, 'h1') "
        "returning id",
        (company_id, url, description),
    ).fetchone()["id"]
    app_id = conn.execute(
        "insert into applications (profile_id, job_id, status) values (%s, %s, 'shortlisted') "
        "returning id",
        (PROFILE_ID, job_id),
    ).fetchone()["id"]
    pack_id = prep_repo.insert_queued(conn, PROFILE_ID, app_id, company_id, extra)
    conn.commit()
    return str(pack_id), str(app_id), str(company_id)


def _deps(conn, *, plan, extracts=(), explores=(), write=None, reader=None, search=None,
          places=None, places_allowed=True, budget=None,
          places_remaining=None) -> tuple[PrepDeps, dict[str, ScriptedLLM]]:
    llms = {
        "plan": ScriptedLLM(plan),
        "extract": ScriptedLLM(*extracts),
        "explore": ScriptedLLM(*explores),
        "write": ScriptedLLM(write or PrepPack()),
    }
    chains = PrepChains(
        plan=PlanChain(llms["plan"], HAIKU),
        extract=ExtractChain(llms["extract"], HAIKU),
        explore=ExploreChain(llms["explore"], HAIKU),
        write=WriteChain(llms["write"], SONNET),
    )
    deps = PrepDeps(
        conn=conn, chains=chains, places=places, reader=reader or FakeReader(), search=search,
        now=NOW, usd_to_nzd=1.70, places_allowed=places_allowed, budget=budget or Budget(),
        places_remaining=places_remaining,
    )
    return deps, llms


def _run(conn, pack_id, app_id, deps):
    return run_graph("prep", {"pack_id": pack_id, "application_id": app_id}, deps)


def test_a_run_saves_a_verified_pack_and_employer_facts(conn):
    pack_id, app_id, company_id = _setup(conn, website="https://example.co.nz")
    reader = FakeReader({"https://example.co.nz": "Example builds port software for NZ importers."})
    search = FakeSearch(lambda q: [hit("https://news.example.org/a",
                                       "Example Freight Tech opened a Dunedin office in 2026.")])
    places = FakePlaces(PlaceMatch(place_id="p1", address="12 Example St, Dunedin", lat=None,
                                   lng=None, website=None, phone="03 000 0000",
                                   name="Example Freight Tech"))
    extracts = [
        ExtractResult(facts=[]),  # s1 job post
        ExtractResult(facts=[  # s2 home page
            Fact(kind="about", text="Builds port software", source_id="s2",
                 quote="builds port software for NZ importers"),
            Fact(kind="about", text="Invented", source_id="s2", quote="not on the page"),
        ]),
        ExtractResult(facts=[  # s3 places
            Fact(kind="practical", text="Office in Dunedin", source_id="s3",
                 quote="12 Example St, Dunedin"),
        ]),
        ExtractResult(facts=[  # s4 search hit
            Fact(kind="news", text="Opened a Dunedin office", source_id="s4",
                 quote="opened a Dunedin office in 2026"),
        ]),
    ]
    write = PrepPack(
        evidence=[EvidenceItem(requirement="Python", status="matched", evidence=BULLET)],
        employer=[SourcedLine(text="Builds port software", source_ids=["s2"]),
                  SourcedLine(text="Unknown claim", source_ids=["s9"])],
    )
    deps, llms = _deps(conn, plan=PlanResult(queries=["Example news"], needs=["about", "news"]),
                       extracts=extracts, write=write, reader=reader, search=search, places=places)

    result = _run(conn, pack_id, app_id, deps)

    assert result.status == "ok", result.error
    row = prep_repo.get(conn, pack_id)
    assert row["status"] == "done"
    assert [line["text"] for line in row["content"]["employer"]] == [
        "Builds port software", "Opened a Dunedin office"]
    assert "Unknown claim" not in str(row["content"])
    assert row["content"]["could_not_verify"] == ["Invented"]
    assert row["content"]["directions_url"].startswith("https://www.google.com/maps/dir/")
    assert row["content"]["evidence"][0]["status"] == "matched"
    assert sorted(f["text"] for f in row["facts"]) == [
        "Builds port software", "Office in Dunedin", "Opened a Dunedin office"]
    assert row["places_calls"] == 1
    assert llms["explore"].calls == []
    saved = {(r["field"], r["value"], r["source"], r["confidence"]) for r in conn.execute(
        "select field, value, source, confidence from company_facts where company_id = %s",
        (company_id,))}
    assert ("about", "Builds port software", "website", "medium") in saved
    assert ("recent_news", "Opened a Dunedin office", "tavily", "medium") in saved
    events = conn.execute(
        "select payload from events where application_id = %s and type = 'note'", (app_id,)
    ).fetchall()
    assert any(e["payload"].get("text") == "Deep search finished" for e in events)


def test_search_results_on_blocked_sites_are_never_read_or_cited(conn):
    pack_id, app_id, _ = _setup(conn)
    reader = FakeReader()
    search = FakeSearch(lambda q: [hit("https://www.seek.co.nz/job/1"),
                                   hit("https://example.co.nz/about")])
    deps, _ = _deps(conn, plan=PlanResult(queries=["q"]), extracts=empties(2), reader=reader,
                    search=search)

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    sources = prep_repo.get(conn, pack_id)["sources"]
    # Search hits are used from their own content; they are never sent to the reader.
    assert not any("seek" in url for url in reader.urls)
    assert [s["url"] for s in sources if s["kind"] == "search"] == ["https://example.co.nz/about"]


def test_a_blocked_extra_link_adds_a_note_and_is_not_fetched(conn):
    pack_id, app_id, _ = _setup(conn, extra="https://www.linkedin.com/jobs/view/1")
    reader = FakeReader()
    deps, _ = _deps(conn, plan=PlanResult(), extracts=empties(1), reader=reader)

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    assert reader.urls == []
    assert ("That link is on a site the app may not open. Paste the job text into Extra details "
            "instead.") in prep_repo.get(conn, pack_id)["notes"]


def test_pasted_extra_text_becomes_a_page(conn):
    pack_id, app_id, _ = _setup(conn, extra="The team uses Kubernetes and Go.")
    deps, llms = _deps(conn, plan=PlanResult(), extracts=empties(2))

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    assert "The team uses Kubernetes and Go." in llms["extract"].calls[1]["user"]
    assert [s["kind"] for s in prep_repo.get(conn, pack_id)["sources"]] == ["job_post", "user"]


def test_explore_stops_after_three_actions(conn):
    pack_id, app_id, _ = _setup(conn)
    search = FakeSearch(lambda q: [hit(f"https://example.co.nz/{q}")])
    explores = [ExploreStep(action="search", argument=f"q{i}") for i in range(5)]
    deps, llms = _deps(conn, plan=PlanResult(needs=["news"]), extracts=empties(4),
                       explores=explores, search=search)

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    assert len(llms["explore"].calls) == 3
    assert search.queries == ["q0", "q1", "q2"]
    assert "Stopped exploring after 3 extra steps." in prep_repo.get(conn, pack_id)["notes"]


def test_a_run_stops_at_the_page_limit_and_says_so(conn):
    pack_id, app_id, _ = _setup(conn)
    search = FakeSearch(lambda q: [hit(f"https://example.co.nz/{i}") for i in range(8)])
    deps, _ = _deps(conn, plan=PlanResult(queries=["q1"]), extracts=empties(7), search=search)

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    row = prep_repo.get(conn, pack_id)
    assert len([s for s in row["sources"] if s["kind"] == "search"]) == 6
    assert "Stopped reading after 6 pages." in row["notes"]


def test_reused_employer_facts_skip_the_home_page_and_places(conn):
    pack_id, app_id, company_id = _setup(conn, website="https://example.co.nz")
    old_job = conn.execute(
        "insert into jobs (company_id, source, external_id, title, dedupe_hash) "
        "values (%s, 'example', 'p0', 'Analyst', 'h0') returning id",
        (company_id,),
    ).fetchone()["id"]
    old_app = conn.execute(
        "insert into applications (profile_id, job_id, status) values (%s, %s, 'found') "
        "returning id",
        (PROFILE_ID, old_job),
    ).fetchone()["id"]
    old = prep_repo.insert_queued(conn, PROFILE_ID, old_app, company_id, None)
    prep_repo.finish(
        conn, old, content={}, notes=[], cost_usd=0, places_calls=0,
        sources=[{"id": "s2", "url": "https://example.co.nz", "title": "Home", "kind": "website"}],
        facts=[{"kind": "about", "text": "Builds port software", "source_id": "s2",
                "quote": "builds port software"}],
    )
    conn.commit()
    reader = FakeReader()
    places = FakePlaces(None)
    write = PrepPack(employer=[SourcedLine(text="Builds port software", source_ids=["r1"])])
    deps, llms = _deps(conn, plan=PlanResult(), extracts=empties(1), write=write, reader=reader,
                       places=places)

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    assert reader.urls == []
    assert places.calls == []
    assert "Already known: about" in llms["plan"].calls[0]["user"]
    content = prep_repo.get(conn, pack_id)["content"]
    assert content["employer"] == [
        {"text": "Builds port software", "source_ids": ["r1"], "quote": "builds port software"}]


def test_empty_job_description_still_produces_a_pack(conn):
    pack_id, app_id, _ = _setup(conn, description="")
    write = PrepPack(evidence=[EvidenceItem(requirement="Python", evidence=None, status="gap")])
    deps, _ = _deps(conn, plan=PlanResult(), extracts=empties(1), write=write)

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    content = prep_repo.get(conn, pack_id)["content"]
    assert {item["status"] for item in content["evidence"]} <= {"gap", "check"}


def test_without_a_resume_the_run_fails_with_the_upload_message(conn):
    pack_id, app_id, _ = _setup(conn, resume=False)
    deps, _ = _deps(conn, plan=PlanResult(), extracts=empties(1))

    result = _run(conn, pack_id, app_id, deps)

    assert result.status == "error"
    assert "Upload your resume first" in result.error
    assert prep_repo.get(conn, pack_id)["status"] == "queued"


def test_the_writer_cannot_add_employer_claims(conn):
    pack_id, app_id, _ = _setup(conn, website="https://example.co.nz")
    reader = FakeReader({"https://example.co.nz": "Example builds port software."})
    extracts = [ExtractResult(facts=[]), ExtractResult(facts=[
        Fact(kind="about", text="Builds port software", source_id="s2",
             quote="builds port software")])]
    write = PrepPack(employer=[SourcedLine(text="Example has 2,000 staff", source_ids=["s2"])],
                     pay=SourcedLine(text="NZ$150k", source_ids=["s1"]))
    deps, _ = _deps(conn, plan=PlanResult(), extracts=extracts, write=write, reader=reader)

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    content = prep_repo.get(conn, pack_id)["content"]
    assert [line["text"] for line in content["employer"]] == ["Builds port software"]
    assert content["pay"] is None
    assert "2,000 staff" not in str(content)


def test_a_run_that_reaches_the_spending_limit_still_saves_a_pack(conn):
    pack_id, app_id, _ = _setup(conn)
    search = FakeSearch(lambda q: [hit(f"https://example.co.nz/{i}") for i in range(3)])
    deps, llms = _deps(conn, plan=PlanResult(queries=["q"]), extracts=empties(4), search=search,
                       budget=Budget(max_model_calls=3))

    result = _run(conn, pack_id, app_id, deps)

    assert result.status == "ok", result.error
    row = prep_repo.get(conn, pack_id)
    assert row["status"] == "done"
    assert "Stopped at the spending limit for one run." in row["notes"]
    assert len(llms["write"].calls) == 1


def test_a_failed_planning_step_still_produces_a_pack(conn):
    pack_id, app_id, _ = _setup(conn)
    deps, _ = _deps(conn, plan=ProviderError("claude", "HTTP 500"), extracts=empties(1))

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    assert "Planning failed (claude: HTTP 500), so no web searches were made." in (
        prep_repo.get(conn, pack_id)["notes"])


def test_explore_reads_only_listed_pages_or_the_employer_site(conn):
    pack_id, app_id, _ = _setup(conn, website="https://example.co.nz")
    reader = FakeReader({"https://example.co.nz": "Home.",
                         "https://example.co.nz/team": "Team page."})
    explores = [ExploreStep(action="read", argument="https://elsewhere.example/a"),
                ExploreStep(action="read", argument="https://example.co.nz/team"),
                ExploreStep(action="done")]
    deps, _ = _deps(conn, plan=PlanResult(needs=["news"]), extracts=empties(3),
                    explores=explores, reader=reader)

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    assert "https://elsewhere.example/a" not in reader.urls
    assert "https://example.co.nz/team" in reader.urls


def test_the_places_cap_counts_every_lookup_in_a_run(conn):
    pack_id, app_id, _ = _setup(conn, website="https://example.co.nz")
    places = FakePlaces(None)
    explores = [ExploreStep(action="place", argument="Example Freight Tech, Dunedin"),
                ExploreStep(action="done")]
    deps, _ = _deps(conn, plan=PlanResult(needs=["news"]), extracts=empties(2),
                    explores=explores, places=places, places_remaining=1,
                    reader=FakeReader({"https://example.co.nz": "Home."}))

    assert _run(conn, pack_id, app_id, deps).status == "ok"

    assert len(places.calls) == 1
