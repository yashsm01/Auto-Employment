import uuid

import pytest
from fastapi.testclient import TestClient

from app.chains.manager import PrepChains
from app.chains.prep_chains import ExploreChain, ExtractChain, PlanChain, WriteChain
from app.core.config import Settings
from app.core.deps import get_settings
from app.main import create_app
from app.repositories import prep_repo
from app.schemas.prep import PlanResult, PrepPack
from app.workers import prep_job
from app.workers.prep_job import process_prep_queue
from tests.fakes import ScriptedLLM

pytestmark = pytest.mark.postgres

PROFILE_ID = "00000000-0000-4000-8000-000000000001"
KEY_MESSAGE = "Deep search needs a Claude key in backend/.env."


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, *args, **kwargs) -> None:
        self.calls.append(args)


@pytest.fixture
def settings(database_url, tmp_path) -> Settings:
    return Settings(database_url=database_url, upload_dir=tmp_path, _env_file=None)


@pytest.fixture
def keyed_settings(database_url, tmp_path) -> Settings:
    return Settings(database_url=database_url, upload_dir=tmp_path, anthropic_api_key="test-key",
                    _env_file=None)


@pytest.fixture
def background(monkeypatch) -> dict[str, Recorder]:
    """No real background work: tailoring and deep search are recorded instead."""
    recorders = {"prep": Recorder(), "tailor": Recorder()}
    monkeypatch.setattr("app.api.prep.process_prep_queue", recorders["prep"])
    monkeypatch.setattr("app.api.applications.process_prep_queue", recorders["prep"])
    monkeypatch.setattr("app.api.applications.process_tailoring_queue", recorders["tailor"])
    return recorders


def _client(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture
def client(settings, background):
    with _client(settings) as test_client:
        yield test_client


@pytest.fixture
def keyed_client(keyed_settings, background):
    with _client(keyed_settings) as test_client:
        yield test_client


def _application(conn, key: str = "1") -> str:
    company_id = conn.execute(
        "insert into companies (name) values (%s) returning id", (f"Example {key} Ltd",)
    ).fetchone()["id"]
    job_id = conn.execute(
        "insert into jobs (company_id, source, external_id, title, description, dedupe_hash) "
        "values (%s, 'example', %s, 'Python Developer', 'Python, FastAPI and SQL.', %s) "
        "returning id",
        (company_id, key, f"hash-{key}"),
    ).fetchone()["id"]
    app_id = conn.execute(
        "insert into applications (profile_id, job_id, status, score) "
        "values (%s, %s, 'shortlisted', 90) returning id",
        (PROFILE_ID, job_id),
    ).fetchone()["id"]
    conn.commit()
    return str(app_id)


def _scripted_chains() -> PrepChains:
    return PrepChains(
        plan=PlanChain(ScriptedLLM(PlanResult()), "claude-haiku-5-5"),
        extract=ExtractChain(ScriptedLLM(), "claude-haiku-5-5"),
        explore=ExploreChain(ScriptedLLM(), "claude-haiku-5-5"),
        write=WriteChain(ScriptedLLM(PrepPack()), "claude-sonnet-5-5"),
    )


def _packs(conn, app_id: str) -> list[dict]:
    return conn.execute(
        "select * from prep_packs where application_id = %s order by created_at", (app_id,)
    ).fetchall()


def test_settings_default_off_with_a_limit_of_30(client):
    body = client.get("/deep-search").json()

    assert {k: body[k] for k in ("enabled", "monthly_limit", "used_this_month", "available")} == {
        "enabled": False, "monthly_limit": 30, "used_this_month": 0, "available": False}


def test_settings_are_saved(client):
    saved = client.put("/deep-search", json={"enabled": True, "monthly_limit": 20})

    assert saved.status_code == 200
    assert client.get("/deep-search").json()["enabled"] is True
    assert client.get("/deep-search").json()["monthly_limit"] == 20


def test_approving_a_job_queues_deep_search_only_when_switched_on(keyed_client, conn, background):
    first, second = _application(conn, "1"), _application(conn, "2")

    keyed_client.post(f"/applications/{first}/decision", json={"action": "approve"})
    assert _packs(conn, first) == []
    assert background["prep"].calls == []

    keyed_client.put("/deep-search", json={"enabled": True, "monthly_limit": 30})
    keyed_client.post(f"/applications/{second}/decision", json={"action": "approve"})

    assert [p["status"] for p in _packs(conn, second)] == ["queued"]
    assert len(background["prep"].calls) == 1


def test_run_button_queues_once_even_if_pressed_twice(keyed_client, conn, background):
    app_id = _application(conn)

    first = keyed_client.post(f"/applications/{app_id}/prep", json={"extra": "Team uses Go."})
    second = keyed_client.post(f"/applications/{app_id}/prep", json={"extra": None})

    assert first.status_code == 200
    assert second.json()["status"] == "queued"
    packs = _packs(conn, app_id)
    assert [(p["status"], p["extra"]) for p in packs] == [("queued", "Team uses Go.")]
    assert first.json()["used_this_month"] == 1


def test_monthly_limit_blocks_new_runs_with_a_clear_message(keyed_client, conn):
    keyed_client.put("/deep-search", json={"enabled": False, "monthly_limit": 1})
    keyed_client.post(f"/applications/{_application(conn, '1')}/prep", json={})

    blocked = keyed_client.post(f"/applications/{_application(conn, '2')}/prep", json={})

    assert blocked.status_code == 409
    assert "You have used all 1 deep searches this month" in blocked.json()["detail"]


def test_a_full_monthly_limit_skips_the_automatic_run_without_blocking_approval(
    keyed_client, conn
):
    keyed_client.put("/deep-search", json={"enabled": True, "monthly_limit": 0})
    app_id = _application(conn)

    approved = keyed_client.post(f"/applications/{app_id}/decision", json={"action": "approve"})

    assert approved.status_code == 200
    assert _packs(conn, app_id) == []


def test_extra_details_over_20000_characters_are_rejected(keyed_client, conn):
    app_id = _application(conn)

    response = keyed_client.post(f"/applications/{app_id}/prep", json={"extra": "x" * 20001})

    assert response.status_code == 422
    assert _packs(conn, app_id) == []


def test_without_a_claude_key_the_view_says_unavailable(client, conn):
    app_id = _application(conn)

    view = client.get(f"/applications/{app_id}/prep").json()
    run = client.post(f"/applications/{app_id}/prep", json={})

    assert (view["status"], view["available"]) == ("none", False)
    assert run.status_code == 400
    assert run.json()["detail"] == KEY_MESSAGE


def test_an_unknown_application_is_404(client):
    assert client.get(f"/applications/{uuid.uuid4()}/prep").status_code == 404


def test_a_failed_run_shows_its_error_and_can_be_retried(keyed_client, conn, keyed_settings,
                                                         monkeypatch):
    monkeypatch.setattr(prep_job, "get_prep_chains", lambda settings: _scripted_chains())
    app_id = _application(conn)  # the example profile has no real resume, so the run fails
    keyed_client.post(f"/applications/{app_id}/prep", json={})

    assert process_prep_queue(keyed_settings) == 1

    view = keyed_client.get(f"/applications/{app_id}/prep").json()
    assert view["status"] == "failed"
    assert view["error"] == "Upload your resume first, on My resume profile."
    retry = keyed_client.post(f"/applications/{app_id}/prep", json={})
    assert retry.json()["status"] == "queued"
    assert [p["status"] for p in _packs(conn, app_id)] == ["failed", "queued"]


def test_the_queue_stops_when_another_deep_search_is_running(conn, keyed_settings, monkeypatch):
    monkeypatch.setattr(prep_job, "get_prep_chains", lambda settings: _scripted_chains())
    app_id = _application(conn)
    pack_id = prep_repo.insert_queued(conn, PROFILE_ID, app_id, None, None)
    conn.execute("insert into graph_runs (graph, status) values ('prep', 'running')")
    conn.commit()

    assert process_prep_queue(keyed_settings) == 0
    assert prep_repo.get(conn, pack_id)["status"] == "queued"


def test_an_interrupted_run_is_marked_failed(conn, keyed_settings, monkeypatch):
    monkeypatch.setattr(prep_job, "get_prep_chains", lambda settings: _scripted_chains())
    app_id = _application(conn)
    pack_id = prep_repo.insert_queued(conn, PROFILE_ID, app_id, None, None)
    conn.execute(
        "update prep_packs set status = 'running', started_at = now() - interval '20 minutes' "
        "where id = %s",
        (pack_id,),
    )
    conn.commit()

    process_prep_queue(keyed_settings)

    row = prep_repo.get(conn, pack_id)
    assert (row["status"], row["error"]) == ("failed", "Deep search was interrupted. Try again.")


def test_a_blocked_extra_link_is_refused_before_queueing(keyed_client, conn, background):
    app_id = _application(conn)

    response = keyed_client.post(
        f"/applications/{app_id}/prep", json={"extra": "https://www.linkedin.com/jobs/view/1"}
    )

    assert response.status_code == 400
    assert "Paste the job text into Extra details instead." in response.json()["detail"]
    assert _packs(conn, app_id) == []
    assert background["prep"].calls == []
