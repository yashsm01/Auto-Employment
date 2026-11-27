import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_settings
from app.main import create_app
from app.repositories import events_repo, profiles_repo
from tests.documents import SAMPLE_RESUME_LINES, make_docx, make_pdf

pytestmark = pytest.mark.postgres


@pytest.fixture
def client(database_url, tmp_path):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=database_url, upload_dir=tmp_path, max_upload_mb=1, _env_file=None
    )
    with TestClient(app) as test_client:
        yield test_client


def _upload(client, name="resume.pdf", data=None):
    content = make_pdf(*SAMPLE_RESUME_LINES) if data is None else data
    return client.post("/profile/resume", files={"file": (name, content)})


def test_profile_starts_as_the_labelled_example(client):
    profile = client.get("/profile").json()

    assert profile["is_example"] is True
    assert "Python Developer" in profile["titles"]
    assert profile["connections"]["claude"] is False


def test_upload_replaces_the_example_with_the_real_resume(client):
    response = _upload(client)

    assert response.status_code == 200
    profile = client.get("/profile").json()
    assert profile["is_example"] is False
    assert profile["filename"] == "resume.pdf"
    assert profile["titles"] == ["Data Engineer"]
    assert "Airflow" in [skill["name"] for skill in profile["skills"]]
    assert "check" in response.json()["warning"].lower()


def test_upload_accepts_a_word_file(client):
    response = _upload(client, "resume.docx", make_docx(*SAMPLE_RESUME_LINES))

    assert response.status_code == 200
    assert client.get("/profile").json()["titles"] == ["Data Engineer"]


def test_upload_removes_example_jobs_and_example_preferences(client):
    client.post("/runs/lead").raise_for_status()
    assert client.get("/shortlist").json()["items"]

    _upload(client).raise_for_status()

    assert client.get("/shortlist").json()["items"] == []
    profile = client.get("/profile").json()
    assert profile["work_rights"] is None
    assert profile["salary_min"] is None


def test_upload_keeps_real_jobs(client, conn):
    conn.execute(
        "insert into jobs (source, external_id, title, dedupe_hash) "
        "values ('trademe', '9', 'Real Job', 'real-hash')"
    )
    conn.commit()

    _upload(client).raise_for_status()

    assert conn.execute("select count(*) as n from jobs").fetchone()["n"] == 1


def test_upload_saves_the_file_under_a_generated_name(client, tmp_path):
    _upload(client, "../../evil.pdf").raise_for_status()

    saved = list(tmp_path.iterdir())
    assert len(saved) == 1
    assert "evil" not in saved[0].name
    assert saved[0].suffix == ".pdf"


def test_a_bad_file_keeps_the_current_profile(client):
    response = _upload(client, "resume.pdf", b"not a pdf")

    assert response.status_code == 400
    assert client.get("/profile").json()["is_example"] is True


def test_a_file_over_the_limit_is_rejected(client, tmp_path):
    response = _upload(client, "resume.pdf", b"%PDF-" + b"0" * (2 * 1024 * 1024))

    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()
    assert list(tmp_path.iterdir()) == []


def _editable(profile: dict, **changes) -> dict:
    keys = (
        "titles", "skills", "tools", "search_queries", "regions", "work_rights",
        "salary_min", "avoid_keywords", "shortlist_threshold", "boards",
    )
    return {**{key: profile[key] for key in keys}, **changes}


def test_saving_the_profile_updates_what_searches_use(client):
    profile = client.get("/profile").json()
    body = _editable(
        profile,
        titles=["Platform Engineer"],
        search_queries=["Platform Engineer Auckland"],
        regions=["Auckland"],
        work_rights="resident",
        salary_min=90000,
        shortlist_threshold=60,
    )

    assert client.put("/profile", json=body).status_code == 200

    saved = client.get("/profile").json()
    assert saved["titles"] == ["Platform Engineer"]
    assert saved["search_queries"] == ["Platform Engineer Auckland"]
    assert saved["regions"] == ["Auckland"]
    assert saved["work_rights"] == "resident"
    assert saved["salary_min"] == 90000
    assert saved["shortlist_threshold"] == 60


def test_saving_career_boards(client):
    board = {"platform": "greenhouse", "token": "examplecompany", "company": "Example Co"}
    body = _editable(client.get("/profile").json(), boards=[board])

    client.put("/profile", json=body).raise_for_status()

    assert client.get("/profile").json()["boards"] == [board]


@pytest.mark.parametrize(
    "change",
    [
        {"work_rights": "unknown"},
        {"shortlist_threshold": 101},
        {"boards": [{"platform": "greenhouse", "token": "../admin", "company": "X"}]},
        {"boards": [{"platform": "seek", "token": "abc", "company": "X"}]},
    ],
)
def test_saving_rejects_invalid_values(client, change):
    body = _editable(client.get("/profile").json(), **change)

    assert client.put("/profile", json=body).status_code == 422


@pytest.mark.parametrize("path", ["/runs/lead", "/profile/resume"])
def test_another_website_cannot_trigger_writes(client, path):
    response = client.post(path, headers={"Origin": "https://evil.example"})

    assert response.status_code == 403


def test_the_dashboard_origin_can_write(client):
    response = client.post("/runs/lead", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200


def _save_regions(client, regions):
    body = _editable(client.get("/profile").json(), regions=regions)
    return client.put("/profile", json=body)


def _track(conn, *, external_id, title, location, region="", status="found", source="trademe"):
    """Store a job and an application for the example profile. Returns the application id."""
    profile_id = profiles_repo.first_profile_id(conn)
    job = conn.execute(
        "insert into jobs (source, external_id, title, location, region, dedupe_hash) "
        "values (%s, %s, %s, %s, %s, %s) returning id",
        (source, external_id, title, location, region, f"hash-{source}-{external_id}"),
    ).fetchone()
    application = conn.execute(
        "insert into applications (profile_id, job_id, status) values (%s, %s, %s) returning id",
        (profile_id, job["id"], status),
    ).fetchone()
    conn.commit()
    return application["id"]


def _status(conn, application_id):
    row = conn.execute(
        "select status from applications where id = %s", (application_id,)
    ).fetchone()
    return row["status"]


def _notes(conn, application_id):
    return [
        event["payload"]["text"]
        for event in events_repo.for_application(conn, application_id)
        if event["type"] == "note"
    ]


def test_changing_areas_closes_outside_jobs(client, conn):
    _save_regions(client, ["Auckland"]).raise_for_status()
    outside_found = _track(
        conn, external_id="a1", title="Python Developer",
        location="Auckland City, Auckland", region="Auckland",
    )
    outside_shortlisted = _track(
        conn, external_id="a2", title="Python Developer",
        location="Auckland City, Auckland", region="Auckland", status="shortlisted",
    )
    inside = _track(
        conn, external_id="w1", title="Python Developer",
        location="Wellington Central, Wellington", region="Wellington",
    )

    response = _save_regions(client, ["Wellington"])

    assert response.status_code == 200
    assert response.json()["closed_outside_areas"] == 2
    assert _status(conn, outside_found) == "closed"
    assert _status(conn, outside_shortlisted) == "closed"
    assert _status(conn, inside) == "found"
    assert _notes(conn, outside_found) == ["Outside your areas"]
    assert _notes(conn, inside) == []


def test_approved_jobs_are_kept_when_areas_change(client, conn):
    _save_regions(client, ["Auckland"]).raise_for_status()
    statuses = ["approved", "tailoring", "ready", "sent", "followed_up", "replied", "closed"]
    tracked = [
        _track(
            conn, external_id=f"s{index}", title="Python Developer",
            location="Auckland City, Auckland", region="Auckland", status=status,
        )
        for index, status in enumerate(statuses)
    ]

    response = _save_regions(client, ["Wellington"])

    assert response.json()["closed_outside_areas"] == 0
    assert [_status(conn, application_id) for application_id in tracked] == statuses


def test_remote_area_keeps_remote_jobs(client, conn):
    _save_regions(client, ["Auckland"]).raise_for_status()
    remote = _track(
        conn, external_id="r1", title="Data Engineer (Remote)", location="Remote", region="",
    )
    onsite = _track(
        conn, external_id="o1", title="Data Engineer",
        location="Wellington Central, Wellington", region="Wellington",
    )

    response = _save_regions(client, ["Remote NZ"])

    assert response.json()["closed_outside_areas"] == 1
    assert _status(conn, remote) == "found"
    assert _status(conn, onsite) == "closed"


def test_reordering_or_recasing_areas_closes_nothing(client, conn):
    _save_regions(client, ["Auckland", "Wellington"]).raise_for_status()
    dunedin = _track(
        conn, external_id="d1", title="Python Developer", location="Dunedin", region="Otago",
    )

    response = _save_regions(client, ["wellington", "AUCKLAND"])

    assert response.json()["closed_outside_areas"] == 0
    assert _status(conn, dunedin) == "found"


def test_clearing_all_areas_closes_nothing(client, conn):
    _save_regions(client, ["Auckland"]).raise_for_status()
    dunedin = _track(
        conn, external_id="d2", title="Python Developer", location="Dunedin", region="Otago",
    )

    response = _save_regions(client, [])

    assert response.json()["closed_outside_areas"] == 0
    assert _status(conn, dunedin) == "found"
