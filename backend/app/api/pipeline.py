from fastapi import APIRouter

from app.core.deps import ConnDep, ProfileIdDep
from app.schemas.application import Pipeline, Shortlist
from app.services import application_service

router = APIRouter(tags=["pipeline"])


@router.get("/pipeline")
def get_pipeline(conn: ConnDep, profile_id: ProfileIdDep) -> Pipeline:
    return application_service.pipeline(conn, profile_id)


@router.get("/shortlist")
def get_shortlist(conn: ConnDep, profile_id: ProfileIdDep) -> Shortlist:
    return Shortlist(items=application_service.shortlist_items(conn, profile_id))
