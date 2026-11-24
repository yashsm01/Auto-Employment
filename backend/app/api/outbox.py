from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks

from app.core.deps import ConnDep, ProfileIdDep, SettingsDep
from app.schemas.outbox import OutboxSettings, OutboxView, OutcomeRequest, SendRequest
from app.services import outbox_service
from app.workers.outbox_job import process_outbox

router = APIRouter(tags=["outbox"])


def _view(conn, profile_id, settings) -> OutboxView:
    return outbox_service.view(conn, profile_id, settings, datetime.now(UTC))


@router.get("/outbox")
def get_outbox(conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep) -> OutboxView:
    return _view(conn, profile_id, settings)


@router.put("/outbox/settings")
def save_outbox_settings(
    body: OutboxSettings, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> OutboxView:
    outbox_service.save_daily_limit(conn, profile_id, body.daily_send_limit)
    conn.commit()
    return _view(conn, profile_id, settings)


@router.post("/applications/{application_id}/send")
def send_application(
    application_id: UUID,
    body: SendRequest,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    background: BackgroundTasks,
) -> OutboxView:
    outbox_service.queue_email(
        conn, profile_id, application_id, body.to, settings, datetime.now(UTC)
    )
    conn.commit()
    background.add_task(process_outbox, settings)
    return _view(conn, profile_id, settings)


@router.post("/applications/{application_id}/applied")
def applied_myself(
    application_id: UUID, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> OutboxView:
    outbox_service.mark_applied_manually(conn, profile_id, application_id, datetime.now(UTC))
    conn.commit()
    return _view(conn, profile_id, settings)


@router.post("/applications/{application_id}/outcome")
def application_outcome(
    application_id: UUID,
    body: OutcomeRequest,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
) -> OutboxView:
    outbox_service.record_outcome(
        conn, profile_id, application_id, body.action, datetime.now(UTC)
    )
    conn.commit()
    return _view(conn, profile_id, settings)


@router.post("/outbox/{outbox_id}/cancel")
def cancel_email(
    outbox_id: UUID, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> OutboxView:
    outbox_service.cancel(conn, profile_id, outbox_id)
    conn.commit()
    return _view(conn, profile_id, settings)


@router.post("/outbox/{outbox_id}/retry")
def retry_email(
    outbox_id: UUID,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    background: BackgroundTasks,
) -> OutboxView:
    outbox_service.retry(conn, profile_id, outbox_id, datetime.now(UTC))
    conn.commit()
    background.add_task(process_outbox, settings)
    return _view(conn, profile_id, settings)
