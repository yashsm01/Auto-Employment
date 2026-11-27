from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks

from app.core.deps import ConnDep, ProfileIdDep, SettingsDep
from app.schemas.application import ApplicationDetail, DecisionRequest, DecisionResponse
from app.services import application_service, prep_service
from app.workers.contacts_job import refresh_contacts
from app.workers.prep_job import process_prep_queue
from app.workers.tailor_job import process_tailoring_queue

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/{application_id}")
def get_application(
    application_id: UUID, conn: ConnDep, profile_id: ProfileIdDep
) -> ApplicationDetail:
    return application_service.detail(conn, profile_id, application_id)


@router.post("/{application_id}/decision")
def decide(
    application_id: UUID,
    body: DecisionRequest,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    background: BackgroundTasks,
) -> DecisionResponse:
    result = application_service.decide(conn, profile_id, application_id, body.action, body.reason)
    conn.commit()
    if body.action == "approve":
        background.add_task(process_tailoring_queue, settings)  # tailor the resume next
        company_id = application_service.company_of(conn, application_id)
        if company_id is not None:
            background.add_task(refresh_contacts, settings, company_id)  # find their contacts
        now = datetime.now(UTC)
        if prep_service.on_approved(conn, profile_id, application_id, settings, now):
            conn.commit()
            background.add_task(process_prep_queue, settings)  # and prepare for it
    return result
