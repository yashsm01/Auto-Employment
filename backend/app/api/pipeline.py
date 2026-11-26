from typing import Annotated

from fastapi import APIRouter, Depends

from app.chains.resume_sections_chain import ResumeSectionsChain
from app.core.deps import ConnDep, ProfileIdDep, get_sections_chain
from app.schemas.application import Pipeline, Shortlist
from app.services import application_service

SectionsChainDep = Annotated[ResumeSectionsChain | None, Depends(get_sections_chain)]

router = APIRouter(tags=["pipeline"])


@router.get("/pipeline")
def get_pipeline(conn: ConnDep, profile_id: ProfileIdDep) -> Pipeline:
    return application_service.pipeline(conn, profile_id)


@router.get("/shortlist")
def get_shortlist(
    conn: ConnDep, profile_id: ProfileIdDep, sections_chain: SectionsChainDep
) -> Shortlist:
    items = application_service.shortlist_items(conn, profile_id, sections_chain)
    conn.commit()  # The first read may cache master CV sections that were read with AI.
    return Shortlist(items=items)
