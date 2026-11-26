from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.chains.resume_sections_chain import ResumeSectionsChain
from app.core.deps import ConnDep, ProfileIdDep, get_sections_chain
from app.schemas.coverage import Coverage, SkillDecisionRequest, SkillDecisionResponse
from app.services import coverage_service

router = APIRouter(tags=["coverage"])
SectionsChainDep = Annotated[ResumeSectionsChain | None, Depends(get_sections_chain)]


@router.get("/applications/{application_id}/coverage")
def get_coverage(
    application_id: UUID, conn: ConnDep, profile_id: ProfileIdDep, sections_chain: SectionsChainDep
) -> Coverage:
    result = coverage_service.for_application(conn, profile_id, application_id, sections_chain)
    conn.commit()  # The first read may cache master CV sections that were read with AI.
    return result


@router.post("/skills/decision")
def decide_skill(
    body: SkillDecisionRequest,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    sections_chain: SectionsChainDep,
) -> SkillDecisionResponse:
    coverage_service.decide(conn, profile_id, body.skill, body.decision, sections_chain)
    conn.commit()
    return SkillDecisionResponse(ok=True)
