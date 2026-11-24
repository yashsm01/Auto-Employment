from fastapi import APIRouter

from app.core.deps import ConnDep, ProfileIdDep, SettingsDep
from app.schemas.application import RunResponse
from app.workers.lead_job import run_lead_search

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/lead")
def start_lead_search(
    conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> RunResponse:
    result = run_lead_search(conn, settings, profile_id)
    return RunResponse(id=result.id, status=result.status, output=result.output, error=result.error)
