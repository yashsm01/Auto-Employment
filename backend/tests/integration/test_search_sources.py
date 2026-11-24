import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_settings
from app.graphs.lead.deps import LeadDeps
from app.graphs.runner import run_graph
from app.main import create_app
from app.providers.jobs.example import ExampleJobSource
from app.schemas.resume import BoardEntry
from app.services.source_service import build_sources
from tests.documents import SAMPLE_RESUME_LINES, make_pdf
from tests.factories import NOW, make_job

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture
def client(database_url, tmp_path):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=database_url, upload_dir=tmp_path, _env_file=None
    )
    with TestClient(app) as test_client:
        yield test_client


def _http() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500)))


def test_example_jobs_are_used_only_for_the_example_profile():
    settings = Settings(_env_file=None)

    example = build_sources(settings, _http(), [], use_examples=True)
    real = build_sources(settings, _http(), [], use_examples=False)

    assert [type(source) for source in example] == [ExampleJobSource]
    assert real == []


def test_a_board_replaces_the_example_jobs():
    board = BoardEntry(platform="greenhouse", token="exampleco", company="Example Co")

    sources = build_sources(Settings(_env_file=None), _http(), [board], use_examples=True)

    assert [source.name for source in sources] == ["ats:greenhouse:exampleco"]


def test_a_real_resume_with_no_sources_explains_what_to_do(client):
    client.post(
        "/profile/resume", files={"file": ("resume.pdf", make_pdf(*SAMPLE_RESUME_LINES))}
    ).raise_for_status()

    output = client.post("/runs/lead").json()["output"]

    assert output["new_jobs"] == 0
    assert any("No job sources" in error for error in output["errors"])


class OneJobSource:
    name = "one"

    def __init__(self, job) -> None:
        self.job = job

    def search(self, keywords):
        return [self.job]


def _deps(conn, job) -> LeadDeps:
    from app.chains.manager import get_chain

    return LeadDeps(conn=conn, sources=[OneJobSource(job)], score_chain=get_chain("score"), now=NOW)


def test_a_skip_lowers_the_score_of_a_later_job_from_that_company(conn):
    first = make_job(external_id="1", title="Backend Developer", company="Skip Co")
    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, first))
    application = conn.execute("select id, score from applications").fetchone()
    conn.execute("update applications set status = 'closed' where id = %s", (application["id"],))
    conn.execute(
        "insert into feedback (application_id, action) values (%s, 'skip')", (application["id"],)
    )
    conn.commit()

    second = make_job(external_id="2", title="Python Developer", company="Skip Co")
    run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, second))

    row = conn.execute(
        "select a.score, a.score_reason from applications a join jobs j on j.id = a.job_id "
        "where j.external_id = '2'"
    ).fetchone()
    assert row["score"] == 97
    assert "past decisions" in row["score_reason"]


def test_run_output_reports_how_jobs_were_scored(conn):
    result = run_graph("lead", {"profile_id": PROFILE_ID}, _deps(conn, make_job()))

    assert result.output["scored"] == 1
    assert result.output["ai_scored"] == 0
    assert result.output["keyword_scored"] == 1
