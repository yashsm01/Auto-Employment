from datetime import UTC, datetime

import httpx
from fastapi import APIRouter

from app.chains.manager import get_chain
from app.core.deps import ConnDep, ProfileIdDep, SettingsDep
from app.graphs.lead.deps import LeadDeps
from app.graphs.runner import run_graph
from app.providers.jobs.factory import build_sources
from app.schemas.application import RunResponse

router = APIRouter(prefix="/runs", tags=["runs"])
SOURCE_TIMEOUT_SECONDS = 20


@router.post("/lead")
def run_lead_search(conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep) -> RunResponse:
    conn.commit()  # end the read transaction that loaded the profile
    with httpx.Client(timeout=SOURCE_TIMEOUT_SECONDS) as client:
        deps = LeadDeps(
            conn=conn,
            sources=build_sources(settings, client),
            score_chain=get_chain("score"),
            now=datetime.now(UTC),
        )
        result = run_graph("lead", {"profile_id": str(profile_id)}, deps)
    return RunResponse(id=result.id, status=result.status, output=result.output, error=result.error)
