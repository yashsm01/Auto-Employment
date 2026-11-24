"""Finds employers on Google Maps and keeps the list whose websites each search checks."""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, Protocol
from urllib.parse import quote
from uuid import UUID

import psycopg

from app.core.errors import Conflict, ProviderError
from app.providers.company.places import PlaceMatch
from app.providers.company.website_reader import is_allowed_url
from app.providers.jobs.employer_sites import SiteEmployer
from app.repositories import companies_repo, employers_repo
from app.schemas.employer import (
    NearbyEmployer,
    NearbyResults,
    SavedEmployer,
    SavedEmployers,
    SaveEmployer,
)
from app.schemas.resume import ResumeProfile, SearchPreferences
from app.services.application_service import safe_url

MAPS_LABEL = "Google Maps"
MAX_DISCOVERY_TERMS = 3


class PlaceSearch(Protocol):
    def search(self, query: str, limit: int = 20) -> list[PlaceMatch]: ...


def _map_url(name: str, address: str | None) -> str:
    place = address or f"{name} New Zealand"
    return f"https://www.google.com/maps/search/?api=1&query={quote(place)}"


def _use_search(
    conn: psycopg.Connection, profile_id: UUID, today: date, daily_limit: int
) -> int | None:
    """Count one Maps search. Returns searches left, or None if the daily limit is reached."""
    data = employers_repo.load_data(conn, profile_id, lock=True)
    usage = data.get("places_usage") or {}
    used = usage.get("count", 0) if usage.get("date") == today.isoformat() else 0
    if used >= daily_limit:
        return None
    employers_repo.update_data(
        conn, profile_id, {"places_usage": {"date": today.isoformat(), "count": used + 1}}
    )
    return daily_limit - used - 1


def _saved_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    return list(data.get("saved_employers") or [])


def search_nearby(
    conn: psycopg.Connection,
    profile_id: UUID,
    places: PlaceSearch,
    business: str,
    town: str,
    today: date,
    daily_limit: int,
) -> NearbyResults:
    # A failed Maps call rolls back this transaction, so it does not use up the limit.
    with conn.transaction():
        left = _use_search(conn, profile_id, today, daily_limit)
        if left is None:
            raise Conflict("The daily Google Maps search limit is reached. Try again tomorrow.")
        found = places.search(f"{business.strip()} in {town.strip()}")
        data = employers_repo.load_data(conn, profile_id)

    saved_ids = [entry["company_id"] for entry in _saved_entries(data)]
    companies = employers_repo.companies_by_id(conn, saved_ids)
    saved_places = {row["google_place_id"] for row in companies.values()}
    return NearbyResults(
        results=[
            NearbyEmployer(
                place_id=place.place_id,
                name=place.name,
                address=place.address,
                phone=place.phone,
                website=safe_url(place.website),
                lat=place.lat,
                lng=place.lng,
                map_url=_map_url(place.name, place.address),
                saved=place.place_id in saved_places,
            )
            for place in found
        ],
        searches_left=left,
    )


def _store(conn: psycopg.Connection, profile_id: UUID, body: SaveEmployer) -> UUID:
    clean = body.model_copy(update={"website": safe_url(body.website)})
    company_id = employers_repo.upsert_company(conn, clean)
    for field, value in (
        ("address", clean.address),
        ("phone", clean.phone),
        ("website", clean.website),
    ):
        if value:
            companies_repo.add_fact(conn, company_id, field, value, "places", "high")

    data = employers_repo.load_data(conn, profile_id, lock=True)
    entries = _saved_entries(data)
    if str(company_id) not in {entry["company_id"] for entry in entries}:
        entries.append({"company_id": str(company_id), "last_checked": None})
    hidden = [place for place in data.get("hidden_places") or [] if place != clean.place_id]
    employers_repo.update_data(
        conn, profile_id, {"saved_employers": entries, "hidden_places": hidden}
    )
    return company_id


def _to_saved(row: dict[str, Any], last_checked: str | None) -> SavedEmployer:
    return SavedEmployer(
        id=row["id"],
        name=row["name"],
        address=row["address"],
        phone=row["phone"],
        website=safe_url(row["website"]),
        map_url=_map_url(row["name"], row["address"]),
        last_checked=datetime.fromisoformat(last_checked) if last_checked else None,
    )


def list_saved(conn: psycopg.Connection, profile_id: UUID) -> SavedEmployers:
    entries = _saved_entries(employers_repo.load_data(conn, profile_id))
    rows = employers_repo.companies_by_id(conn, [entry["company_id"] for entry in entries])
    return SavedEmployers(
        items=[
            _to_saved(rows[entry["company_id"]], entry.get("last_checked"))
            for entry in entries
            if entry["company_id"] in rows
        ]
    )


def save(conn: psycopg.Connection, profile_id: UUID, body: SaveEmployer) -> SavedEmployer:
    with conn.transaction():
        company_id = _store(conn, profile_id, body)
        entries = _saved_entries(employers_repo.load_data(conn, profile_id))
        row = employers_repo.companies_by_id(conn, [str(company_id)])[str(company_id)]
    entry = next(e for e in entries if e["company_id"] == str(company_id))
    return _to_saved(row, entry.get("last_checked"))


def remove(conn: psycopg.Connection, profile_id: UUID, company_id: UUID) -> None:
    """Stop checking an employer, and stop later searches adding it back."""
    with conn.transaction():
        data = employers_repo.load_data(conn, profile_id, lock=True)
        entries = [e for e in _saved_entries(data) if e["company_id"] != str(company_id)]
        hidden = list(data.get("hidden_places") or [])
        row = employers_repo.companies_by_id(conn, [str(company_id)]).get(str(company_id))
        if row and row["google_place_id"] and row["google_place_id"] not in hidden:
            hidden.append(row["google_place_id"])
        employers_repo.update_data(
            conn, profile_id, {"saved_employers": entries, "hidden_places": hidden}
        )


def employers_to_check(
    conn: psycopg.Connection, profile_id: UUID, limit: int
) -> list[SiteEmployer]:
    """Employers with a readable website, longest unchecked first."""
    entries = _saved_entries(employers_repo.load_data(conn, profile_id))
    rows = employers_repo.companies_by_id(conn, [entry["company_id"] for entry in entries])
    ordered = sorted(entries, key=lambda entry: entry.get("last_checked") or "")
    chosen: list[SiteEmployer] = []
    for entry in ordered:
        row = rows.get(entry["company_id"])
        if row and row["website"] and is_allowed_url(row["website"]):
            chosen.append(
                SiteEmployer(
                    company_id=row["id"],
                    name=row["name"],
                    website=row["website"],
                    address=row["address"],
                )
            )
        if len(chosen) >= limit:
            break
    return chosen


def mark_checked(
    conn: psycopg.Connection, profile_id: UUID, company_ids: Sequence[UUID], when: datetime
) -> None:
    checked = {str(company_id) for company_id in company_ids}
    with conn.transaction():
        data = employers_repo.load_data(conn, profile_id, lock=True)
        entries = [
            {**entry, "last_checked": when.isoformat()}
            if entry["company_id"] in checked
            else entry
            for entry in _saved_entries(data)
        ]
        employers_repo.update_data(conn, profile_id, {"saved_employers": entries})


def discovery_queries(
    resume: ResumeProfile, prefs: SearchPreferences, today: date, limit: int
) -> list[str]:
    """Rotate through titles and towns by day, so every town gets searched over time."""
    terms = resume.titles[:MAX_DISCOVERY_TERMS] or [
        skill.name for skill in resume.skills[:MAX_DISCOVERY_TERMS]
    ]
    towns = [town for town in prefs.regions if not town.casefold().startswith("remote")]
    towns = towns or ["New Zealand"]
    combos = [f"{term} company in {town}" for town in towns for term in terms]
    if not combos:
        return []
    start = today.toordinal() % len(combos)
    rotated = combos[start:] + combos[:start]
    return rotated[:limit]


def discover(
    conn: psycopg.Connection,
    profile_id: UUID,
    places: PlaceSearch,
    resume: ResumeProfile,
    prefs: SearchPreferences,
    today: date,
    per_run: int,
    daily_limit: int,
) -> dict[str, Any]:
    """Find employers for this resume and towns, and add them to the checked list."""
    found = 0
    try:
        for query in discovery_queries(resume, prefs, today, per_run):
            with conn.transaction():
                if _use_search(conn, profile_id, today, daily_limit) is None:
                    break
                results = places.search(query)
                hidden = set(employers_repo.load_data(conn, profile_id).get("hidden_places") or [])
                for place in results:
                    if place.place_id in hidden or not place.name:
                        continue
                    _store(
                        conn,
                        profile_id,
                        SaveEmployer(
                            place_id=place.place_id,
                            name=place.name[:200],
                            address=(place.address or "")[:300] or None,
                            phone=(place.phone or "")[:40] or None,
                            website=(place.website or "")[:500] or None,
                            lat=place.lat,
                            lng=place.lng,
                        ),
                    )
                    found += 1
    except ProviderError as error:
        return {"source": MAPS_LABEL, "jobs": 0, "status": "error", "detail": str(error)}
    return {
        "source": MAPS_LABEL,
        "jobs": 0,
        "status": "ok",
        "detail": f"Found {found} employers to check",
    }
