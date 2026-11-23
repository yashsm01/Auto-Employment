from uuid import UUID

from fastapi import APIRouter

from app.core.deps import ConnDep, ProfileIdDep
from app.schemas.application import DecisionRequest, DecisionResponse
from app.services import application_service

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("/{application_id}/decision")
def decide(
    application_id: UUID, body: DecisionRequest, conn: ConnDep, profile_id: ProfileIdDep
) -> DecisionResponse:
    result = application_service.decide(conn, profile_id, application_id, body.action, body.reason)
    conn.commit()
    return result
