import pytest

from app.core.errors import Conflict, ProviderError
from app.graphs.lead.deps import LeadDeps
from app.graphs.runner import run_graph
from app.schemas.job import JobDraft, ScoreResult
from tests.factories import NOW, make_job

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"


class FixedSource:
    name = "fixed"

    def __init__(self, jobs: list[JobDraft]) -> None:
        self.jobs = jobs
        self.keywords: list[str] = []

    def search(self, keywords: str) -> list[JobDraft]:
        self.keywords.append(keywords)
        return self.jobs


class BrokenSource:
    name = "broken"

    def search(self, keywords: str) -> list[JobDraft]:
        raise ProviderError("broken", "HTTP 500")


class ExplodingChain:
    def run(self, resume, job) -> ScoreResult:
        raise RuntimeError("model unavailable")


def _good_job() -> JobDraft:
    return make_job(external_id="good")


def _weak_job() -> JobDraft:
    return make_job(
        external_id="weak",
        title="Support Analyst",
        description="Excel with Salesforce, SAP and Tableau.",
    )


def _unrelated_job() -> JobDraft:
    return make_job(
        external_id="unrelated",
        title="Registered Nurse",
        description="Care for patients on the ward.",
    )


def _deps(conn, *sources) -> LeadDeps:
    from app.chains.manager import get_chain

    return LeadDeps(conn=conn, sources=list(sources), score_chain=get_chain("score"), now=NOW)


def _statuses(conn) -> dict[str, str]:
    rows = conn.execute(
        "select j.external_id, a.status from applications a join jobs j on j.id = a.job_id"
    ).fetchall()
    return {row["external_id"]: row["status"] for row in rows}


def test_run_shortlists_good_jobs_and_closes_the_rest(conn):
    source = FixedSource([_good_job(), _weak_job(), _unrelated_job()])

    result = run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, source))

    assert result.status == "ok"
    assert _statuses(conn) == {"good": "shortlisted", "weak": "closed", "unrelated": "closed"}
    assert result.output["new_jobs"] == 3
    assert result.output["shortlisted"] == 1


def test_run_stores_score_details_for_the_shortlist(conn):
    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, FixedSource([_good_job()])))

    row = conn.execute(
        "select score, matched_skills, missing_skills, score_reason from applications"
    ).fetchone()

    assert row["score"] == 100
    assert row["matched_skills"] == ["Python", "FastAPI", "SQL"]
    assert row["missing_skills"] == []
    assert "Python" in row["score_reason"]


def test_run_searches_keywords_without_the_region(conn):
    source = FixedSource([])

    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, source))

    assert "Python Developer" in source.keywords
    assert not any("Auckland" in keywords for keywords in source.keywords)
    assert len(source.keywords) == len(set(source.keywords))


def test_second_run_does_not_duplicate_jobs(conn):
    source = FixedSource([_good_job()])
    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, source))

    result = run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, source))

    assert result.output["new_jobs"] == 0
    assert conn.execute("select count(*) as n from applications").fetchone()["n"] == 1


def test_one_failing_source_does_not_stop_the_others(conn):
    result = run_graph(
        "lead",
        {"profile_id": PROFILE_ID},
        _deps(conn, BrokenSource(), FixedSource([_good_job()])),
    )

    assert result.status == "ok"
    assert _statuses(conn) == {"good": "shortlisted"}
    assert any("broken" in error for error in result.output["errors"])


def test_failed_run_records_the_node_and_keeps_no_partial_data(conn):
    deps = _deps(conn, FixedSource([_good_job()]))
    deps.score_chain = ExplodingChain()

    result = run_graph("lead", {"profile_id": PROFILE_ID}, deps)

    run = conn.execute("select status, failed_node, error from graph_runs").fetchone()
    assert result.status == "error"
    assert run["status"] == "error"
    assert run["failed_node"] == "score"
    assert "model unavailable" in run["error"]
    assert conn.execute("select count(*) as n from jobs").fetchone()["n"] == 0


def test_a_second_run_is_refused_while_one_is_running(conn):
    conn.execute("insert into graph_runs (graph, status) values ('lead', 'running')")

    with pytest.raises(Conflict):
        run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, FixedSource([])))


def test_a_stale_running_row_does_not_block_new_runs(conn):
    conn.execute(
        "insert into graph_runs (graph, status, started_at) "
        "values ('lead', 'running', now() - interval '2 hours')"
    )

    result = run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, FixedSource([])))

    assert result.status == "ok"
