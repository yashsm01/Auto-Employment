import pytest

from app.services.lead_service import build_queries, drop_unwanted, keywords_for
from tests.factories import NOW, make_job, make_prefs, make_resume


def _kept(jobs, regions) -> list[str]:
    return [job.location for job in drop_unwanted(jobs, make_prefs(regions=regions), NOW)]


def _at(location: str, source: str = "trademe", region: str = ""):
    return make_job(external_id=location, source=source, location=location, region=region)


def test_a_local_town_can_be_chosen():
    jobs = [_at("Timaru, Canterbury"), _at("Ashburton, Canterbury")]

    assert _kept(jobs, ["Timaru"]) == ["Timaru, Canterbury"]


def test_a_region_includes_its_towns():
    jobs = [_at("Timaru, Canterbury"), _at("Dunedin, Otago")]

    assert _kept(jobs, ["Canterbury"]) == ["Timaru, Canterbury"]


@pytest.mark.parametrize(
    ("chosen", "location"),
    [("Whangarei", "Whangārei, Northland"), ("Taupō", "Taupo, Waikato"), ("timaru", "TIMARU")],
)
def test_town_names_match_with_or_without_macrons_and_capitals(chosen, location):
    assert _kept([_at(location)], [chosen]) == [location]


def test_all_of_new_zealand_keeps_any_town():
    jobs = [_at("Kaitaia, Northland"), _at("Bluff, Southland")]

    assert _kept(jobs, []) == ["Kaitaia, Northland", "Bluff, Southland"]


@pytest.mark.parametrize(
    "location",
    ["London, United Kingdom", "Remote, United States", "Remote", "Sydney, Australia"],
)
def test_all_of_new_zealand_drops_overseas_jobs_from_global_boards(location):
    assert _kept([_at(location, source="ats")], []) == []


@pytest.mark.parametrize(
    "location",
    ["Auckland, New Zealand", "Remote - NZ", "Invercargill", "Hamilton, Waikato", "Whangārei"],
)
def test_all_of_new_zealand_keeps_nz_jobs_from_global_boards(location):
    assert _kept([_at(location, source="ats")], []) == [location]


@pytest.mark.parametrize(
    ("chosen", "location"),
    [
        ("Wellington", "Wellington, Florida"),
        ("Hamilton", "Hamilton, Ontario"),
        ("Christchurch", "Christchurch, Dorset"),
    ],
)
def test_a_same_named_overseas_place_is_not_matched(chosen, location):
    assert _kept([_at(location, source="ats")], [chosen]) == []


def test_a_board_job_in_a_chosen_small_town_is_kept():
    assert _kept([_at("Tokomaru Bay", source="ats")], ["Tokomaru Bay"]) == ["Tokomaru Bay"]


def test_a_board_job_offered_in_nz_or_overseas_is_kept():
    location = "Auckland / Sydney"

    assert _kept([_at(location, source="ats")], ["Auckland"]) == [location]


def test_all_of_new_zealand_searches_without_a_place_name():
    resume = make_resume(titles=["Python Developer"], skills=[])

    assert build_queries(resume, make_prefs(regions=[])) == ["Python Developer"]


def test_many_towns_do_not_crowd_out_job_titles():
    titles = ["Python Developer", "Backend Developer", "Automation Engineer"]
    towns = ["Timaru", "Oamaru", "Nelson", "Blenheim", "Gisborne", "Napier"]
    prefs = make_prefs(regions=towns)

    queries = build_queries(make_resume(titles=titles, skills=[]), prefs, limit=10)

    assert len(queries) == 10
    assert {keywords_for(query, towns) for query in queries} == set(titles)
