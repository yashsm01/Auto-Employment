from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from app.core.deps import ConnDep, ProfileIdDep, SettingsDep, get_places
from app.schemas.employer import (
    NearbyResults,
    NearbySearch,
    SavedEmployer,
    SavedEmployers,
    SaveEmployer,
)
from app.services import employer_service
from app.services.employer_service import PlaceSearch

router = APIRouter(prefix="/employers", tags=["employers"])
PlacesDep = Annotated[PlaceSearch, Depends(get_places)]


@router.post("/search")
def search_employers(
    body: NearbySearch,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    places: PlacesDep,
) -> NearbyResults:
    today = datetime.now(ZoneInfo("Pacific/Auckland")).date()
    results = employer_service.search_nearby(
        conn,
        profile_id,
        places,
        body.business,
        body.town,
        today,
        settings.max_nearby_searches_per_day,
    )
    conn.commit()
    return results


@router.get("")
def list_employers(conn: ConnDep, profile_id: ProfileIdDep) -> SavedEmployers:
    result = employer_service.list_saved(conn, profile_id)
    conn.commit()
    return result


@router.post("")
def save_employer(body: SaveEmployer, conn: ConnDep, profile_id: ProfileIdDep) -> SavedEmployer:
    result = employer_service.save(conn, profile_id, body)
    conn.commit()
    return result


@router.delete("/{company_id}")
def remove_employer(
    company_id: UUID, conn: ConnDep, profile_id: ProfileIdDep
) -> dict[str, bool]:
    employer_service.remove(conn, profile_id, company_id)
    conn.commit()
    return {"removed": True}
