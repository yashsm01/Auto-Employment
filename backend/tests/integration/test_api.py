import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_settings
from app.main import create_app

pytestmark = pytest.mark.postgres


@pytest.fixture
def client(database_url):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=database_url, _env_file=None
    )
    with TestClient(app) as test_client:
        yield test_client


def _first_shortlisted(client) -> dict:
    client.post("/runs/lead").raise_for_status()
    return client.get("/shortlist").json()["items"][0]


def test_health_does_not_need_a_database():
    assert TestClient(create_app()).get("/health").json() == {"status": "ok"}


def test_run_with_no_keys_uses_labelled_example_jobs(client):
    summary = client.post("/runs/lead").json()

    assert summary["status"] == "ok"
    assert summary["output"]["shortlisted"] > 0
    items = client.get("/shortlist").json()["items"]
    assert items
    assert all(item["is_example"] for item in items)


def test_shortlist_is_sorted_by_score(client):
    client.post("/runs/lead").raise_for_status()

    scores = [item["score"] for item in client.get("/shortlist").json()["items"]]

    assert scores == sorted(scores, reverse=True)


def test_jobs_show_their_region_rather_than_a_suburb(client):
    client.post("/runs/lead").raise_for_status()

    cities = {item["title"]: item["city"] for item in client.get("/shortlist").json()["items"]}

    assert cities["Backend Engineer"] == "Auckland"  # location is "Auckland CBD, Auckland"
    assert cities["Automation Engineer"] == "Remote"


def test_pipeline_counts_match_the_board(client):
    client.post("/runs/lead").raise_for_status()

    pipeline = client.get("/pipeline").json()
    columns = {column["key"]: column for column in pipeline["columns"]}

    assert [column["key"] for column in pipeline["columns"]] == [
        "shortlisted", "resume_ready", "sent", "followed_up", "replied",
    ]
    assert pipeline["stats"]["shortlisted"] == columns["shortlisted"]["count"]
    assert columns["shortlisted"]["count"] == len(columns["shortlisted"]["cards"])
    assert pipeline["last_run_at"] is not None


def test_approve_moves_the_job_to_resume_ready(client):
    item = _first_shortlisted(client)

    response = client.post(f"/applications/{item['id']}/decision", json={"action": "approve"})

    assert response.status_code == 200
    assert response.json()["status"] == "tailoring"
    columns = {c["key"]: c for c in client.get("/pipeline").json()["columns"]}
    assert item["id"] in [card["id"] for card in columns["resume_ready"]["cards"]]
    assert item["id"] not in [card["id"] for card in columns["shortlisted"]["cards"]]


def test_skip_removes_the_job_and_saves_the_reason(client, conn):
    item = _first_shortlisted(client)

    response = client.post(
        f"/applications/{item['id']}/decision",
        json={"action": "skip", "reason": "Too far away"},
    )

    assert response.json()["status"] == "closed"
    assert item["id"] not in [i["id"] for i in client.get("/shortlist").json()["items"]]
    feedback = conn.execute("select action, reason from feedback").fetchone()
    assert feedback == {"action": "skip", "reason": "Too far away"}


def test_a_job_cannot_be_decided_twice(client):
    item = _first_shortlisted(client)
    url = f"/applications/{item['id']}/decision"
    client.post(url, json={"action": "approve"}).raise_for_status()

    assert client.post(url, json={"action": "skip"}).status_code == 409


def test_deciding_an_unknown_application_returns_404(client):
    url = "/applications/00000000-0000-4000-8000-00000000ffff/decision"

    assert client.post(url, json={"action": "approve"}).status_code == 404


def test_decision_rejects_an_unknown_action(client):
    item = _first_shortlisted(client)
    url = f"/applications/{item['id']}/decision"

    assert client.post(url, json={"action": "send-now"}).status_code == 422
