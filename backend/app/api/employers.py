from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.deps import (
    ConnDep,
    ProfileIdDep,
    SettingsDep,
    get_contact_tools,
    get_places,
)
from app.schemas.contacts import EmployerContacts
from app.schemas.employer import (
    NearbyResults,
    NearbySearch,
    SavedEmployer,
    SavedEmployers,
    SaveEmployer,
)
from app.services import contact_service, employer_service
from app.services.contact_service import ContactTools
from app.services.employer_service import PlaceSearch
from app.workers.contacts_job import refresh_contacts

router = APIRouter(prefix="/employers", tags=["employers"])
PlacesDep = Annotated[PlaceSearch, Depends(get_places)]
ContactToolsDep = Annotated[ContactTools, Depends(get_contact_tools)]


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
def save_employer(
    body: SaveEmployer,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    background: BackgroundTasks,
) -> SavedEmployer:
    result = employer_service.save(conn, profile_id, body)
    conn.commit()
    background.add_task(refresh_contacts, settings, result.id)
    return result


@router.get("/{company_id}/contacts")
def get_contacts(company_id: UUID, conn: ConnDep, profile_id: ProfileIdDep) -> EmployerContacts:
    employer_service.require_access(conn, profile_id, company_id)
    return contact_service.view(conn, company_id)


@router.post("/{company_id}/contacts")
def look_up_contacts(
    company_id: UUID, conn: ConnDep, profile_id: ProfileIdDep, tools: ContactToolsDep
) -> EmployerContacts:
    """Read the employer's pages now, even if they were checked recently."""
    employer_service.require_access(conn, profile_id, company_id)
    result = contact_service.lookup(conn, company_id, tools, datetime.now(UTC), force=True)
    conn.commit()
    return result


@router.delete("/{company_id}")
def remove_employer(
    company_id: UUID, conn: ConnDep, profile_id: ProfileIdDep
) -> dict[str, bool]:
    employer_service.remove(conn, profile_id, company_id)
    conn.commit()
    return {"removed": True}
