from uuid import UUID

from fastapi import APIRouter

from app.core.deps import ConnDep, ProfileIdDep
from app.schemas.application import ApplicationDetail, DecisionRequest, DecisionResponse
from app.services import application_service

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/{application_id}")
def get_application(
    application_id: UUID, conn: ConnDep, profile_id: ProfileIdDep
) -> ApplicationDetail:
    return application_service.detail(conn, profile_id, application_id)


@router.post("/{application_id}/decision")
def decide(
    application_id: UUID, body: DecisionRequest, conn: ConnDep, profile_id: ProfileIdDep
) -> DecisionResponse:
    result = application_service.decide(conn, profile_id, application_id, body.action, body.reason)
    conn.commit()
    return result
